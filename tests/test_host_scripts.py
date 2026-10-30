"""host/ scripts run against a fake `incus`, to check the `all` loops and that secrets only travel on stdin."""

import os
import subprocess
import unittest

from tests.helpers import REPO, SECRET_HEX, scratch_dir, write_env

# 和真的 incus exec 一樣會把 stdin 讀完，只記下開頭。迴圈裡哪一步沒有接好 stdin，後面的學生就會被吃掉。
FAKE_INCUS = r"""#!/bin/bash
[ "$1" = exec ] || { echo "$*" >>"$FAKE_LOG"; exit 0; }
name=$2
shift 2
while [ "$1" != -- ]; do shift; done
shift
stdin=$(mktemp)
cat >"$stdin"
input=$(head -c 300 "$stdin" | tr '\0' '.')
rm -f "$stdin"
printf 'exec %s | %s | %s\n' "$name" "$*" "${input//$'\n'/\\n}" >>"$FAKE_LOG"
[ "$name" = "$FAKE_FAIL" ] && exit 1
if [ "$*" = "bash -s" ]; then echo "100.92.0.${name: -2}"; fi
exit 0
"""


class HostScriptTest(unittest.TestCase):
    def setUp(self):
        self.dir = scratch_dir()
        bin_dir = self.dir / "bin"
        bin_dir.mkdir()
        (bin_dir / "incus").write_text(FAKE_INCUS)
        (bin_dir / "incus").chmod(0o755)
        self.log = self.dir / "incus.log"
        self.env = {
            **os.environ,
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "LAB_DIR": str(REPO),
            "LAB_ENV": str(write_env(STUDENT_COUNT="3", LAB_SECRET=SECRET_HEX)),
            "FAKE_LOG": str(self.log),
            "FAKE_FAIL": "",
        }

    def run_script(self, name, *args, stdin="", fail=""):
        env = {**self.env, "FAKE_FAIL": fail}
        return subprocess.run(
            ["bash", str(REPO / "host" / name), *args], input=stdin, env=env, capture_output=True, text=True
        )

    def calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def test_set_password_all_reaches_every_student_through_stdin(self):
        lines = "student01 pass-one-aaaa\nstudent02 pass-two-bbbb\nstudent03 pass-three-cc\n"
        result = self.run_script("set-password.sh", "all", stdin=lines)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.calls(),
            [
                "exec linux-2026-student01 | chpasswd | student:pass-one-aaaa",
                "exec linux-2026-student02 | chpasswd | student:pass-two-bbbb",
                "exec linux-2026-student03 | chpasswd | student:pass-three-cc",
            ],
        )

    def test_one_failure_does_not_stop_the_others(self):
        lines = "student01 pass-one-aaaa\nstudent02 pass-two-bbbb\nstudent03 pass-three-cc\n"
        result = self.run_script("set-password.sh", "all", stdin=lines, fail="linux-2026-student02")
        self.assertEqual(result.returncode, 1)
        self.assertIn("student02", result.stderr)
        self.assertEqual(len(self.calls()), 3)
        self.assertIn("linux-2026-student03: password set", result.stdout)

    def test_enroll_all_prints_one_ip_per_student(self):
        keys = "".join(f"student0{n} 0000000{n}-0000-4000-8000-000000000000\n" for n in (1, 2, 3))
        result = self.run_script("enroll-netbird.sh", "all", stdin=keys)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "student01 100.92.0.01\nstudent02 100.92.0.02\nstudent03 100.92.0.03\n")
        key_writes = [c for c in self.calls() if "cat > /run/netbird-setup-key |" in c]
        self.assertEqual(len(key_writes), 3)
        for n, call in enumerate(key_writes, 1):
            # key 只在 stdin（最後一欄），不在指令參數裡。
            argv, stdin = call.rsplit(" | ", 1)
            self.assertEqual(stdin, f"0000000{n}-0000-4000-8000-000000000000")
            self.assertNotIn("0000-4000-8000", argv)

    def test_enroll_without_key_skips_writing_one(self):
        result = self.run_script("enroll-netbird.sh", "student02", stdin="")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "student02 100.92.0.02\n")
        self.assertFalse([c for c in self.calls() if "cat > /run/netbird-setup-key |" in c])

    @unittest.skipUnless(os.geteuid() == 0, "the host side reads lab files only root can read (lab 11 is mode 000)")
    def test_labs_are_unpacked_as_the_student(self):
        # 用學生的身分解開，學生在 ~/lab 裡放的連結就指不到系統檔案。
        result = self.run_script("seed-labs.sh", "student01")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("linux-2026-student01: seeded", result.stdout)
        self.assertTrue([c for c in self.calls() if "| runuser -u student -- sh -c mkdir -p /home/student/lab" in c])

    def test_one_lab_can_be_reset_and_the_old_copy_kept(self):
        result = self.run_script("seed-labs.sh", "student02", "05-organize")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("reset 05-organize, the old copy is ~/lab/.05-organize.old-", result.stdout)
        resets = [c for c in self.calls() if "runuser -u student -- sh -c cd /home/student/lab" in c]
        self.assertEqual(len(resets), 1)
        self.assertIn(" sh 05-organize .05-organize.old-", resets[0])

    def test_bad_lab_names_are_refused_before_touching_the_vm(self):
        for lab in ("../etc", "05-organize;id", "99-no-such-lab"):
            result = self.run_script("seed-labs.sh", "student02", lab)
            self.assertNotEqual(result.returncode, 0, lab)
        self.assertEqual(self.calls(), [])

    def test_unknown_student_is_refused(self):
        result = self.run_script("set-password.sh", "student09", stdin="pass-word-xyz\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls(), [])


if __name__ == "__main__":
    unittest.main()
