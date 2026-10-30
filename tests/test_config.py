import os
import unittest

from labctl.config import KEYS, host_env_text, load_config, parse_env
from tests.helpers import EXAMPLE_ENV, SECRET_HEX, example_config, scratch_dir, write_env


class ExampleTest(unittest.TestCase):
    def test_example_lists_every_key_once_in_order(self):
        self.assertEqual(list(parse_env(EXAMPLE_ENV.read_text(encoding="utf-8"))), list(KEYS))

    def test_example_loads_without_comments(self):
        self.assertNotIn("#", EXAMPLE_ENV.read_text(encoding="utf-8"))
        config = load_config(EXAMPLE_ENV)
        self.assertEqual(config.students()[0], "student01")
        self.assertEqual(config.students()[-1], "student40")
        self.assertEqual(config.management_url, "https://netbird.example.com")

    def test_lists_are_split_on_commas(self):
        config = example_config(TEACHER_DEVICES="laptop,desktop", PROTECTED_NETWORKS="203.0.113.0/24,198.51.100.0/24")
        self.assertEqual(config.teacher_devices, ("laptop", "desktop"))
        self.assertEqual([str(n) for n in config.protected_networks], ["203.0.113.0/24", "198.51.100.0/24"])

    def test_netbird_version_follows_the_pinned_server(self):
        self.assertRegex(load_config(EXAMPLE_ENV).netbird_version, r"^\d+\.\d+\.\d+$")


class FileFormatTest(unittest.TestCase):
    def assertRejected(self, text, message):
        path = scratch_dir() / ".env"
        path.write_text(text, encoding="utf-8")
        path.chmod(0o600)
        with self.assertRaises(ValueError) as ctx:
            load_config(path)
        self.assertIn(message, str(ctx.exception))

    def test_every_missing_key_is_named(self):
        self.assertRejected("COHORT=linux-2026\n", "missing: STUDENT_COUNT, TEACHER_DEVICES")

    def test_unknown_key_is_named(self):
        # 打錯字的設定如果被默默忽略，那個值就一直是預設值。
        with self.assertRaises(ValueError) as ctx:
            example_config(VM_MEMORY_MB="2048")
        self.assertIn("unknown: VM_MEMORY_MB", str(ctx.exception))

    def test_values_make_or_shell_would_rewrite_are_refused(self):
        # Make 的 include 不會去掉引號，# 之後會被當成註解。
        for value in ('"netbird.example.com"', "a b", "x#y", "$HOME", "`id`"):
            with self.assertRaises(ValueError, msg=value):
                parse_env(f"NETBIRD_DOMAIN={value}\n")

    def test_key_set_twice_is_refused(self):
        with self.assertRaises(ValueError):
            parse_env("COHORT=a\nCOHORT=b\n")

    def test_line_without_equals_is_refused(self):
        with self.assertRaises(ValueError):
            parse_env("COHORT\n")

    def test_missing_file_says_how_to_create_it(self):
        with self.assertRaises(ValueError) as ctx:
            load_config(scratch_dir() / ".env")
        self.assertIn("make env", str(ctx.exception))

    @unittest.skipIf(os.geteuid() == 0, "root reads any file")
    def test_file_with_secrets_readable_by_others_is_refused(self):
        with self.assertRaises(ValueError) as ctx:
            load_config(write_env(mode=0o644, LAB_SECRET=SECRET_HEX))
        self.assertIn("chmod 600", str(ctx.exception))

    def test_file_without_secrets_may_be_shared(self):
        self.assertEqual(load_config(write_env(mode=0o644)).cohort, "linux-2026")


class ValuesTest(unittest.TestCase):
    def assertRejected(self, **overrides):
        with self.assertRaises(ValueError, msg=overrides):
            example_config(**overrides)

    def test_student_count_range(self):
        self.assertRejected(STUDENT_COUNT="0")
        self.assertRejected(STUDENT_COUNT="100")
        self.assertRejected(STUDENT_COUNT="ten")
        self.assertEqual(example_config(STUDENT_COUNT="99").students()[-1], "student99")

    def test_revoked_students_must_exist(self):
        self.assertRejected(STUDENT_COUNT="40", REVOKED_STUDENTS="student41")
        self.assertRejected(REVOKED_STUDENTS="student01,student01")
        self.assertEqual(example_config(REVOKED_STUDENTS="student03").revoked_students, ("student03",))

    def test_teacher_devices_required_and_unique(self):
        self.assertRejected(TEACHER_DEVICES="")
        self.assertRejected(TEACHER_DEVICES="laptop,laptop")
        self.assertRejected(TEACHER_DEVICES="My_Laptop")

    def test_required_values_may_not_be_empty(self):
        with self.assertRaises(ValueError) as ctx:
            example_config(NETBIRD_DOMAIN="", ADMIN_EMAIL="")
        self.assertIn("NETBIRD_DOMAIN, ADMIN_EMAIL", str(ctx.exception))

    def test_ssh_targets_need_a_user(self):
        self.assertRejected(LAB_SSH="lab-host")
        self.assertRejected(NETBIRD_SSH="203.0.113.10")

    def test_lab_secret_is_64_hex_digits(self):
        self.assertRejected(LAB_SECRET="abc")
        self.assertRejected(LAB_SECRET="z" * 64)
        self.assertEqual(example_config(LAB_SECRET=SECRET_HEX).lab_secret, bytes.fromhex(SECRET_HEX))

    def test_unsupported_guest_rejected(self):
        self.assertRejected(GUEST_OS="debian-12")

    def test_student_sudo_must_be_true_or_false(self):
        self.assertRejected(STUDENT_SUDO="yes")

    def test_vm_resources_have_limits(self):
        self.assertRejected(VM_VCPU="9")
        self.assertRejected(VM_MEMORY_MIB="512")
        self.assertRejected(VM_DISK_GIB="4")

    def test_pool_must_be_private_ipv4(self):
        self.assertRejected(VM_NETWORK_POOL="198.51.100.0/24")
        self.assertRejected(VM_NETWORK_POOL="fd00::/64")
        self.assertRejected(VM_NETWORK_POOL="10.231.0.1/16")

    def test_pool_must_fit_every_vm(self):
        # /24 切成 /28 只有 16 格。
        self.assertRejected(VM_NETWORK_POOL="10.231.0.0/24", STUDENT_COUNT="17")
        self.assertEqual(example_config(VM_NETWORK_POOL="10.231.0.0/24", STUDENT_COUNT="16").student_count, 16)

    def test_protected_networks(self):
        self.assertRejected(PROTECTED_NETWORKS="10.231.8.0/24")  # 和 VM 網段重疊
        self.assertRejected(PROTECTED_NETWORKS="2001:db8::/32")
        self.assertRejected(PROTECTED_NETWORKS="203.0.113.0/33")

    def test_locale_and_timezone(self):
        self.assertRejected(GUEST_LOCALE="zh_TW")
        self.assertRejected(GUEST_TIMEZONE="Taipei time")
        config = example_config(GUEST_LOCALE="en_US.UTF-8", GUEST_TIMEZONE="UTC")
        self.assertEqual((config.guest_locale, config.guest_timezone), ("en_US.UTF-8", "UTC"))


class HostEnvTest(unittest.TestCase):
    def test_host_copy_drops_only_the_netbird_token(self):
        path = write_env(NETBIRD_PAT="nbp_" + "x" * 36, LAB_SECRET=SECRET_HEX)
        text = host_env_text(path)
        self.assertIn("NETBIRD_PAT=\n", text)
        self.assertNotIn("nbp_", text)
        self.assertIn(f"LAB_SECRET={SECRET_HEX}\n", text)
        self.assertEqual(list(parse_env(text)), list(KEYS))


if __name__ == "__main__":
    unittest.main()
