"""pacecalc のコマンドラインインターフェース。

使い方:
    python -m pacecalc pace --speed 12
    python -m pacecalc finish --distance 42.195 --pace 5:30
    python -m pacecalc splits --distance 10 --pace 5:00
    python -m pacecalc splits --distance 10 --target 50:00 --interval 5 --format csv
    python -m pacecalc climb --distance 24.03 --gain 1211 --weight 76 --power 226.6
    python -m pacecalc course --gpx course.gpx --power 230 --weight 76
"""

import argparse
import csv
import sys
import unicodedata

from .climb import climb_time_sec
from .core import format_hms, format_pace, speed_to_pace_sec
from .course import load_gpx_points, plan_course
from .predict import finish_time_sec
from .splits import split_table


def parse_pace(text):
    """"M:SS" 形式のペース文字列を秒/km に変換する（例: "5:30" → 330）。

    秒は 0〜59 の整数 2 桁、分は 0 以上の整数とする。形式不正は ValueError。
    """
    parts = text.strip().split(":")
    if len(parts) != 2:
        raise ValueError("ペースは M:SS 形式で指定してください: %r" % text)
    minutes_str, seconds_str = parts
    if not minutes_str.isdigit() or not seconds_str.isdigit() or len(seconds_str) != 2:
        raise ValueError("ペースは M:SS 形式で指定してください: %r" % text)
    minutes, seconds = int(minutes_str), int(seconds_str)
    if seconds >= 60:
        raise ValueError("ペースの秒は 00〜59 で指定してください: %r" % text)
    return minutes * 60 + seconds


def parse_time(text):
    """"MM:SS" または "H:MM:SS" 形式のタイム文字列を秒に変換する（例: "50:00" → 3000）。

    "MM:SS" の分は 0 以上の整数（桁数制限なし）、秒は 2 桁の 00〜59。
    "H:MM:SS" の時は 0 以上の整数、分・秒は 2 桁の 00〜59。形式不正は ValueError。
    """
    parts = text.strip().split(":")
    if len(parts) not in (2, 3) or not all(p.isdigit() for p in parts):
        raise ValueError("タイムは MM:SS または H:MM:SS 形式で指定してください: %r" % text)
    if len(parts[-1]) != 2 or int(parts[-1]) >= 60:
        raise ValueError("タイムの秒は 00〜59 の 2 桁で指定してください: %r" % text)
    if len(parts) == 3 and (len(parts[1]) != 2 or int(parts[1]) >= 60):
        raise ValueError("タイムの分は 00〜59 の 2 桁で指定してください: %r" % text)
    total = 0
    for part in parts:
        total = total * 60 + int(part)
    return total


def _format_km(value):
    """距離（km）を表示用に整形する（小数第 4 位まで、末尾の 0 は省く。例: 1.0 → "1"）。"""
    text = "%.4f" % value
    return text.rstrip("0").rstrip(".")


def _display_width(text):
    """端末上の表示幅を返す（全角文字は 2 桁として数える）。"""
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def _rjust(text, width):
    """表示幅を考慮して右揃えする。"""
    return " " * (width - _display_width(text)) + text


def _print_splits(rows, fmt):
    """スプリット表を表形式または CSV で標準出力に書く。"""
    if fmt == "csv":
        writer = csv.writer(sys.stdout, lineterminator="\n")
        writer.writerow(["distance_km", "lap", "elapsed"])
        for point, lap, elapsed in rows:
            writer.writerow([_format_km(point), format_pace(lap), format_hms(elapsed)])
        return
    table = [("距離(km)", "ラップ", "累計")]
    table += [(_format_km(p), format_pace(lap), format_hms(el)) for p, lap, el in rows]
    widths = [max(_display_width(row[i]) for row in table) for i in range(3)]
    for row in table:
        print("  ".join(_rjust(cell, width) for cell, width in zip(row, widths)))


def _print_course(rows, total_sec):
    """コース計画の区間表と総所要時間を標準出力に書く。"""
    table = [("区間(km)", "勾配(%)", "速度(km/h)", "所要", "累計")]
    elapsed = 0.0
    for start, end, gradient, speed, time_sec in rows:
        elapsed += time_sec
        table.append((
            "%s-%s" % (_format_km(start), _format_km(end)),
            "%+.1f" % gradient,
            "%.1f" % speed,
            format_pace(time_sec),
            format_hms(elapsed),
        ))
    widths = [max(_display_width(row[i]) for row in table) for i in range(len(table[0]))]
    for row in table:
        print("  ".join(_rjust(cell, width) for cell, width in zip(row, widths)))
    print("総所要時間: %s" % format_hms(total_sec))


def _build_parser():
    parser = argparse.ArgumentParser(
        prog="pacecalc",
        description="ラン／サイクリング向けのペース計算ツール",
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    p_pace = sub.add_parser("pace", help="速度（km/h）からペース（/km）を表示する")
    p_pace.add_argument("--speed", type=float, required=True, help="速度（km/h）")

    p_finish = sub.add_parser("finish", help="距離とペースから完走タイムを表示する")
    p_finish.add_argument("--distance", type=float, required=True, help="距離（km）")
    p_finish.add_argument("--pace", required=True, help='ペース（"M:SS" 形式、例: 5:30）')

    p_splits = sub.add_parser("splits", help="区間ごとの通過タイム表（スプリット表）を表示する")
    p_splits.add_argument("--distance", type=float, required=True, help="距離（km）")
    group = p_splits.add_mutually_exclusive_group(required=True)
    group.add_argument("--pace", help='ペース（"M:SS" 形式、例: 5:00）')
    group.add_argument("--target", help='目標タイム（"MM:SS" または "H:MM:SS" 形式、例: 50:00）')
    p_splits.add_argument("--interval", type=float, default=1.0, help="区間幅（km、既定 1）")
    p_splits.add_argument(
        "--format", choices=("table", "csv"), default="table", help="出力形式（既定 table）"
    )

    p_climb = sub.add_parser("climb", help="一定パワーで登坂したときの予測タイムを表示する（推定値）")
    p_climb.add_argument("--distance", type=float, required=True, help="距離（km）")
    p_climb.add_argument("--gain", type=float, required=True, help="獲得標高（m）")
    p_climb.add_argument("--weight", type=float, required=True, help="総重量（kg、体重＋機材）")
    p_climb.add_argument("--power", type=float, required=True, help="平均パワー（W）")

    p_course = sub.add_parser("course", help="GPX コースを一定パワーで走る区間ごとの計画を表示する（推定値）")
    p_course.add_argument("--gpx", required=True, help="GPX ファイルのパス")
    p_course.add_argument("--power", type=float, required=True, help="平均パワー（W）")
    p_course.add_argument("--weight", type=float, required=True, help="総重量（kg、体重＋機材）")
    p_course.add_argument("--segment", type=float, default=1.0, help="区間幅（km、既定 1）")

    return parser


def main(argv=None):
    """CLI のエントリポイント。結果を標準出力に書き、終了コードを返す。

    入力エラー時は標準エラーにメッセージを出し、終了コード 2 を返す。
    """
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "pace":
            print("%s /km" % format_pace(speed_to_pace_sec(args.speed)))
        elif args.command == "finish":
            pace_sec = parse_pace(args.pace)
            print(format_hms(finish_time_sec(args.distance, pace_sec)))
        elif args.command == "splits":
            if args.pace is not None:
                rows = split_table(args.distance, pace_sec=parse_pace(args.pace),
                                   interval_km=args.interval)
            else:
                rows = split_table(args.distance, target_time_sec=parse_time(args.target),
                                   interval_km=args.interval)
            _print_splits(rows, args.format)
        elif args.command == "climb":
            print(format_hms(climb_time_sec(args.distance, args.gain, args.weight, args.power)))
        elif args.command == "course":
            try:
                with open(args.gpx, encoding="utf-8-sig") as f:
                    text = f.read()
            except (OSError, UnicodeDecodeError) as exc:
                raise ValueError("GPX ファイルを読めません: %s" % exc)
            rows, total = plan_course(load_gpx_points(text), args.power, args.weight,
                                      segment_km=args.segment)
            _print_course(rows, total)
    except ValueError as exc:
        print("pacecalc: エラー: %s" % exc, file=sys.stderr)
        return 2
    return 0
