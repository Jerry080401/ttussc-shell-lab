#!/bin/bash
# 課程結束後：VM 關機而且不跟著主機開機，停掉 Incus、VM 隔離防火牆和閘道同步。
# 不刪 VM、硬碟和設定。要再上課時重跑 make host 和 make vms。
set -euo pipefail
here=$(dirname "$(readlink -f "$0")")
# shellcheck source=common.sh
. "$here/common.sh"

[ "$(id -u)" -eq 0 ] || die "run as root (sudo)"

disable_units() {
    local unit
    for unit in "$@"; do
        if systemctl list-unit-files --no-legend "$unit" | grep -q .; then
            systemctl disable --now "$unit" 2>/dev/null
        fi
    done
}

if systemctl -q is-active incus.service || systemctl -q is-active incus.socket; then
    # 看主機上實際有哪些這一班的 VM，不只名單上的人數，人數改少時留下來的 VM 也一起關。
    cohort=$(labctl config get cohort)
    running=()
    list=$(incus list --format csv -c n | grep -E "^${cohort}-student[0-9]{2}\$" || true)
    for name in $list; do
        incus config set "$name" boot.autostart=false
        if [ "$(incus info "$name" | awk '/^Status:/ {print $2}')" = RUNNING ]; then
            running+=("$name")
        fi
    done
    if [ "${#running[@]}" -gt 0 ]; then
        echo "== 關機：${#running[@]} 台"
        incus stop --timeout 180 "${running[@]}" || incus stop --force "${running[@]}"
    fi
    # 只停 incus.service 會留下 bridge 和 dnsmasq，incusd shutdown 才會一起收掉。
    if systemctl -q is-active incus.service; then
        timeout 300 /usr/libexec/incus/incusd shutdown
    fi
fi

echo "== 停用 Incus、防火牆和閘道同步"
disable_units incus-startup.service incus.socket incus.service incus-user.socket incus-user.service
disable_units ttussc-gateway-sync.timer ttussc-lab-firewall.service
if nft list table inet ttussc_lab >/dev/null 2>&1; then
    nft delete table inet ttussc_lab
fi
echo "完成。VM 和資料都還在，要再上課時跑 make host 和 make vms。"
