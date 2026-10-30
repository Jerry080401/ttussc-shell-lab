"""VM plan: name, resources and network of every student's VM. Pure computation, never touches a host."""

import hashlib
import ipaddress

from labctl.config import SUBNET_PREFIX, select_students
from labctl.firewall import BRIDGE_PREFIX

VM_FIELDS = (
    "name",
    "hostname",
    "image",
    "vcpu",
    "memory_mib",
    "disk_gib",
    "bridge",
    "subnet",
    "prefix",
    "gateway",
    "address",
)


def vm_name(cohort, sid):
    return f"{cohort}-{sid}"


def groups(cohort, sid):
    """NetBird groups of one student, the same names Terraform creates."""
    return {"client": f"{cohort}-client-{sid}", "vm": f"{cohort}-vm-{sid}"}


def guest_hostname(sid):
    """Hostname inside the VM, shown in the prompt and checked by lab 01."""
    return f"lab-{sid}"


def bridge_name(cohort, sid):
    # 名稱一改，主機上既有的 bridge 就對不上了。Linux 介面名稱最多 15 個字元。
    return BRIDGE_PREFIX + hashlib.sha256(f"{cohort}:{sid}".encode()).hexdigest()[:10]


def build_plan(config, selected=None):
    chosen = set(select_students(config.students(), selected))
    pool = config.vm_network_pool
    instances = []
    for slot, sid in enumerate(config.students(), 1):
        if sid not in chosen:
            continue
        start = int(pool.network_address) + (slot - 1) * 2 ** (32 - SUBNET_PREFIX)
        subnet = ipaddress.ip_network((start, SUBNET_PREFIX))
        instances.append(
            {
                "student_id": sid,
                "slot": slot,
                "name": vm_name(config.cohort, sid),
                "hostname": guest_hostname(sid),
                "guest_os": config.guest_os,
                "image": config.image,
                "vcpu": config.vm_vcpu,
                "memory_mib": config.vm_memory_mib,
                "disk_gib": config.vm_disk_gib,
                "sudo": config.student_sudo,
                "locale": config.guest_locale,
                "timezone": config.guest_timezone,
                "network": {
                    "bridge": bridge_name(config.cohort, sid),
                    "subnet": str(subnet),
                    "prefix": SUBNET_PREFIX,
                    "gateway": str(subnet.network_address + 1),
                    "address": str(subnet.network_address + 2),
                },
                "netbird_groups": groups(config.cohort, sid),
            }
        )
    if len({i["network"]["bridge"] for i in instances}) != len(instances):
        raise ValueError("generated bridge name collision, change COHORT")
    count = len(instances)
    return {
        "cohort": config.cohort,
        "students": [i["student_id"] for i in instances],
        "protected_networks": [str(n) for n in config.protected_networks],
        "budget": {
            "vm_count": count,
            "vcpu_total": count * config.vm_vcpu,
            "memory_mib_total": count * config.vm_memory_mib,
            "disk_gib_total": count * config.vm_disk_gib,
        },
        "instances": instances,
    }


def vm_fields(instance, fields):
    """Values of `fields` for one instance, for host scripts that read them with `read`."""
    flat = {**instance, **instance["network"]}
    unknown = [f for f in fields if f not in VM_FIELDS]
    if unknown:
        raise ValueError(f"unknown VM field: {', '.join(unknown)} (choose from {', '.join(VM_FIELDS)})")
    return [str(flat[f]) for f in fields]
