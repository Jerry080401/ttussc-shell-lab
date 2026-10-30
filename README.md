# ttussc-shell-lab

[![CI](https://github.com/Jerry080401/ttussc-shell-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/Jerry080401/ttussc-shell-lab/actions/workflows/ci.yml)

TTUSSC「Linux 常用指令」社課用的實驗環境。每個學生分到一台 Ubuntu VM，先用 NetBird 加入課程的私人網路，再 SSH 進自己的 VM 做題目。題目有 13 題，解開會拿到 flag。

```text
學生筆電 ──NetBird（WireGuard）──> 自己的 VM（實驗主機上的 Incus/KVM）
    │                                   │
    └──────── 註冊 ──> NetBird 伺服器（VPS）<── 註冊 ┘
```

## 需要的機器

- 一台 VPS 跑 NetBird 伺服器：Ubuntu 24.04 或 26.04，2 GB 記憶體，要有公網 IP，對外開 TCP 22、80、443 和 UDP 3478。另外要一個網域，A 紀錄指到這台 VPS，用 Cloudflare 的話要設成 DNS only。
- 一台實驗主機放學生的 VM：Ubuntu 24.04 或 26.04，x86_64，要有 `/dev/kvm`。不需要公網 IP。不要裝 Docker，它會把轉送的預設規則改成 DROP，VM 會上不了網。
- 老師自己的電腦（Linux 或 WSL）：要有 `make`、`python3`（含 venv）、`terraform` 和 `ssh`，而且要能 SSH 進 VPS 和實驗主機。實驗主機上的帳號要能免密碼 sudo。

## 安裝

```bash
make env        # 產生 .env，照下面的表填好
make netbird    # 在 VPS 上裝 NetBird，管理員密碼存在 local/netbird-admin-password
```

用 `ADMIN_EMAIL` 和這組密碼登入 `https://NETBIRD_DOMAIN`，幫自己的帳號建一個 Personal Access Token，填進 `.env` 的 `NETBIRD_PAT`，再接著做：

```bash
make keys       # NetBird 的群組、規則和一次性 setup key
make host       # 實驗主機：Incus 和隔離 VM 的防火牆
make vms        # 建全班的 VM，會先建兩台試跑
make enroll     # 讓每台 VM 加入 NetBird
make labs       # 放題目
make passwords  # 產生學生密碼，設定到 VM 裡
make cards      # 全班的連線指令，寫到 local/cards.md
```

老師的電腦也要加入 NetBird 才連得到 VM。key 在 `terraform -chdir=netbird/terraform output -json setup_keys` 的 `teachers` 裡，用 `netbird up --management-url https://NETBIRD_DOMAIN --setup-key 那把key` 加入。

`local/cards.md` 有每個學生的連線指令和密碼，發的時候一人只給自己那一段。學生要先照 [學生連線說明](docs/STUDENT_GUIDE.md) 裝好 NetBird。

每個指令都可以重跑，做過的部分會跳過。打 `make` 可以看到全部的指令。

## 設定

設定全部放在 `.env`。裡面有密碼和 token，權限要設成 600，別人讀得到的話 labctl 會直接停下來。值不要加引號，也不要有空白。

| 變數 | 說明 |
|---|---|
| `COHORT` | 班級代號，VM 和 NetBird 群組的名稱都會用它開頭 |
| `STUDENT_COUNT` | 學生人數，最多 99。學生 ID 是 `student01` 到 `studentNN` |
| `TEACHER_DEVICES` | 老師的裝置名稱，用逗號分隔，每台會拿到一把 setup key |
| `REVOKED_STUDENTS` | 要撤權的學生，用逗號分隔。他的連線規則會關掉，setup key 會作廢 |
| `NETBIRD_DOMAIN` | NetBird 伺服器的網域 |
| `NETBIRD_PUBLIC_IP` | VPS 的公網 IP。安裝前會檢查網域是不是只指到這個 IP |
| `NETBIRD_SSH` | 登入 VPS 用的 `帳號@主機`，主機可以填 IP 或 `~/.ssh/config` 裡的名稱 |
| `ADMIN_EMAIL` | NetBird 的管理員帳號，申請 HTTPS 憑證也用這個信箱 |
| `NETBIRD_PAT` | NetBird 的 Personal Access Token，裝好 NetBird 之後才建得出來 |
| `SETUP_KEY_DAYS` | setup key 幾天後失效，1 到 30 |
| `LAB_SSH` | 登入實驗主機用的 `帳號@主機` |
| `LAB_SECRET` | 產生每個學生的題目資料用的密鑰，`make env` 會自動產生 |
| `GUEST_OS` | VM 的系統，`ubuntu-26.04` 或 `ubuntu-24.04` |
| `GUEST_LOCALE` | VM 的語系。填 `zh_TW.UTF-8` 會另外裝中文的指令說明和 man page |
| `GUEST_TIMEZONE` | VM 的時區 |
| `STUDENT_SUDO` | 學生在自己的 VM 裡能不能用 sudo（要打自己的密碼） |
| `VM_VCPU` | 每台 VM 的 CPU 數 |
| `VM_MEMORY_MIB` | 每台 VM 的記憶體（MiB） |
| `VM_DISK_GIB` | 每台 VM 的硬碟（GiB） |
| `VM_NETWORK_POOL` | VM 用的私有網段，每台依序切一個 /28 |
| `PROTECTED_NETWORKS` | 另外不讓 VM 連的網段，用逗號分隔。學校或公司內網用的是公網位址時要填 |

## 上課

```bash
make class-start  # 上課前十分鐘左右開 NetBird
make status       # 看全班的 VM 和學生電腦有沒有連上
make class-stop   # 下課後關 NetBird，VPS 對外只剩 SSH
```

## 常見狀況

| 狀況 | 做法 |
|---|---|
| 學生的 setup key 用掉了或過期 | `make renew-keys STUDENTS="student05"`，再 `make cards`。不加 `STUDENTS` 會換掉全班的 |
| 學生想重做某一題 | `make reset-lab STUDENT=student05 LAB=05-organize`，舊的資料夾會改名留在學生的 `~/lab` |
| 重建一位學生的 VM | 在實驗主機上 `sudo incus delete --force linux-2026-student05`（`linux-2026` 換成你的 `COHORT`），到 NetBird 網頁刪掉這台舊的 peer，再跑 `make renew-keys KEY=vm STUDENTS="student05"` 和 `make vms enroll labs passwords cards` |
| 撤掉一位學生 | 把他的 ID 加進 `REVOKED_STUDENTS`，再跑 `make keys` |
| 學生人數改了 | 改 `STUDENT_COUNT`，再跑 `make keys host vms enroll labs passwords cards`。人數變少時，多出來的 VM 不會自動刪掉，但一樣會被隔離 |

## 課程結束

```bash
make teardown     # VM 關機，也不會跟著主機開機，再停掉 Incus 和隔離防火牆
make class-stop
```

VM 和學生的資料都會留著，要再上課的話重跑 `make host` 和 `make vms`。

NetBird 的資料沒有備份。VPS 壞掉的話，先把 `local/terraform.tfstate*` 移到別的地方，重跑 `make netbird`，建一個新的 Personal Access Token，跑 `make keys`，最後用 `make enroll` 和 `make cards` 讓 VM 和學生的電腦重新加入。要升級 NetBird 時，改 `versions.lock.json` 裡的版本和映像 digest，再跑 `make netbird`。上課期間不要升級。

## 隔離怎麼做

NetBird 預設的 All 政策會被關掉。每個學生只有一條規則：自己的電腦連自己的 VM，而且只開 TCP 22。`make keys` 跑完會再用 API 檢查一次，只要還有開著的政策用到 All 群組就會報錯。

實驗主機用 nftables 管所有 `tl` 開頭的 bridge。VM 之間互相連不到，也連不到主機（DNS、DHCP 除外）、私有網段和同一個區網的機器，只能經過主機目前的預設閘道上網。主機換了網路、閘道還沒同步之前，VM 會先斷網。防火牆沒載入成功的話 Incus 不會啟動。這些規則有測試，會在 network namespace 裡送真的封包檢查。

setup key 都只能用一次。密碼和 key 只經過 stdin 傳到主機和 VM，不會出現在指令參數裡。`.env` 和 `local/` 都不進 Git。

## 文件

- [學生連線說明](docs/STUDENT_GUIDE.md)：課前準備和上課時的連線步驟，可以直接發給學生
- [簡報](https://canva.link/ebc3teparl7gopj)：社課「Linux 常用指令」的投影片（Canva）
- [題目](docs/LABS.md)：每題在練什麼、答案、資料怎麼產生、怎麼改題目

## 開發

```bash
make test   # 測試
make lint   # ruff、shellcheck、terraform fmt
make fmt    # 自動整理格式
```

防火牆的封包測試需要 `unshare`、`nsenter`、`ip`、`ping` 和 `nft`，缺了會跳過。CI 會用 root 跑。

## 授權

[MIT](LICENSE)。答對時印出的企鵝是照 TTUSSC 的社團 logo。
