"""pacecalc.splits と CLI の splits サブコマンドのテスト。"""

import contextlib
import io
import os
import subprocess
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from pacecalc import split_table
from pacecalc.cli import main, parse_time


def run_main(argv):
    """main を呼び出し、(終了コード, 標準出力, 標準エラー) を返す。"""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = main(argv)
        except SystemExit as exc:  # argparse のエラー
            code = exc.code
    return code, out.getvalue(), err.getvalue()


class TestSplitTable(unittest.TestCase):
    def assertRows(self, actual, expected):
        self.assertEqual(len(actual), len(expected))
        for got, want in zip(actual, expected):
            for g, w in zip(got, want):
                self.assertAlmostEqual(g, w, places=6)

    def test_pace_even(self):
        rows = split_table(10, pace_sec=300)
        self.assertEqual(len(rows), 10)
        self.assertRows(rows[:2], [(1, 300, 300), (2, 300, 600)])
        self.assertRows(rows[-1:], [(10, 300, 3000)])

    def test_tuple_shape(self):
        for row in split_table(3, pace_sec=300):
            self.assertIsInstance(row, tuple)
            self.assertEqual(len(row), 3)

    def test_fraction_last_segment(self):
        rows = split_table(10.5, pace_sec=300, interval_km=3)
        self.assertRows(rows, [(3, 900, 900), (6, 900, 1800), (9, 900, 2700), (10.5, 450, 3150)])

    def test_last_point_is_exact_distance(self):
        rows = split_table(42.195, pace_sec=330)
        self.assertEqual(len(rows), 43)
        self.assertEqual(rows[-1][0], 42.195)
        self.assertAlmostEqual(rows[-1][1], 0.195 * 330, places=6)
        self.assertAlmostEqual(rows[-1][2], 42.195 * 330, places=6)

    def test_float_interval_no_tiny_segment(self):
        # 0.1 × 10 などの浮動小数点誤差で極小の端数区間が出ないこと
        rows = split_table(1.0, pace_sec=300, interval_km=0.1)
        self.assertEqual(len(rows), 10)
        self.assertEqual(rows[-1][0], 1.0)
        rows = split_table(0.3, pace_sec=300, interval_km=0.1)
        self.assertEqual(len(rows), 3)

    def test_target_even_pace(self):
        rows = split_table(10, target_time_sec=3000, interval_km=5)
        self.assertRows(rows, [(5, 1500, 1500), (10, 1500, 3000)])

    def test_target_fraction(self):
        rows = split_table(21.0975, target_time_sec=6300, interval_km=5)
        self.assertEqual(len(rows), 5)
        self.assertAlmostEqual(rows[-1][2], 6300, places=6)
        self.assertAlmostEqual(sum(r[1] for r in rows), 6300, places=6)

    def test_interval_larger_than_distance(self):
        rows = split_table(3, pace_sec=300, interval_km=5)
        self.assertRows(rows, [(3, 900, 900)])

    def test_interval_equal_distance(self):
        rows = split_table(5, pace_sec=300, interval_km=5)
        self.assertRows(rows, [(5, 1500, 1500)])

    def test_both_or_neither_error(self):
        with self.assertRaises(ValueError):
            split_table(10, pace_sec=300, target_time_sec=3000)
        with self.assertRaises(ValueError):
            split_table(10)

    def test_non_positive_error(self):
        for kwargs in (
            dict(distance_km=0, pace_sec=300),
            dict(distance_km=-1, pace_sec=300),
            dict(distance_km=10, pace_sec=300, interval_km=0),
            dict(distance_km=10, pace_sec=300, interval_km=-1),
            dict(distance_km=10, pace_sec=0),
            dict(distance_km=10, target_time_sec=0),
        ):
            with self.assertRaises(ValueError, msg=kwargs):
                split_table(**kwargs)


class TestParseTime(unittest.TestCase):
    def test_normal(self):
        self.assertEqual(parse_time("50:00"), 3000)
        self.assertEqual(parse_time("05:30"), 330)
        self.assertEqual(parse_time("125:00"), 7500)
        self.assertEqual(parse_time("1:45:00"), 6300)
        self.assertEqual(parse_time("3:05:09"), 11109)

    def test_invalid(self):
        for text in ("50", "50:0", "50:60", "1:60:00", "1:5:00", "1:00:00:00", "a:00", "-5:00", ""):
            with self.assertRaises(ValueError, msg=text):
                parse_time(text)


class TestSplitsCli(unittest.TestCase):
    def test_table(self):
        code, out, err = run_main(["splits", "--distance", "10", "--pace", "5:00"])
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        lines = out.splitlines()
        self.assertEqual(len(lines), 11)  # 見出し + 10 区間
        for word in ("距離", "ラップ", "累計"):
            self.assertIn(word, lines[0])
        self.assertEqual(lines[1].split(), ["1", "5:00", "0:05:00"])
        self.assertEqual(lines[-1].split(), ["10", "5:00", "0:50:00"])

    def test_target_interval(self):
        code, out, _ = run_main(["splits", "--distance", "10", "--target", "50:00", "--interval", "5"])
        self.assertEqual(code, 0)
        rows = [line.split() for line in out.splitlines()[1:]]
        self.assertEqual(rows, [["5", "25:00", "0:25:00"], ["10", "25:00", "0:50:00"]])

    def test_target_hms_fraction(self):
        code, out, _ = run_main(
            ["splits", "--distance", "21.0975", "--target", "1:45:00", "--interval", "5"]
        )
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines()[-1].split(), ["21.0975", "5:28", "1:45:00"])

    def test_csv(self):
        code, out, _ = run_main(
            ["splits", "--distance", "10.5", "--pace", "5:00", "--interval", "3", "--format", "csv"]
        )
        self.assertEqual(code, 0)
        self.assertEqual(
            out,
            "distance_km,lap,elapsed\n"
            "3,15:00,0:15:00\n"
            "6,15:00,0:30:00\n"
            "9,15:00,0:45:00\n"
            "10.5,7:30,0:52:30\n",
        )

    def test_pace_and_target_error(self):
        code, out, _ = run_main(["splits", "--distance", "10", "--pace", "5:00", "--target", "50:00"])
        self.assertEqual(code, 2)
        self.assertEqual(out, "")

    def test_neither_pace_nor_target_error(self):
        code, _, _ = run_main(["splits", "--distance", "10"])
        self.assertEqual(code, 2)

    def test_invalid_values_error(self):
        for argv in (
            ["splits", "--distance", "0", "--pace", "5:00"],
            ["splits", "--distance", "10", "--pace", "5:00", "--interval", "0"],
            ["splits", "--distance", "10", "--target", "50:75"],
            ["splits", "--distance", "10", "--pace", "5:60"],
            ["splits", "--distance", "10", "--target", "0:00"],
        ):
            code, out, err = run_main(argv)
            self.assertEqual(code, 2, msg=argv)
            self.assertEqual(out, "", msg=argv)
            self.assertIn("エラー", err, msg=argv)

    def test_invalid_format_error(self):
        code, _, _ = run_main(["splits", "--distance", "10", "--pace", "5:00", "--format", "json"])
        self.assertEqual(code, 2)

    def test_subprocess(self):
        result = subprocess.run(
            [sys.executable, "-m", "pacecalc", "splits", "--distance", "10", "--pace", "5:00",
             "--target", "50:00"],
            cwd=ROOT, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 2)
        result = subprocess.run(
            [sys.executable, "-m", "pacecalc", "splits", "--distance", "5", "--pace", "5:00",
             "--format", "csv"],
            cwd=ROOT, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.splitlines()[-1], "5,5:00,0:25:00")


if __name__ == "__main__":
    unittest.main()
