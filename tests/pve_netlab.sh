#!/bin/bash
# PVE 版容器網路的功能測試：在全新的 network namespace 裡模擬 PVE 主機、兩台容器、對外網段上的
# 來源和上游閘道，載入 labctl 產生的 nftables 規則後實際連線，每項輸出「<檢查名稱> <結果>」。
#
# 只能由 tests/test_pve_netns.py 透過 `unshare -n`（或 `unshare -Urn`）執行。
#
# 用法：pve_netlab.sh NETWORK L2 ACCESS ACCESS_ONE SYNC SYNC_EMPTY
#   NETWORK      NAT 和 L3 隔離規則（PROTECTED_NETWORKS=198.51.100.0/24）
#   L2           橋接層規則；核心不支援 nft bridge family 時傳 -，相關檢查照樣執行
#   ACCESS       兩位學生的轉發規則：22001 → ct1、22002 → ct2，只接受 192.0.2.10
#   ACCESS_ONE   只剩第一位學生的轉發規則
#   SYNC         把上游閘道設成 192.0.2.254 的同步腳本
#   SYNC_EMPTY   清空閘道的同步腳本
#
# 位址配置：
#   ct1 10.10.10.2、ct2 10.10.10.3 —(vmbr1 10.10.10.1/24)— host —(vmbr0 192.0.2.1/24)—
#     client 192.0.2.10、stranger 192.0.2.20、閘道 192.0.2.254（後面有 203.0.113.10「網際網路」、
#     10.99.0.10 私有網段、10.99.0.53 私有網段裡的 DNS 伺服器、198.51.100.10 受保護網段）
# NETWORK 把 10.99.0.53 當成容器的 DNS 伺服器。
# 每個服務連上就回傳自己的名字，連不上是 blocked。
set -eu

NFT=${NFT:-nft}
NETWORK=$1 L2=$2 ACCESS=$3 ACCESS_ONE=$4 SYNC=$5 SYNC_EMPTY=$6

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

CT1=$(node); CT2=$(node); CLIENT=$(node); STRANGER=$(node); GW=$(node)
PIDS=("$CT1" "$CT2" "$CLIENT" "$STRANGER" "$GW")

ip link set lo up
sysctl -qw net.ipv4.ip_forward=1
# 和沒開 PVE 防火牆的主機一樣：橋接的流量不經過 L3 規則（br_netfilter 關閉），容器互連只能靠 L2 規則擋。
for knob in bridge-nf-call-iptables bridge-nf-call-ip6tables bridge-nf-call-arptables; do
    [ ! -e "/proc/sys/net/bridge/$knob" ] || sysctl -qw "net.bridge.$knob=0"
done
for pid in $CT1 $CT2 $CLIENT $STRANGER $GW; do at "$pid" ip link set lo up; done

# 容器端：一座橋接，兩台容器各接一個連接埠，名稱和 PVE 一樣是 veth<CTID>i0。
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

# 對外端：主機介面 vmbr0，預設路由經過閘道。
ip link add vmbr0 type bridge
ip link set vmbr0 up
ip addr add 192.0.2.1/24 dev vmbr0
ip route add default via 192.0.2.254
attach_lan() {  # pid host-side-veth address
    ip link add "$2" type veth peer name eth0 netns "$1"
    ip link set "$2" master vmbr0 up
    at "$1" ip link set eth0 up
    at "$1" ip addr add "$3/24" dev eth0
}
attach_lan "$CLIENT" client0 192.0.2.10
attach_lan "$STRANGER" strange0 192.0.2.20
attach_lan "$GW" gw0 192.0.2.254
for address in 203.0.113.10 10.99.0.10 10.99.0.53 198.51.100.10; do at "$GW" ip addr add "$address/32" dev lo; done

# 服務：連上就回傳名字。直接用 nsenter 啟動，$! 才是 python 本身，結束時殺得到。
serve() {  # pid port name（pid 為 - 表示主機自己）
    local cmd=(python3 -c '
import socket, sys
s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("0.0.0.0", int(sys.argv[1]))); s.listen()
while True:
    c = s.accept()[0]; c.sendall(sys.argv[2].encode()); c.close()' "$2" "$3")
    if [ "$1" = - ]; then "${cmd[@]}" >/dev/null 2>&1 & else nsenter --net="/proc/$1/ns/net" -- "${cmd[@]}" >/dev/null 2>&1 & fi
    PIDS+=("$!")
}
serve "$CT1" 22 ct1
serve "$CT2" 22 ct2
serve - 22 host_ssh
serve - 8006 host_webui
serve "$CLIENT" 7000 lan_host
serve "$GW" 80 net
serve "$GW" 53 dns
sleep 0.5

connect() {  # name pid address port [source]
    local got
    got=$(at "$2" python3 -c '
import socket, sys
try:
    s = socket.socket(); s.settimeout(1)
    if len(sys.argv) > 3:
        s.bind((sys.argv[3], 0))
    s.connect((sys.argv[1], int(sys.argv[2])))
    print(s.recv(16).decode() or "blocked")
except OSError:
    print("blocked")' "${@:3}")
    echo "$1 $got"
}

"$NFT" -f "$NETWORK"
[ "$L2" = - ] || "$NFT" -f "$L2"
"$NFT" -f "$ACCESS"
"$NFT" -f "$SYNC"

# 從對外網段連進容器。
connect client_22001 "$CLIENT" 192.0.2.1 22001
connect client_22002 "$CLIENT" 192.0.2.1 22002
connect client_22003 "$CLIENT" 192.0.2.1 22003
connect stranger_22001 "$STRANGER" 192.0.2.1 22001

# 從容器出去。
connect ct1_internet "$CT1" 203.0.113.10 80
connect ct1_ct2 "$CT1" 10.10.10.3 22
connect ct1_host_ssh "$CT1" 10.10.10.1 22
connect ct1_host_webui "$CT1" 10.10.10.1 8006
connect ct1_host_uplink_webui "$CT1" 192.0.2.1 8006
connect ct1_lan_host "$CT1" 192.0.2.10 7000
connect ct1_gateway "$CT1" 192.0.2.254 80
connect ct1_private "$CT1" 10.99.0.10 80
connect ct1_protected "$CT1" 198.51.100.10 80
connect ct1_dns "$CT1" 10.99.0.53 53
connect ct1_private_port_53 "$CT1" 10.99.0.10 53
connect ct1_dns_other_port "$CT1" 10.99.0.53 80

# 冒用不是自己的位址。
at "$CT2" ip addr add 10.10.10.9/24 dev eth0
connect ct2_spoofed_source "$CT2" 203.0.113.10 80 10.10.10.9

# 沒有已知的上游閘道時斷網（fail-closed），但轉發進來的 SSH 照常。
"$NFT" -f "$SYNC_EMPTY"
connect ct1_internet_no_gateway "$CT1" 203.0.113.10 80
connect client_22001_no_gateway "$CLIENT" 192.0.2.1 22001
"$NFT" -f "$SYNC"

# 重跑：同一份規則再載入一次，不會重複或失效。
"$NFT" -f "$NETWORK"
"$NFT" -f "$ACCESS"
"$NFT" -f "$SYNC"
connect reload_client_22001 "$CLIENT" 192.0.2.1 22001
connect reload_ct1_internet "$CT1" 203.0.113.10 80

# 人數變少：只更新 map，第二位的埠就不再轉發。
"$NFT" -f "$ACCESS_ONE"
connect fewer_client_22001 "$CLIENT" 192.0.2.1 22001
connect fewer_client_22002 "$CLIENT" 192.0.2.1 22002
