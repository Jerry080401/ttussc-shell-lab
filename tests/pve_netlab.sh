#!/bin/bash
# PVE 版轉發規則的功能測試：在全新的 network namespace 裡模擬 PVE 主機、兩台容器和兩個來源，
# 載入 labctl 產生的 nftables 規則後實際連線，每項輸出「<檢查名稱> <結果>」。
#
# 只能由 tests/test_pve_netns.py 透過 `unshare -n`（或 `unshare -Urn`）執行。
#
# 用法：pve_netlab.sh ACCESS_RULES ACCESS_RULES_ONE_STUDENT
#   ACCESS_RULES               兩位學生的規則：22001 → ct1、22002 → ct2，只接受 192.0.2.10
#   ACCESS_RULES_ONE_STUDENT   只剩第一位學生的規則
#
# 位址配置：
#   client 192.0.2.10、stranger 192.0.2.20 —(vmbr0 192.0.2.1)— host —(vmbr1 10.10.10.1/24)— ct1 10.10.10.2、ct2 10.10.10.3
# 容器的 22 埠回傳自己的名字，連線結果是 ct1、ct2 或 blocked。
set -eu

NFT=${NFT:-nft}
RULES=$1 RULES_ONE=$2

# 安全檢查：只在只有 lo 的全新 namespace 裡執行，絕不動到真實主機的網路。
if [ "$(ip -o link show | wc -l)" -ne 1 ]; then
    echo "refusing to run: not inside a fresh network namespace" >&2
    exit 3
fi

PIDS=()
cleanup() { [ "${#PIDS[@]}" -gt 0 ] && kill "${PIDS[@]}" 2>/dev/null; true; }
trap cleanup EXIT

node() { unshare -n sleep 300 >/dev/null 2>&1 & echo $!; }
at() { local pid=$1; shift; nsenter --net="/proc/$pid/ns/net" -- "$@"; }

CT1=$(node); CT2=$(node); CLIENT=$(node); STRANGER=$(node)
PIDS=("$CT1" "$CT2" "$CLIENT" "$STRANGER")

ip link set lo up
sysctl -qw net.ipv4.ip_forward=1
for pid in $CT1 $CT2 $CLIENT $STRANGER; do at "$pid" ip link set lo up; done

# 容器端：一座橋接，兩台容器各接一個連接埠。
ip link add vmbr1 type bridge
ip link set vmbr1 up
ip addr add 10.10.10.1/24 dev vmbr1
attach_ct() {  # pid host-side-veth address
    ip link add "$2" type veth peer name eth0 netns "$1"
    ip link set "$2" master vmbr1 up
    at "$1" ip link set eth0 up
    at "$1" ip addr add "$3/24" dev eth0
    at "$1" ip route add default via 10.10.10.1
}
attach_ct "$CT1" veth201i0 10.10.10.2
attach_ct "$CT2" veth202i0 10.10.10.3

# 對外端：主機介面 vmbr0，client 和 stranger 在同一個網段。
ip link add vmbr0 type bridge
ip link set vmbr0 up
ip addr add 192.0.2.1/24 dev vmbr0
attach_peer() {  # pid host-side-veth address
    ip link add "$2" type veth peer name eth0 netns "$1"
    ip link set "$2" master vmbr0 up
    at "$1" ip link set eth0 up
    at "$1" ip addr add "$3/24" dev eth0
}
attach_peer "$CLIENT" client0 192.0.2.10
attach_peer "$STRANGER" strange0 192.0.2.20

# 每台容器的 22 埠：連上就回傳自己的名字。直接用 nsenter 啟動，$! 才是 python 本身，結束時殺得到。
serve() {  # pid name
    nsenter --net="/proc/$1/ns/net" -- python3 -c '
import socket, sys
s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("0.0.0.0", 22)); s.listen()
while True:
    c = s.accept()[0]; c.sendall(sys.argv[1].encode()); c.close()' "$2" >/dev/null 2>&1 &
    PIDS+=("$!")
}
serve "$CT1" ct1
serve "$CT2" ct2
sleep 0.5

connect() {  # name pid port
    local got
    got=$(at "$2" python3 -c '
import socket, sys
try:
    c = socket.create_connection(("192.0.2.1", int(sys.argv[1])), timeout=1)
    print(c.recv(16).decode() or "blocked")
except OSError:
    print("blocked")' "$3")
    echo "$1 $got"
}

"$NFT" -f "$RULES"
connect client_22001 "$CLIENT" 22001
connect client_22002 "$CLIENT" 22002
connect client_22003 "$CLIENT" 22003
connect stranger_22001 "$STRANGER" 22001

# 重跑：同一份規則再載入一次，不會重複或失效。
"$NFT" -f "$RULES"
connect reload_client_22001 "$CLIENT" 22001

# 人數變少：只更新 map，第二位的埠就不再轉發。
"$NFT" -f "$RULES_ONE"
connect fewer_client_22001 "$CLIENT" 22001
connect fewer_client_22002 "$CLIENT" 22002
