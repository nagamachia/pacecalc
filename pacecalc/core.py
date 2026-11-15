"""pacecalc のコア変換関数。

ペース（秒/km）と速度（km/h）の相互変換、および表示用の書式化を提供する。
"""

import math

SECONDS_PER_HOUR = 3600.0


def _round_half_up(value: float) -> int:
    """四捨五入して int を返す（Python 組み込みの round は偶数丸めのため使わない）。"""
    return int(math.floor(value + 0.5))


def speed_to_pace_sec(speed_kmh: float) -> float:
    """速度（km/h）からペース（秒/km）を返す。0 以下は ValueError。"""
    if speed_kmh <= 0:
        raise ValueError("speed_kmh は 0 より大きい値を指定してください")
    return SECONDS_PER_HOUR / speed_kmh


def pace_to_speed_kmh(pace_sec: float) -> float:
    """ペース（秒/km）から速度（km/h）を返す。0 以下は ValueError。"""
    if pace_sec <= 0:
        raise ValueError("pace_sec は 0 より大きい値を指定してください")
    return SECONDS_PER_HOUR / pace_sec


def format_pace(pace_sec: float) -> str:
    """秒/km を "M:SS" 形式の文字列にする（例: 330 → "5:30"）。

    秒は四捨五入し、59.5 秒以上は分へ繰り上げる（例: 359.6 → "6:00"）。
    負値は ValueError。
    """
    if pace_sec < 0:
        raise ValueError("pace_sec は 0 以上の値を指定してください")
    total = _round_half_up(pace_sec)
    minutes, seconds = divmod(total, 60)
    return "%d:%02d" % (minutes, seconds)


def format_hms(seconds: float) -> str:
    """秒を "H:MM:SS" 形式の文字列にする（例: 3725 → "1:02:05"）。

    秒は四捨五入し、分・時への繰り上がりも処理する。負値は ValueError。
    """
    if seconds < 0:
        raise ValueError("seconds は 0 以上の値を指定してください")
    total = _round_half_up(seconds)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return "%d:%02d:%02d" % (hours, minutes, secs)
