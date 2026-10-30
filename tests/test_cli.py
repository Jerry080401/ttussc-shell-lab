import json
import os
import stat
import subprocess
import sys
import unittest

from labctl.labs import LABS
from tests.helpers import EXAMPLE_ENV, REPO, SECRET_HEX, scratch_dir, write_env


def labctl(*args, stdin=None):
    return subprocess.run(
        [sys.executable, "-m", "labctl", *map(str, args)], cwd=REPO, input=stdin, capture_output=True, text=True
    )


def terraform_output(students):
    """The same shape as `terraform output -json setup_keys`."""
    return json.dumps(
        {
            "clients": {sid: f"000000{sid[-2:]}-0000-4000-8000-000000000000" for sid in students},
            "vms": {sid: f"000000{sid[-2:]}-0000-4000-8000-111111111111" for sid in students},
            "teachers": {},
        }
    )


class ConfigCommandTest(unittest.TestCase):
    def test_check_reports_the_settings(self):
        result = labctl("--env", EXAMPLE_ENV, "config", "check")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("40 students", result.stdout)

    def test_get_prints_one_value_but_never_a_secret(self):
        self.assertEqual(
            labctl("--env", EXAMPLE_ENV, "config", "get", "management_url").stdout, "https://netbird.example.com\n"
        )
        self.assertEqual(labctl("--env", EXAMPLE_ENV, "config", "get", "student_sudo").stdout, "true\n")
        for name in ("netbird_pat", "lab_secret", "no_such_setting"):
            self.assertEqual(labctl("--env", EXAMPLE_ENV, "config", "get", name).returncode, 2, name)

    def test_invalid_config_exits_2_with_message(self):
        result = labctl("--env", write_env(GUEST_OS="debian-12"), "plan")
        self.assertEqual(result.returncode, 2)
        self.assertTrue(result.stderr.startswith("ERROR:"), result.stderr)
        self.assertEqual(result.stdout, "")


class PlanCommandTest(unittest.TestCase):
    def test_plan_prints_selected_students(self):
        result = labctl("--env", EXAMPLE_ENV, "plan", "--students", "student01", "student02")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["students"], ["student01", "student02"])

    def test_students_lists_everyone(self):
        result = labctl("--env", EXAMPLE_ENV, "students")
        self.assertEqual(result.stdout.split(), [f"student{n:02d}" for n in range(1, 41)])

    def test_vm_prints_requested_fields_for_shell_scripts(self):
        result = labctl("--env", EXAMPLE_ENV, "vm", "student02", "name", "address")
        self.assertEqual(result.stdout, "linux-2026-student02 10.231.0.18\n")


class RenderCommandTest(unittest.TestCase):
    def test_cloud_init_for_one_student(self):
        result = labctl("--env", EXAMPLE_ENV, "render", "cloud-init", "student02")
        self.assertEqual(result.returncode, 0, result.stderr)
        header, body = result.stdout.split("\n", 1)
        self.assertEqual(header, "#cloud-config")
        self.assertEqual(json.loads(body)["hostname"], "lab-student02")

    def test_cloud_init_unknown_student_fails(self):
        self.assertEqual(labctl("--env", EXAMPLE_ENV, "render", "cloud-init", "student99").returncode, 2)

    def test_firewall_matches_every_lab_bridge_by_name(self):
        result = labctl("--env", EXAMPLE_ENV, "render", "firewall")
        self.assertEqual(result.returncode, 0, result.stderr)
        # 用名稱比對所有 tl* 介面，不列出今天名單上的 bridge，人數變少時留下來的 VM 也一樣被隔離。
        self.assertIn('iifname "tl*" drop', result.stdout)
        self.assertIn('oifname "tl*" drop', result.stdout)
        self.assertNotIn("tl617e6724c6", result.stdout)


class GatewaySyncCommandTest(unittest.TestCase):
    def run_sync(self, stdin):
        return labctl("render", "gateway-sync", stdin=stdin)

    def test_default_gateway_from_ip_route_json(self):
        routes = [
            {
                "dst": "default",
                "gateway": "192.168.1.1",
                "dev": "eth0",
                "protocol": "dhcp",
                "prefsrc": "192.168.1.23",
                "metric": 100,
                "flags": [],
            }
        ]
        result = self.run_sync(json.dumps(routes))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout,
            "flush set inet ttussc_lab uplink_gateways\nadd element inet ttussc_lab uplink_gateways { 192.168.1.1 }\n",
        )

    def test_no_default_route_empties_the_set(self):
        # 沒有預設路由時只清空，VM 連不出去（fail-closed）。
        result = self.run_sync("[]\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "flush set inet ttussc_lab uplink_gateways\n")

    def test_garbage_input_is_refused(self):
        for stdin in (
            "not json",
            '{"gateway": "1.2.3.4"}',
            '[{"dst": "default", "gateway": "1.2.3.4 } ; flush ruleset"}]',
        ):
            result = self.run_sync(stdin)
            self.assertEqual(result.returncode, 2, stdin)
            self.assertEqual(result.stdout, "")


class LabsCommandTest(unittest.TestCase):
    def test_build_creates_all_labs_for_one_student(self):
        out = scratch_dir() / "lab"
        result = labctl("--env", write_env(LAB_SECRET=SECRET_HEX), "labs", "build", "student01", "--out", out)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((out / "README.md").is_file())
        self.assertEqual(len([p for p in out.iterdir() if p.is_dir()]), 13)
        self.assertNotIn("TTUSSC{", result.stdout)  # 產生題目時不印出答案

    def test_build_rejects_student_not_in_class(self):
        out = scratch_dir() / "lab"
        result = labctl("--env", write_env(LAB_SECRET=SECRET_HEX), "labs", "build", "student41", "--out", out)
        self.assertEqual(result.returncode, 2)
        self.assertTrue(result.stderr.startswith("ERROR:"), result.stderr)
        self.assertFalse(out.exists())

    def test_build_needs_a_lab_secret(self):
        out = scratch_dir() / "lab"
        result = labctl("--env", EXAMPLE_ENV, "labs", "build", "student01", "--out", out)
        self.assertEqual(result.returncode, 2)
        self.assertIn("make env", result.stderr)

    @unittest.skipIf(os.geteuid() == 0, "root reads any file")
    def test_env_with_secret_readable_by_others_is_refused(self):
        # LAB_SECRET 決定每位學生的題目資料，只有老師能讀。
        out = scratch_dir() / "lab"
        env = write_env(mode=0o644, LAB_SECRET=SECRET_HEX)
        result = labctl("--env", env, "labs", "build", "student01", "--out", out)
        self.assertEqual(result.returncode, 2)
        self.assertIn("chmod 600", result.stderr)

    def test_flags_lists_the_answers(self):
        # flag 全班相同，答案就是每題一句，不需要設定檔。
        result = labctl("labs", "flags")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {lab.LAB_ID: lab.FLAG for lab in LABS})


class DeployFilesTest(unittest.TestCase):
    """passwords, keys, peers and cards: the files `make passwords`, `make enroll` and `make cards` pass along."""

    def setUp(self):
        self.dir = scratch_dir()
        self.env = write_env(STUDENT_COUNT="3")
        self.students = ["student01", "student02", "student03"]

    def test_passwords_are_created_once_and_exported_as_lines(self):
        file = self.dir / "passwords.json"
        self.assertEqual(labctl("--env", self.env, "passwords", "new", "--file", file).returncode, 0)
        self.assertEqual(stat.S_IMODE(file.stat().st_mode), 0o600)
        first = file.read_text()
        self.assertIn("added 0", labctl("--env", self.env, "passwords", "new", "--file", file).stdout)
        self.assertEqual(file.read_text(), first)
        lines = labctl("--env", self.env, "passwords", "export", "--file", file).stdout.splitlines()
        self.assertEqual([line.split()[0] for line in lines], self.students)

    def test_vm_keys_become_lines_for_the_host(self):
        result = labctl("--env", self.env, "keys", "vm", stdin=terraform_output(self.students))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines()[0], "student01 00000001-0000-4000-8000-111111111111")

    def test_enrolled_ips_are_saved_and_cards_written(self):
        peers = self.dir / "peers.json"
        lines = "".join(f"{sid} 100.92.10.{n}\n" for n, sid in enumerate(self.students, 1))
        result = labctl("--env", self.env, "peers", "import", "--file", peers, stdin=lines)
        self.assertEqual(result.returncode, 0, result.stderr)
        passwords = self.dir / "passwords.json"
        labctl("--env", self.env, "passwords", "new", "--file", passwords)
        out = self.dir / "cards.md"
        result = labctl(
            "--env",
            self.env,
            "cards",
            "--peers",
            peers,
            "--passwords",
            passwords,
            "--out",
            out,
            stdin=terraform_output(self.students),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        doc = out.read_text(encoding="utf-8")
        self.assertEqual(doc.count("\n- student"), 3)
        self.assertIn("ssh student@100.92.10.2\n", doc)
        self.assertIn(
            "--management-url https://netbird.example.com --setup-key 00000002-0000-4000-8000-000000000000", doc
        )
        self.assertEqual(result.stdout, "wrote 3 students to " + str(out) + "\n")

    @unittest.skipIf(os.geteuid() == 0, "root reads any file")
    def test_password_file_readable_by_others_is_refused(self):
        passwords = self.dir / "passwords.json"
        labctl("--env", self.env, "passwords", "new", "--file", passwords)
        passwords.chmod(0o644)
        result = labctl("--env", self.env, "passwords", "export", "--file", passwords)
        self.assertEqual(result.returncode, 2)
        self.assertIn("chmod 600", result.stderr)


class NetbirdCommandTest(unittest.TestCase):
    def test_empty_token_is_refused_before_any_request(self):
        result = labctl("--env", EXAMPLE_ENV, "netbird", "default-policy")
        self.assertEqual(result.returncode, 2)
        self.assertIn("NETBIRD_PAT", result.stderr)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
