"""pacecalc の GPX コース対応。

GPX の点列を読み込み、累積距離で区間に切って勾配を求め、T005 の物理モデル
（pacecalc.climb）を区間ごとに適用して一定パワー走行の計画を立てる。
前提（標高なしの扱い、下りの速度上限など）は docs/model.md を参照。
"""

import bisect
import math
import xml.etree.ElementTree as ET
from typing import Optional, Sequence

from .climb import _resistance_power

EARTH_RADIUS_M = 6371008.8  # 地球の平均半径（m、IUGG）
MAX_SPEED_KMH = 60.0  # 急な下りで速度が発散しないための上限（km/h）

_EPS_KM = 1e-9  # これ未満の距離差は同じ位置とみなす
# 最終区間の端数がこれ未満なら独立した区間にせず直前の区間に吸収する（km）。
# 座標の丸め（GPX の小数 6 桁 ≒ 0.1 m）や浮動小数の誤差で生じる微小な残りを想定。
# 実際の上限は min(_ABSORB_KM, 区間幅 × _ABSORB_RATIO)（区間幅が極端に小さい場合への配慮）。
_ABSORB_KM = 1e-3  # 1 m
_ABSORB_RATIO = 0.01
_BISECTION_ITERATIONS = 200

# 型ヒント用の別名: GPX の点 (lat, lon, ele)、区間、計画の行
Point = tuple[float, float, Optional[float]]
Segment = tuple[float, float, float, float, float, float]
PlanRow = tuple[float, float, float, float, float]


def _local_name(tag):
    """"{namespace}name" 形式のタグから名前部分だけを返す。"""
    return tag.rsplit("}", 1)[-1]


def load_gpx_points(text: str) -> list[Point]:
    """GPX 文字列をパースし、(lat, lon, ele) のリストを返す。

    トラック点（trkpt）を文書順に読む。trkpt がなければルート点（rtept）を読む。
    複数の trk / trkseg は文書順に連結する。名前空間あり／なしの両方に対応。
    ele がない（または空の）点は標高 None とする。
    XML として不正、lat / lon がない・数値でない場合は ValueError。
    """
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise ValueError("GPX を解析できません: %s" % exc)
    elements = [el for el in root.iter() if _local_name(el.tag) == "trkpt"]
    if not elements:
        elements = [el for el in root.iter() if _local_name(el.tag) == "rtept"]
    points = []
    for el in elements:
        try:
            lat = float(el.attrib["lat"])
            lon = float(el.attrib["lon"])
        except (KeyError, ValueError):
            raise ValueError("lat / lon が不正な点があります")
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            raise ValueError("lat / lon が範囲外の点があります: (%r, %r)" % (lat, lon))
        ele = None
        for child in el:
            if _local_name(child.tag) == "ele" and child.text and child.text.strip():
                try:
                    ele = float(child.text)
                except ValueError:
                    raise ValueError("ele が数値ではありません: %r" % child.text)
                break
        points.append((lat, lon, ele))
    return points


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """2 点間の大圏距離（m）を haversine 公式で返す（球体近似、半径 6371008.8 m）。"""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = phi2 - phi1
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))


def _cumulative_km(points):
    """各点までの累積距離（km）のリストを返す（水平距離のみ）。"""
    cum = [0.0]
    for (lat1, lon1, _), (lat2, lon2, _) in zip(points, points[1:]):
        cum.append(cum[-1] + haversine_m(lat1, lon1, lat2, lon2) / 1000.0)
    return cum


def _elevation_at(cum, points, x):
    """累積距離 x（km）の位置の標高を線形補間で返す。前後どちらかが None なら None。"""
    i = bisect.bisect_right(cum, x) - 1
    i = max(0, min(i, len(cum) - 2))
    e1, e2 = points[i][2], points[i + 1][2]
    if e1 is None or e2 is None:
        return None
    span = cum[i + 1] - cum[i]
    if span <= 0:
        return e2
    t = min(1.0, max(0.0, (x - cum[i]) / span))
    return e1 + (e2 - e1) * t


def course_segments(points: Sequence[Point], segment_km: float = 1.0) -> list[Segment]:
    """累積距離で区間に切り、区間ごとの (start_km, end_km, distance_km, gain_m, loss_m, gradient_pct) を返す。

    区間の境目の標高は前後の点から線形補間する。最後の区間は総距離ちょうどで終わり、
    端数は短い区間になる。ただし端数が 1 m（区間幅の 1% の方が小さければそちら）未満のときは
    長さ 0 に近い区間を作らず、直前の区間に吸収する（総距離が区間幅の倍数ちょうどの場合など）。勾配は (gain - loss) / 区間距離 × 100（%）。
    標高 None の点を含む部分（前後どちらかが None の 2 点間）は gain / loss を 0 として扱う。
    点が 2 点未満、総距離が 0、segment_km が 0 以下なら ValueError。
    """
    if segment_km <= 0:
        raise ValueError("segment_km は 0 より大きい値を指定してください")
    if len(points) < 2:
        raise ValueError("コースには 2 点以上が必要です")
    cum = _cumulative_km(points)
    total = cum[-1]
    if total <= _EPS_KM:
        raise ValueError("コースの総距離が 0 です")

    absorb = min(_ABSORB_KM, segment_km * _ABSORB_RATIO)
    bounds = [0.0]
    k = 1
    while k * segment_km < total - absorb:
        bounds.append(k * segment_km)
        k += 1
    bounds.append(total)

    segments = []
    for start, end in zip(bounds, bounds[1:]):
        lo = bisect.bisect_right(cum, start)
        hi = bisect.bisect_left(cum, end)
        profile = [_elevation_at(cum, points, start)]
        profile += [points[i][2] for i in range(lo, hi)]
        profile.append(points[-1][2] if end == total else _elevation_at(cum, points, end))
        gain = loss = 0.0
        for e1, e2 in zip(profile, profile[1:]):
            if e1 is None or e2 is None:
                continue
            if e2 > e1:
                gain += e2 - e1
            else:
                loss += e1 - e2
        distance = end - start
        gradient = (gain - loss) / (distance * 1000.0) * 100.0
        segments.append((start, end, distance, gain, loss, gradient))
    return segments


def _steady_speed_ms(gradient_pct, total_weight_kg, power_w, cda, crr, air_density,
                     drivetrain_efficiency, max_speed_ms):
    """勾配 gradient_pct（%、負は下り）を一定パワーで走るときの速度（m/s）を返す。

    climb_time_sec と同じ釣り合いの式を、負の勾配も許して二分法で解く。
    下りでは抵抗パワーが v の小さいところで負になるが、正の根はただ 1 つなので
    二分法で求まる。解が max_speed_ms を超える場合は max_speed_ms を返す。
    """
    theta = math.atan(gradient_pct / 100.0)
    sin_t, cos_t = math.sin(theta), math.cos(theta)
    wheel_power = power_w * drivetrain_efficiency

    def excess(v):
        return _resistance_power(v, total_weight_kg, sin_t, cos_t, cda, crr,
                                 air_density) - wheel_power

    if excess(max_speed_ms) <= 0:
        return max_speed_ms
    lo, hi = 0.0, max_speed_ms
    for _ in range(_BISECTION_ITERATIONS):
        mid = (lo + hi) / 2.0
        if excess(mid) < 0:
            lo = mid
        else:
            hi = mid
        if hi - lo <= 1e-12 * hi:
            break
    return (lo + hi) / 2.0


def plan_course(points: Sequence[Point], power_w: float, total_weight_kg: float,
                segment_km: float = 1.0, cda: float = 0.32, crr: float = 0.004,
                air_density: float = 1.0,
                drivetrain_efficiency: float = 0.97) -> tuple[list[PlanRow], float]:
    """一定パワー power_w（W）でコースを走る計画を返す。

    course_segments の区間ごとの勾配に T005 の物理モデルを適用し、
    (rows, total_time_sec) を返す。rows は区間ごとの
    (start_km, end_km, gradient_pct, speed_kmh, time_sec) のリスト、
    total_time_sec は全区間の所要時間の合計（秒）。
    急な下りで速度が発散しないよう、速度は MAX_SPEED_KMH（60 km/h）で頭打ちにする。
    物理パラメータ（cda / crr / air_density / drivetrain_efficiency）の既定値は
    climb_time_sec と同じ。パワー・重量が 0 以下などの不正値は ValueError。
    """
    if power_w <= 0:
        raise ValueError("power_w は 0 より大きい値を指定してください")
    if total_weight_kg <= 0:
        raise ValueError("total_weight_kg は 0 より大きい値を指定してください")
    if cda < 0:
        raise ValueError("cda は 0 以上の値を指定してください")
    if crr < 0:
        raise ValueError("crr は 0 以上の値を指定してください")
    if air_density < 0:
        raise ValueError("air_density は 0 以上の値を指定してください")
    if not 0 < drivetrain_efficiency <= 1:
        raise ValueError("drivetrain_efficiency は 0 より大きく 1 以下で指定してください")
    max_speed_ms = MAX_SPEED_KMH / 3.6
    rows = []
    total = 0.0
    for start, end, distance, _gain, _loss, gradient in course_segments(points, segment_km):
        v = _steady_speed_ms(gradient, total_weight_kg, power_w, cda, crr, air_density,
                             drivetrain_efficiency, max_speed_ms)
        time_sec = distance * 1000.0 / v
        total += time_sec
        rows.append((start, end, gradient, v * 3.6, time_sec))
    return rows, total
