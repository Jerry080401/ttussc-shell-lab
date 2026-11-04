"""答對時和 flag 一起印出的點陣圖。"""

import unittest

from labctl.labs import LABS, art

ART_LABS = [lab.LAB_ID for lab in LABS]


class ArtTest(unittest.TestCase):
    def test_every_lab_has_its_own_picture(self):
        pictures = [art.render(lab_id) for lab_id in ART_LABS]
        self.assertEqual(len(set(pictures)), len(ART_LABS))

    def test_items_are_monochrome_blocks_that_fit_a_terminal(self):
        for name in art.ITEMS:
            lines = art.item(name).rstrip("\n").split("\n")
            self.assertLessEqual(set("".join(lines)), set(" ▀▄█"), name)
            self.assertLessEqual(max(len(line) for line in lines), 30, name)
            self.assertEqual(lines, [line.rstrip() for line in lines], name)

    def test_monochrome_blocks_that_fit_a_terminal(self):
        for lab_id in ART_LABS:
            lines = art.render(lab_id).rstrip("\n").split("\n")
            self.assertTrue(art.render(lab_id).endswith("\n"), lab_id)
            self.assertLessEqual(set("".join(lines)), set(" ▀▄█"), lab_id)
            self.assertLessEqual(max(len(line) for line in lines), 60, lab_id)
            self.assertLessEqual(len(lines), 20, lab_id)
            self.assertEqual(lines, [line.rstrip() for line in lines], lab_id)

    def test_club_spider_is_in_every_picture(self):
        # 左邊都是參考社團 logo 畫的蜘蛛，只有右邊的道具不同。
        spider = art.render_grid(art.SPIDER)
        for lab_id in ART_LABS:
            lines = art.render(lab_id).split("\n")
            for row, spider_row in enumerate(spider):
                self.assertEqual(lines[row][: len(spider_row)], spider_row, (lab_id, row))

    def test_props_are_not_taller_than_the_spider(self):
        # 道具比蜘蛛高的話，頂端會被切掉。
        for lab_id, prop in art.PROPS.items():
            self.assertLessEqual(len(art._rows(prop)), len(art._rows(art.SPIDER)), lab_id)

    def test_prop_sits_on_the_same_baseline_as_the_logo(self):
        # 道具的最後一格要和左邊的圖同一列，最後一行的下半格才會有東西。
        left = max(len(row) for row in art._rows(art.SPIDER)) + art.GAP
        for lab_id in ART_LABS:
            last = art.render(lab_id).rstrip("\n").split("\n")[-1]
            self.assertTrue(set(last[left:]) & set("▄█"), lab_id)


if __name__ == "__main__":
    unittest.main()
