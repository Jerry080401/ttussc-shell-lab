"""Lab catalog and build properties. Solving each lab is tested in tests/private/ (not published)."""

import re
import subprocess
import unittest

from labctl.labs import LABS, build_labs
from tests.helpers import scratch_dir

SECRET = b"s" * 32
COHORT = "linux-2026"
FLAG_RE = re.compile(r"TTUSSC\{[^}\s]*\}")
# 真的 flag 是每題固定的一句話（全班相同），假的 flag 是 16 位十六進位的亂碼。
SENTENCE_RE = re.compile(r"^TTUSSC\{[a-z0-9]+(?:_[a-z0-9]+)+\}$")
FAKE_RE = re.compile(r"^TTUSSC\{[0-9a-f]{16}\}$")


def new_root():
    return scratch_dir() / "lab"


def build(student="student01"):
    root = new_root()
    return root, build_labs(root, SECRET, COHORT, student)


def sh(cwd, script, env=None):
    return subprocess.run(["bash", "-c", script], cwd=cwd, capture_output=True, text=True, env=env)


def snapshot(root):
    """Relative path -> (mode, bytes) for every file and directory under root."""
    out = {}
    for path in sorted(root.rglob("*")):
        if path.name == "index" and path.parent.name == ".git":
            continue  # git 的 stat 快取（含 inode、ctime），本來就每次不同
        mode = path.lstat().st_mode & 0o7777
        if path.is_dir():
            out[str(path.relative_to(root))] = (mode, None)
        else:
            path.chmod(mode | 0o400)
            out[str(path.relative_to(root))] = (mode, path.read_bytes())
            path.chmod(mode)
    return out


def plaintext_flags(workspace):
    """Flags readable with plain grep (ignores .git internals)."""
    result = sh(workspace, "grep -rhoI --exclude-dir=.git 'TTUSSC{[0-9a-z_]*}' . || true")
    return set(result.stdout.split())


class CatalogTest(unittest.TestCase):
    def test_labs_numbered_in_class_order(self):
        # 題號就是上課做的順序：基本指令×2、路徑、檔案操作×4、管線、資料處理、行程、權限、加分×2。
        self.assertEqual(
            [lab.LAB_ID for lab in LABS],
            [
                "01-check-in",
                "02-read-the-manual",
                "03-paths",
                "04-hidden-file",
                "05-organize",
                "06-find-real-file",
                "07-archive",
                "08-grep-log",
                "09-sort-uniq",
                "10-signals",
                "11-chmod",
                "12-diff-config",
                "13-git-history",
            ],
        )

    def test_readme_heading_matches_number_and_title(self):
        root, _ = build()
        for lab in LABS:
            first = (root / lab.LAB_ID / "README.md").read_text(encoding="utf-8").splitlines()[0]
            self.assertEqual(first, f"# {lab.LAB_ID[:2]} {lab.TITLE}")

    def test_flags_are_one_sentence_per_lab_for_everyone(self):
        _, first = build("student01")
        _, second = build("student02")
        self.assertEqual(first, {lab.LAB_ID: lab.FLAG for lab in LABS})
        self.assertEqual(second, first)
        self.assertEqual(len(set(first.values())), len(LABS))
        for lab_id, flag in first.items():
            self.assertRegex(flag, SENTENCE_RE, lab_id)

    def test_every_lab_has_instructions_and_overview_lists_them(self):
        root, _ = build()
        overview = (root / "README.md").read_text(encoding="utf-8")
        for lab in LABS:
            self.assertIn(lab.LAB_ID, overview)
            self.assertIn(lab.TITLE, overview)
            self.assertGreater(len((root / lab.LAB_ID / "README.md").read_text(encoding="utf-8")), 50)

    def test_rebuild_is_byte_identical(self):
        # 「恢復原題」必須得到一模一樣的資料。
        first, _ = build()
        second, _ = build()
        self.assertEqual(snapshot(first), snapshot(second))

    def test_other_student_gets_other_data(self):
        first, _ = build("student01")
        second, _ = build("student02")
        self.assertNotEqual(snapshot(first), snapshot(second))

    def test_says_flag_not_the_old_word(self):
        # 統一叫 flag，不用「暗號」。
        root, _ = build()
        for path in root.rglob("*"):
            if path.is_file() and ".git" not in path.parts:
                path.chmod(path.stat().st_mode | 0o400)
                self.assertNotIn("暗號".encode(), path.read_bytes(), path)

    def test_refuses_to_overwrite_existing_work(self):
        root = new_root()
        root.mkdir()
        (root / "my-notes.txt").write_text("學生自己的筆記")
        with self.assertRaises(ValueError):
            build_labs(root, SECRET, COHORT, "student01")
        self.assertEqual((root / "my-notes.txt").read_text(), "學生自己的筆記")


if __name__ == "__main__":
    unittest.main()
