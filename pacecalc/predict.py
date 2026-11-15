"""pacecalc の完走タイム予測関数。

距離とペースからの完走タイム計算、および Riegel 式による別距離のタイム予測を提供する。
"""


def finish_time_sec(distance_km: float, pace_sec: float) -> float:
    """距離（km）とペース（秒/km）から完走タイム（秒）を返す。

    距離・ペースのどちらかが 0 以下なら ValueError。
    """
    if distance_km <= 0:
        raise ValueError("distance_km は 0 より大きい値を指定してください")
    if pace_sec <= 0:
        raise ValueError("pace_sec は 0 より大きい値を指定してください")
    return distance_km * pace_sec


def riegel_predict_sec(known_distance_km: float, known_time_sec: float, target_distance_km: float,
                       exponent: float = 1.06) -> float:
    """Riegel 式 T2 = T1 × (D2/D1)^exponent で目標距離の予測タイム（秒）を返す。

    known_distance_km / known_time_sec / target_distance_km / exponent の
    いずれかが 0 以下なら ValueError。
    """
    if known_distance_km <= 0:
        raise ValueError("known_distance_km は 0 より大きい値を指定してください")
    if known_time_sec <= 0:
        raise ValueError("known_time_sec は 0 より大きい値を指定してください")
    if target_distance_km <= 0:
        raise ValueError("target_distance_km は 0 より大きい値を指定してください")
    if exponent <= 0:
        raise ValueError("exponent は 0 より大きい値を指定してください")
    return known_time_sec * (target_distance_km / known_distance_km) ** exponent
