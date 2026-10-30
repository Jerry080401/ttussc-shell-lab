import json
import stat
import unittest

from labctl import keys
from tests.helpers import scratch_dir

STUDENTS = ["student01", "student02"]
OUTPUT = json.dumps(
    {
        "clients": {"student01": "11111111-2222-3333-4444-555555555555"},
        "vms": {
            "student01": "AAAAAAAA-2222-3333-4444-555555555555",
            "student02": "BBBBBBBB-2222-3333-4444-555555555555",
        },
        "teachers": {},
    }
)


class VmKeyLinesTest(unittest.TestCase):
    def test_one_line_per_student(self):
        self.assertEqual(
            keys.vm_key_lines(OUTPUT, STUDENTS),
            "student01 AAAAAAAA-2222-3333-4444-555555555555\nstudent02 BBBBBBBB-2222-3333-4444-555555555555\n",
        )

    def test_missing_key_is_named(self):
        with self.assertRaises(ValueError) as ctx:
            keys.vm_key_lines(OUTPUT, [*STUDENTS, "student03"])
        self.assertIn("student03", str(ctx.exception))

    def test_other_json_is_refused(self):
        for text in ("", "[]", '{"clients": {}}'):
            with self.assertRaises(ValueError, msg=text):
                keys.vm_key_lines(text, STUDENTS)


class ImportPeersTest(unittest.TestCase):
    def test_merges_ips_and_keeps_other_fields(self):
        path = scratch_dir() / "peers.json"
        path.write_text(json.dumps({"student01": {"netbird_ip": "100.92.0.1", "note": "kept"}}))
        self.assertEqual(keys.import_peers(path, "student01 100.92.0.9\n\nstudent02 100.92.0.2\n", STUDENTS), 2)
        self.assertEqual(
            keys.load_peers(path),
            {"student01": {"netbird_ip": "100.92.0.9", "note": "kept"}, "student02": {"netbird_ip": "100.92.0.2"}},
        )
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_bad_lines_are_refused(self):
        path = scratch_dir() / "peers.json"
        for text in ("student01\n", "student09 100.92.0.1\n", "student01 not-an-ip\n", "student01 1.2.3.4 extra\n"):
            with self.assertRaises(ValueError, msg=text):
                keys.import_peers(path, text, STUDENTS)
        self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
