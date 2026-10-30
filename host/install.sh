#!/bin/bash
# 設定實驗主機：裝 Incus，載入 VM 隔離防火牆，啟用閘道同步。可以重跑，改了 STUDENT_COUNT 也要重跑。
# make host 會先把程式放到 /opt/ttussc/labs、設定放到 /etc/ttussc/lab.env，再執行這支。
set -euo pipefail
here=$(dirname "$(readlink -f "$0")")
# shellcheck source=common.sh
. "$here/common.sh"

[ "$(id -u)" -eq 0 ] || die "run as root (sudo)"
[ "$(uname -m)" = x86_64 ] || die "only x86_64 hosts are supported"
[ -e /dev/kvm ] || die "/dev/kvm is missing, this host cannot run KVM virtual machines"
# shellcheck source=/dev/null
. /etc/os-release
case "$ID $VERSION_ID" in
    "ubuntu 24.04" | "ubuntu 26.04") ;;
    *) die "only Ubuntu 24.04 and 26.04 are supported, this is $PRETTY_NAME" ;;
esac
labctl config check

echo "== 套件"
apt-get update -q
DEBIAN_FRONTEND=noninteractive apt-get install -y -q incus qemu-system-x86 qemu-utils ovmf nftables python3

echo "== VM 隔離防火牆和閘道同步"
# 防火牆要比 Incus 先起來，VM 才不會在沒有隔離的情況下開機。
install -d -m 0700 /etc/ttussc
labctl render firewall >/etc/ttussc/lab-firewall.nft.new
nft -c -f /etc/ttussc/lab-firewall.nft.new
mv /etc/ttussc/lab-firewall.nft.new /etc/ttussc/lab-firewall.nft
install -m 0755 "$here/gateway-sync" /usr/local/sbin/ttussc-gateway-sync
install -m 0644 "$here"/systemd/ttussc-* /etc/systemd/system/
systemctl daemon-reload
systemctl enable ttussc-lab-firewall.service ttussc-gateway-sync.timer
systemctl restart ttussc-lab-firewall.service
systemctl start ttussc-gateway-sync.timer

echo "== Incus"
systemctl enable --now incus.socket incus-startup.service
if ! incus storage show default >/dev/null 2>&1; then
    # 沒有先自己建 storage pool 時用 Incus 的預設值，VM 硬碟放在 /var/lib/incus。
    incus admin init --auto
fi
echo "完成，下一步：make vms"
