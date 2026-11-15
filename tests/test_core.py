"""pacecalc.core のテスト。"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from pacecalc import format_hms, format_pace, pace_to_speed_kmh, speed_to_pace_sec


class TestSpeedToPace(unittest.TestCase):
    def test_normal(self):
        self.assertAlmostEqual(speed_to_pace_sec(12.0), 300.0)
        self.assertAlmostEqual(speed_to_pace_sec(10.0), 360.0)
        self.assertAlmostEqual(speed_to_pace_sec(36.0), 100.0)

    def test_zero_raises(self):
        with self.assertRaises(ValueError):
            speed_to_pace_sec(0)

    def test_negative_raises(self):
        with self.assertRaises(ValueError):
            speed_to_pace_sec(-5)


class TestPaceToSpeed(unittest.TestCase):
    def test_normal(self):
        self.assertAlmostEqual(pace_to_speed_kmh(300), 12.0)
        self.assertAlmostEqual(pace_to_speed_kmh(330), 3600 / 330)

    def test_round_trip(self):
        for speed in (5.0, 9.7, 12.0, 42.195):
            self.assertAlmostEqual(pace_to_speed_kmh(speed_to_pace_sec(speed)), speed)

    def test_zero_raises(self):
        with self.assertRaises(ValueError):
            pace_to_speed_kmh(0)

    def test_negative_raises(self):
        with self.assertRaises(ValueError):
            pace_to_speed_kmh(-1)


class TestFormatPace(unittest.TestCase):
    def test_normal(self):
        self.assertEqual(format_pace(330), "5:30")
        self.assertEqual(format_pace(300), "5:00")
        self.assertEqual(format_pace(65), "1:05")

    def test_rounding(self):
        self.assertEqual(format_pace(330.4), "5:30")
        self.assertEqual(format_pace(330.5), "5:31")  # 四捨五入（偶数丸めではない）
        self.assertEqual(format_pace(332.5), "5:33")

    def test_carry_over_60(self):
        self.assertEqual(format_pace(359.5), "6:00")
        self.assertEqual(format_pace(359.6), "6:00")
        self.assertEqual(format_pace(59.7), "1:00")

    def test_zero(self):
        self.assertEqual(format_pace(0), "0:00")

    def test_large_minutes(self):
        self.assertEqual(format_pace(754), "12:34")

    def test_negative_raises(self):
        with self.assertRaises(ValueError):
            format_pace(-1)


class TestFormatHms(unittest.TestCase):
    def test_normal(self):
        self.assertEqual(format_hms(3725), "1:02:05")
        self.assertEqual(format_hms(59), "0:00:59")
        self.assertEqual(format_hms(36000), "10:00:00")

    def test_zero(self):
        self.assertEqual(format_hms(0), "0:00:00")

    def test_rounding_and_carry(self):
        self.assertEqual(format_hms(3725.4), "1:02:05")
        self.assertEqual(format_hms(59.5), "0:01:00")
        self.assertEqual(format_hms(3599.5), "1:00:00")

    def test_negative_raises(self):
        with self.assertRaises(ValueError):
            format_hms(-1)
        with self.assertRaises(ValueError):
            format_hms(-0.1)


if __name__ == "__main__":
    unittest.main()
