"""答對時和 flag 一起印出的點陣圖。"""

import unittest

from labctl.labs import LABS, art

# Lab 08 的 flag 寫在 log 的某一行，多行的圖放不進去，所以這題沒有圖。
ART_LABS = [lab.LAB_ID for lab in LABS if lab.LAB_ID != "08-grep-log"]


class ArtTest(unittest.TestCase):
    def test_every_lab_but_08_has_its_own_picture(self):
        pictures = [art.render(lab_id) for lab_id in ART_LABS]
        self.assertEqual(len(set(pictures)), len(ART_LABS))
        with self.assertRaises(KeyError):
            art.render("08-grep-log")

    def test_monochrome_blocks_that_fit_a_terminal(self):
        for lab_id in ART_LABS:
            lines = art.render(lab_id).rstrip("\n").split("\n")
            self.assertTrue(art.render(lab_id).endswith("\n"), lab_id)
            self.assertLessEqual(set("".join(lines)), set(" ▀▄█"), lab_id)
            self.assertLessEqual(max(len(line) for line in lines), 60, lab_id)
            self.assertLessEqual(len(lines), 20, lab_id)
            self.assertEqual(lines, [line.rstrip() for line in lines], lab_id)

    def test_club_penguin_is_in_every_picture(self):
        # 左邊都是 TTUSSC logo 的牛仔帽企鵝，只有右邊的道具不同。
        penguin = art.render_grid(art.PENGUIN)
        for lab_id in ART_LABS:
            lines = art.render(lab_id).split("\n")
            for row, penguin_row in enumerate(penguin):
                self.assertEqual(lines[row][: len(penguin_row)], penguin_row, (lab_id, row))


if __name__ == "__main__":
    unittest.main()
