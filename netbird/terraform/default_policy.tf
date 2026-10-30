# NetBird 安裝時自帶「All → All」政策，所有裝置互通，學生就能連到別人的 VM。
# make keys 會用 API 查出它的 ID，Terraform 接管並停用它（不刪除，方便必要時查看原設定）。
import {
  for_each = var.default_policy_id == "" ? toset([]) : toset([var.default_policy_id])
  to       = netbird_policy.default_all[0]
  id       = each.key
}

resource "netbird_policy" "default_all" {
  count       = var.default_policy_id == "" ? 0 : 1
  name        = "Default"
  description = "This is a default rule that allows connections between all the resources"
  enabled     = false

  rule {
    name          = "Default"
    action        = "accept"
    bidirectional = true
    protocol      = "all"
    sources       = [data.netbird_group.all.id]
    destinations  = [data.netbird_group.all.id]
  }
}

data "netbird_group" "all" {
  name = "All"
}
