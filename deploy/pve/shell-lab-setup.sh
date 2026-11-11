#!/bin/bash
# 在 Proxmox VE 主機上用原生 LXC 部署 shell-lab：
# 一座 NAT 橋接、每人一台 Ubuntu 容器，以及讓使用者連進容器的連線方式（access/<ACCESS_MODE>.sh）。
#
# 用法（root）：shell-lab-setup.sh [--dry-run | --passwords | --stop | --start | --destroy]
#   （無）        建立 NAT 橋接、連線方式和全部容器
#   --dry-run     只印出會做的事，不實際執行
#   --passwords   設定密碼：stdin 每行「學生ID 密碼」（labctl pve passwords-export 的輸出）
#   --stop        關閉所有容器（保留）
#   --start       啟動所有容器
#   --destroy     刪除所有容器、連線方式和容器網路，主機恢復原狀（需要確認）
#
# 設定：同目錄的 shell-lab.env（從 shell-lab.env.example 複製），由 labctl 檢查並補上預設值。
# 也可以用 ENV_FILE=路徑 指定別的設定檔。labctl 在這支腳本往上兩層的目錄（repo 根目錄）。
set -euo pipefail

here=$(dirname "$(readlink -f "$0")")
repo=$(readlink -f "$here/../..")
ENV_FILE=${ENV_FILE:-$here/shell-lab.env}

INTERFACES=/etc/network/interfaces
BRIDGE_FILE=/etc/network/interfaces.d/shell-lab
STATE_DIR=/etc/shell-lab
NETWORK_RULES=$STATE_DIR/pve-network.nft
NETWORK_UNIT=shell-lab-pve-network.service
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
    sed -n '5,11s/^# \{0,1\}//p' "$0"
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
    [ -f "$here/access/$ACCESS_MODE.sh" ] || die "找不到連線方式 $here/access/$ACCESS_MODE.sh"
    # shellcheck source=access/portforward.sh
    . "$here/access/$ACCESS_MODE.sh"
}

# 讀一位學生的容器欄位：ct_info student01 → CTID CT_NAME ADDRESS
ct_info() {
    read -r CTID CT_NAME ADDRESS < <(labctl pve ct "$1" ctid hostname address </dev/null)
}

# 這幾個函式在讀 stdin 的迴圈裡也會用到，不能把 stdin 吃掉。
ct_exists() { pct status "$1" </dev/null >/dev/null 2>&1; }
ct_running() { [ "$(pct status "$1" </dev/null 2>/dev/null)" = "status: running" ]; }
ct_hostname() { pct config "$1" </dev/null | awk '/^hostname:/ {print $2}'; }

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

# ---- 容器網路 ----
# 橋接寫成 interfaces.d 裡的獨立檔案；MASQUERADE 和 IP 轉送由 systemd 服務在容器啟動前設定。
# 第一次部署時記下原本的 ip_forward，--destroy 時設回去，主機恢復原狀。
bridge_config() {
    cat <<EOF
# 由 shell-lab-setup.sh 產生：shell-lab 容器用的 NAT 橋接。--destroy 會刪掉這個檔案。
auto $NAT_BRIDGE
iface $NAT_BRIDGE inet static
	address $NAT_GATEWAY/${NAT_SUBNET#*/}
	bridge-ports none
	bridge-stp off
	bridge-fd 0
EOF
}

network_unit() {
    cat <<EOF
# 由 shell-lab-setup.sh 產生：shell-lab 容器網路的 nftables 規則和 IP 轉送。
[Unit]
Description=shell-lab container network
Before=pve-guests.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/sbin/sysctl -q -w net.ipv4.ip_forward=1
ExecStart=/usr/sbin/nft -f $NETWORK_RULES

[Install]
WantedBy=multi-user.target
EOF
}

network_precheck() {
    command -v nft >/dev/null || soft_die "找不到 nft，請先安裝：apt install nftables"
    if ! grep -qE '^[[:space:]]*source[[:space:]]+/etc/network/interfaces\.d/\*' "$INTERFACES" 2>/dev/null; then
        soft_die "$INTERFACES 沒有 source /etc/network/interfaces.d/*，請先加上這一行"
    fi
    # 同名的橋接只能是我們自己的檔案。
    if grep -lsE "^iface[[:space:]]+$NAT_BRIDGE([[:space:]]|\$)" "$INTERFACES" /etc/network/interfaces.d/* |
        grep -qvxF "$BRIDGE_FILE"; then
        soft_die "已經有別的設定定義了 $NAT_BRIDGE，請在設定檔換一個 NAT_BRIDGE"
    fi
}

write_if_changed() {  # 路徑 內容；內容不同才寫入，回傳 0 表示有改
    local path=$1 content=$2
    if [ -f "$path" ] && [ "$(cat "$path")" = "$content" ]; then
        return 1
    fi
    printf '%s\n' "$content" >"$path.new"
    mv "$path.new" "$path"
}

setup_network() {
    step "容器網路：橋接 $NAT_BRIDGE（$NAT_GATEWAY），$NAT_SUBNET 經主機 MASQUERADE 上網"
    if $DRY_RUN; then
        printf '    %s[dry-run]%s 寫入 %s 並 ifup %s：\n' "$C_DIM" "$C_RESET" "$BRIDGE_FILE" "$NAT_BRIDGE"
        bridge_config | sed 's/^/        /'
        printf '    %s[dry-run]%s 寫入 %s：\n' "$C_DIM" "$C_RESET" "$NETWORK_RULES"
        labctl pve render-network | sed 's/^/        /'
        printf '    %s[dry-run]%s 寫入 /etc/systemd/system/%s 並啟用（打開 IP 轉送）\n' "$C_DIM" "$C_RESET" "$NETWORK_UNIT"
        return
    fi
    install -d -m 0700 "$STATE_DIR"
    [ -f "$STATE_DIR/ip_forward.orig" ] || sysctl -n net.ipv4.ip_forward >"$STATE_DIR/ip_forward.orig"

    labctl pve render-network >"$NETWORK_RULES.new"
    nft -c -f "$NETWORK_RULES.new"
    mv "$NETWORK_RULES.new" "$NETWORK_RULES"
    write_if_changed "/etc/systemd/system/$NETWORK_UNIT" "$(network_unit)" || true
    systemctl daemon-reload
    systemctl enable "$NETWORK_UNIT" >/dev/null 2>&1
    systemctl restart "$NETWORK_UNIT"
    ok "nft table shell_lab_nat 已載入，IP 轉送已打開"

    # 只啟用這座橋接，不重新套用整份網路設定。
    if write_if_changed "$BRIDGE_FILE" "$(bridge_config)"; then
        ifdown "$NAT_BRIDGE" >/dev/null 2>&1 || true
    fi
    ifup "$NAT_BRIDGE"
    ok "橋接 $NAT_BRIDGE 已啟用（$BRIDGE_FILE）"
}

remove_network() {
    local orig=0
    step "移除容器網路"
    if systemctl -q is-enabled "$NETWORK_UNIT" 2>/dev/null; then
        systemctl disable --now "$NETWORK_UNIT" >/dev/null 2>&1
    fi
    rm -f "/etc/systemd/system/$NETWORK_UNIT"
    systemctl daemon-reload
    nft delete table ip shell_lab_nat 2>/dev/null || true
    if [ -f "$BRIDGE_FILE" ]; then
        ifdown "$NAT_BRIDGE" >/dev/null 2>&1 || true
        rm -f "$BRIDGE_FILE"
    fi
    [ -f "$STATE_DIR/ip_forward.orig" ] && orig=$(cat "$STATE_DIR/ip_forward.orig")
    sysctl -q -w "net.ipv4.ip_forward=$orig"
    rm -f "$NETWORK_RULES" "$STATE_DIR/ip_forward.orig"
    rmdir "$STATE_DIR" 2>/dev/null || true
    ok "已刪除橋接 $NAT_BRIDGE、nft table shell_lab_nat 和 $NETWORK_UNIT，ip_forward 設回 $orig"
}

# ---- 容器 ----
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

# 容器內的設定：labctl pve render-guest-setup 產生的腳本，經 stdin 交給容器裡的 bash。
# 這個函式在 || 裡呼叫，set -e 不會生效，所以每一步都檢查結果。
provision() {
    local setup
    # shellcheck disable=SC2016 # 這段在容器裡展開
    pct exec "$CTID" -- sh -c 'i=0; until getent hosts archive.ubuntu.com >/dev/null; do
        i=$((i + 1)); [ "$i" -lt 30 ] || exit 1; sleep 2; done' ||
        { err "CT $CTID 連不上網路，請檢查 $NAT_BRIDGE 和 nft table shell_lab_nat"; return 1; }
    setup=$(labctl pve render-guest-setup) || return 1
    printf '%s\n' "$setup" | pct exec "$CTID" -- bash -s >/dev/null ||
        { err "CT $CTID 容器內的設定失敗（套件、sshd 或帳號）"; return 1; }
}

create_containers() {
    local i=0 args
    step "建立 ${#STUDENTS[@]} 台容器（$CT_CORES vCPU / ${CT_MEMORY_MB}MB / ${CT_DISK_GB}GB，$STORAGE）"
    for SID in "${STUDENTS[@]}"; do
        i=$((i + 1))
        ct_info "$SID"
        step "[$i/${#STUDENTS[@]}] CT $CTID $CT_NAME  $ADDRESS  ←  $(access_connect "$SID")"
        if ! $DRY_RUN && ct_exists "$CTID"; then
            ct_owned || die "CT $CTID 已被其他容器使用，請調整 CTID_START"
            ok "已存在，略過"
            continue
        fi
        mapfile -d '' -t args < <(create_args)
        run pct create "$CTID" "${args[@]}"
        if $DRY_RUN; then
            printf '    %s[dry-run]%s 容器內：執行 labctl pve render-guest-setup（套件、sshd、語系、帳號 student%s）\n' \
                "$C_DIM" "$C_RESET" "$($STUDENT_SUDO && echo '，sudo 群組')"
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
    network_precheck
    access_prepare
    setup_network
    access_apply
    create_containers
    if $DRY_RUN; then
        step "dry-run 結束，沒有做任何變更"
    else
        step "完成。下一步設定密碼：labctl pve passwords-export | $0 --passwords（make pve 會自動接好）"
    fi
}

# stdin 每行「學生ID 密碼」。密碼經 stdin 交給容器裡的 chpasswd，不出現在指令參數裡。
cmd_passwords() {
    local sid password failed=()
    precheck false
    step "設定密碼"
    while read -r sid password; do
        [ -n "$sid" ] || continue
        if ! printf '%s\n' "${STUDENTS[@]}" | grep -qxF -- "$sid"; then
            warn "$sid 不在名單上，略過"
            failed+=("$sid")
            continue
        fi
        ct_info "$sid"
        if ! ct_owned; then
            warn "$sid 的容器 CT $CTID 不存在"
            failed+=("$sid")
            continue
        fi
        if [ -n "$password" ] && printf 'student:%s\n' "$password" | pct exec "$CTID" -- chpasswd; then
            ok "CT $CTID $CT_NAME 密碼已設定"
        else
            failed+=("$sid")
        fi
    done
    [ "${#failed[@]}" -eq 0 ] || die "這些學生沒有設定成功：${failed[*]}"
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
    step "即將刪除下列容器（含硬碟）、連線方式 $ACCESS_MODE 和容器網路 $NAT_BRIDGE："
    each_owned list_one
    printf '%s輸入 yes 確認刪除：%s' "$C_YELLOW" "$C_RESET"
    read -r answer || true
    [ "$answer" = yes ] || die "已取消"
    step "刪除容器"
    each_owned destroy_one
    access_remove
    remove_network
    step "完成，主機已恢復原狀"
}

case ${1:-} in
-h | --help) usage 0 ;;
"" | --dry-run | --passwords | --stop | --start | --destroy) ;;
*) usage 2 >&2 ;;
esac
load_settings
case ${1:-} in
"") cmd_create ;;
--dry-run)
    DRY_RUN=true
    cmd_create
    ;;
--passwords) cmd_passwords ;;
--stop) cmd_stop ;;
--start) cmd_start ;;
--destroy) cmd_destroy ;;
esac
