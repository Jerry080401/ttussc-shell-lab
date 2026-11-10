#!/bin/bash
# 在 Proxmox VE 主機上用原生 LXC 部署 shell-lab：
# 一座 NAT 橋接、每人一台 Ubuntu 容器，以及「對外介面:埠 → 容器:22」的轉發規則。
#
# 用法（root）：shell-lab-setup.sh [--dry-run | --stop | --start | --destroy]
#   （無）      建立 NAT 橋接、全部容器和轉發規則，並產生連線資訊檔
#   --dry-run   只印出會做的事，不實際執行
#   --stop      關閉所有容器（保留）
#   --start     啟動所有容器
#   --destroy   刪除所有容器與轉發規則（需要確認）
#
# 設定：同目錄的 shell-lab.env（從 shell-lab.env.example 複製），由 labctl 檢查並補上預設值。
# 也可以用 ENV_FILE=路徑 指定別的設定檔。labctl 在這支腳本往上兩層的目錄（repo 根目錄）。
set -euo pipefail

here=$(dirname "$(readlink -f "$0")")
repo=$(readlink -f "$here/../..")
ENV_FILE=${ENV_FILE:-$here/shell-lab.env}

CRED_FILE=$here/shell-lab-credentials.txt
FORWARD_HOOK=/etc/network/if-up.d/shell-lab-portforward
DNAT_CHAIN=SHELL_LAB_DNAT
INTERFACES=/etc/network/interfaces
BRIDGE_MARKER="# shell-lab NAT bridge (managed by shell-lab-setup.sh)"
PASSWORD_LENGTH=12
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
    sed -n '5,10s/^# \{0,1\}//p' "$0"
    exit "${1:-0}"
}

# ---- 設定 ----
labctl() {
    PYTHONPATH="$repo" python3 -m labctl --env "$ENV_FILE" "$@"
}

load_settings() {
    local settings
    command -v python3 >/dev/null || die "找不到 python3，請先安裝：apt install python3"
    [ -f "$repo/labctl/pve.py" ] || die "找不到 $repo/labctl，請把整個 repo（至少 labctl/ 和 deploy/pve/）放在一起"
    settings=$(labctl pve settings) || die "設定檔 $ENV_FILE 有問題，見上面的錯誤訊息"
    # labctl 只輸出檢查過的 KEY=value，值裡沒有空白、引號或 $。
    eval "$settings"
    mapfile -t STUDENTS < <(labctl pve students)
}

# 讀一位學生的容器欄位：ct_info student01 → CTID CT_NAME ADDRESS PORT
ct_info() {
    read -r CTID CT_NAME ADDRESS PORT < <(labctl pve ct "$1" ctid hostname address port)
}

ct_exists() { pct status "$1" >/dev/null 2>&1; }
ct_running() { [ "$(pct status "$1" 2>/dev/null)" = "status: running" ]; }
ct_hostname() { pct config "$1" | awk '/^hostname:/ {print $2}'; }

# 這個 CTID 是不是這位學生的容器（以主機名稱判斷），避免動到範圍內的其他容器。
ct_owned() {
    ct_exists "$CTID" || return 1
    if [ "$(ct_hostname "$CTID")" != "$CT_NAME" ]; then
        warn "CT $CTID 的主機名稱不是 $CT_NAME，不是本腳本建立的，略過"
        return 1
    fi
}

# ---- 前置檢查 ----
precheck() {
    local need_template=$1
    [ "$(id -u)" -eq 0 ] || soft_die "請用 root 執行"
    command -v pct >/dev/null || soft_die "找不到 pct：這支腳本要在 Proxmox VE 主機上執行"
    if $need_template; then
        if command -v pveam >/dev/null && pveam list "$TEMPLATE_STORAGE" 2>/dev/null | grep -qF "vztmpl/$GUEST_TEMPLATE"; then
            ok "樣板 $TEMPLATE_STORAGE:vztmpl/$GUEST_TEMPLATE"
        else
            soft_die "$(
                printf '%s\n' "找不到 LXC 樣板 $TEMPLATE_STORAGE:vztmpl/$GUEST_TEMPLATE，請先下載："
                printf '%s\n' "  pveam update"
                printf '%s\n' "  pveam available --section system | grep $GUEST_OS"
                printf '%s' "  pveam download $TEMPLATE_STORAGE <樣板名稱>   （名稱不同的話，同步改設定檔的 GUEST_TEMPLATE）"
            )"
        fi
    fi
}

resolve_address() {
    if [ -z "$PORTFORWARD_ADDRESS" ]; then
        PORTFORWARD_ADDRESS=$(ip -4 -o addr show dev "$PORTFORWARD_IFACE" 2>/dev/null | awk '{split($4, a, "/"); print a[1]; exit}')
        [ -n "$PORTFORWARD_ADDRESS" ] || {
            soft_die "取不到 $PORTFORWARD_IFACE 的 IPv4 位址，請在設定檔填 PORTFORWARD_ADDRESS"
            PORTFORWARD_ADDRESS="<PORTFORWARD_ADDRESS>"
        }
    fi
    ok "連線位址 $PORTFORWARD_ADDRESS（$PORTFORWARD_IFACE）"
}

# ---- NAT 橋接 ----
bridge_stanza() {
    cat <<EOF
$BRIDGE_MARKER
auto $NAT_BRIDGE
iface $NAT_BRIDGE inet static
	address $NAT_GATEWAY/${NAT_SUBNET#*/}
	bridge-ports none
	bridge-stp off
	bridge-fd 0
	post-up   echo 1 > /proc/sys/net/ipv4/ip_forward
	post-up   iptables -t nat -A POSTROUTING -s $NAT_SUBNET ! -o $NAT_BRIDGE -j MASQUERADE
	post-down iptables -t nat -D POSTROUTING -s $NAT_SUBNET ! -o $NAT_BRIDGE -j MASQUERADE
EOF
}

setup_bridge() {
    step "NAT 橋接 $NAT_BRIDGE（$NAT_GATEWAY，$NAT_SUBNET MASQUERADE）"
    if [ -f "$INTERFACES" ] && grep -qE "^iface[[:space:]]+$NAT_BRIDGE([[:space:]]|\$)" "$INTERFACES"; then
        if grep -qxF "$BRIDGE_MARKER" "$INTERFACES"; then
            ok "$INTERFACES 已有 $NAT_BRIDGE，略過（要改設定請先手動刪掉那一段）"
        else
            warn "$INTERFACES 已有不是本腳本建立的 $NAT_BRIDGE，沿用現有設定；請確認它是 $NAT_GATEWAY 且有做 MASQUERADE"
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
    local sid
    cat <<EOF
#!/bin/sh
# 由 shell-lab-setup.sh 產生：$PORTFORWARD_IFACE 上的 TCP 埠 → 容器的 22 埠，只接受 $PORTFORWARD_SOURCES。
# 重跑 shell-lab-setup.sh 會覆寫這個檔案，--destroy 會刪掉它和規則。
[ -z "\${IFACE:-}" ] || [ "\$IFACE" = "$NAT_BRIDGE" ] || [ "\$IFACE" = "--all" ] || exit 0
iptables -t nat -N $DNAT_CHAIN 2>/dev/null || true
iptables -t nat -F $DNAT_CHAIN
iptables -t nat -C PREROUTING -i $PORTFORWARD_IFACE -p tcp -j $DNAT_CHAIN 2>/dev/null ||
	iptables -t nat -A PREROUTING -i $PORTFORWARD_IFACE -p tcp -j $DNAT_CHAIN
EOF
    for sid in "${STUDENTS[@]}"; do
        ct_info "$sid"
        printf 'iptables -t nat -A %s -s %s -p tcp --dport %s -j DNAT --to-destination %s:22\n' \
            "$DNAT_CHAIN" "$PORTFORWARD_SOURCES" "$PORT" "$ADDRESS"
    done
}

setup_forwarding() {
    local last=$((PORTFORWARD_PORT_START + STUDENT_COUNT - 1))
    step "連接埠轉發 $PORTFORWARD_IFACE:$PORTFORWARD_PORT_START-$last → 容器:22（來源 $PORTFORWARD_SOURCES）"
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
    iptables -t nat -D PREROUTING -i "$PORTFORWARD_IFACE" -p tcp -j "$DNAT_CHAIN" 2>/dev/null || true
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
    local args
    args=(
        "$TEMPLATE_STORAGE:vztmpl/$GUEST_TEMPLATE"
        --hostname "$CT_NAME"
        --cores "$CT_CORES"
        --memory "$CT_MEMORY_MB"
        --swap "$CT_SWAP_MB"
        --rootfs "$STORAGE:$CT_DISK_GB"
        --net0 "name=eth0,bridge=$NAT_BRIDGE,ip=$ADDRESS/${NAT_SUBNET#*/},gw=$NAT_GATEWAY"
        --unprivileged 1
        # Ubuntu 24.04 的 systemd 要 nesting 才能正常啟動 systemd-networkd 等服務。
        --features nesting=1
        --onboot 1
        --start 1
    )
    [ -z "$CT_NAMESERVER" ] || args+=(--nameserver "$CT_NAMESERVER")
    printf '%s\0' "${args[@]}"
}

# 容器內的設定。每一步都檢查結果：這個函式在 || 裡呼叫，set -e 不會生效。
provision() {
    local pw groups=()
    # shellcheck disable=SC2016 # 這段在容器裡展開
    pct exec "$CTID" -- sh -c 'i=0; until getent hosts archive.ubuntu.com >/dev/null; do
        i=$((i + 1)); [ "$i" -lt 30 ] || exit 1; sleep 2; done' ||
        { err "CT $CTID 連不上網路，請檢查 $NAT_BRIDGE、MASQUERADE 和 FORWARD 規則"; return 1; }
    pct exec "$CTID" -- env DEBIAN_FRONTEND=noninteractive \
        sh -c 'apt-get update -q && apt-get install -y -q openssh-server sudo' >/dev/null || return 1
    pct exec "$CTID" -- sh -c 'printf "PasswordAuthentication yes\n" >/etc/ssh/sshd_config.d/00-shell-lab.conf' || return 1
    ! $STUDENT_SUDO || groups=(-G sudo)
    pct exec "$CTID" -- useradd -m -s /bin/bash "${groups[@]}" student || return 1
    pw=$(gen_password)
    # 密碼從 stdin 傳進去，不出現在指令參數裡。
    printf 'student:%s\n' "$pw" | pct exec "$CTID" -- chpasswd || return 1
    pct exec "$CTID" -- sh -c 'systemctl enable ssh >/dev/null 2>&1; systemctl restart ssh' || return 1
    printf '%s\tssh student@%s -p %s\t%s\n' "$SID" "$PORTFORWARD_ADDRESS" "$PORT" "$pw" >>"$CRED_FILE"
}

create_containers() {
    local i=0 args
    step "建立 ${#STUDENTS[@]} 台容器（$CT_CORES vCPU / ${CT_MEMORY_MB}MB / ${CT_DISK_GB}GB，$STORAGE）"
    if ! $DRY_RUN && [ ! -f "$CRED_FILE" ]; then
        (
            umask 077
            printf '# shell-lab 連線資訊：含明碼密碼，發完請刪除，不要 commit。\n# 學生\t連線指令\t密碼\n' >"$CRED_FILE"
        )
    fi
    for SID in "${STUDENTS[@]}"; do
        i=$((i + 1))
        ct_info "$SID"
        step "[$i/${#STUDENTS[@]}] CT $CTID $CT_NAME  $ADDRESS  ←  $PORTFORWARD_ADDRESS:$PORT"
        if ! $DRY_RUN && ct_exists "$CTID"; then
            ct_owned || die "CT $CTID 已被其他容器使用，請調整 CTID_START"
            ok "已存在，略過（密碼見原本的連線資訊檔）"
            continue
        fi
        mapfile -d '' -t args < <(create_args)
        run pct create "$CTID" "${args[@]}"
        if $DRY_RUN; then
            printf '    %s[dry-run]%s 容器內：安裝 openssh-server、開啟密碼登入、建立 student%s、設隨機密碼\n' \
                "$C_DIM" "$C_RESET" "$($STUDENT_SUDO && echo '（sudo 群組）')"
            continue
        fi
        if ! provision; then
            warn "CT $CTID 設定失敗，刪掉這台，修正後重跑即可"
            pct stop "$CTID" >/dev/null 2>&1 || true
            pct destroy "$CTID" --purge >/dev/null 2>&1 || true
            die "CT $CTID 建立失敗"
        fi
        ok "完成"
    done
}

# 對每位學生已存在、屬於本腳本的容器執行 "$@"。
each_owned() {
    local found=0
    for SID in "${STUDENTS[@]}"; do
        ct_info "$SID"
        ct_owned 2>/dev/null || continue
        found=1
        "$@"
    done
    [ "$found" -eq 1 ] || warn "沒有找到本腳本建立的容器"
}

stop_one() {
    if ct_running "$CTID"; then
        pct shutdown "$CTID" --timeout 60 || pct stop "$CTID"
        ok "CT $CTID $CT_NAME 已關閉"
    else
        ok "CT $CTID $CT_NAME 本來就是關的"
    fi
}

start_one() {
    if ct_running "$CTID"; then
        ok "CT $CTID $CT_NAME 已在執行"
    else
        pct start "$CTID"
        ok "CT $CTID $CT_NAME 已啟動"
    fi
}

destroy_one() {
    if ct_running "$CTID"; then
        pct stop "$CTID"
    fi
    pct destroy "$CTID" --purge
    ok "CT $CTID $CT_NAME 已刪除"
}

list_one() { printf '      CT %s  %s\n' "$CTID" "$CT_NAME"; }

# ---- 子命令 ----
cmd_create() {
    step "前置檢查"
    precheck true
    resolve_address
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
    precheck false
    step "關閉容器"
    each_owned stop_one
}

cmd_start() {
    precheck false
    step "啟動容器"
    each_owned start_one
}

cmd_destroy() {
    local answer
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
-h | --help) usage 0 ;;
"" | --dry-run | --stop | --start | --destroy) ;;
*) usage 2 >&2 ;;
esac
load_settings
case ${1:-} in
"") cmd_create ;;
--dry-run)
    DRY_RUN=true
    cmd_create
    ;;
--stop) cmd_stop ;;
--start) cmd_start ;;
--destroy) cmd_destroy ;;
esac
