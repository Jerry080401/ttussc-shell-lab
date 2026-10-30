import stat
import unittest

from labctl.cards import build_cards, render_markdown, write_markdown
from tests.helpers import scratch_dir

URL = "https://netbird.example.com"
TWO = ["student01", "student02"]


def inputs():
    peers = {
        "student01": {"netbird_ip": "100.92.10.21", "ssh_fingerprint": "SHA256:" + "A" * 43},
        "student02": {"netbird_ip": "100.92.10.22", "ssh_fingerprint": "SHA256:" + "B" * 43},
    }
    passwords = {"student01": "abcd-efgh-jkmn", "student02": "pqrs-tuvw-xyz2"}
    keys = {"student01": "3F2A9C1E-7B4D-4E8A-9C61-2D5B8F0A1E47", "student02": "11111111-2222-3333-4444-555555555555"}
    return peers, passwords, keys


def entry(doc, sid):
    """One student's bullet: the lines nested under `- <sid>`."""
    return doc.split(f"- {sid}\n", 1)[1].split("\n- ", 1)[0]


class BuildCardsTest(unittest.TestCase):
    def test_each_entry_holds_only_its_own_secrets(self):
        peers, passwords, keys = inputs()
        own = entry(render_markdown(build_cards(TWO, peers, passwords, keys, URL).values()), "student01")
        for value in (keys["student01"], passwords["student01"], "100.92.10.21"):
            self.assertIn(value, own)
        for value in (keys["student02"], passwords["student02"], "100.92.10.22"):
            self.assertNotIn(value, own)

    def test_commands_are_complete_without_placeholders(self):
        # 學生整行複製貼上就能用，Windows PowerShell 會把 < 當成保留運算子。
        peers, passwords, keys = inputs()
        doc = render_markdown(build_cards(TWO, peers, passwords, keys, URL).values())
        # 兩個指令放在同一個程式碼區塊，一行一個。
        self.assertIn(
            "- student01\n"
            "  ```\n"
            f"  netbird up --management-url {URL} --setup-key {keys['student01']}\n"
            "  ssh student@100.92.10.21\n"
            "  ```\n"
            "  - 密碼 `abcd-efgh-jkmn`\n",
            doc,
        )
        self.assertNotIn("<", doc)
        self.assertNotIn(">", doc)

    def test_install_commands_come_first_and_only_once(self):
        doc = render_markdown(build_cards(TWO, *inputs(), URL).values())
        self.assertEqual(doc.count("https://pkgs.netbird.io/windows/x64"), 1)
        self.assertIn("  - `.\\netbird-installer.exe`\n", doc)
        self.assertLess(doc.index("https://pkgs.netbird.io/install.sh"), doc.index("- student01\n"))

    def test_host_key_fingerprint_is_left_off(self):
        # 清單只給連線需要的東西，學生第一次連線直接輸入 yes。
        doc = render_markdown(build_cards(TWO, *inputs(), URL).values())
        self.assertNotIn("SHA256", doc)
        self.assertNotIn("指紋", doc)

    def test_missing_or_malformed_data_names_each_student(self):
        peers, passwords, keys = inputs()
        del passwords["student02"]
        keys["student01"] = "not-a-key"
        with self.assertRaises(ValueError) as ctx:
            build_cards(TWO, peers, passwords, keys, URL)
        self.assertIn("student01 (setup key)", str(ctx.exception))
        self.assertIn("student02 (password)", str(ctx.exception))

    def test_values_that_would_change_a_command_are_refused(self):
        bad_values = [
            ("keys", "3F2A9C1E-7B4D-4E8A-9C61-2D5B8F0A1E47 --foo"),
            ("passwords", "has spaces in it"),
            ("peers", {"netbird_ip": "100.92.10.21 -oProxyCommand=x"}),
        ]
        for which, value in bad_values:
            peers, passwords, keys = inputs()
            {"keys": keys, "passwords": passwords, "peers": peers}[which]["student01"] = value
            with self.assertRaises(ValueError, msg=which):
                build_cards(TWO, peers, passwords, keys, URL)
        with self.assertRaises(ValueError):
            build_cards(TWO, *inputs(), "https://netbird.example.com --setup-key x")

    def test_selection_limits_cards_and_rejects_unknown_students(self):
        cards = build_cards(TWO, *inputs(), URL, ["student02"])
        self.assertEqual(list(cards), ["student02"])
        with self.assertRaises(ValueError):
            build_cards(TWO, *inputs(), URL, ["student99"])

    def test_backticks_in_a_password_keep_the_list_intact(self):
        peers, passwords, keys = inputs()
        passwords["student02"] = "`tick`tock"
        doc = render_markdown(build_cards(TWO, peers, passwords, keys, URL).values())
        self.assertEqual(doc.count("\n- student"), 2)
        self.assertIn("`` `tick`tock ``", doc)


class WriteMarkdownTest(unittest.TestCase):
    def test_file_is_private_and_replaced_in_one_step(self):
        cards = build_cards(TWO, *inputs(), URL)
        path = scratch_dir() / "cards.md"
        path.write_text("old list")
        path.chmod(0o644)
        write_markdown(path, cards)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(path.read_text(encoding="utf-8"), render_markdown(cards.values()))
        self.assertEqual([p.name for p in path.parent.iterdir()], ["cards.md"])  # 沒有留下暫存檔


if __name__ == "__main__":
    unittest.main()
