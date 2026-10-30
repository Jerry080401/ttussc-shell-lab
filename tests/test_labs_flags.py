import unittest

from labctl.labs.flags import derive_seed

SECRET = b"k" * 32


class SeedTest(unittest.TestCase):
    """每位學生的題目資料由老師的金鑰推導。flag 是每題固定的一句話（見各題的 FLAG）。"""

    def test_same_inputs_give_same_seed(self):
        # 「恢復原題」要得到一模一樣的資料。
        self.assertEqual(
            derive_seed(SECRET, "linux-2026", "student01", "01-check-in"),
            derive_seed(SECRET, "linux-2026", "student01", "01-check-in"),
        )

    def test_each_student_lab_and_round_differs(self):
        seeds = {
            derive_seed(SECRET, "linux-2026", s, lab, round_)
            for s in ("student01", "student02")
            for lab in ("01-check-in", "02-read-the-manual")
            for round_ in (1, 2)
        }
        self.assertEqual(len(seeds), 8)

    def test_different_secret_changes_seed(self):
        self.assertNotEqual(
            derive_seed(SECRET, "linux-2026", "student01", "01-check-in"),
            derive_seed(b"z" * 32, "linux-2026", "student01", "01-check-in"),
        )

    def test_short_secret_rejected(self):
        with self.assertRaises(ValueError):
            derive_seed(b"short", "linux-2026", "student01", "01-check-in")


if __name__ == "__main__":
    unittest.main()
