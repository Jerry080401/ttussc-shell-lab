locals {
  cohort          = var.cohort
  students        = [for i in range(1, var.student_count + 1) : format("student%02d", i)]
  teacher_devices = [for d in split(",", var.teacher_devices) : trimspace(d) if trimspace(d) != ""]
  revoked         = toset([for s in split(",", var.revoked_students) : trimspace(s) if trimspace(s) != ""])
  expiry_seconds  = var.setup_key_days * 86400
}

# ---------- 群組 ----------

resource "netbird_group" "teachers" {
  name = "${local.cohort}-teachers"
}

resource "netbird_group" "lab_vms" {
  name = "${local.cohort}-lab-vms"
}

resource "netbird_group" "lab_host_admin" {
  name = "${local.cohort}-lab-host-admin"
}

resource "netbird_group" "client" {
  for_each = toset(local.students)
  name     = "${local.cohort}-client-${each.key}"
}

resource "netbird_group" "vm" {
  for_each = toset(local.students)
  name     = "${local.cohort}-vm-${each.key}"
}

# ---------- 存取規則：學生只能 SSH 到自己的 VM ----------

resource "netbird_policy" "student_ssh" {
  for_each    = toset(local.students)
  name        = "${local.cohort}-${each.key}-ssh"
  description = "${each.key} client -> own VM, TCP 22 only"
  enabled     = !contains(local.revoked, each.key)

  rule {
    name          = "${each.key}-ssh"
    action        = "accept"
    bidirectional = false
    protocol      = "tcp"
    ports         = ["22"]
    sources       = [netbird_group.client[each.key].id]
    destinations  = [netbird_group.vm[each.key].id]
  }
}

resource "netbird_policy" "teacher_lab_ssh" {
  name    = "${local.cohort}-teacher-lab-ssh"
  enabled = true

  rule {
    name          = "teacher-lab-ssh"
    action        = "accept"
    bidirectional = false
    protocol      = "tcp"
    ports         = ["22"]
    sources       = [netbird_group.teachers.id]
    destinations  = [netbird_group.lab_vms.id]
  }
}

resource "netbird_policy" "teacher_host_ssh" {
  name    = "${local.cohort}-teacher-host-ssh"
  enabled = true

  rule {
    name          = "teacher-host-ssh"
    action        = "accept"
    bidirectional = false
    protocol      = "tcp"
    ports         = ["22"]
    sources       = [netbird_group.teachers.id]
    destinations  = [netbird_group.lab_host_admin.id]
  }
}

# ---------- 一次性 setup key：一人一把、一台 VM 一把 ----------

resource "netbird_setup_key" "client" {
  for_each       = toset(local.students)
  name           = "${local.cohort}-client-${each.key}"
  type           = "one-off"
  auto_groups    = [netbird_group.client[each.key].id]
  expiry_seconds = local.expiry_seconds
  ephemeral      = false
  revoked        = contains(local.revoked, each.key)
}

resource "netbird_setup_key" "vm" {
  for_each       = toset(local.students)
  name           = "${local.cohort}-vm-${each.key}"
  type           = "one-off"
  auto_groups    = [netbird_group.vm[each.key].id, netbird_group.lab_vms.id]
  expiry_seconds = local.expiry_seconds
  ephemeral      = false
  revoked        = contains(local.revoked, each.key)
}

resource "netbird_setup_key" "teacher" {
  for_each       = toset(local.teacher_devices)
  name           = "${local.cohort}-teacher-${each.key}"
  type           = "one-off"
  auto_groups    = [netbird_group.teachers.id]
  expiry_seconds = local.expiry_seconds
  ephemeral      = false
}
