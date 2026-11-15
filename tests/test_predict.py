"""pacecalc.predict のテスト。"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from pacecalc import finish_time_sec, format_hms, riegel_predict_sec


class TestFinishTime(unittest.TestCase):
    def test_normal(self):
        self.assertAlmostEqual(finish_time_sec(10, 300), 3000.0)
        self.assertAlmostEqual(finish_time_sec(42.195, 330), 13924.35)

    def test_marathon_format(self):
        self.assertEqual(format_hms(finish_time_sec(42.195, 330)), "3:52:04")

    def test_invalid_distance(self):
        for d in (0, -1, -0.1):
            with self.assertRaises(ValueError):
                finish_time_sec(d, 300)

    def test_invalid_pace(self):
        for p in (0, -300):
            with self.assertRaises(ValueError):
                finish_time_sec(10, p)


class TestRiegel(unittest.TestCase):
    def test_same_distance(self):
        self.assertAlmostEqual(riegel_predict_sec(10, 3000, 10), 3000.0)

    def test_default_exponent(self):
        # 10km 50分 → ハーフ: 3000 × (21.0975/10)^1.06 ≒ 6619.2 秒
        expected = 3000 * (21.0975 / 10) ** 1.06
        self.assertAlmostEqual(riegel_predict_sec(10, 3000, 21.0975), expected)
        self.assertEqual(format_hms(expected), "1:50:19")

    def test_custom_exponent(self):
        self.assertAlmostEqual(riegel_predict_sec(5, 1200, 10, exponent=1.0), 2400.0)
        self.assertAlmostEqual(riegel_predict_sec(5, 1200, 10, 1.1), 1200 * 2 ** 1.1)

    def test_shorter_target(self):
        self.assertLess(riegel_predict_sec(10, 3000, 5), 1500.0)

    def test_invalid_inputs(self):
        cases = [
            (0, 3000, 10),
            (-10, 3000, 10),
            (10, 0, 10),
            (10, -1, 10),
            (10, 3000, 0),
            (10, 3000, -5),
        ]
        for args in cases:
            with self.assertRaises(ValueError, msg=str(args)):
                riegel_predict_sec(*args)

    def test_invalid_exponent(self):
        for e in (0, -1.06):
            with self.assertRaises(ValueError):
                riegel_predict_sec(10, 3000, 21.0975, exponent=e)


if __name__ == "__main__":
    unittest.main()
