"""用學生會打的指令實際解題：每題都要拿到 is1ab{...}，畫面也要放得進 80 欄的終端機。"""

import subprocess
import unicodedata
import unittest

from labctl.labs import build_labs, lab01_check_in
from labctl.plan import guest_hostname
from tests.helpers import scratch_dir

STUDENT = "student01"
TERMINAL_COLUMNS = 80


def columns(line):
    """這一行在終端機上佔幾欄：中文和全形標點佔兩欄。"""
    return sum(2 if unicodedata.east_asian_width(char) in "WF" else 1 for char in line)


def sh(cwd, script):
    return subprocess.run(["bash", "-c", script], cwd=cwd, capture_output=True, text=True)


class WalkthroughCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = scratch_dir() / "lab"
        build_labs(cls.root, b"s" * 32, "linux-2026", STUDENT)

    def assert_solved(self, result, lab):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(lab.FLAG, result.stdout)
        for line in result.stdout.splitlines():
            self.assertLessEqual(columns(line), TERMINAL_COLUMNS, line)


class Lab01Test(WalkthroughCase):
    def test_account_and_hostname_print_the_flag(self):
        result = sh(self.root / lab01_check_in.LAB_ID, f"./check student {guest_hostname(STUDENT)}")
        self.assert_solved(result, lab01_check_in)

    def test_wrong_answer_points_back_to_the_commands(self):
        result = sh(self.root / lab01_check_in.LAB_ID, "./check student wrong-host")
        self.assertEqual(result.returncode, 1)
        self.assertIn("whoami", result.stdout)
        self.assertNotIn("is1ab{", result.stdout)

    def test_missing_arguments_show_usage(self):
        result = sh(self.root / lab01_check_in.LAB_ID, "./check")
        self.assertEqual(result.returncode, 2)
        self.assertIn("用法", result.stdout)


if __name__ == "__main__":
    unittest.main()
