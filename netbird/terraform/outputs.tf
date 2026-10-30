# setup key 明文：make enroll 和 make cards 會直接接過去用。發給學生時每個人只給自己那一段。
output "setup_keys" {
  sensitive = true
  value = {
    clients  = { for id, k in netbird_setup_key.client : id => k.key }
    vms      = { for id, k in netbird_setup_key.vm : id => k.key }
    teachers = { for id, k in netbird_setup_key.teacher : id => k.key }
  }
}
