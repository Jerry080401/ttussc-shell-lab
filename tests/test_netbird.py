import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from labctl import netbird


class FakeApi:
    """A local HTTP server that answers like the NetBird management API."""

    def __init__(self, routes, status=200):
        api = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                api.headers = dict(self.headers)
                body = json.dumps(routes.get(self.path, {})).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def close(self):
        self.server.shutdown()
        self.server.server_close()


class DefaultPolicyTest(unittest.TestCase):
    def client(self, routes, status=200):
        api = FakeApi(routes, status)
        self.addCleanup(api.close)
        self.api = api
        return netbird.Client(api.url, "token-value")

    def test_finds_the_default_policy_by_name(self):
        client = self.client({"/api/policies": [{"id": "p1", "name": "ssh"}, {"id": "p2", "name": "Default"}]})
        self.assertEqual(netbird.default_policy_id(client), "p2")
        self.assertEqual(self.api.headers["Authorization"], "Token token-value")

    def test_missing_default_policy_is_an_empty_answer(self):
        self.assertEqual(netbird.default_policy_id(self.client({"/api/policies": []})), "")

    def test_api_errors_stop_instead_of_answering_empty(self):
        # 空字串會讓 Terraform 刪掉已經接管的預設政策，所以錯誤一定要停下來。
        with self.assertRaises(ValueError):
            netbird.default_policy_id(self.client({}, status=401))

    def test_unreachable_server_mentions_class_start(self):
        api = FakeApi({})
        url = api.url
        api.close()
        with self.assertRaises(ValueError) as ctx:
            netbird.default_policy_id(netbird.Client(url, "token-value"))
        self.assertIn("make class-start", str(ctx.exception))

    def test_empty_token_is_refused(self):
        with self.assertRaises(ValueError):
            netbird.Client("https://netbird.example.com", "")


GROUPS = ({"id": "g-all", "name": "All"}, {"id": "g-vm", "name": "linux-2026-vm-student01"})


class OpenPoliciesTest(unittest.TestCase):
    def open_policies(self, policies):
        api = FakeApi({"/api/groups": list(GROUPS), "/api/policies": policies})
        self.addCleanup(api.close)
        return netbird.open_policies(netbird.Client(api.url, "token-value"))

    def test_enabled_all_to_all_policy_is_found(self):
        default = {
            "name": "Default",
            "enabled": True,
            "rules": [{"sources": [{"id": "g-all", "name": "All"}], "destinations": [{"id": "g-all", "name": "All"}]}],
        }
        self.assertEqual(self.open_policies([default]), ["Default"])

    def test_group_ids_without_names_are_resolved(self):
        policy = {"name": "custom", "enabled": True, "rules": [{"sources": ["g-vm"], "destinations": ["g-all"]}]}
        self.assertEqual(self.open_policies([policy]), ["custom"])

    def test_disabled_policies_and_student_rules_pass(self):
        default = {"name": "Default", "enabled": False, "rules": [{"sources": ["g-all"], "destinations": ["g-all"]}]}
        ssh = {"name": "student01-ssh", "enabled": True, "rules": [{"sources": ["g-vm"], "destinations": ["g-vm"]}]}
        self.assertEqual(self.open_policies([default, ssh]), [])


class StatusTableTest(unittest.TestCase):
    def test_counts_vms_and_student_computers(self):
        peers = [
            {
                "hostname": "lab-student01",
                "ip": "100.92.0.1",
                "connected": True,
                "groups": [{"name": "linux-2026-vm-student01"}],
            },
            {
                "hostname": "laptop",
                "ip": "100.92.0.50",
                "connected": False,
                "groups": [{"name": "linux-2026-client-student01"}],
            },
            {
                "hostname": "teacher",
                "ip": "100.92.0.99",
                "connected": True,
                "groups": [{"name": "linux-2026-teachers"}],
            },
        ]
        table = netbird.status_table("linux-2026", ["student01", "student02"], peers)
        self.assertIn("VM 在線 1/2　已加入電腦 1/2　電腦在線 0/2", table)
        self.assertIn("○ laptop 100.92.0.50", table)
        self.assertIn("（還沒加入）", table.splitlines()[2])
        self.assertIn("老師：● teacher 100.92.0.99", table)


if __name__ == "__main__":
    unittest.main()
