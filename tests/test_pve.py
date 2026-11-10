import json
import subprocess
import sys
import unittest

from labctl.config import parse_env
from labctl.pve import (
    ACCESS_SETTINGS,
    DEFAULTS,
    build_pve_config,
    build_pve_plan,
    ct_fields,
    load_pve_config,
    shell_settings,
)
from tests.helpers import REPO, SECRET_HEX, scratch_dir

EXAMPLE = REPO / "deploy" / "pve" / "shell-lab.env.example"

REQUIRED = {"PORTFORWARD_SOURCES": "198.51.100.0/24"}


def config(**values):
    return build_pve_config({**REQUIRED, **values})


def write_pve_env(mode=0o600, **values):
    path = scratch_dir() / "shell-lab.env"
    path.write_text("".join(f"{k}={v}\n" for k, v in {**REQUIRED, **values}.items()), encoding="utf-8")
    path.chmod(mode)
    return path


def labctl(*args):
    return subprocess.run([sys.executable, "-m", "labctl", *map(str, args)], cwd=REPO, capture_output=True, text=True)


class PveSettingsTest(unittest.TestCase):
    def test_defaults_need_only_the_access_sources(self):
        c = config()
        self.assertEqual(c.student_count, 20)
        self.assertFalse(c.student_sudo)
        self.assertEqual(c.access_mode, "portforward")
        self.assertEqual(c.access["sources"], ("198.51.100.0/24",))

    def test_access_sources_are_required(self):
        with self.assertRaises(ValueError) as ctx:
            build_pve_config({})
        self.assertIn("PORTFORWARD_SOURCES", str(ctx.exception))

    def test_every_source_is_allowed_only_when_written_out(self):
        self.assertEqual(config(PORTFORWARD_SOURCES="0.0.0.0/0").access["sources"], ("0.0.0.0/0",))

    def test_unknown_and_other_mode_keys_are_refused(self):
        with self.assertRaises(ValueError) as ctx:
            config(STUDENT_COUNTS="3")
        self.assertIn("STUDENT_COUNTS", str(ctx.exception))

    def test_unknown_access_mode_is_refused(self):
        with self.assertRaises(ValueError):
            config(ACCESS_MODE="telnet")

    def test_template_must_match_the_guest_os(self):
        with self.assertRaises(ValueError):
            config(GUEST_OS="ubuntu-26.04")  # 預設樣板是 24.04
        c = config(GUEST_OS="ubuntu-26.04", GUEST_TEMPLATE="ubuntu-26.04-standard_26.04-1_amd64.tar.zst")
        self.assertEqual(c.guest_os, "ubuntu-26.04")

    def test_bad_values_are_refused(self):
        for key, value in (
            ("STUDENT_COUNT", "0"),
            ("STUDENT_COUNT", "100"),
            ("CTID_START", "99"),
            ("NAT_SUBNET", "203.0.113.0/24"),
            ("NAT_SUBNET", "10.10.10.1/24"),
            ("PORTFORWARD_PORT_START", "80"),
            ("PORTFORWARD_PORT_START", "65530"),
            ("PORTFORWARD_SOURCES", "1.2.3"),
            ("PORTFORWARD_ADDRESS", "a b"),
            ("CT_NAMESERVER", "dns"),
            ("STUDENT_SUDO", "yes"),
            ("LAB_SECRET", "abc"),
            ("PVE_SSH", "pve"),
        ):
            with self.assertRaises(ValueError, msg=f"{key}={value}"):
                config(**{key: value})

    def test_subnet_must_hold_every_container(self):
        with self.assertRaises(ValueError):
            config(NAT_SUBNET="10.10.10.0/29", STUDENT_COUNT="6")
        config(NAT_SUBNET="10.10.10.0/29", STUDENT_COUNT="5")

    def test_protected_networks_must_not_overlap_the_subnet(self):
        with self.assertRaises(ValueError):
            config(PROTECTED_NETWORKS="10.10.0.0/16")

    def test_file_with_a_secret_must_be_private(self):
        with self.assertRaises(ValueError):
            load_pve_config(write_pve_env(mode=0o644, LAB_SECRET=SECRET_HEX))
        self.assertEqual(load_pve_config(write_pve_env(LAB_SECRET=SECRET_HEX)).lab_secret, bytes.fromhex(SECRET_HEX))


class PveExampleTest(unittest.TestCase):
    def test_example_lists_every_setting_once_in_order(self):
        # 範例檔列出所有設定，順序和程式裡的一樣，讀者才找得到每個值。
        keys = list(parse_env(EXAMPLE.read_text(encoding="utf-8")))
        self.assertEqual(keys, [*DEFAULTS, *ACCESS_SETTINGS["portforward"]])

    def test_example_values_are_the_defaults(self):
        # 範例檔寫的值就是程式的預設值，例外是語系和時區（範例給常用值）。
        values = parse_env(EXAMPLE.read_text(encoding="utf-8"))
        defaults = {**DEFAULTS, **ACCESS_SETTINGS["portforward"]}
        differ = {k for k, v in values.items() if v != (defaults[k] or "")}
        self.assertEqual(differ, {"GUEST_LOCALE", "GUEST_TIMEZONE"})

    def test_example_loads_once_the_sources_are_filled_in(self):
        values = parse_env(EXAMPLE.read_text(encoding="utf-8"))
        self.assertEqual(build_pve_config({**values, **REQUIRED}).student_count, 20)


class PvePlanTest(unittest.TestCase):
    def test_each_student_gets_a_ctid_address_and_port(self):
        plan = build_pve_plan(config(STUDENT_COUNT="3"))
        self.assertEqual(plan["students"], ["student01", "student02", "student03"])
        first, last = plan["instances"][0], plan["instances"][-1]
        self.assertEqual((first["ctid"], first["address"], first["access"]["port"]), (201, "10.10.10.2", 22001))
        self.assertEqual((last["ctid"], last["address"], last["access"]["port"]), (203, "10.10.10.4", 22003))
        self.assertEqual(first["gateway"], "10.10.10.1")
        self.assertEqual(first["hostname"], "lab-student01")  # 第 1 題檢查這個名稱

    def test_selected_students_keep_their_own_numbers(self):
        plan = build_pve_plan(config(STUDENT_COUNT="3"), ["student03"])
        self.assertEqual([i["ctid"] for i in plan["instances"]], [203])

    def test_fields_for_shell_scripts(self):
        instance = build_pve_plan(config(), ["student02"])["instances"][0]
        self.assertEqual(ct_fields(instance, ["ctid", "address", "port"]), ["202", "10.10.10.3", "22002"])
        with self.assertRaises(ValueError):
            ct_fields(instance, ["student_id"])

    def test_shell_settings_leave_out_the_secret(self):
        text = shell_settings(config(LAB_SECRET=SECRET_HEX))
        self.assertNotIn(SECRET_HEX, text)
        self.assertIn("NAT_GATEWAY=10.10.10.1\n", text)
        self.assertIn("PORTFORWARD_SOURCES=198.51.100.0/24\n", text)
        for line in text.splitlines():
            self.assertRegex(line, r"^[A-Z_]+=[A-Za-z0-9._/,:@+-]*$")


class PveCommandTest(unittest.TestCase):
    def test_check_and_plan(self):
        env = write_pve_env(STUDENT_COUNT="2")
        result = labctl("--env", env, "pve", "check")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("2 containers, access mode portforward", result.stdout)
        plan = json.loads(labctl("--env", env, "pve", "plan").stdout)
        self.assertEqual(plan["students"], ["student01", "student02"])
        self.assertEqual(labctl("--env", env, "pve", "ct", "student02", "ctid", "port").stdout, "202 22002\n")

    def test_errors_exit_nonzero(self):
        env = write_pve_env(STUDENT_COUNT="2")
        result = labctl("--env", env, "pve", "ct", "student09", "ctid")
        self.assertEqual(result.returncode, 2)
        self.assertIn("ERROR", result.stderr)


if __name__ == "__main__":
    unittest.main()
