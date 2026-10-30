terraform {
  required_version = ">= 1.16.0, < 2.0.0"

  required_providers {
    netbird = {
      source  = "netbirdio/netbird"
      version = "0.0.10"
    }
  }

  # state 內含 setup key 明文，只放在不進 Git 的 local/。
  backend "local" {
    path = "../../local/terraform.tfstate"
  }
}

# token 是 .env 的 NETBIRD_PAT，make 會用環境變數 NB_PAT 傳進來。
provider "netbird" {
  management_url = var.management_url
}
