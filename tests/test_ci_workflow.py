"""GitHub Actions ワークフロー（.github/workflows/test.yml）の内容を検査するテスト。

標準ライブラリのみを使うため YAML パーサは使わず、必須キーと値が
期待どおりのインデントで記述されているかを行単位で確認する。
"""

import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOW = os.path.join(ROOT, ".github", "workflows", "test.yml")


class TestCIWorkflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(WORKFLOW, encoding="utf-8") as f:
            cls.text = f.read()
        cls.lines = cls.text.splitlines()

    def test_no_tabs(self):
        # YAML ではインデントにタブを使えない
        self.assertNotIn("\t", self.text)

    def test_triggers(self):
        self.assertIn("on:", self.lines)
        self.assertIn("  push:", self.lines)
        self.assertIn("  pull_request:", self.lines)

    def test_runner_and_python(self):
        self.assertIn("jobs:", self.lines)
        self.assertIn("    runs-on: ubuntu-latest", self.lines)
        self.assertIn("        uses: actions/setup-python@v5", self.lines)
        self.assertIn('          python-version: "3.12"', self.lines)

    def test_checkout_and_test_step(self):
        self.assertIn("        uses: actions/checkout@v4", self.lines)
        self.assertIn(
            "        run: python -m unittest discover -s tests", self.lines
        )


if __name__ == "__main__":
    unittest.main()
