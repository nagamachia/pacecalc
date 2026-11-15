"""パッケージング（pyproject.toml・バージョン・型ヒント・README・CHANGELOG）を検査するテスト。"""

import contextlib
import importlib
import io
import os
import typing
import unittest

import pacecalc
from pacecalc import cli

try:
    import tomllib
except ImportError:  # Python 3.10 には tomllib がない
    tomllib = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        return f.read()


@unittest.skipIf(tomllib is None, "tomllib がない（Python 3.11 未満）")
class TestPyproject(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(ROOT, "pyproject.toml"), "rb") as f:
            cls.data = tomllib.load(f)

    def test_build_backend(self):
        self.assertEqual(self.data["build-system"]["build-backend"], "setuptools.build_meta")
        self.assertTrue(any(r.startswith("setuptools") for r in self.data["build-system"]["requires"]))

    def test_metadata(self):
        project = self.data["project"]
        self.assertEqual(project["name"], "pacecalc")
        self.assertEqual(project["version"], "1.0.0")
        self.assertEqual(project["requires-python"], ">=3.10")
        self.assertEqual(project["readme"], "README.md")
        self.assertEqual(project.get("dependencies", []), [])
        # description は英語 1 行
        description = project["description"]
        self.assertNotIn("\n", description)
        self.assertTrue(description.isascii())

    def test_console_script(self):
        target = self.data["project"]["scripts"]["pacecalc"]
        self.assertEqual(target, "pacecalc.cli:main")
        module_name, func_name = target.split(":")
        func = getattr(importlib.import_module(module_name), func_name)
        self.assertTrue(callable(func))

    def test_version_matches_package(self):
        self.assertEqual(self.data["project"]["version"], pacecalc.__version__)


class TestVersion(unittest.TestCase):
    def test_version(self):
        self.assertEqual(pacecalc.__version__, "1.0.0")

    def test_public_api_kept(self):
        for name in ["speed_to_pace_sec", "pace_to_speed_kmh", "format_pace", "format_hms",
                     "finish_time_sec", "riegel_predict_sec", "split_table", "climb_time_sec",
                     "required_power_w", "load_gpx_points", "haversine_m", "course_segments",
                     "plan_course"]:
            self.assertIn(name, pacecalc.__all__)
            self.assertTrue(callable(getattr(pacecalc, name)))

    def test_console_entry_returns_exit_code(self):
        # コンソールスクリプトは sys.exit(main()) で呼ばれるため、終了コードを返すこと
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(cli.main(["pace", "--speed", "12"]), 0)
        self.assertEqual(out.getvalue(), "5:00 /km\n")


class TestTypeHints(unittest.TestCase):
    PUBLIC = ["speed_to_pace_sec", "pace_to_speed_kmh", "format_pace", "format_hms",
              "finish_time_sec", "riegel_predict_sec", "split_table", "climb_time_sec",
              "required_power_w", "load_gpx_points", "haversine_m", "course_segments",
              "plan_course"]

    def test_all_params_and_return_annotated(self):
        import inspect
        for name in self.PUBLIC:
            func = getattr(pacecalc, name)
            hints = typing.get_type_hints(func)
            params = inspect.signature(func).parameters
            with self.subTest(name=name):
                self.assertIn("return", hints)
                for param in params:
                    self.assertIn(param, hints)

    def test_some_hints(self):
        self.assertIs(typing.get_type_hints(pacecalc.format_pace)["return"], str)
        self.assertIs(typing.get_type_hints(pacecalc.speed_to_pace_sec)["speed_kmh"], float)


class TestDocs(unittest.TestCase):
    def test_readme_badge_at_top(self):
        lines = [line for line in _read("README.md").splitlines() if line.strip()]
        self.assertEqual(lines[0], "# pacecalc")
        self.assertIn(
            "https://github.com/nagamachia/pacecalc/actions/workflows/test.yml/badge.svg", lines[1])

    def test_readme_install(self):
        readme = _read("README.md")
        self.assertIn("## インストール", readme)
        self.assertIn("git clone https://github.com/nagamachia/pacecalc.git", readme)
        self.assertIn("pip install .", readme)
        self.assertIn("pip install git+https://github.com/nagamachia/pacecalc", readme)

    def test_changelog(self):
        changelog = _read("CHANGELOG.md")
        self.assertIn("## [1.0.0]", changelog)
        for task in ["T001", "T002", "T003", "T004", "T005", "T006", "T006R"]:
            self.assertIn(task, changelog)


if __name__ == "__main__":
    unittest.main()
