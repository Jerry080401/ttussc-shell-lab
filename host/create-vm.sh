#!/bin/bash
# 為一位學生建立 VM：專屬的 bridge、cloud-init、固定的 IP，開機後等 cloud-init 跑完。
# 重跑是安全的，已經存在的 bridge 和 VM 會跳過。
# 用法（在實驗主機上）：sudo create-vm.sh student01
#                       sudo create-vm.sh all    先建兩台試跑，都成功才一次 6 台建其他台
set -euo pipefail
here=$(dirname "$(readlink -f "$0")")
# shellcheck source=common.sh
. "$here/common.sh"

if [ "${1:-}" = all ]; then
    list=$(labctl students)
    mapfile -t students <<<"$list"
    echo "試跑：${students[*]:0:2}"
    for sid in "${students[@]:0:2}"; do
        "$0" "$sid" </dev/null
    done
    if [ "${#students[@]}" -gt 2 ]; then
        echo "試跑成功，建立其他 $((${#students[@]} - 2)) 台"
        printf '%s\n' "${students[@]:2}" | xargs -P 6 -I{} "$0" {}
    fi
    echo "全部完成"
    exit 0
fi

sid=${1:?usage: create-vm.sh studentNN|all}
read -r name bridge gateway prefix address image vcpu mem disk < <(
    labctl vm "$sid" name bridge gateway prefix address image vcpu memory_mib disk_gib
)

if ! incus network show "$bridge" >/dev/null 2>&1; then
    # DHCP 只發規劃好的那一個位址。IPv6 關掉，主機防火牆也會擋。
    # Ubuntu 24.04 的 Incus 6.0.0 還沒有 network create --description，所以不加說明。
    incus network create "$bridge" ipv4.address="$gateway/$prefix" \
        ipv4.nat=true ipv4.dhcp.ranges="$address-$address" ipv6.address=none
fi

if ! incus info "$name" >/dev/null 2>&1; then
    user_data=$(labctl render cloud-init "$sid")
    incus init "$image" "$name" --vm --storage default --network "$bridge" \
        -c limits.cpu="$vcpu" -c limits.memory="${mem}MiB" \
        -c cloud-init.user-data="$user_data" -d root,size="${disk}GiB"
    incus config device set "$name" eth0 ipv4.address="$address"
fi
# 上課期間跟著主機開機，teardown.sh 會關掉。
incus config set "$name" boot.autostart=true

if [ "$(incus info "$name" | awk '/^Status:/ {print $2}')" != RUNNING ]; then
    incus start "$name"
fi

# 等 VM 裡的 incus-agent 起來，再等 cloud-init 跑完（第一次開機要裝套件，要幾分鐘）。
for _ in $(seq 1 90); do
    incus exec "$name" -- true </dev/null 2>/dev/null && break
    sleep 2
done
incus exec "$name" -- cloud-init status --wait </dev/null >/dev/null || true
status=$(incus exec "$name" -- cloud-init status </dev/null | awk '/^status:/ {print $2}')
echo "$name cloud-init: ${status:-unknown}"
[ "$status" = "done" ]
