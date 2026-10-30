import random
import stat
import unittest

from labctl import passwords
from tests.helpers import scratch_dir

STUDENTS = ["student01", "student02"]


class PasswordTest(unittest.TestCase):
    def test_format_and_alphabet(self):
        value = passwords.generate(random.Random(1))
        self.assertRegex(value, r"^[a-z2-9]{4}-[a-z2-9]{4}-[a-z2-9]{4}$")
        self.assertEqual(set(value) - set(passwords.ALPHABET), {"-"})
        self.assertEqual(len(passwords.ALPHABET), 32)
        self.assertEqual(set("0o1l") & set(passwords.ALPHABET), set())

    def test_ensure_adds_only_missing_passwords(self):
        path = scratch_dir() / "passwords.json"
        self.assertEqual(passwords.ensure(path, STUDENTS[:1]), 1)
        first = passwords.load(path)["student01"]
        self.assertEqual(passwords.ensure(path, STUDENTS), 1)
        self.assertEqual(passwords.load(path)["student01"], first)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_export_needs_every_student(self):
        path = scratch_dir() / "passwords.json"
        passwords.ensure(path, STUDENTS[:1])
        with self.assertRaises(ValueError) as ctx:
            passwords.export_lines(path, STUDENTS)
        self.assertIn("student02", str(ctx.exception))

    def test_export_refuses_values_that_would_break_a_line(self):
        path = scratch_dir() / "passwords.json"
        path.write_text('{"student01": "two words", "student02": "fine-pass-word"}')
        path.chmod(0o600)
        with self.assertRaises(ValueError) as ctx:
            passwords.export_lines(path, STUDENTS)
        self.assertIn("student01", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
