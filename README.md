# ttussc-shell-lab

[![CI](https://github.com/Jerry080401/ttussc-shell-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/Jerry080401/ttussc-shell-lab/actions/workflows/ci.yml)

Linux 命令列社課的上課環境。每位學生有一台自己的 Ubuntu VM，從自己的筆電用 NetBird 加 SSH 登入做題目。題目共 13 題，從 `whoami` 到 `git log`，答對會印出 flag。

```text
學生筆電 ──NetBird（WireGuard）──> 自己的 VM（實驗主機上的 Incus/KVM）
    │                                   │
    └──────── 註冊 ──> NetBird 伺服器（VPS）<── 註冊 ┘
                       決定誰可以連誰
```

## 需要準備

- **VPS**：放 NetBird 伺服器。Ubuntu 24.04 或 26.04，2 GB 記憶體，公網 IP，對外開 TCP 22、80、443 和 UDP 3478。網域要有一筆 A 紀錄指向這台 VPS，用 Cloudflare 的話要設成 DNS only。
- **實驗主機**：放學生的 VM。Ubuntu 24.04 或 26.04，x86_64，要有 `/dev/kvm`。不需要公網 IP，VM 會主動連到 NetBird。
- **老師的電腦**：Linux 或 WSL，裝好 `make`、`python3`（含 venv）、`terraform` 和 `ssh`。要能 SSH 登入 VPS 和實驗主機，實驗主機的帳號要能免密碼 sudo。

## 從零開始

```bash
make env        # 建立 .env，照下面的設定表填好
make netbird    # 在 VPS 上安裝 NetBird，管理員密碼存在 local/netbird-admin-password
```

用 `ADMIN_EMAIL` 和管理員密碼登入 `https://NETBIRD_DOMAIN`，替自己的帳號建立 Personal Access Token，填進 `.env` 的 `NETBIRD_PAT`。

```bash
make keys       # 建立群組、存取規則和一次性 setup key
make host       # 設定實驗主機：Incus、VM 隔離防火牆
make vms        # 建立全班的 VM，先建兩台試跑
make enroll     # 每台 VM 加入 NetBird
make labs       # 把題目放進每台 VM
make passwords  # 產生學生密碼並設定到 VM
make cards      # 產生全班的連線清單 local/cards.md
```

老師的電腦也要加入 NetBird 才連得到 VM。setup key 在 `terraform -chdir=netbird/terraform output -json setup_keys` 的 `teachers` 裡，用 `netbird up --management-url https://NETBIRD_DOMAIN --setup-key 那把key` 加入。

`local/cards.md` 有每位學生的連線指令和密碼，發給學生時每個人只給自己那一段。學生要先照 [學生連線說明](docs/STUDENT_GUIDE.md) 裝好 NetBird。

每個步驟都可以重跑，已經做好的部分會跳過。執行 `make` 會列出全部指令。

## 設定

全部設定都在 `.env`。裡面有秘密，權限要是 600，其他人讀得到時 labctl 會停下來。值不要加引號，也不要有空白。

| 變數 | 說明 |
|---|---|
| `COHORT` | 班級代號，VM 和 NetBird 群組名稱的開頭 |
| `STUDENT_COUNT` | 學生人數，最多 99 人，學生 ID 是 `student01` 到 `studentNN` |
| `TEACHER_DEVICES` | 老師的裝置名稱，用逗號分隔，每台各有一把 setup key |
| `REVOKED_STUDENTS` | 要撤權的學生，用逗號分隔。他的連線規則會停用，setup key 會撤銷 |
| `NETBIRD_DOMAIN` | NetBird 伺服器的網域 |
| `NETBIRD_PUBLIC_IP` | VPS 的公網 IP。安裝前會檢查網域是不是只指向這個 IP |
| `NETBIRD_SSH` | 登入 VPS 的 `帳號@主機`，主機可以填 IP 或 `~/.ssh/config` 裡的名稱 |
| `ADMIN_EMAIL` | NetBird 管理員帳號，也是申請 HTTPS 憑證用的信箱 |
| `NETBIRD_PAT` | NetBird 的 Personal Access Token，裝好 NetBird 之後才建得出來 |
| `SETUP_KEY_DAYS` | setup key 的有效天數，1 到 30 天 |
| `LAB_SSH` | 登入實驗主機的 `帳號@主機` |
| `LAB_SECRET` | 產生每位學生題目資料用的秘密，`make env` 會自動產生 |
| `GUEST_OS` | VM 的系統，`ubuntu-26.04` 或 `ubuntu-24.04` |
| `GUEST_LOCALE` | VM 的語系。`zh_TW.UTF-8` 會另外裝中文的指令說明和 man page |
| `GUEST_TIMEZONE` | VM 的時區 |
| `STUDENT_SUDO` | 學生在自己的 VM 裡能不能用 sudo，要輸入自己的密碼 |
| `VM_VCPU` | 每台 VM 的 CPU 數 |
| `VM_MEMORY_MIB` | 每台 VM 的記憶體（MiB） |
| `VM_DISK_GIB` | 每台 VM 的硬碟（GiB） |
| `VM_NETWORK_POOL` | VM 用的私有網段，每台依序切一個 /28 |
| `PROTECTED_NETWORKS` | VM 不能連的其他網段，用逗號分隔。學校或公司內網用的是公網位址時要填 |

## 上課

```bash
make class-start  # 上課前約 10 分鐘開 NetBird
make status       # 看全班的 VM 和學生電腦在不在線
make class-stop   # 下課後關 NetBird，VPS 對外只剩 SSH
```

## 常見狀況

| 狀況 | 做法 |
|---|---|
| 學生的 setup key 用掉了或過期 | `make renew-keys STUDENTS="student05"`，再 `make cards`。不加 `STUDENTS` 會換掉全班的 |
| 學生想重做某一題 | `make reset-lab STUDENT=student05 LAB=05-organize`，舊的資料夾會改名留在學生的 `~/lab` |
| 重建一位學生的 VM | 在實驗主機上 `sudo incus delete --force linux-2026-student05`（`linux-2026` 是 `COHORT`），在 NetBird 網頁刪掉這台舊的 peer，再跑 `make renew-keys KEY=vm STUDENTS="student05"` 和 `make vms enroll labs passwords cards` |
| 撤掉一位學生 | 把 ID 加進 `REVOKED_STUDENTS`，再跑 `make keys` |
| 學生人數改變 | 改 `STUDENT_COUNT`，再跑 `make keys host vms enroll labs passwords cards`。人數變少時，多出來的 VM 不會自動刪掉，但一樣會被隔離 |

## 課程結束

```bash
make teardown     # VM 關機、不跟著主機開機，停掉 Incus 和隔離防火牆
make class-stop
```

VM 和學生的資料都會留著。要再上課時，重跑 `make host` 和 `make vms`。

NetBird 的資料沒有備份。VPS 壞掉的話，先把 `local/terraform.tfstate*` 移到別的地方，再重跑 `make netbird`、建新的 Personal Access Token、跑 `make keys`，最後用 `make enroll` 和 `make cards` 讓 VM 和學生的電腦重新加入。要升級 NetBird 時，改 `versions.lock.json` 的版本和映像 digest，再跑 `make netbird`。不要在上課期間升級。

## 安全設計

- NetBird 預設的 All 政策會被停用。每位學生只有一條規則：自己的電腦連自己的 VM，只開 TCP 22。`make keys` 跑完會用 API 檢查，確定沒有任何開著的政策用到 All 群組。
- VM 之間互相隔離，也連不到實驗主機（DNS 和 DHCP 除外）、私有網段和同一個區網的設備，只能經過主機目前的預設閘道上網。規則套用在每一個 `tl*` 開頭的 bridge，不看名單，防火牆沒載入成功時 Incus 也不會啟動。這些規則有測試，會在 network namespace 裡送真的封包驗證。
- 主機換了網路、閘道還沒同步時，VM 會先斷網，不會連到新網段裡的設備。
- setup key 都是一次性的，過了 `SETUP_KEY_DAYS` 就失效。
- 密碼和 setup key 只經過 stdin 傳到主機和 VM，不會出現在指令參數裡。
- 秘密只放在 `.env` 和 `local/`，兩個都不進 Git。

## 文件

- [學生連線說明](docs/STUDENT_GUIDE.md)：課前準備和上課時的連線步驟，可以直接發給學生
- [簡報](https://canva.link/ebc3teparl7gopj)：社課「Linux 常用指令」的投影片（Canva）
- [題目設計](docs/LABS.md)：13 題在練什麼、資料怎麼產生、怎麼改題目

## 開發

```bash
make test   # 測試
make lint   # ruff、shellcheck、terraform fmt
make fmt    # 自動整理格式
```

防火牆的封包測試需要 `unshare`、`nsenter`、`ip`、`ping` 和 `nft`，缺少時會略過。CI 會用 root 跑這個測試。

## 授權

[MIT](LICENSE)。答對時印出的企鵝圖案是照 TTUSSC 的社團 logo 描的。
