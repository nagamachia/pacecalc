"""pacecalc.cli のテスト（main 関数の呼び出しと subprocess の両方で検証）。"""

import contextlib
import io
import os
import subprocess
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from pacecalc.cli import main, parse_pace


def run_main(argv):
    """main を呼び出し、(終了コード, 標準出力, 標準エラー) を返す。"""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = main(argv)
        except SystemExit as exc:  # argparse のエラー
            code = exc.code
    return code, out.getvalue(), err.getvalue()


class TestParsePace(unittest.TestCase):
    def test_normal(self):
        self.assertEqual(parse_pace("5:30"), 330)
        self.assertEqual(parse_pace("0:45"), 45)
        self.assertEqual(parse_pace("12:05"), 725)

    def test_invalid(self):
        for text in ("5", "5:3", "5:60", "5:30:00", "a:30", "-5:30", "5:3a", ""):
            with self.assertRaises(ValueError, msg=text):
                parse_pace(text)


class TestMain(unittest.TestCase):
    def test_pace(self):
        code, out, _ = run_main(["pace", "--speed", "12"])
        self.assertEqual(code, 0)
        self.assertEqual(out, "5:00 /km\n")

    def test_pace_fraction(self):
        code, out, _ = run_main(["pace", "--speed", "11"])
        self.assertEqual(code, 0)
        self.assertEqual(out, "5:27 /km\n")  # 327.27... → 5:27

    def test_finish(self):
        code, out, _ = run_main(["finish", "--distance", "42.195", "--pace", "5:30"])
        self.assertEqual(code, 0)
        self.assertEqual(out, "3:52:04\n")

    def test_pace_zero_speed_error(self):
        code, out, err = run_main(["pace", "--speed", "0"])
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("エラー", err)

    def test_finish_bad_pace_error(self):
        code, out, err = run_main(["finish", "--distance", "10", "--pace", "5:75"])
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("エラー", err)

    def test_finish_zero_distance_error(self):
        code, _, err = run_main(["finish", "--distance", "0", "--pace", "5:30"])
        self.assertEqual(code, 2)
        self.assertIn("エラー", err)

    def test_missing_command(self):
        code, _, _ = run_main([])
        self.assertEqual(code, 2)

    def test_missing_argument(self):
        code, _, _ = run_main(["finish", "--distance", "10"])
        self.assertEqual(code, 2)


class TestSubprocess(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "pacecalc"] + list(args),
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

    def test_pace(self):
        result = self.run_cli("pace", "--speed", "12")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "5:00 /km")

    def test_finish(self):
        result = self.run_cli("finish", "--distance", "42.195", "--pace", "5:30")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "3:52:04")

    def test_error_exit_code(self):
        result = self.run_cli("finish", "--distance", "-1", "--pace", "5:30")
        self.assertEqual(result.returncode, 2)
        self.assertIn("エラー", result.stderr)


if __name__ == "__main__":
    unittest.main()
