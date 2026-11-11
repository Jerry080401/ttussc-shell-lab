"""deploy/pve/shell-lab-setup.sh against a fake `pct`, to check the loops and that secrets only travel on stdin."""

import os
import subprocess
import unittest

from tests.helpers import REPO, SECRET_HEX, scratch_dir

SCRIPT = REPO / "deploy" / "pve" / "shell-lab-setup.sh"

# 容器 CTID 201 起，主機名稱 lab-studentNN。FAKE_CTS 列出存在的 CTID，FAKE_OTHER 是主機名稱不符的。
# exec 和真的 pct exec 一樣會把 stdin 讀完，只記下開頭；迴圈裡哪一步沒接好 stdin，後面的學生就會被吃掉。
FAKE_PCT = r"""#!/bin/bash
cmd=$1 id=$2
case $cmd in
status)
    [[ " $FAKE_CTS " == *" $id "* ]] || exit 2
    echo "status: running" ;;
config)
    if [ "$id" = "$FAKE_OTHER" ]; then echo "hostname: someone-else"; exit 0; fi
    printf 'hostname: lab-student%02d\n' $((id - 200)) ;;
exec)
    shift 2
    [ "$1" = -- ] && shift
    stdin=$(mktemp)
    cat >"$stdin"
    input=$(head -c 300 "$stdin" | tr '\0' '.')
    rm -f "$stdin"
    printf 'exec %s | %s | %s\n' "$id" "$*" "${input//$'\n'/\\n}" >>"$FAKE_LOG"
    [ "$id" = "$FAKE_FAIL" ] && exit 1 ;;
*)
    echo "$*" >>"$FAKE_LOG" ;;
esac
exit 0
"""

FAKE_ID = """#!/bin/sh
[ "$1" = -u ] && { echo 0; exit 0; }
exec /usr/bin/id "$@"
"""


class PveScriptTest(unittest.TestCase):
    def setUp(self):
        self.dir = scratch_dir()
        bin_dir = self.dir / "bin"
        bin_dir.mkdir()
        for name, text in (("pct", FAKE_PCT), ("id", FAKE_ID)):
            (bin_dir / name).write_text(text)
            (bin_dir / name).chmod(0o755)
        env_file = self.dir / "shell-lab.env"
        env_file.write_text(f"STUDENT_COUNT=3\nLAB_SECRET={SECRET_HEX}\nPORTFORWARD_SOURCES=192.0.2.0/24\n")
        env_file.chmod(0o600)
        self.log = self.dir / "pct.log"
        self.env = {
            **os.environ,
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "ENV_FILE": str(env_file),
            "FAKE_LOG": str(self.log),
            "FAKE_CTS": "201 202 203",
            "FAKE_OTHER": "",
            "FAKE_FAIL": "",
        }

    def run_script(self, *args, stdin="", **env):
        return subprocess.run(
            ["bash", str(SCRIPT), *args], input=stdin, env={**self.env, **env}, capture_output=True, text=True
        )

    def calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def test_passwords_reach_every_container_through_stdin(self):
        lines = "student01 pass-one-aaaa\nstudent02 pass-two-bbbb\nstudent03 pass-three-cc\n"
        result = self.run_script("--passwords", stdin=lines)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.calls(),
            [
                "exec 201 | chpasswd | student:pass-one-aaaa",
                "exec 202 | chpasswd | student:pass-two-bbbb",
                "exec 203 | chpasswd | student:pass-three-cc",
            ],
        )

    def test_one_failure_does_not_stop_the_others(self):
        lines = "student01 pass-one-aaaa\nstudent02 pass-two-bbbb\nstudent03 pass-three-cc\n"
        result = self.run_script("--passwords", stdin=lines, FAKE_FAIL="202")
        self.assertEqual(result.returncode, 1)
        self.assertIn("student02", result.stderr)
        self.assertEqual(len(self.calls()), 3)

    def test_unknown_student_and_foreign_container_are_skipped(self):
        lines = "student09 pass-nine-xxxx\nstudent02 pass-two-bbbb\nstudent03 pass-three-cc\n"
        result = self.run_script("--passwords", stdin=lines, FAKE_OTHER="202")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.calls(), ["exec 203 | chpasswd | student:pass-three-cc"])

    @unittest.skipUnless(os.geteuid() == 0, "building every lab reads files only root can read (lab 11 is mode 000)")
    def test_labs_are_unpacked_as_the_student(self):
        result = self.run_script("--labs", "student01")
        self.assertEqual(result.returncode, 0, result.stderr)
        unpack = [c for c in self.calls() if "runuser -u student -- sh -c mkdir -p /home/student/lab" in c]
        self.assertEqual(len(unpack), 1)
        self.assertTrue(unpack[0].startswith("exec 201 | "))

    def test_one_lab_can_be_reset_and_the_old_copy_kept(self):
        result = self.run_script("--labs", "student02", "05-organize")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("重設 05-organize，舊的在 ~/lab/.05-organize.old-", result.stdout)
        resets = [c for c in self.calls() if "runuser -u student -- sh -c cd /home/student/lab" in c]
        self.assertEqual(len(resets), 1)
        self.assertTrue(resets[0].startswith("exec 202 | "))
        self.assertIn(" sh 05-organize .05-organize.old-", resets[0])

    def test_bad_lab_or_student_is_refused_before_touching_containers(self):
        for args in (
            ("student02", "../etc"),
            ("student02", "05-organize;id"),
            ("student02", "99-no-such-lab"),
            ("student09", "05-organize"),
        ):
            result = self.run_script("--labs", *args)
            self.assertNotEqual(result.returncode, 0, args)
        self.assertEqual(self.calls(), [])

    def test_bad_settings_stop_before_touching_containers(self):
        (self.dir / "shell-lab.env").write_text("STUDENT_COUNT=0\nPORTFORWARD_SOURCES=192.0.2.0/24\n")
        result = self.run_script("--passwords", stdin="student01 pass-one-aaaa\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls(), [])


if __name__ == "__main__":
    unittest.main()
