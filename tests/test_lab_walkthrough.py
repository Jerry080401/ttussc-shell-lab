"""用學生會打的指令實際解題：每題都要拿到 flag{...}，畫面也要放得進 80 欄的終端機。"""

import functools
import os
import re
import shlex
import shutil
import subprocess
import unicodedata
import unittest
from pathlib import Path

from labctl.labs import (
    build_labs,
    full_flag,
    lab01_check_in,
    lab02_read_the_manual,
    lab03_paths,
    lab04_hidden_file,
    lab05_organize,
    lab06_find_real_file,
    lab07_archive,
    lab08_grep_log,
    lab09_sort_uniq,
    lab10_signals,
    lab11_chmod,
    lab12_diff_config,
    lab13_git_history,
)
from labctl.plan import guest_hostname
from tests.helpers import scratch_dir

STUDENT = "student01"
TERMINAL_COLUMNS = 80


def columns(line):
    """這一行在終端機上佔幾欄：中文和全形標點佔兩欄。"""
    return sum(2 if unicodedata.east_asian_width(char) in "WF" else 1 for char in line)


def sh(cwd, script):
    return subprocess.run(["bash", "-c", script], cwd=cwd, capture_output=True, text=True)


@functools.cache
def shared_root():
    root = scratch_dir() / "lab"
    build_labs(root, b"s" * 32, "linux-2026", STUDENT)
    return root


class WalkthroughCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 唯讀的題目全部共用一份：第 8 題的 log 有二十萬行，每次重建太慢。
        cls.root = shared_root()

    def assert_solved(self, result, lab):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(full_flag(lab), result.stdout)
        for line in result.stdout.splitlines():
            self.assertLessEqual(columns(line), TERMINAL_COLUMNS, line)


class FlagPrefixTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = scratch_dir() / "lab"
        build_labs(cls.root, b"s" * 32, "linux-2026", STUDENT, flag_prefix="ctf")

    def test_solved_lab_prints_the_custom_prefix(self):
        result = sh(self.root / lab01_check_in.LAB_ID, f"./check student {guest_hostname(STUDENT)}")
        self.assertIn(f"ctf{{{lab01_check_in.FLAG}}}", result.stdout)

    def test_overview_and_decoys_use_the_custom_prefix(self):
        self.assertIn("`ctf{...}`", (self.root / "README.md").read_text(encoding="utf-8"))
        for workspace, target in ((lab06_find_real_file, "storage"), (lab08_grep_log, "service.log")):
            directory = self.root / workspace.LAB_ID
            self.assertEqual(sh(directory, f"grep -rlF 'flag{{' {target} | wc -l").stdout.strip(), "0")
            self.assertNotEqual(sh(directory, f"grep -rlF 'ctf{{' {target} | wc -l").stdout.strip(), "0")


class Lab01Test(WalkthroughCase):
    def test_account_and_hostname_print_the_flag(self):
        result = sh(self.root / lab01_check_in.LAB_ID, f"./check student {guest_hostname(STUDENT)}")
        self.assert_solved(result, lab01_check_in)

    def test_wrong_answer_points_back_to_the_commands(self):
        result = sh(self.root / lab01_check_in.LAB_ID, "./check student wrong-host")
        self.assertEqual(result.returncode, 1)
        self.assertIn("whoami", result.stdout)
        self.assertNotIn("flag{", result.stdout)

    def test_missing_arguments_show_usage(self):
        result = sh(self.root / lab01_check_in.LAB_ID, "./check")
        self.assertEqual(result.returncode, 2)
        self.assertIn("用法", result.stdout)


class Lab02Test(WalkthroughCase):
    def line_from_manual(self):
        workspace = self.root / lab02_read_the_manual.LAB_ID
        if shutil.which("man"):
            manual = sh(workspace, "man ./phone.1").stdout
        else:
            manual = (workspace / "phone.1").read_text(encoding="utf-8")
        return re.search(r"朋友的線路：第 (\d+) 號", manual).group(1)

    def test_help_points_to_the_manual(self):
        result = sh(self.root / lab02_read_the_manual.LAB_ID, "./phone --help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("man ./phone.1", result.stdout)

    def test_line_from_the_manual_prints_the_flag_with_short_and_long_options(self):
        line = self.line_from_manual()
        for options in (f"-l {line} -d", f"--line {line} --decode", f"-dl{line}"):
            result = sh(self.root / lab02_read_the_manual.LAB_ID, f"./phone {options}")
            self.assert_solved(result, lab02_read_the_manual)

    def test_other_lines_in_the_manual_each_have_their_own_message(self):
        workspace = self.root / lab02_read_the_manual.LAB_ID
        text = (workspace / "phone.1").read_text(encoding="utf-8")
        table = dict(re.findall(r"(\S+的線路)：第 (\d+) 號", text))
        self.assertEqual(len(table), 5)
        self.assertNotIn("風聲", text)  # 接了才知道
        del table["朋友的線路"]
        messages = {sh(workspace, f"./phone -l {number} -d").stdout for number in table.values()}
        self.assertEqual(len(messages), 4)
        for message in messages:
            self.assertNotIn("flag{", message)
            self.assertLessEqual(columns(message.strip()), TERMINAL_COLUMNS, message)
        self.assertIn("沒有人接", sh(workspace, "./phone -l 1 -d").stdout)

    def test_each_wrong_step_says_what_to_do_next(self):
        workspace = self.root / lab02_read_the_manual.LAB_ID
        line = self.line_from_manual()
        self.assertIn("--help", sh(workspace, "./phone").stdout)
        self.assertIn("-d", sh(workspace, f"./phone -l {line}").stdout)
        self.assertIn("man ./phone.1", sh(workspace, "./phone -l 1 -d").stdout)


class Lab03Test(WalkthroughCase):
    def workspace(self):
        return self.root / lab03_paths.LAB_ID

    def mailbox(self):
        return self.workspace() / "forest/big-tree/hole/mailbox"

    def test_absolute_path_from_the_post_office_prints_the_flag(self):
        self.assert_solved(sh(self.workspace() / "post-office", f"pwd && {self.mailbox()}"), lab03_paths)

    def test_relative_path_is_refused_even_from_the_post_office(self):
        result = sh(self.workspace() / "post-office", "../forest/big-tree/hole/mailbox")
        self.assertEqual(result.returncode, 1)
        self.assertIn("絕對路徑", result.stdout)
        self.assertNotIn("flag{", result.stdout)

    def test_absolute_path_from_elsewhere_says_to_go_to_the_post_office(self):
        result = sh(self.mailbox().parent, str(self.mailbox()))
        self.assertEqual(result.returncode, 1)
        self.assertIn("post-office", result.stdout)
        self.assertNotIn("flag{", result.stdout)


class Lab04Test(WalkthroughCase):
    def test_plain_ls_shows_no_note_and_ls_a_finds_exactly_one(self):
        workspace = self.root / lab04_hidden_file.LAB_ID
        self.assertEqual(sh(workspace, "ls *-tree/branch | grep -c note").stdout.strip(), "0")
        notes = list(workspace.rglob(".note"))
        self.assertEqual(len(notes), 1)
        self.assertIn(".note", sh(notes[0].parent, "ls -a").stdout)
        self.assert_solved(sh(notes[0].parent, "cat .note"), lab04_hidden_file)


class Lab05Test(WalkthroughCase):
    def fresh_workspace(self):
        root = scratch_dir() / "lab"
        build_labs(root, b"s" * 32, "linux-2026", "student05")
        return root / lab05_organize.LAB_ID

    def test_the_readme_commands_print_the_flag(self):
        workspace = self.fresh_workspace()
        script = "mkdir box && mv nest/*.silk box && rm nest/*.leaf && cp map.txt map.bak && ./check"
        self.assert_solved(sh(workspace, script), lab05_organize)

    def test_check_names_what_is_left_to_do(self):
        result = sh(self.fresh_workspace(), "./check")
        self.assertEqual(result.returncode, 1)
        for hint in ("mkdir", "束絲線沒搬", ".leaf", "map.bak"):
            self.assertIn(hint, result.stdout)
        self.assertNotIn("flag{", result.stdout)

    def guarded(self, workspace, script):
        """像學生的 shell 一樣裝好 rm 的保護，在這題的資料夾執行。"""
        setup = lab05_organize.RM_GUARD + f"HOME={shlex.quote(str(workspace.parent.parent))}\n"
        return subprocess.run(["bash", "-c", setup + script], cwd=workspace, capture_output=True, text=True)

    def test_rm_refuses_things_to_keep_and_says_why(self):
        workspace = self.fresh_workspace()
        before = sorted(path.name for path in (workspace / "nest").iterdir())
        for target, reason in (
            ("nest/*.silk", "絲"),
            ("nest/*.water", "露水"),
            ("map.txt", "地圖"),
            ("nest/*", "不能刪"),
            ("-r nest", "絲線或露水"),
            ("-rf .", "絲線或露水"),
            ("-rf ~/lab", "整個巢穴"),
        ):
            result = self.guarded(workspace, f"rm {target}")
            self.assertEqual(result.returncode, 1, target)
            self.assertIn(reason, result.stderr, target)
            self.assertIn("什麼都沒有刪", result.stderr, target)
            for line in result.stderr.splitlines():
                self.assertLessEqual(columns(line), TERMINAL_COLUMNS, target)
        self.assertEqual(sorted(path.name for path in (workspace / "nest").iterdir()), before)
        self.assertTrue((workspace / "map.txt").exists())

    def test_rm_still_deletes_the_leaves_and_other_files(self):
        workspace = self.fresh_workspace()
        script = "mkdir box && mv nest/*.silk box && rm nest/*.leaf && cp map.txt map.bak && ./check"
        self.assert_solved(self.guarded(workspace, script), lab05_organize)
        self.assertEqual(self.guarded(workspace, "mkdir empty && rm -r empty && rm map.bak").returncode, 0)
        self.assertFalse((workspace / "map.bak").exists())

    def test_rm_outside_this_lab_is_not_touched(self):
        workspace = self.fresh_workspace()
        other = scratch_dir()
        (other / "red.silk").write_text("not the lab\n")
        self.assertEqual(self.guarded(workspace, f"rm {other}/red.silk").returncode, 0)
        self.assertFalse((other / "red.silk").exists())

    def test_box_inside_nest_does_not_duplicate_the_silk(self):
        workspace = self.fresh_workspace()
        result = sh(workspace, "mkdir nest/box && mv nest/*.silk nest/box && ./check")
        self.assertIn("box 建到 nest 裡面", result.stdout)
        self.assertNotIn("不能丟", result.stdout)
        self.assertEqual(list((workspace / "nest").glob("*.silk")), [])

    def test_deleted_silk_and_water_come_back_with_a_warning(self):
        workspace = self.fresh_workspace()
        before = {path.name: path.read_bytes() for path in (workspace / "nest").iterdir() if path.suffix != ".leaf"}
        result = sh(workspace, "rm -f nest/*.silk nest/*.water; ./check")
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("flag{", result.stdout)
        after = {path.name: path.read_bytes() for path in (workspace / "nest").iterdir()}
        self.assertEqual({name: after.get(name) for name in before}, before)

    def test_can_still_finish_after_deleting_everything(self):
        workspace = self.fresh_workspace()
        sh(workspace, "rm -f nest/* map.txt; ./check")
        script = "mkdir box && mv nest/*.silk box && cp map.txt map.bak && ./check"
        self.assert_solved(sh(workspace, script), lab05_organize)


class Lab06Test(WalkthroughCase):
    def test_find_with_both_conditions_finds_exactly_the_real_item(self):
        workspace = self.root / lab06_find_real_file.LAB_ID
        size = re.search(r"檔案大小 (\d+) 位元組", (workspace / "README.md").read_text(encoding="utf-8")).group(1)
        found = sh(workspace, f"find storage -name '*.silk' -size {size}c").stdout.split()
        self.assertEqual(len(found), 1)
        result = sh(workspace, f"cat {found[0]}")
        self.assert_solved(result, lab06_find_real_file)
        self.assertEqual(int(size), Path(workspace / found[0]).stat().st_size)

    def test_one_condition_alone_is_not_enough(self):
        workspace = self.root / lab06_find_real_file.LAB_ID
        size = re.search(r"檔案大小 (\d+) 位元組", (workspace / "README.md").read_text(encoding="utf-8")).group(1)
        self.assertGreater(len(sh(workspace, "find storage -name '*.silk'").stdout.split()), 1)
        self.assertGreater(len(sh(workspace, f"find storage -size {size}c").stdout.split()), 1)


class DecoyTest(WalkthroughCase):
    SENTENCE = "flag{[a-z0-9]*_[a-z0-9_]*}"

    def test_decoys_in_lab_06_look_like_real_flags(self):
        workspace = self.root / lab06_find_real_file.LAB_ID
        flags = set(sh(workspace, f"grep -rhoE '{self.SENTENCE}' storage").stdout.split())
        self.assertGreater(len(flags), 5)
        self.assertIn(full_flag(lab06_find_real_file), flags)

    def test_decoys_in_lab_08_look_like_real_flags(self):
        workspace = self.root / lab08_grep_log.LAB_ID
        self.assertGreater(int(sh(workspace, f"grep -cE '{self.SENTENCE}' service.log").stdout), 1000)
        self.assertEqual(sh(workspace, "grep -cE 'flag[{][0-9a-f]{16}[}]' service.log").stdout.strip(), "0")


class Lab07Test(WalkthroughCase):
    def test_unwrapping_layer_by_layer_prints_the_flag(self):
        workspace = scratch_dir()
        shutil.copy(self.root / lab07_archive.LAB_ID / "package.bin", workspace)
        self.assertIn("gzip", sh(workspace, "file package.bin").stdout)
        self.assertEqual(sh(workspace, "tar xzf package.bin").returncode, 0)
        self.assertIn("inner.gz", sh(workspace / "package", "cat card.txt").stdout)
        self.assertIn("gzip", sh(workspace / "package", "file inner.gz").stdout)
        self.assert_solved(sh(workspace / "package", "gunzip inner.gz && cat inner"), lab07_archive)

    def test_flag_is_not_readable_without_unwrapping(self):
        workspace = self.root / lab07_archive.LAB_ID
        self.assertNotIn(b"flag{", (workspace / "package.bin").read_bytes())


class Lab08Test(WalkthroughCase):
    def test_check_confirms_the_real_flag_with_a_picture(self):
        workspace = self.root / lab08_grep_log.LAB_ID
        result = sh(workspace, f"./check {full_flag(lab08_grep_log)}")
        self.assert_solved(result, lab08_grep_log)
        self.assertRegex(result.stdout, "[▀▄█]")

    def test_check_refuses_a_decoy_and_the_log_has_no_picture(self):
        workspace = self.root / lab08_grep_log.LAB_ID
        decoy = sh(workspace, f"grep -m1 -o 'note=flag.*' service.log | grep -v {lab08_grep_log.FLAG}").stdout
        result = sh(workspace, f"./check {decoy.strip().removeprefix('note=')}")
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("答對", result.stdout)
        self.assertEqual(sh(workspace, "grep -c '█' service.log").stdout.strip(), "0")

    def test_two_greps_with_a_pipe_find_exactly_one_line(self):
        workspace = self.root / lab08_grep_log.LAB_ID
        lines = sh(workspace, "grep user=xiaoyi service.log | grep result=success").stdout.splitlines()
        self.assertEqual(len(lines), 1)
        self.assertIn(lab08_grep_log.FLAG, lines[0])

    def test_one_grep_alone_is_not_enough(self):
        workspace = self.root / lab08_grep_log.LAB_ID
        self.assertGreater(int(sh(workspace, "grep -c user=xiaoyi service.log").stdout), 1)
        self.assertGreater(int(sh(workspace, "grep -c result=success service.log").stdout), 1)


class Lab09Test(WalkthroughCase):
    PIPELINE = "tail -n +2 fixes.csv | cut -d, -f2 | sort | uniq -c | sort -nr"

    def test_counting_with_the_pipeline_names_the_winner(self):
        workspace = self.root / lab09_sort_uniq.LAB_ID
        counts = sh(workspace, self.PIPELINE).stdout.split("\n")
        winner = counts[0].split()[1]
        self.assertNotEqual(counts[0].split()[0], counts[1].split()[0])  # 第一名不會同分
        self.assert_solved(sh(workspace, f"./check {winner}"), lab09_sort_uniq)

    def test_a_runner_up_is_refused(self):
        workspace = self.root / lab09_sort_uniq.LAB_ID
        runner_up = sh(workspace, self.PIPELINE).stdout.split("\n")[1].split()[1]
        result = sh(workspace, f"./check {runner_up}")
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("flag{", result.stdout)
        for line in result.stdout.splitlines():
            self.assertLessEqual(columns(line), TERMINAL_COLUMNS, line)


class Lab10Test(WalkthroughCase):
    def run_in_background(self, signal_name):
        return sh(
            self.root / lab10_signals.LAB_ID,
            f"./sleepy & pid=$!; sleep 1; ps -o comm= -p $pid; kill -{signal_name} $pid; wait $pid",
        )

    def test_usr1_from_the_background_prints_the_flag(self):
        result = self.run_in_background("USR1")
        self.assert_solved(result, lab10_signals)
        self.assertIn("sleepy", result.stdout)  # ps 看得到 sleepy，不是 python3

    def test_other_signals_explain_what_to_send_instead(self):
        for signal_name in ("TERM", "INT"):
            result = self.run_in_background(signal_name)
            self.assertNotIn("flag{", result.stdout, signal_name)
            self.assertIn("USR1", result.stdout, signal_name)
            for line in result.stdout.splitlines():
                self.assertLessEqual(columns(line), TERMINAL_COLUMNS, line)


class Lab11Test(WalkthroughCase):
    def fresh_workspace(self):
        workspace = scratch_dir()
        source = self.root / lab11_chmod.LAB_ID / "locked.txt"
        source.chmod(0o400)
        shutil.copy(source, workspace / "locked.txt")
        source.chmod(0o000)
        (workspace / "locked.txt").chmod(0o000)
        return workspace

    def test_ls_shows_no_permission_and_chmod_opens_it(self):
        workspace = self.fresh_workspace()
        self.assertTrue(sh(workspace, "ls -l locked.txt").stdout.startswith("----------"))
        if os.geteuid() != 0:  # root 不受檔案權限限制
            self.assertNotEqual(sh(workspace, "cat locked.txt").returncode, 0)
        self.assert_solved(sh(workspace, "chmod u+r locked.txt && cat locked.txt"), lab11_chmod)


class Lab12Test(WalkthroughCase):
    def fresh_workspace(self):
        workspace = scratch_dir() / "lab12"
        shutil.copytree(self.root / lab12_diff_config.LAB_ID, workspace)
        return workspace

    def test_diff_shows_three_wrong_lines_and_check_refuses_until_fixed(self):
        workspace = self.fresh_workspace()
        diff = sh(workspace, "diff web.conf expected.conf")
        self.assertEqual(diff.returncode, 1)
        self.assertEqual(len([line for line in diff.stdout.splitlines() if line.startswith("<")]), 3)
        result = sh(workspace, "./check")
        self.assertEqual(result.returncode, 1)
        self.assertIn("diff", result.stdout)
        self.assertNotIn("flag{", result.stdout)

    def test_fixing_each_line_from_the_diff_prints_the_flag(self):
        workspace = self.fresh_workspace()
        for line in sh(workspace, "diff web.conf expected.conf").stdout.splitlines():
            if line.startswith(">"):
                key = line[2:].split(" = ")[0]
                sh(workspace, f"sed -i 's/^{key} = .*/{line[2:]}/' web.conf")
        self.assert_solved(sh(workspace, "./check"), lab12_diff_config)


class Lab13Test(WalkthroughCase):
    def repo(self):
        return self.root / lab13_git_history.LAB_ID / "notes"

    def test_git_show_before_the_delete_prints_the_flag(self):
        log = sh(self.repo(), "git log --oneline").stdout
        self.assertIn("記下點心櫃密碼", log)
        commit = next(line.split()[0] for line in log.splitlines() if "記下點心櫃密碼" in line)
        self.assert_solved(sh(self.repo(), f"git show {commit}"), lab13_git_history)

    def test_password_is_deleted_and_flag_stays_out_of_plain_grep(self):
        self.assertFalse((self.repo() / "password.txt").exists())
        self.assertEqual(sh(self.repo(), "grep -ra 'flag{' .").stdout, "")


if __name__ == "__main__":
    unittest.main()
