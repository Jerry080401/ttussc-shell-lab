import unittest

from labctl.plan import build_plan, vm_fields
from tests.helpers import example_config


def plan_for(selected=("student01", "student02"), **env):
    return build_plan(example_config(**env), list(selected) if selected else None)


class TwoStudentPlanTest(unittest.TestCase):
    def setUp(self):
        self.plan = plan_for()
        self.by_id = {i["student_id"]: i for i in self.plan["instances"]}

    def test_each_student_gets_own_subnet_by_number(self):
        s1, s2 = self.by_id["student01"]["network"], self.by_id["student02"]["network"]
        self.assertEqual((s1["subnet"], s1["gateway"], s1["address"]), ("10.231.0.0/28", "10.231.0.1", "10.231.0.2"))
        self.assertEqual((s2["subnet"], s2["gateway"], s2["address"]), ("10.231.0.16/28", "10.231.0.17", "10.231.0.18"))

    def test_bridge_names_are_stable(self):
        # 名稱一旦改變，主機上既有的 bridge 和防火牆規則就對不上了。
        self.assertEqual(self.by_id["student01"]["network"]["bridge"], "tl617e6724c6")
        self.assertEqual(self.by_id["student02"]["network"]["bridge"], "tl3f1ae80e23")

    def test_instance_and_group_names_match_terraform(self):
        inst = self.by_id["student01"]
        self.assertEqual(inst["name"], "linux-2026-student01")
        self.assertEqual(inst["hostname"], "lab-student01")
        self.assertEqual(
            inst["netbird_groups"], {"client": "linux-2026-client-student01", "vm": "linux-2026-vm-student01"}
        )

    def test_budget_counts_only_selected_students(self):
        self.assertEqual(
            self.plan["budget"], {"vm_count": 2, "vcpu_total": 2, "memory_mib_total": 2048, "disk_gib_total": 16}
        )

    def test_ubuntu_26_04_guest_uses_its_cloud_image(self):
        self.assertEqual(self.by_id["student01"]["image"], "images:ubuntu/26.04/cloud")

    def test_settings_are_carried_into_each_vm(self):
        inst = plan_for(STUDENT_SUDO="false", GUEST_LOCALE="en_US.UTF-8", GUEST_TIMEZONE="UTC")["instances"][0]
        self.assertEqual((inst["sudo"], inst["locale"], inst["timezone"]), (False, "en_US.UTF-8", "UTC"))


class SelectionTest(unittest.TestCase):
    def test_everyone_by_default_in_order(self):
        plan = plan_for(selected=None)
        self.assertEqual(plan["students"], [f"student{n:02d}" for n in range(1, 41)])
        self.assertEqual(plan["instances"][-1]["network"]["subnet"], "10.231.2.112/28")

    def test_unknown_or_duplicate_selection_rejected(self):
        for selected in (["student41"], ["student01", "student01"]):
            with self.assertRaises(ValueError, msg=selected):
                plan_for(selected=selected)


class VmFieldsTest(unittest.TestCase):
    def test_fields_in_requested_order(self):
        inst = plan_for(selected=["student02"])["instances"][0]
        self.assertEqual(vm_fields(inst, ["name", "address", "prefix"]), ["linux-2026-student02", "10.231.0.18", "28"])

    def test_unknown_field_rejected(self):
        inst = plan_for(selected=["student02"])["instances"][0]
        with self.assertRaises(ValueError):
            vm_fields(inst, ["password"])


if __name__ == "__main__":
    unittest.main()
