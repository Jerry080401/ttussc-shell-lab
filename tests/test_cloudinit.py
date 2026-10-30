import json
import shutil
import subprocess
import tempfile
import unittest

from labctl.cloudinit import CHINESE_PACKAGES, SWITCH_TO_GNU_COREUTILS, render_user_data
from labctl.plan import build_plan
from tests.helpers import example_config

try:
    import yaml
except ImportError:  # cloud-init 本身用 PyYAML，測試環境沒有時只檢查 JSON。
    yaml = None


def instance(student="student01", **env):
    return build_plan(example_config(**env), [student])["instances"][0]


def parsed(text):
    header, body = text.split("\n", 1)
    assert header == "#cloud-config", header
    doc = json.loads(body)
    if yaml is not None:
        assert yaml.safe_load(body) == doc
    return doc


def sshd_settings(doc):
    files = {f["path"]: f for f in doc["write_files"]}
    dropin = files["/etc/ssh/sshd_config.d/00-ttussc-lab.conf"]
    settings = {}
    for line in dropin["content"].splitlines():
        if line.strip() and not line.startswith("#"):
            key, value = line.split(None, 1)
            settings.setdefault(key.lower(), value)  # sshd：同一設定以第一次出現為準
    return settings


class CloudConfigTest(unittest.TestCase):
    def test_is_valid_cloud_config(self):
        self.assertIsInstance(parsed(render_user_data(instance())), dict)

    @unittest.skipUnless(shutil.which("cloud-init"), "cloud-init not installed")
    def test_passes_cloud_init_schema_validation(self):
        with tempfile.NamedTemporaryFile("w", suffix=".yml", encoding="utf-8") as handle:
            handle.write(render_user_data(instance()))
            handle.flush()
            result = subprocess.run(["cloud-init", "schema", "-c", handle.name], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_hostname_is_per_student(self):
        self.assertEqual(parsed(render_user_data(instance("student02")))["hostname"], "lab-student02")

    def test_only_the_student_account_is_created(self):
        doc = parsed(render_user_data(instance()))
        self.assertEqual([u["name"] for u in doc["users"]], ["student"])
        self.assertTrue(doc["users"][0]["lock_passwd"])

    def test_student_with_sudo_joins_sudo_group_and_needs_password(self):
        user = parsed(render_user_data(instance(STUDENT_SUDO="true")))["users"][0]
        self.assertIn("sudo", user["groups"])
        self.assertNotIn("sudo", user)  # cloud-init 的 sudo 規則（如 NOPASSWD）一律不用

    def test_student_without_sudo_has_no_admin_group(self):
        user = parsed(render_user_data(instance(STUDENT_SUDO="false")))["users"][0]
        self.assertNotIn("sudo", user.get("groups", []))
        self.assertNotIn("sudo", user)

    def test_no_credentials_are_embedded(self):
        # user-data 會留在 guest 裡，學生讀得到。密碼與金鑰另外經由 stdin 設定。
        doc = parsed(render_user_data(instance()))
        for key in ("passwd", "hashed_passwd", "plain_text_passwd", "ssh_authorized_keys"):
            self.assertNotIn(key, doc["users"][0])
        for key in ("chpasswd", "password", "ssh_authorized_keys"):
            self.assertNotIn(key, doc)

    def test_chinese_help_man_pages_and_editors_installed(self):
        doc = parsed(render_user_data(instance()))
        self.assertEqual((doc["locale"], doc["timezone"]), ("zh_TW.UTF-8", "Asia/Taipei"))
        for package in ("language-pack-zh-hant", "manpages-zh", "man-db", "vim", "git"):
            self.assertIn(package, doc["packages"])
        profile = {f["path"]: f for f in doc["write_files"]}["/etc/profile.d/ttussc-locale.sh"]["content"]
        self.assertIn("export LANGUAGE=zh_TW:zh\n", profile)

    def test_other_locale_skips_chinese_packages(self):
        doc = parsed(render_user_data(instance(GUEST_LOCALE="en_US.UTF-8", GUEST_TIMEZONE="UTC")))
        self.assertEqual((doc["locale"], doc["timezone"]), ("en_US.UTF-8", "UTC"))
        for package in CHINESE_PACKAGES:
            self.assertNotIn(package, doc["packages"])
        profile = {f["path"]: f for f in doc["write_files"]}["/etc/profile.d/ttussc-locale.sh"]["content"]
        self.assertIn("export LANG=en_US.UTF-8\n", profile)
        self.assertNotIn("LANGUAGE=zh", profile)

    def test_standard_ubuntu_server_toolset_installed(self):
        # 映像只有最小系統，ubuntu-standard 補上一般 Ubuntu Server 的常用工具（nano、wget、man…）。
        doc = parsed(render_user_data(instance()))
        for package in ("ubuntu-standard", "tree", "unzip", "xxd"):
            self.assertIn(package, doc["packages"])

    def test_switches_to_gnu_coreutils_for_chinese_help(self):
        # uutils 版的 ls、cp 等沒有中文翻譯，換成 GNU 版後 ls --help 才會顯示中文。
        doc = parsed(render_user_data(instance()))
        self.assertIn(SWITCH_TO_GNU_COREUTILS, doc["runcmd"])
        for arg in ("coreutils-from-gnu", "coreutils-from-uutils-", "--allow-remove-essential", "-y"):
            self.assertIn(arg, SWITCH_TO_GNU_COREUTILS)
        # 放進 packages 會和 coreutils-from-uutils 衝突，整批套件都裝不起來。
        self.assertNotIn("coreutils-from-gnu", doc["packages"])

    def test_ubuntu_24_04_keeps_its_gnu_coreutils(self):
        # 24.04 沒有 coreutils-from-gnu 這個套件，執行切換會讓 cloud-init 失敗。
        doc = parsed(render_user_data(instance(GUEST_OS="ubuntu-24.04")))
        self.assertNotIn(SWITCH_TO_GNU_COREUTILS, doc["runcmd"])

    def test_docs_exclusion_removed_before_packages_install(self):
        # 精簡映像會用 dpkg path-exclude 丟掉 man page 與翻譯，必須在裝套件前移除。
        doc = parsed(render_user_data(instance()))
        self.assertIn(["rm", "-f", "/etc/dpkg/dpkg.cfg.d/excludes"], doc["bootcmd"])

    def test_sshd_only_allows_the_student(self):
        settings = sshd_settings(parsed(render_user_data(instance())))
        self.assertEqual(settings["permitrootlogin"], "no")
        self.assertEqual(settings["allowusers"], "student")
        self.assertEqual(settings["disableforwarding"], "yes")

    def test_students_log_in_with_a_password(self):
        doc = parsed(render_user_data(instance()))
        self.assertTrue(doc["ssh_pwauth"])
        self.assertEqual(sshd_settings(doc)["passwordauthentication"], "yes")
        self.assertEqual(sshd_settings(doc)["kbdinteractiveauthentication"], "no")


if __name__ == "__main__":
    unittest.main()
