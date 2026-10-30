#!/bin/bash
# 防火牆功能測試：在「全新的 network namespace」裡模擬宿主機、兩台學生 VM 與上游網路，
# 載入 labctl 產生的 nftables 規則後實際送封包，每項輸出「<檢查名稱> reachable|blocked」。
#
# 只能由 tests/test_firewall_netns.py 透過 `unshare -n`（或 `unshare -Urn`）執行。
#
# 用法：netlab.sh RULESET SYNC_OLD_GW SYNC_NEW_GW SYNC_EMPTY RULESET_PROTECTED
#   RULESET            labctl 產生的規則，環境變數 BR1、BR2 是兩台 VM 的 bridge 名稱
#   SYNC_OLD_GW        把閘道設成 198.51.100.1 的同步腳本
#   SYNC_NEW_GW        把閘道設成 198.51.100.254 的同步腳本
#   SYNC_EMPTY         清空閘道的同步腳本
#   RULESET_PROTECTED  另外封鎖 203.0.113.0/24 的規則
#
# 位址配置：
#   vm1 10.231.0.2/28 —(BR1 10.231.0.1)— host —(BR2 10.231.0.17)— vm2 10.231.0.18/28
#   host up0 198.51.100.2/24 — lan：閘道 198.51.100.1（之後改為 .254）、區網設備 198.51.100.20、
#   「網際網路」主機 203.0.113.10 與 192.0.2.10（位於閘道後方）
set -eu

NFT=${NFT:-nft}
BR1=${BR1:?BR1 is required} BR2=${BR2:?BR2 is required}
RULESET=$1 SYNC_OLD=$2 SYNC_NEW=$3 SYNC_EMPTY=$4 RULESET_PROTECTED=$5

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
setup_ns() {
    "$@" sysctl -qw net.ipv6.conf.all.accept_dad=0 net.ipv6.conf.default.accept_dad=0
    "$@" ip link set lo up
}

VM1=$(node); VM2=$(node); LAN=$(node)
PIDS=("$VM1" "$VM2" "$LAN")

setup_ns
sysctl -qw net.ipv4.ip_forward=1
for pid in $VM1 $VM2 $LAN; do setup_ns at "$pid"; done

attach_vm() {  # pid bridge gateway/prefix address/prefix gateway host-side-veth
    ip link add "$2" type bridge
    ip link set "$2" up
    ip addr add "$3" dev "$2"
    ip link add "$6" type veth peer name eth0 netns "$1"
    ip link set "$6" master "$2" up
    at "$1" ip link set eth0 up
    at "$1" ip addr add "$4" dev eth0
    at "$1" ip route add default via "$5"
}
attach_vm "$VM1" "$BR1" 10.231.0.1/28 10.231.0.2/28 10.231.0.1 vm1tap
attach_vm "$VM2" "$BR2" 10.231.0.17/28 10.231.0.18/28 10.231.0.17 vm2tap

ip link add up0 type veth peer name eth0 netns "$LAN"
ip link set up0 up
ip addr add 198.51.100.2/24 dev up0
ip route add default via 198.51.100.1
at "$LAN" ip link set eth0 up
at "$LAN" ip addr add 198.51.100.1/24 dev eth0
at "$LAN" ip addr add 198.51.100.20/24 dev eth0
at "$LAN" ip addr add 203.0.113.10/32 dev lo
at "$LAN" ip addr add 192.0.2.10/32 dev lo
at "$LAN" ip route add 10.231.0.0/16 via 198.51.100.2

# 宿主機上的服務：SSH（22/tcp）與 DNS（53/tcp、53/udp）。
python3 - <<'PY' &
import socket, threading
def tcp(port):
    s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", port)); s.listen()
    while True:
        s.accept()[0].close()
def udp(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.bind(("0.0.0.0", port))
    while True:
        data, addr = s.recvfrom(512); s.sendto(data, addr)
for target, port in ((tcp, 22), (tcp, 53), (udp, 53)):
    threading.Thread(target=target, args=(port,), daemon=True).start()
threading.Event().wait()
PY
PIDS+=("$!")
sleep 0.5

ping_check() {  # name pid address
    if at "$2" ping -c1 -W1 "$3" >/dev/null 2>&1; then echo "$1 reachable"; else echo "$1 blocked"; fi
}
tcp_check() {  # name pid address port
    if at "$2" python3 -c 'import socket,sys; socket.create_connection((sys.argv[1], int(sys.argv[2])), timeout=1)' "$3" "$4" 2>/dev/null
    then echo "$1 reachable"; else echo "$1 blocked"; fi
}
udp_check() {  # name pid address port
    if at "$2" python3 -c '
import socket, sys
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.settimeout(1)
s.sendto(b"ping", (sys.argv[1], int(sys.argv[2]))); s.recvfrom(16)' "$3" "$4" 2>/dev/null
    then echo "$1 reachable"; else echo "$1 blocked"; fi
}
host_ll=$(ip -6 -o addr show dev "$BR1" scope link | awk '{print $4}' | cut -d/ -f1)
ping6_check() {  # name pid link-local
    if at "$2" ping -6 -c1 -W1 "$3%eth0" >/dev/null 2>&1; then echo "$1 reachable"; else echo "$1 blocked"; fi
}

"$NFT" -f "$RULESET"
"$NFT" -f "$SYNC_OLD"

ping_check vm1_internet "$VM1" 203.0.113.10
ping_check vm1_lan_host "$VM1" 198.51.100.20
ping_check vm1_gateway "$VM1" 198.51.100.1
ping_check vm1_vm2 "$VM1" 10.231.0.18
ping_check vm2_vm1 "$VM2" 10.231.0.2
tcp_check vm1_host_ssh "$VM1" 10.231.0.1 22
tcp_check vm1_host_uplink_ssh "$VM1" 198.51.100.2 22
tcp_check vm1_other_bridge_ssh "$VM1" 10.231.0.17 22
tcp_check vm1_host_dns_tcp "$VM1" 10.231.0.1 53
udp_check vm1_host_dns_udp "$VM1" 10.231.0.1 53
ping6_check vm1_host_ipv6 "$VM1" "$host_ll"
ping_check lan_to_vm1 "$LAN" 10.231.0.2

# 上游閘道換了（例如 DHCP 換網段），規則還沒同步：必須斷網（fail-closed）。
at "$LAN" ip addr add 198.51.100.254/24 dev eth0
ip route replace default via 198.51.100.254
ping_check vm1_internet_stale_gateway "$VM1" 203.0.113.10
"$NFT" -f "$SYNC_NEW"
ping_check vm1_internet_after_sync "$VM1" 203.0.113.10

"$NFT" -f "$SYNC_EMPTY"
ping_check vm1_internet_no_gateway "$VM1" 203.0.113.10

# 另外列入保護的網段（例如學校的公網位址）。
"$NFT" -f "$RULESET_PROTECTED"
"$NFT" -f "$SYNC_NEW"
ping_check vm1_protected_network "$VM1" 203.0.113.10
ping_check vm1_other_internet "$VM1" 192.0.2.10
