# PVE LXC 部署

在一台 Proxmox VE 主機上用原生 LXC 容器部署 shell-lab。容器放在 NAT 網段裡，主機把對外介面上的不同連接埠轉發到各容器的 SSH，使用者直接 `ssh 帳號@主機位址 -p 連接埠` 連進自己的容器。

兩種方案的差別：

| | NetBird 版 | PVE LXC 版 |
|---|---|---|
| 連線方式 | WireGuard overlay，使用者端要裝 NetBird | NAT 連接埠轉發，使用者端只要 ssh |
| 隔離單位 | Incus/KVM VM，各自的核心 | LXC 容器，和主機共用核心 |
| 存取控制 | 每人一條 NetBird 規則 | iptables 限制來源網段（`ALLOWED_SOURCE_CIDR`） |
| 需要的機器 | VPS + 實驗主機 | 一台 PVE 主機，要有連得到的位址 |

## 架構

```text
使用者 ──ssh──> PVE 主機 對外介面 WAN_IFACE（PUBLIC_IP）
                    │  iptables DNAT，只接受 ALLOWED_SOURCE_CIDR
                    │    :22001 → 10.10.10.101:22
                    │    :22002 → 10.10.10.102:22
                    │    ...
                    ▼
               NAT 橋接 NAT_BRIDGE（10.10.10.1/24，bridge-ports none）
                    │                        ▲
                    ├─ CT 201 shell-lab-01   │ 容器上網：MASQUERADE 經 WAN_IFACE
                    ├─ CT 202 shell-lab-02   │
                    └─ ...                   ┘
```

## 前置需求

- Proxmox VE 9.x，以 root 執行腳本。
- 已下載 Ubuntu 24.04 LXC 樣板：

  ```bash
  pveam update
  pveam available --section system | grep ubuntu-24.04
  pveam download local ubuntu-24.04-standard_24.04-2_amd64.tar.zst
  ```

  名稱和預設不同時，把實際的檔名填進設定檔的 `TEMPLATE`。
- 一個使用者連得到的對外位址，以及 `PORT_START` 起連續 `COUNT` 個沒被占用的 TCP 埠。
- `CTID_START` 起連續 `COUNT` 個沒被使用的 CTID。

## 設定

在自己電腦的 repo 裡複製設定範例再編輯：

```bash
cp deploy/pve/shell-lab.env.example deploy/pve/shell-lab.env
chmod 600 deploy/pve/shell-lab.env
```

這份設定和 NetBird 版的 `.env` 分開，`make pve-*` 每次都會把它和腳本一起送到 PVE 主機。腳本會先載入同目錄的 `shell-lab.env`，沒填的才用預設值。

| 變數 | 預設 | 說明 |
|---|---|---|
| `PVE_SSH` | 必填（用 make 時） | 登入 PVE 主機的 `帳號@主機`，可以是 `~/.ssh/config` 裡的名稱。不是 root 的話要能 sudo |
| `WAN_IFACE` | `vmbr0` | 主機連外的介面，只轉發從這裡進來的連線 |
| `PUBLIC_IP` | 留白 | 寫進連線資訊檔的位址。留白取 `WAN_IFACE` 上的 IPv4；主機前面還有一層 NAT 時要填外面的位址 |
| `ALLOWED_SOURCE_CIDR` | 必填 | 允許連入的來源網段，多個用逗號分隔 |
| `NAT_BRIDGE` | `vmbr1` | 給容器用的 NAT 橋接 |
| `NAT_ADDRESS` | `10.10.10.1/24` | 橋接的位址和前綴長度，也是容器的閘道 |
| `CT_IP_OFFSET` | `101` | 第一台容器的位址是網段起點加上這個數 |
| `COUNT` | `20` | 容器數量，帳號和主機名稱從 01 開始編 |
| `CTID_START` | `201` | 第一台的 CTID，依序加一 |
| `PORT_START` | `22001` | 第一台的對外埠，依序加一 |
| `TEMPLATE_STORAGE` | `local` | 樣板所在的儲存 |
| `TEMPLATE` | `ubuntu-24.04-standard_24.04-2_amd64.tar.zst` | 樣板檔名 |
| `STORAGE` | `local-lvm` | 容器根目錄的儲存 |
| `CT_CORES` | `1` | 每台的 vCPU |
| `CT_MEMORY_MB` | `1024` | 每台的記憶體（MB） |
| `CT_SWAP_MB` | `512` | 每台的 swap（MB） |
| `CT_DISK_GB` | `8` | 每台的硬碟（GB） |
| `CT_NAMESERVER` | 留白 | 容器的 DNS，留白沿用主機設定 |
| `CT_HOSTNAME_PREFIX` | `shell-lab-` | 主機名稱前綴，例如 `shell-lab-01` |
| `USER_PREFIX` | `user` | 帳號前綴，例如 `user01` |
| `USER_SUDO` | `true` | 帳號要不要加入 sudo 群組 |
| `PASSWORD_LENGTH` | `12` | 隨機密碼長度 |
| `CRED_FILE` | `shell-lab-credentials.txt` | 連線資訊檔，相對路徑以腳本目錄為準 |
| `FORWARD_HOOK` | `/etc/network/if-up.d/shell-lab-portforward` | 開機時載入轉發規則的腳本 |
| `DNAT_CHAIN` | `SHELL_LAB_DNAT` | 放轉發規則的 iptables chain |

第 N 台（從 1 起算）的對應關係：CTID = `CTID_START + N - 1`，對外埠 = `PORT_START + N - 1`，位址 = 網段起點 + `CT_IP_OFFSET + N - 1`。

## 使用

在自己電腦的 repo 根目錄執行。每個指令都會先把腳本和 `deploy/pve/shell-lab.env` 送到 PVE 主機的 `/opt/shell-lab/pve`，再用 root 執行：

| 指令 | 做什麼 |
|---|---|
| `make pve-dry-run` | 只印出會做的事，不做任何變更 |
| `make pve` | 建立 NAT 橋接、全部容器和轉發規則，連線資訊存到 `local/pve-credentials.txt` |
| `make pve-stop` | 關閉所有容器，資料保留 |
| `make pve-start` | 啟動所有容器 |
| `make pve-destroy` | 刪除所有容器（含硬碟）、轉發規則和連線資訊，要輸入 `yes` 確認 |

典型的流程：

1. `make pve-dry-run` 確認位址、埠和 CTID 的對應。
2. `make pve` 建立全部。完成後把 `local/pve-credentials.txt` 裡每個人的那一行分別交給對應的使用者。
3. 不用的時候 `make pve-stop`，要用之前 `make pve-start`。容器預設會跟著主機開機。
4. 全部結束後 `make pve-destroy`。

`make pve` 把連線資訊抓回 `local/` 後，會刪掉 PVE 主機上那份。重跑時新建的容器會附加到 `local/pve-credentials.txt` 後面。

### 直接在 PVE 主機上執行

沒有 make 的話，也可以把 `deploy/pve` 複製到 PVE 主機上，在那裡建好 `shell-lab.env`，用 root 直接跑腳本。這時連線資訊會留在腳本旁邊的 `shell-lab-credentials.txt`（`CRED_FILE`）。要用別的設定檔可以 `ENV_FILE=/路徑/my.env ./shell-lab-setup.sh`。

| 指令 | 對應的 make |
|---|---|
| `./shell-lab-setup.sh --dry-run` | `make pve-dry-run`。直接跑時前置檢查失敗只會警告，可以在任何機器上預覽 |
| `./shell-lab-setup.sh` | `make pve` |
| `./shell-lab-setup.sh --stop` | `make pve-stop` |
| `./shell-lab-setup.sh --start` | `make pve-start` |
| `./shell-lab-setup.sh --destroy` | `make pve-destroy` |

建立時做的事：

- 在 `/etc/network/interfaces` 附加一段 NAT 橋接設定（post-up 打開 IP 轉送並做 MASQUERADE），再 `ifreload -a`。已經有同名的橋接時沿用，不會改它。
- 產生 `FORWARD_HOOK`，在 `DNAT_CHAIN` 裡放每台容器的 DNAT 規則，並立刻載入。橋接每次起來時會重新載入，所以開機後規則還在。
- 逐台 `pct create`，在容器裡安裝 openssh-server 和 sudo、開啟 SSH 密碼登入、建立帳號、設定隨機密碼。密碼從 stdin 傳進容器，不會出現在指令參數裡。

可以重跑：已經存在、主機名稱相符的容器會略過（密碼不變，看原本的連線資訊檔）；轉發規則每次都會整份重建。某台設定失敗時，腳本會刪掉那一台再停下來，修正問題後重跑即可。

`--stop`、`--start`、`--destroy` 只會動 `CTID_START` 起 `COUNT` 台裡、主機名稱相符的容器。`COUNT` 改小之前請先 `--destroy`，不然多出來的容器不會被處理。`--destroy` 不會刪 NAT 橋接；不需要的話，手動刪掉 `/etc/network/interfaces` 裡 `# shell-lab NAT bridge` 開頭的那一段，再 `ifreload -a`。

## 安全注意事項

- **連線資訊檔是明碼密碼。** 檔案權限是 600，也被 `.gitignore` 擋掉；發完之後請刪除。
- **不要在 PVE 主機上裝 Docker。** Docker 會把 iptables 的 FORWARD 預設政策改成 DROP，容器會上不了網，轉發也會失效。
- **LXC 和主機共用核心**，隔離比 VM 弱。容器雖然是 unprivileged，仍不適合拿來跑不受信任或具危害性的程式。
- **務必收斂 `ALLOWED_SOURCE_CIDR`。** 轉發只接受這個範圍的來源；填 `0.0.0.0/0` 等於把每台容器的 SSH 開給所有人，腳本會警告。
- 容器之間目前沒有隔離，同一個 NAT 網段裡可以互相連線，也連得到主機在 NAT 網段上的位址。

## TODO

- 用 nftables 規則隔離容器彼此，以及容器到主機和內部網段的連線（做法可以參考 NetBird 版的 `host/` 防火牆）。
- 這個方案目前只建立容器和帳號，還沒有把 `labctl/` 的題目放進容器。
