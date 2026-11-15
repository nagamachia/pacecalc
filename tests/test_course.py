"""pacecalc.course（GPX コース対応）のテスト。"""

import contextlib
import io
import math
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

import pacecalc
from pacecalc.cli import main
from pacecalc.climb import climb_time_sec
from pacecalc.core import speed_to_pace_sec
from pacecalc.course import (MAX_SPEED_KMH, course_segments, haversine_m, load_gpx_points,
                             plan_course)
from pacecalc.predict import finish_time_sec

# 赤道上で経度 1 度あたりの距離（km）。haversine_m と同じ地球半径から求める。
KM_PER_DEG = 2 * math.pi * 6371008.8 / 360 / 1000.0
STEP_KM = 0.1


def make_gpx(elevations, namespace=True, step_km=STEP_KM):
    """赤道上を東へ step_km ごとに進む点列の GPX 文字列を作る（標高 None は ele なし）。"""
    pts = []
    for i, ele in enumerate(elevations):
        lon = i * step_km / KM_PER_DEG
        inner = "" if ele is None else "<ele>%r</ele>" % ele
        pts.append('<trkpt lat="0" lon="%r">%s</trkpt>' % (lon, inner))
    xmlns = ' xmlns="http://www.topografix.com/GPX/1/1"' if namespace else ""
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<gpx version="1.1" creator="test"%s><trk><name>t</name><trkseg>%s'
            '</trkseg></trk></gpx>' % (xmlns, "".join(pts)))


# 5 km、100 m ごとに 5 m 登る一定勾配 5% の登り（獲得標高 250 m）
CLIMB_GPX = make_gpx([100.0 + 5.0 * i for i in range(51)])
# 5 km の平坦
FLAT_GPX = make_gpx([50.0] * 51)


def make_rounded_gpx(n_points, step_km, digits=6):
    """make_gpx と同じ経路で、経度を小数 digits 桁に丸めた GPX を作る（実際の GPX に多い形式）。

    丸めにより総距離が区間幅の倍数からわずか（数 cm）にずれる。標高は 100 m ずつ登る一定勾配。
    """
    pts = ['<trkpt lat="0" lon="%.*f"><ele>%r</ele></trkpt>'
           % (digits, i * step_km / KM_PER_DEG, 100.0 + 5.0 * i) for i in range(n_points)]
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<gpx version="1.1" creator="test">'
            '<trk><trkseg>%s</trkseg></trk></gpx>' % "".join(pts))


def run_main(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = main(argv)
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


class TestHaversine(unittest.TestCase):
    def test_one_degree_on_equator(self):
        self.assertAlmostEqual(haversine_m(0, 0, 0, 1) / 1000.0, 111.19, delta=0.05)

    def test_zero_and_symmetry(self):
        self.assertEqual(haversine_m(35.0, 139.0, 35.0, 139.0), 0.0)
        self.assertAlmostEqual(haversine_m(35.0, 139.0, 35.5, 139.7),
                               haversine_m(35.5, 139.7, 35.0, 139.0))

    def test_meridian(self):
        # 子午線方向も 1 度 ≒ 111.19 km（球体近似）
        self.assertAlmostEqual(haversine_m(10, 20, 11, 20) / 1000.0, 111.19, delta=0.05)


class TestLoadGpx(unittest.TestCase):
    def test_with_namespace(self):
        pts = load_gpx_points(make_gpx([1.0, 2.0, 3.0]))
        self.assertEqual(len(pts), 3)
        self.assertEqual(pts[0], (0.0, 0.0, 1.0))
        self.assertEqual(pts[2][2], 3.0)

    def test_without_namespace(self):
        self.assertEqual(load_gpx_points(make_gpx([1.0, 2.0], namespace=False)),
                         load_gpx_points(make_gpx([1.0, 2.0])))

    def test_missing_ele_is_none(self):
        pts = load_gpx_points(make_gpx([1.0, None, 3.0]))
        self.assertIsNone(pts[1][2])
        self.assertEqual(pts[2][2], 3.0)

    def test_rtept_fallback(self):
        text = ('<gpx xmlns="http://www.topografix.com/GPX/1/0"><rte>'
                '<rtept lat="35.1" lon="139.2"><ele>10</ele></rtept>'
                '<rtept lat="35.2" lon="139.3"/></rte></gpx>')
        self.assertEqual(load_gpx_points(text), [(35.1, 139.2, 10.0), (35.2, 139.3, None)])

    def test_invalid(self):
        for text in ("not xml", "<gpx><trk><trkseg><trkpt lat='0'/></trkseg></trk></gpx>",
                     "<gpx><trk><trkseg><trkpt lat='a' lon='0'/></trkseg></trk></gpx>",
                     "<gpx><trk><trkseg><trkpt lat='0' lon='0'><ele>x</ele></trkpt>"
                     "</trkseg></trk></gpx>"):
            with self.assertRaises(ValueError, msg=text):
                load_gpx_points(text)


class TestCourseSegments(unittest.TestCase):
    def test_constant_climb(self):
        segs = course_segments(load_gpx_points(CLIMB_GPX), segment_km=1.0)
        self.assertEqual(len(segs), 5)
        self.assertAlmostEqual(sum(s[2] for s in segs), 5.0, places=6)
        self.assertAlmostEqual(segs[-1][1], 5.0, places=6)
        self.assertAlmostEqual(sum(s[3] for s in segs), 250.0, places=6)
        self.assertAlmostEqual(sum(s[4] for s in segs), 0.0, places=6)
        for start, end, dist, gain, loss, gradient in segs:
            self.assertAlmostEqual(gain, 50.0, places=4)
            self.assertAlmostEqual(gradient, 5.0, places=4)
            self.assertAlmostEqual(end - start, dist)

    def test_fractional_last_segment(self):
        segs = course_segments(load_gpx_points(CLIMB_GPX), segment_km=2.0)
        self.assertEqual(len(segs), 3)
        self.assertAlmostEqual(segs[-1][2], 1.0, places=6)
        self.assertAlmostEqual(sum(s[3] for s in segs), 250.0, places=6)

    def test_exact_multiple_has_no_empty_segment(self):
        # 回帰（T006R）: 総距離が区間幅の倍数ちょうどのとき、長さ 0 の最終区間を作らない
        cases = [
            (make_gpx([0.0] * 31), 1.0, 3),            # 3.0 km / 1 km
            (make_gpx([0.0] * 31), 0.1, 30),           # 3.0 km / 0.1 km
            (make_gpx([0.0] * 61, step_km=0.05), 0.3, 10),  # 3.0 km / 0.3 km
            (make_rounded_gpx(31, 0.1), 1.0, 3),       # 丸めで総距離 3.00004 km
            (make_rounded_gpx(31, 0.1, digits=7), 1.0, 3),  # 丸めで総距離 2.999999 km
            (make_rounded_gpx(31, 0.1), 0.5, 6),
        ]
        for gpx, seg_km, expected in cases:
            with self.subTest(seg_km=seg_km, expected=expected):
                pts = load_gpx_points(gpx)
                segs = course_segments(pts, segment_km=seg_km)
                self.assertEqual(len(segs), expected)
                for start, end, dist, _gain, _loss, _grad in segs:
                    self.assertGreater(dist, seg_km * 0.5)
                    self.assertAlmostEqual(end - start, dist)
                # 区間はすき間なく 0 から総距離まで続く
                self.assertEqual(segs[0][0], 0.0)
                for a, b in zip(segs, segs[1:]):
                    self.assertEqual(a[1], b[0])
                total = sum(haversine_m(p[0], p[1], q[0], q[1])
                            for p, q in zip(pts, pts[1:])) / 1000.0
                self.assertAlmostEqual(segs[-1][1], total, places=9)

    def test_tiny_remainder_absorbed_into_previous(self):
        # 微小な端数は直前の区間に吸収され、距離と獲得標高は失われない
        pts = load_gpx_points(make_rounded_gpx(31, 0.1))
        segs = course_segments(pts, segment_km=1.0)
        self.assertEqual(segs[-1][0], 2.0)
        self.assertGreater(segs[-1][1], 3.0)
        self.assertAlmostEqual(sum(s[3] for s in segs), 150.0, places=6)

    def test_short_remainder_kept(self):
        # 吸収するのは 1 m 未満のみ。それ以上の端数は従来どおり短い区間として出す
        segs = course_segments(load_gpx_points(make_gpx([0.0] * 31)), segment_km=0.998)
        self.assertEqual(len(segs), 4)
        self.assertAlmostEqual(segs[-1][2], 0.006, places=6)
        segs = course_segments(load_gpx_points(make_gpx([0.0] * 31)), segment_km=0.9998)
        self.assertEqual(len(segs), 3)
        self.assertAlmostEqual(segs[-1][2], 1.0004, places=6)

    def test_boundary_interpolation(self):
        # 点の間隔 0.3 km と区間幅 1 km がずれていても獲得標高は保存される
        segs = course_segments(load_gpx_points(
            make_gpx([10.0 * i for i in range(11)], step_km=0.3)), segment_km=1.0)
        self.assertEqual(len(segs), 3)
        self.assertAlmostEqual(sum(s[3] for s in segs), 100.0, places=6)
        self.assertAlmostEqual(segs[0][3], 100.0 / 3.0, places=4)

    def test_descent(self):
        segs = course_segments(load_gpx_points(make_gpx([300.0 - 5.0 * i for i in range(21)])))
        self.assertEqual(len(segs), 2)
        for s in segs:
            self.assertAlmostEqual(s[3], 0.0)
            self.assertAlmostEqual(s[4], 50.0, places=4)
            self.assertAlmostEqual(s[5], -5.0, places=4)

    def test_missing_elevation_counts_zero(self):
        segs = course_segments(load_gpx_points(make_gpx([None] * 21)))
        self.assertEqual(len(segs), 2)
        for s in segs:
            self.assertEqual((s[3], s[4], s[5]), (0.0, 0.0, 0.0))
        # 一部だけ欠けている場合、欠けた点に接する部分だけ 0 になる
        elevations = [10.0 * i for i in range(11)]
        elevations[5] = None
        segs = course_segments(load_gpx_points(make_gpx(elevations)))
        self.assertAlmostEqual(segs[0][3], 80.0, places=6)

    def test_invalid(self):
        pts = load_gpx_points(CLIMB_GPX)
        with self.assertRaises(ValueError):
            course_segments(pts, segment_km=0)
        with self.assertRaises(ValueError):
            course_segments(pts[:1])
        with self.assertRaises(ValueError):
            course_segments([(0.0, 0.0, 1.0), (0.0, 0.0, 2.0)])


class TestPlanCourse(unittest.TestCase):
    def test_flat_matches_finish_time(self):
        pts = load_gpx_points(FLAT_GPX)
        rows, total = plan_course(pts, 200, 76)
        self.assertEqual(len(rows), 5)
        # 平坦なら T005 の climb_time_sec（獲得標高 0）と同じ速度になる
        flat_time = climb_time_sec(5.0, 0, 76, 200)
        flat_speed = 5.0 / flat_time * 3600.0
        for row in rows:
            self.assertAlmostEqual(row[3], flat_speed, places=6)
        # その速度のペースで T002 の finish_time_sec を計算すると総所要時間と一致する
        self.assertAlmostEqual(total, finish_time_sec(5.0, speed_to_pace_sec(flat_speed)),
                               places=3)
        self.assertAlmostEqual(total, sum(r[4] for r in rows))

    def test_climb_slower_than_flat(self):
        _, flat_total = plan_course(load_gpx_points(FLAT_GPX), 230, 76)
        rows, climb_total = plan_course(load_gpx_points(CLIMB_GPX), 230, 76)
        self.assertGreater(climb_total, flat_total)
        flat_rows, _ = plan_course(load_gpx_points(FLAT_GPX), 230, 76)
        for climb_row, flat_row in zip(rows, flat_rows):
            self.assertLess(climb_row[3], flat_row[3])
        # 一定勾配なら climb_time_sec と一致する
        self.assertAlmostEqual(climb_total, climb_time_sec(5.0, 250, 76, 230), delta=0.01)

    def test_steep_descent_capped(self):
        pts = load_gpx_points(make_gpx([1000.0 - 15.0 * i for i in range(21)]))
        rows, total = plan_course(pts, 200, 76)
        for row in rows:
            self.assertAlmostEqual(row[3], MAX_SPEED_KMH)
        self.assertAlmostEqual(total, 2.0 / MAX_SPEED_KMH * 3600.0)

    def test_gentle_descent_between(self):
        pts = load_gpx_points(make_gpx([100.0 - 0.5 * i for i in range(21)]))  # -0.5%
        rows, _ = plan_course(pts, 200, 76)
        flat_rows, _ = plan_course(load_gpx_points(FLAT_GPX), 200, 76)
        self.assertGreater(rows[0][3], flat_rows[0][3])
        self.assertLess(rows[0][3], MAX_SPEED_KMH)

    def test_physics_kwargs(self):
        pts = load_gpx_points(FLAT_GPX)
        _, base = plan_course(pts, 200, 76)
        _, aero = plan_course(pts, 200, 76, cda=0.25)
        self.assertLess(aero, base)

    def test_invalid(self):
        pts = load_gpx_points(FLAT_GPX)
        for kwargs in (dict(power_w=0, total_weight_kg=76), dict(power_w=200, total_weight_kg=0),
                       dict(power_w=200, total_weight_kg=76, cda=-1),
                       dict(power_w=200, total_weight_kg=76, drivetrain_efficiency=1.5)):
            with self.assertRaises(ValueError, msg=kwargs):
                plan_course(pts, **kwargs)
        with self.assertRaises(TypeError):
            plan_course(pts, 200, 76, unknown=1)

    def test_exported(self):
        for name in ("load_gpx_points", "haversine_m", "course_segments", "plan_course"):
            self.assertTrue(hasattr(pacecalc, name))


class TestPlanCourseExactMultiple(unittest.TestCase):
    def test_no_zero_time_row(self):
        # 回帰（T006R）: 所要 0 秒の区間が計画に出ない
        pts = load_gpx_points(make_rounded_gpx(31, 0.1))
        rows, total = plan_course(pts, 230, 76, segment_km=1.0)
        self.assertEqual(len(rows), 3)
        for row in rows:
            self.assertGreater(row[4], 60.0)
        self.assertAlmostEqual(total, sum(r[4] for r in rows))

    def test_cli_has_no_empty_row(self):
        fd, path = tempfile.mkstemp(suffix=".gpx")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(make_rounded_gpx(31, 0.1))
            code, out, err = run_main(["course", "--gpx", path, "--power", "230",
                                       "--weight", "76"])
        finally:
            os.remove(path)
        self.assertEqual(code, 0, err)
        lines = out.splitlines()
        self.assertEqual(len(lines), 1 + 3 + 1)
        self.assertIn("2-3", lines[3])
        self.assertNotIn("3-3", out)


class TestCourseCli(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".gpx")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(CLIMB_GPX)

    def tearDown(self):
        os.remove(self.path)

    def test_table(self):
        code, out, err = run_main(["course", "--gpx", self.path, "--power", "230",
                                   "--weight", "76"])
        self.assertEqual(code, 0, err)
        lines = out.splitlines()
        self.assertIn("区間(km)", lines[0])
        self.assertIn("勾配(%)", lines[0])
        self.assertIn("速度(km/h)", lines[0])
        self.assertIn("累計", lines[0])
        self.assertEqual(len(lines), 1 + 5 + 1)
        self.assertIn("0-1", lines[1])
        self.assertIn("+5.0", lines[1])
        self.assertIn("4-5", lines[5])
        total = climb_time_sec(5.0, 250, 76, 230)
        expected = pacecalc.format_hms(total)
        self.assertEqual(lines[-1], "総所要時間: %s" % expected)
        self.assertTrue(lines[5].endswith(expected))

    def test_errors(self):
        code, _, err = run_main(["course", "--gpx", self.path + ".missing", "--power", "230",
                                 "--weight", "76"])
        self.assertEqual(code, 2)
        self.assertIn("エラー", err)
        code, _, err = run_main(["course", "--gpx", self.path, "--power", "0", "--weight", "76"])
        self.assertEqual(code, 2)

    def test_subprocess(self):
        result = subprocess.run(
            [sys.executable, "-m", "pacecalc", "course", "--gpx", self.path,
             "--power", "230", "--weight", "76", "--segment", "2.5"],
            cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(result.stdout.splitlines()), 1 + 2 + 1)


if __name__ == "__main__":
    unittest.main()
