"""pacecalc のヒルクライム物理モデル。

平均勾配の定常モデルで、一定パワーで登ったときの所要時間と、
目標タイムに必要な平均パワーを計算する。式と前提は docs/model.md を参照。

    power × drivetrain_efficiency = (m·g·sinθ + Crr·m·g·cosθ)·v + 0.5·ρ·CdA·v³

θ は平均勾配 gain/distance から θ = atan(gain / distance) で求める。
"""

import math

GRAVITY = 9.80665  # 標準重力加速度（m/s²）

_BISECTION_ITERATIONS = 200


def _check_params(distance_km, elevation_gain_m, total_weight_kg, cda, crr, air_density,
                  drivetrain_efficiency):
    """共通パラメータを検証し、(距離 m, sinθ, cosθ) を返す。"""
    if distance_km <= 0:
        raise ValueError("distance_km は 0 より大きい値を指定してください")
    if elevation_gain_m < 0:
        raise ValueError("elevation_gain_m は 0 以上の値を指定してください")
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
    distance_m = distance_km * 1000.0
    theta = math.atan(elevation_gain_m / distance_m)
    return distance_m, math.sin(theta), math.cos(theta)


def _resistance_power(v, total_weight_kg, sin_t, cos_t, cda, crr, air_density):
    """速度 v（m/s）を維持するのに車輪で必要なパワー（W）。"""
    m_g = total_weight_kg * GRAVITY
    return (m_g * sin_t + crr * m_g * cos_t) * v + 0.5 * air_density * cda * v ** 3


def climb_time_sec(distance_km: float, elevation_gain_m: float, total_weight_kg: float,
                   power_w: float, cda: float = 0.32, crr: float = 0.004,
                   air_density: float = 1.0, drivetrain_efficiency: float = 0.97) -> float:
    """一定パワー power_w（W）で登ったときの予測所要時間（秒）を返す。

    距離（km）・獲得標高（m）・総重量（kg、体重＋機材）から平均勾配を求め、
    釣り合いの式を速度について二分法で解く。
    距離・重量・パワーが 0 以下、獲得標高が負なら ValueError。
    """
    distance_m, sin_t, cos_t = _check_params(distance_km, elevation_gain_m, total_weight_kg,
                                             cda, crr, air_density, drivetrain_efficiency)
    if power_w <= 0:
        raise ValueError("power_w は 0 より大きい値を指定してください")
    wheel_power = power_w * drivetrain_efficiency

    def excess(v):
        return _resistance_power(v, total_weight_kg, sin_t, cos_t, cda, crr,
                                 air_density) - wheel_power

    # 抵抗パワーは v について単調増加（v=0 で 0）なので、上限を倍々に広げてから二分法で解く。
    lo, hi = 0.0, 1.0
    while excess(hi) < 0:
        lo, hi = hi, hi * 2.0
        if hi > 1e9:
            raise ValueError("抵抗がほぼ 0 のため速度を求められません（cda / crr / 勾配を確認してください）")
    for _ in range(_BISECTION_ITERATIONS):
        mid = (lo + hi) / 2.0
        if excess(mid) < 0:
            lo = mid
        else:
            hi = mid
        if hi - lo <= 1e-12 * hi:
            break
    v = (lo + hi) / 2.0
    return distance_m / v


def required_power_w(distance_km: float, elevation_gain_m: float, total_weight_kg: float,
                     target_time_sec: float, cda: float = 0.32, crr: float = 0.004,
                     air_density: float = 1.0, drivetrain_efficiency: float = 0.97) -> float:
    """目標タイム target_time_sec（秒）で登るのに必要な平均パワー（W）を返す。

    climb_time_sec の逆算。速度 v = 距離 / 目標タイム を式に代入して求める。
    距離・重量・目標タイムが 0 以下、獲得標高が負なら ValueError。
    """
    distance_m, sin_t, cos_t = _check_params(distance_km, elevation_gain_m, total_weight_kg,
                                             cda, crr, air_density, drivetrain_efficiency)
    if target_time_sec <= 0:
        raise ValueError("target_time_sec は 0 より大きい値を指定してください")
    v = distance_m / target_time_sec
    return _resistance_power(v, total_weight_kg, sin_t, cos_t, cda, crr,
                             air_density) / drivetrain_efficiency
