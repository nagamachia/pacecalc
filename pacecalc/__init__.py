"""pacecalc: エンデュランススポーツ（ラン／サイクリング）向けのペース計算ライブラリ。"""

from .climb import climb_time_sec, required_power_w
from .core import format_hms, format_pace, pace_to_speed_kmh, speed_to_pace_sec
from .course import course_segments, haversine_m, load_gpx_points, plan_course
from .predict import finish_time_sec, riegel_predict_sec
from .splits import split_table

__version__ = "1.0.0"

__all__ = [
    "__version__",
    "speed_to_pace_sec",
    "pace_to_speed_kmh",
    "format_pace",
    "format_hms",
    "finish_time_sec",
    "riegel_predict_sec",
    "split_table",
    "climb_time_sec",
    "required_power_w",
    "load_gpx_points",
    "haversine_m",
    "course_segments",
    "plan_course",
]
