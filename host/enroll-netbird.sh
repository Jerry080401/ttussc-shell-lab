#!/bin/bash
# 讓學生 VM 加入 NetBird：裝鎖定版本的 NetBird，用這台 VM 自己的一次性 setup key 註冊，印出「學生ID IP」。
# setup key 從 stdin 讀，不放在參數裡，用完就刪。已經連上的 VM 不需要 key。
# 用法（在實驗主機上）：sudo enroll-netbird.sh student01 < key
#                       sudo enroll-netbird.sh all < 每行「學生ID key」（make enroll 會接好）
set -euo pipefail
here=$(dirname "$(readlink -f "$0")")
# shellcheck source=common.sh
. "$here/common.sh"

if [ "${1:-}" = all ]; then
    for_each_line "$0"
    exit
fi

sid=${1:?usage: enroll-netbird.sh studentNN|all}
IFS= read -r key || true
name=$(labctl vm "$sid" name)
version=$(labctl config get netbird_version)
url=$(labctl config get management_url)

if [ -n "$key" ]; then
    printf '%s\n' "$key" | incus exec "$name" -- sh -c 'umask 077; cat > /run/netbird-setup-key'
fi

ip=$(incus exec "$name" --env NB_VERSION="$version" --env NB_URL="$url" -- bash -s <<'VM'
set -euo pipefail
trap 'rm -f /run/netbird-setup-key' EXIT
if [ "$(netbird version 2>/dev/null)" != "$NB_VERSION" ]; then
    curl -fsSL https://pkgs.netbird.io/debian/public.key |
        gpg --batch --yes --dearmor -o /usr/share/keyrings/netbird-archive-keyring.gpg
    echo 'deb [signed-by=/usr/share/keyrings/netbird-archive-keyring.gpg] https://pkgs.netbird.io/debian stable main' \
        >/etc/apt/sources.list.d/netbird.list
    apt-get update -q >/dev/null
    DEBIAN_FRONTEND=noninteractive apt-get install -y -q --allow-downgrades --allow-change-held-packages \
        "netbird=$NB_VERSION" >/dev/null
    apt-mark hold netbird >/dev/null
fi
systemctl is-active --quiet netbird || { netbird service install >/dev/null 2>&1 || true; netbird service start >/dev/null; }

if ! netbird status 2>/dev/null | grep -q '^Management: Connected'; then
    [ -s /run/netbird-setup-key ] || { echo "not connected and no setup key given" >&2; exit 2; }
    netbird up --management-url "$NB_URL" --setup-key-file /run/netbird-setup-key >/dev/null
fi
for _ in $(seq 1 30); do
    netbird status 2>/dev/null | grep -q '^Management: Connected' && break
    sleep 2
done
netbird status --json | python3 -c 'import json, sys; print(json.load(sys.stdin)["netbirdIp"].split("/")[0])'
VM
)
echo "$sid $ip"
