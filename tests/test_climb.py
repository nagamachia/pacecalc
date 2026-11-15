"""pacecalc.climb（ヒルクライム物理モデル）の検証テスト。"""

import contextlib
import io
import os
import subprocess
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

import pacecalc
from pacecalc.climb import GRAVITY, climb_time_sec, required_power_w
from pacecalc.cli import main

# 富士スバルラインの実測ケース
FUJI = dict(distance_km=24.03, elevation_gain_m=1211, total_weight_kg=76)
FUJI_POWER = 226.6
FUJI_ACTUAL_SEC = 5135  # 1:25:35


class TestMonotonicity(unittest.TestCase):
    def test_more_power_is_faster(self):
        times = [climb_time_sec(power_w=p, **FUJI) for p in (100, 150, 200, 250, 300, 400)]
        for slower, faster in zip(times, times[1:]):
            self.assertLess(faster, slower)

    def test_heavier_is_slower(self):
        times = [climb_time_sec(24.03, 1211, w, FUJI_POWER) for w in (55, 65, 76, 90, 110)]
        for lighter, heavier in zip(times, times[1:]):
            self.assertGreater(heavier, lighter)

    def test_steeper_is_slower(self):
        times = [climb_time_sec(10, g, 70, 250) for g in (0, 200, 500, 800)]
        for easier, harder in zip(times, times[1:]):
            self.assertGreater(harder, easier)

    def test_faster_target_needs_more_power(self):
        powers = [required_power_w(target_time_sec=t, **FUJI) for t in (7000, 6000, 5000, 4000)]
        for lower, higher in zip(powers, powers[1:]):
            self.assertGreater(higher, lower)


class TestRoundTrip(unittest.TestCase):
    def test_time_to_power_to_time(self):
        cases = [
            (24.03, 1211, 76, 226.6, {}),
            (10, 0, 80, 200, {}),  # 平坦
            (5, 600, 60, 350, {}),
            (40, 300, 85, 180, dict(cda=0.25, crr=0.005, air_density=1.225,
                                    drivetrain_efficiency=0.95)),
        ]
        for dist, gain, weight, power, kw in cases:
            t = climb_time_sec(dist, gain, weight, power, **kw)
            p = required_power_w(dist, gain, weight, t, **kw)
            self.assertAlmostEqual(p, power, places=6, msg=(dist, gain, weight, power))

    def test_power_to_time_to_power(self):
        for target in (3600, 5135, 9000):
            p = required_power_w(target_time_sec=target, **FUJI)
            self.assertAlmostEqual(climb_time_sec(power_w=p, **FUJI), target, places=4)


class TestPhysics(unittest.TestCase):
    def test_required_power_matches_formula(self):
        # 3% 勾配の手計算値と一致すること
        import math
        dist_km, gain, m, t = 10, 300, 70, 1800
        v = 10000 / t
        th = math.atan(300 / 10000)
        expected = ((m * GRAVITY * math.sin(th) + 0.004 * m * GRAVITY * math.cos(th)) * v
                    + 0.5 * 1.0 * 0.32 * v ** 3) / 0.97
        self.assertAlmostEqual(required_power_w(dist_km, gain, m, t), expected, places=9)

    def test_flat_zero_gain_allowed(self):
        t = climb_time_sec(40, 0, 80, 200)
        self.assertGreater(t, 0)
        # 平坦 200W なら 30〜45 km/h 程度の現実的な範囲
        speed_kmh = 40 / (t / 3600)
        self.assertTrue(30 < speed_kmh < 45, speed_kmh)


class TestRealWorld(unittest.TestCase):
    def test_fuji_subaru_line_within_10_percent(self):
        predicted = climb_time_sec(power_w=FUJI_POWER, **FUJI)
        self.assertLessEqual(abs(predicted - FUJI_ACTUAL_SEC) / FUJI_ACTUAL_SEC, 0.10,
                             "予測 %.0f 秒 / 実測 %d 秒" % (predicted, FUJI_ACTUAL_SEC))


class TestValidation(unittest.TestCase):
    def test_climb_time_invalid(self):
        for args in [(0, 100, 70, 200), (-1, 100, 70, 200), (10, 100, 0, 200),
                     (10, 100, -70, 200), (10, 100, 70, 0), (10, 100, 70, -200),
                     (10, -1, 70, 200)]:
            with self.assertRaises(ValueError, msg=args):
                climb_time_sec(*args)

    def test_required_power_invalid(self):
        for args in [(0, 100, 70, 3600), (10, 100, 0, 3600), (10, 100, 70, 0),
                     (10, 100, 70, -1), (10, -1, 70, 3600)]:
            with self.assertRaises(ValueError, msg=args):
                required_power_w(*args)

    def test_invalid_optional_params(self):
        for kw in [dict(drivetrain_efficiency=0), dict(drivetrain_efficiency=1.5),
                   dict(cda=-0.1), dict(crr=-0.1), dict(air_density=-1)]:
            with self.assertRaises(ValueError, msg=kw):
                climb_time_sec(10, 100, 70, 200, **kw)
            with self.assertRaises(ValueError, msg=kw):
                required_power_w(10, 100, 70, 3600, **kw)

    def test_no_resistance_raises(self):
        with self.assertRaises(ValueError):
            climb_time_sec(10, 0, 70, 200, cda=0, crr=0)

    def test_package_exports(self):
        self.assertIs(pacecalc.climb_time_sec, climb_time_sec)
        self.assertIs(pacecalc.required_power_w, required_power_w)


def run_main(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = main(argv)
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


class TestClimbCli(unittest.TestCase):
    ARGS = ["climb", "--distance", "24.03", "--gain", "1211", "--weight", "76",
            "--power", "226.6"]

    def test_climb_output(self):
        code, out, _ = run_main(self.ARGS)
        self.assertEqual(code, 0)
        self.assertRegex(out, r"^\d+:\d{2}:\d{2}\n$")
        expected = pacecalc.format_hms(climb_time_sec(power_w=FUJI_POWER, **FUJI))
        self.assertEqual(out, expected + "\n")

    def test_climb_invalid(self):
        code, out, err = run_main(["climb", "--distance", "10", "--gain", "100",
                                   "--weight", "70", "--power", "0"])
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("エラー", err)

    def test_climb_missing_arg(self):
        code, _, _ = run_main(["climb", "--distance", "10", "--gain", "100", "--weight", "70"])
        self.assertEqual(code, 2)

    def test_climb_subprocess(self):
        result = subprocess.run([sys.executable, "-m", "pacecalc"] + self.ARGS, cwd=ROOT,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertRegex(result.stdout, r"^\d+:\d{2}:\d{2}\n$")


if __name__ == "__main__":
    unittest.main()
