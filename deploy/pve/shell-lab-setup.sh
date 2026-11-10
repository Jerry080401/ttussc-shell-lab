#!/bin/bash
# 在 Proxmox VE 主機上用原生 LXC 部署 shell-lab：
# 一座 NAT 橋接、N 台 Ubuntu 容器，以及「對外介面:埠 → 容器:22」的轉發規則。
#
# 用法（root）：shell-lab-setup.sh [--dry-run | --stop | --start | --destroy]
#   （無）      建立 NAT 橋接、全部容器和轉發規則，並產生連線資訊檔
#   --dry-run   只印出會做的事，不實際執行
#   --stop      關閉所有容器（保留）
#   --start     啟動所有容器
#   --destroy   刪除所有容器與轉發規則（需要確認）
#
# 設定：同目錄的 shell-lab.env（從 shell-lab.env.example 複製）會先載入，
# 沒設定的值才用下面的預設值。也可以用 ENV_FILE=路徑 指定別的設定檔。
set -euo pipefail

here=$(dirname "$(readlink -f "$0")")
ENV_FILE=${ENV_FILE:-$here/shell-lab.env}
if [ -f "$ENV_FILE" ]; then
    # shellcheck source=/dev/null
    . "$ENV_FILE"
fi

# ---- 可覆寫的設定（變數說明見 shell-lab.env.example）----
WAN_IFACE=${WAN_IFACE:-vmbr0}
PUBLIC_IP=${PUBLIC_IP:-}
ALLOWED_SOURCE_CIDR=${ALLOWED_SOURCE_CIDR:-}
NAT_BRIDGE=${NAT_BRIDGE:-vmbr1}
NAT_ADDRESS=${NAT_ADDRESS:-10.10.10.1/24}
CT_IP_OFFSET=${CT_IP_OFFSET:-101}
COUNT=${COUNT:-20}
CTID_START=${CTID_START:-201}
PORT_START=${PORT_START:-22001}
TEMPLATE_STORAGE=${TEMPLATE_STORAGE:-local}
TEMPLATE=${TEMPLATE:-ubuntu-24.04-standard_24.04-2_amd64.tar.zst}
STORAGE=${STORAGE:-local-lvm}
CT_CORES=${CT_CORES:-1}
CT_MEMORY_MB=${CT_MEMORY_MB:-1024}
CT_SWAP_MB=${CT_SWAP_MB:-512}
CT_DISK_GB=${CT_DISK_GB:-8}
CT_NAMESERVER=${CT_NAMESERVER:-}
CT_HOSTNAME_PREFIX=${CT_HOSTNAME_PREFIX:-shell-lab-}
USER_PREFIX=${USER_PREFIX:-user}
USER_SUDO=${USER_SUDO:-true}
PASSWORD_LENGTH=${PASSWORD_LENGTH:-12}
CRED_FILE=${CRED_FILE:-shell-lab-credentials.txt}
FORWARD_HOOK=${FORWARD_HOOK:-/etc/network/if-up.d/shell-lab-portforward}
DNAT_CHAIN=${DNAT_CHAIN:-SHELL_LAB_DNAT}

# 相對路徑的連線資訊檔放在腳本旁邊，才會被 .gitignore 擋到。
case $CRED_FILE in /*) ;; *) CRED_FILE=$here/$CRED_FILE ;; esac

INTERFACES=/etc/network/interfaces
BRIDGE_MARKER="# shell-lab NAT bridge (managed by shell-lab-setup.sh)"
DRY_RUN=false

# ---- 輸出 ----
if [ -t 1 ]; then
    C_BLUE=$'\e[1;34m' C_GREEN=$'\e[32m' C_YELLOW=$'\e[33m' C_RED=$'\e[31m' C_DIM=$'\e[2m' C_RESET=$'\e[0m'
else
    C_BLUE='' C_GREEN='' C_YELLOW='' C_RED='' C_DIM='' C_RESET=''
fi
step() { printf '%s==>%s %s\n' "$C_BLUE" "$C_RESET" "$*"; }
ok() { printf '    %s✓%s %s\n' "$C_GREEN" "$C_RESET" "$*"; }
warn() { printf '    %s!%s %s\n' "$C_YELLOW" "$C_RESET" "$*" >&2; }
err() { printf '%s錯誤：%s%s\n' "$C_RED" "$*" "$C_RESET" >&2; }
die() {
    err "$*"
    exit 1
}
# dry-run 時把前置檢查的失敗降成警告，方便在任何機器上預覽。
soft_die() { if $DRY_RUN; then warn "$*（dry-run，繼續）"; else die "$*"; fi; }
# 實際執行，或在 dry-run 時只印出指令。
run() {
    if $DRY_RUN; then
        printf '    %s[dry-run]%s' "$C_DIM" "$C_RESET"
        printf ' %q' "$@"
        printf '\n'
    else
        "$@"
    fi
}

usage() {
    sed -n '4,10s/^# \{0,1\}//p' "$0"
    exit "${1:-0}"
}

# ---- 網段計算 ----
ip2int() {
    local a b c d
    IFS=. read -r a b c d <<<"$1"
    echo $(((a << 24) | (b << 16) | (c << 8) | d))
}
int2ip() {
    local n=$1
    echo "$(((n >> 24) & 255)).$(((n >> 16) & 255)).$(((n >> 8) & 255)).$((n & 255))"
}

is_uint() { [[ $1 =~ ^[0-9]+$ ]]; }
is_ipv4() { [[ $1 =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; }

validate_config() {
    local name
    for name in COUNT CTID_START PORT_START CT_IP_OFFSET CT_CORES CT_MEMORY_MB CT_SWAP_MB CT_DISK_GB PASSWORD_LENGTH; do
        is_uint "${!name}" || die "$name 必須是正整數，目前是「${!name}」"
    done
    [ "$COUNT" -ge 1 ] || die "COUNT 至少要 1"
    if [ "$PASSWORD_LENGTH" -lt 8 ] || [ "$PASSWORD_LENGTH" -gt 64 ]; then
        die "PASSWORD_LENGTH 要在 8 到 64 之間"
    fi
    [ "$CTID_START" -ge 100 ] || die "CTID_START 至少要 100（PVE 的 CTID 從 100 開始）"
    [ $((PORT_START + COUNT - 1)) -le 65535 ] || die "PORT_START + COUNT 超過 65535"
    [[ $USER_PREFIX =~ ^[a-z_][a-z0-9_-]*$ ]] || die "USER_PREFIX 只能用小寫英數字、_、-，且不能以數字開頭"
    [[ $CT_HOSTNAME_PREFIX =~ ^[a-zA-Z0-9-]*$ ]] || die "CT_HOSTNAME_PREFIX 只能用英數字和 -"
    [[ $USER_SUDO =~ ^(true|false)$ ]] || die "USER_SUDO 要填 true 或 false"

    NAT_GATEWAY=${NAT_ADDRESS%/*}
    NAT_PREFIXLEN=${NAT_ADDRESS#*/}
    if ! is_ipv4 "$NAT_GATEWAY" || ! is_uint "$NAT_PREFIXLEN"; then
        die "NAT_ADDRESS 要寫成 位址/前綴長度，例如 10.10.10.1/24"
    fi
    if [ "$NAT_PREFIXLEN" -lt 8 ] || [ "$NAT_PREFIXLEN" -gt 30 ]; then
        die "NAT_ADDRESS 的前綴長度要在 8 到 30 之間"
    fi
    local gw mask bcast
    gw=$(ip2int "$NAT_GATEWAY")
    mask=$(((0xFFFFFFFF << (32 - NAT_PREFIXLEN)) & 0xFFFFFFFF))
    NAT_NET_INT=$((gw & mask))
    bcast=$((NAT_NET_INT | (~mask & 0xFFFFFFFF)))
    NAT_NETWORK=$(int2ip "$NAT_NET_INT")/$NAT_PREFIXLEN
    local first=$((NAT_NET_INT + CT_IP_OFFSET)) last=$((NAT_NET_INT + CT_IP_OFFSET + COUNT - 1))
    if [ "$CT_IP_OFFSET" -lt 1 ] || [ "$last" -ge "$bcast" ]; then
        die "容器位址 $(int2ip "$first") 起 $COUNT 個超出 $NAT_NETWORK，請調整 NAT_ADDRESS、CT_IP_OFFSET 或 COUNT"
    fi
    [ "$gw" -lt "$first" ] || [ "$gw" -gt "$last" ] || die "橋接位址 $NAT_GATEWAY 落在容器位址範圍內，請調整 CT_IP_OFFSET"
}

validate_forwarding() {
    [ -n "$ALLOWED_SOURCE_CIDR" ] ||
        die "請在設定檔填 ALLOWED_SOURCE_CIDR（允許連入的來源網段，多個用逗號分隔）"
    local cidr
    for cidr in ${ALLOWED_SOURCE_CIDR//,/ }; do
        if ! is_ipv4 "${cidr%/*}" || { [[ $cidr == */* ]] && ! [[ ${cidr#*/} =~ ^[0-9]{1,2}$ ]]; }; then
            die "ALLOWED_SOURCE_CIDR 裡的「$cidr」不是 IPv4 位址或網段"
        fi
        [ "$cidr" != 0.0.0.0/0 ] || warn "ALLOWED_SOURCE_CIDR 含 0.0.0.0/0，任何來源都連得進來，建議收斂"
    done
}

# ---- 每台容器的編號、位址、埠 ----
ct_id() { echo $((CTID_START + $1 - 1)); }
ct_port() { echo $((PORT_START + $1 - 1)); }
ct_ip() { int2ip $((NAT_NET_INT + CT_IP_OFFSET + $1 - 1)); }
ct_num() { printf '%02d' "$1"; }
ct_name() { echo "${CT_HOSTNAME_PREFIX}$(ct_num "$1")"; }
ct_user() { echo "${USER_PREFIX}$(ct_num "$1")"; }

ct_exists() { pct status "$1" >/dev/null 2>&1; }
ct_running() { [ "$(pct status "$1" 2>/dev/null)" = "status: running" ]; }
ct_hostname() { pct config "$1" | awk '/^hostname:/ {print $2}'; }

# 這個 CTID 是不是本腳本建立的第 i 台（以主機名稱判斷），避免動到範圍內的其他容器。
ct_owned() {
    local ctid=$1 i=$2
    ct_exists "$ctid" || return 1
    if [ "$(ct_hostname "$ctid")" != "$(ct_name "$i")" ]; then
        warn "CT $ctid 的主機名稱不是 $(ct_name "$i")，不是本腳本建立的，略過"
        return 1
    fi
}

# ---- 前置檢查 ----
precheck() {
    local need_template=$1
    [ "$(id -u)" -eq 0 ] || soft_die "請用 root 執行"
    command -v pct >/dev/null || soft_die "找不到 pct：這支腳本要在 Proxmox VE 主機上執行"
    if $need_template; then
        if command -v pveam >/dev/null && pveam list "$TEMPLATE_STORAGE" 2>/dev/null | grep -qF "vztmpl/$TEMPLATE"; then
            ok "樣板 $TEMPLATE_STORAGE:vztmpl/$TEMPLATE"
        else
            soft_die "$(
                printf '%s\n' "找不到 LXC 樣板 $TEMPLATE_STORAGE:vztmpl/$TEMPLATE，請先下載："
                printf '%s\n' "  pveam update"
                printf '%s\n' "  pveam available --section system | grep ubuntu-24.04"
                printf '%s' "  pveam download $TEMPLATE_STORAGE <樣板名稱>   （名稱不同的話，同步改設定檔的 TEMPLATE）"
            )"
        fi
    fi
}

resolve_public_ip() {
    if [ -z "$PUBLIC_IP" ]; then
        PUBLIC_IP=$(ip -4 -o addr show dev "$WAN_IFACE" 2>/dev/null | awk '{split($4, a, "/"); print a[1]; exit}')
        [ -n "$PUBLIC_IP" ] || {
            soft_die "取不到 $WAN_IFACE 的 IPv4 位址，請在設定檔填 PUBLIC_IP"
            PUBLIC_IP="<PUBLIC_IP>"
        }
    fi
    ok "對外介面 $WAN_IFACE，連線位址 $PUBLIC_IP"
}

# ---- NAT 橋接 ----
bridge_stanza() {
    cat <<EOF
$BRIDGE_MARKER
auto $NAT_BRIDGE
iface $NAT_BRIDGE inet static
	address $NAT_ADDRESS
	bridge-ports none
	bridge-stp off
	bridge-fd 0
	post-up   echo 1 > /proc/sys/net/ipv4/ip_forward
	post-up   iptables -t nat -A POSTROUTING -s $NAT_NETWORK -o $WAN_IFACE -j MASQUERADE
	post-down iptables -t nat -D POSTROUTING -s $NAT_NETWORK -o $WAN_IFACE -j MASQUERADE
EOF
}

setup_bridge() {
    step "NAT 橋接 $NAT_BRIDGE（$NAT_ADDRESS，經 $WAN_IFACE MASQUERADE）"
    if [ -f "$INTERFACES" ] && grep -qE "^iface[[:space:]]+$NAT_BRIDGE([[:space:]]|\$)" "$INTERFACES"; then
        if grep -qxF "$BRIDGE_MARKER" "$INTERFACES"; then
            ok "$INTERFACES 已有 $NAT_BRIDGE，略過（要改設定請先手動刪掉那一段）"
        else
            warn "$INTERFACES 已有不是本腳本建立的 $NAT_BRIDGE，沿用現有設定；請確認它是 $NAT_ADDRESS 且有做 MASQUERADE"
        fi
        return
    fi
    if $DRY_RUN; then
        printf '    %s[dry-run]%s 附加到 %s：\n' "$C_DIM" "$C_RESET" "$INTERFACES"
        bridge_stanza | sed 's/^/        /'
    else
        printf '\n%s\n' "$(bridge_stanza)" >>"$INTERFACES"
        ok "已寫入 $INTERFACES"
    fi
    run ifreload -a
}

# ---- 連接埠轉發 ----
forward_hook() {
    local i
    cat <<EOF
#!/bin/sh
# 由 shell-lab-setup.sh 產生：$WAN_IFACE 上的 TCP 埠 → 容器的 22 埠，只接受 $ALLOWED_SOURCE_CIDR。
# 重跑 shell-lab-setup.sh 會覆寫這個檔案，--destroy 會刪掉它和規則。
[ -z "\${IFACE:-}" ] || [ "\$IFACE" = "$NAT_BRIDGE" ] || [ "\$IFACE" = "--all" ] || exit 0
iptables -t nat -N $DNAT_CHAIN 2>/dev/null || true
iptables -t nat -F $DNAT_CHAIN
iptables -t nat -C PREROUTING -i $WAN_IFACE -p tcp -j $DNAT_CHAIN 2>/dev/null ||
	iptables -t nat -A PREROUTING -i $WAN_IFACE -p tcp -j $DNAT_CHAIN
EOF
    for i in $(seq 1 "$COUNT"); do
        printf 'iptables -t nat -A %s -s %s -p tcp --dport %s -j DNAT --to-destination %s:22\n' \
            "$DNAT_CHAIN" "$ALLOWED_SOURCE_CIDR" "$(ct_port "$i")" "$(ct_ip "$i")"
    done
}

setup_forwarding() {
    step "連接埠轉發 $WAN_IFACE:$PORT_START-$((PORT_START + COUNT - 1)) → 容器:22（來源 $ALLOWED_SOURCE_CIDR）"
    if $DRY_RUN; then
        printf '    %s[dry-run]%s 寫入 %s 並執行：\n' "$C_DIM" "$C_RESET" "$FORWARD_HOOK"
        forward_hook | sed 's/^/        /'
        return
    fi
    mkdir -p "$(dirname "$FORWARD_HOOK")"
    forward_hook >"$FORWARD_HOOK.new"
    chmod 755 "$FORWARD_HOOK.new"
    mv "$FORWARD_HOOK.new" "$FORWARD_HOOK"
    env -u IFACE "$FORWARD_HOOK"
    ok "規則已載入，開機時由 $FORWARD_HOOK 自動載入"
}

remove_forwarding() {
    step "移除連接埠轉發"
    iptables -t nat -D PREROUTING -i "$WAN_IFACE" -p tcp -j "$DNAT_CHAIN" 2>/dev/null || true
    iptables -t nat -F "$DNAT_CHAIN" 2>/dev/null || true
    iptables -t nat -X "$DNAT_CHAIN" 2>/dev/null || true
    rm -f "$FORWARD_HOOK"
    ok "已刪除 $DNAT_CHAIN 和 $FORWARD_HOOK"
}

# ---- 容器 ----
gen_password() {
    # 去掉容易看錯的 0 O 1 l I。
    head -c 1024 /dev/urandom | LC_ALL=C tr -dc 'A-HJ-NP-Za-km-z2-9' | cut -c "1-$PASSWORD_LENGTH"
}

create_args() {
    local i=$1 args
    args=(
        "$TEMPLATE_STORAGE:vztmpl/$TEMPLATE"
        --hostname "$(ct_name "$i")"
        --cores "$CT_CORES"
        --memory "$CT_MEMORY_MB"
        --swap "$CT_SWAP_MB"
        --rootfs "$STORAGE:$CT_DISK_GB"
        --net0 "name=eth0,bridge=$NAT_BRIDGE,ip=$(ct_ip "$i")/$NAT_PREFIXLEN,gw=$NAT_GATEWAY"
        --unprivileged 1
        --features nesting=1
        --onboot 1
        --start 1
    )
    [ -z "$CT_NAMESERVER" ] || args+=(--nameserver "$CT_NAMESERVER")
    printf '%s\0' "${args[@]}"
}

# 容器內的設定。每一步都檢查結果：這個函式在 || 裡呼叫，set -e 不會生效。
provision() {
    local ctid=$1 user=$2 port=$3 pw groups=()
    # shellcheck disable=SC2016 # 這段在容器裡展開
    pct exec "$ctid" -- sh -c 'i=0; until getent hosts archive.ubuntu.com >/dev/null; do
        i=$((i + 1)); [ "$i" -lt 30 ] || exit 1; sleep 2; done' ||
        { err "CT $ctid 連不上網路，請檢查 $NAT_BRIDGE、MASQUERADE 和 FORWARD 規則"; return 1; }
    pct exec "$ctid" -- env DEBIAN_FRONTEND=noninteractive \
        sh -c 'apt-get update -q && apt-get install -y -q openssh-server sudo' >/dev/null || return 1
    pct exec "$ctid" -- sh -c 'printf "PasswordAuthentication yes\n" >/etc/ssh/sshd_config.d/00-shell-lab.conf' || return 1
    ! $USER_SUDO || groups=(-G sudo)
    pct exec "$ctid" -- useradd -m -s /bin/bash "${groups[@]}" "$user" || return 1
    pw=$(gen_password)
    # 密碼從 stdin 傳進去，不出現在指令參數裡。
    printf '%s:%s\n' "$user" "$pw" | pct exec "$ctid" -- chpasswd || return 1
    pct exec "$ctid" -- sh -c 'systemctl enable ssh >/dev/null 2>&1; systemctl restart ssh' || return 1
    printf '%s\tssh %s@%s -p %s\t%s\n' "$user" "$user" "$PUBLIC_IP" "$port" "$pw" >>"$CRED_FILE"
}

create_containers() {
    local i ctid ip user port args
    step "建立 $COUNT 台容器（CT $CTID_START-$((CTID_START + COUNT - 1))，$CT_CORES vCPU / ${CT_MEMORY_MB}MB / ${CT_DISK_GB}GB，$STORAGE）"
    if ! $DRY_RUN && [ ! -f "$CRED_FILE" ]; then
        (
            umask 077
            printf '# shell-lab 連線資訊：含明碼密碼，發完請刪除，不要 commit。\n# 帳號\t連線指令\t密碼\n' >"$CRED_FILE"
        )
    fi
    for i in $(seq 1 "$COUNT"); do
        ctid=$(ct_id "$i") ip=$(ct_ip "$i") user=$(ct_user "$i") port=$(ct_port "$i")
        step "[$i/$COUNT] CT $ctid $(ct_name "$i")  $ip  ←  $PUBLIC_IP:$port  帳號 $user"
        if ! $DRY_RUN && ct_exists "$ctid"; then
            ct_owned "$ctid" "$i" || die "CT $ctid 已被其他容器使用，請調整 CTID_START"
            ok "已存在，略過（密碼見原本的連線資訊檔）"
            continue
        fi
        mapfile -d '' -t args < <(create_args "$i")
        run pct create "$ctid" "${args[@]}"
        if $DRY_RUN; then
            printf '    %s[dry-run]%s 容器內：安裝 openssh-server、開啟密碼登入、建立 %s%s、設隨機密碼\n' \
                "$C_DIM" "$C_RESET" "$user" "$($USER_SUDO && echo '（sudo 群組）')"
            continue
        fi
        if ! provision "$ctid" "$user" "$port"; then
            warn "CT $ctid 設定失敗，刪掉這台，修正後重跑即可"
            pct stop "$ctid" >/dev/null 2>&1 || true
            pct destroy "$ctid" --purge >/dev/null 2>&1 || true
            die "CT $ctid 建立失敗"
        fi
        ok "完成"
    done
}

each_owned() {
    local i ctid found=0
    for i in $(seq 1 "$COUNT"); do
        ctid=$(ct_id "$i")
        ct_owned "$ctid" "$i" 2>/dev/null || continue
        found=1
        "$@" "$ctid" "$i"
    done
    [ "$found" -eq 1 ] || warn "CT $CTID_START-$((CTID_START + COUNT - 1)) 裡沒有本腳本建立的容器"
}

stop_one() {
    if ct_running "$1"; then
        pct shutdown "$1" --timeout 60 || pct stop "$1"
        ok "CT $1 $(ct_name "$2") 已關閉"
    else
        ok "CT $1 $(ct_name "$2") 本來就是關的"
    fi
}

start_one() {
    if ct_running "$1"; then
        ok "CT $1 $(ct_name "$2") 已在執行"
    else
        pct start "$1"
        ok "CT $1 $(ct_name "$2") 已啟動"
    fi
}

destroy_one() {
    ct_running "$1" && pct stop "$1"
    pct destroy "$1" --purge
    ok "CT $1 $(ct_name "$2") 已刪除"
}

list_one() { printf '      CT %s  %s\n' "$1" "$(ct_name "$2")"; }

# ---- 子命令 ----
cmd_create() {
    validate_config
    validate_forwarding
    step "前置檢查"
    precheck true
    resolve_public_ip
    setup_bridge
    if ! $DRY_RUN; then
        sysctl -q -w net.ipv4.ip_forward=1
    fi
    setup_forwarding
    create_containers
    if $DRY_RUN; then
        step "dry-run 結束，沒有做任何變更"
    else
        step "完成。連線資訊：$CRED_FILE（含明碼密碼，發完請刪除）"
    fi
}

cmd_stop() {
    validate_config
    precheck false
    step "關閉容器"
    each_owned stop_one
}

cmd_start() {
    validate_config
    precheck false
    step "啟動容器"
    each_owned start_one
}

cmd_destroy() {
    local answer
    validate_config
    precheck false
    step "即將刪除下列容器（含硬碟）、轉發規則 $DNAT_CHAIN 和連線資訊檔："
    each_owned list_one
    printf '%s輸入 yes 確認刪除：%s' "$C_YELLOW" "$C_RESET"
    read -r answer || true
    [ "$answer" = yes ] || die "已取消"
    step "刪除容器"
    each_owned destroy_one
    remove_forwarding
    rm -f "$CRED_FILE"
    ok "已刪除 $CRED_FILE"
    step "完成。NAT 橋接 $NAT_BRIDGE 保留在 $INTERFACES，不需要的話手動刪掉那一段後 ifreload -a"
}

case ${1:-} in
"") cmd_create ;;
--dry-run)
    DRY_RUN=true
    cmd_create
    ;;
--stop) cmd_stop ;;
--start) cmd_start ;;
--destroy) cmd_destroy ;;
-h | --help) usage 0 ;;
*) usage 2 >&2 ;;
esac
