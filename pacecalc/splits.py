"""pacecalc のスプリット表（区間ごとの通過タイム表）生成。

一定ペース（イーブンペース）で走ったときの、区間ごとのラップと累計タイムを計算する。
"""

import math
from typing import Optional

# 浮動小数点誤差の吸収幅（km）。0.1 m 未満の端数は端数区間として扱わない。
_EPS_KM = 1e-9


def split_table(distance_km: float, pace_sec: Optional[float] = None,
                target_time_sec: Optional[float] = None,
                interval_km: float = 1.0) -> list[tuple[float, float, float]]:
    """区間ごとの通過タイム表を返す。

    pace_sec（秒/km）か target_time_sec（目標タイム、秒）のどちらか一方を必ず指定する。
    target_time_sec の場合はイーブンペース（target_time_sec / distance_km）で計算する。

    戻り値は (point_km, lap_sec, elapsed_sec) のタプルのリスト。point_km は interval_km 刻みで、
    最後の要素は distance_km ちょうど（割り切れない端数は短い区間になる）。
    interval_km が distance_km より大きい場合は区間 1 つだけになる。

    次の場合は ValueError:
    - pace_sec と target_time_sec の両方を指定、またはどちらも未指定
    - distance_km、interval_km、pace_sec、target_time_sec のいずれかが 0 以下
    """
    if (pace_sec is None) == (target_time_sec is None):
        raise ValueError("pace_sec と target_time_sec のどちらか一方だけを指定してください")
    if distance_km <= 0:
        raise ValueError("distance_km は 0 より大きい値を指定してください")
    if interval_km <= 0:
        raise ValueError("interval_km は 0 より大きい値を指定してください")
    if pace_sec is not None:
        if pace_sec <= 0:
            raise ValueError("pace_sec は 0 より大きい値を指定してください")
        pace = pace_sec
    else:
        if target_time_sec <= 0:
            raise ValueError("target_time_sec は 0 より大きい値を指定してください")
        pace = target_time_sec / distance_km

    # 誤差の累積を避けるため、通過点は i * interval_km で求める。
    full_count = int(math.floor(distance_km / interval_km + _EPS_KM))
    points = [i * interval_km for i in range(1, full_count + 1)]
    points = [p for p in points if p < distance_km - _EPS_KM]
    points.append(distance_km)

    rows = []
    prev = 0.0
    for point in points:
        rows.append((point, (point - prev) * pace, point * pace))
        prev = point
    return rows
