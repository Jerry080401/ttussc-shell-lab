# shellcheck shell=bash
# shellcheck disable=SC2154 # 設定和共用函式來自 shell-lab-setup.sh
# 連線方式 portforward：PORTFORWARD_IFACE 上的一個 TCP 埠對應一台容器的 22 埠，只接受 PORTFORWARD_SOURCES。
#
# 每個連線方式是 access/<ACCESS_MODE>.sh，由 shell-lab-setup.sh 載入，要提供：
#   access_prepare        前置檢查，補齊執行時才知道的值
#   access_apply          在主機上建立連線需要的東西（可以重跑）；DRY_RUN=true 時只印出來
#   access_remove         移除 access_apply 建立的東西
#   access_connect SID    印出這位學生的連線指令
# 可以用 shell-lab-setup.sh 的 step/ok/warn/soft_die/run、labctl、STUDENTS 和 ct_info。

FORWARD_HOOK=/etc/network/if-up.d/shell-lab-portforward
DNAT_CHAIN=SHELL_LAB_DNAT

access_port() {
    labctl pve ct "$1" port
}

access_prepare() {
    if [ -z "$PORTFORWARD_ADDRESS" ]; then
        PORTFORWARD_ADDRESS=$(ip -4 -o addr show dev "$PORTFORWARD_IFACE" 2>/dev/null | awk '{split($4, a, "/"); print a[1]; exit}')
        [ -n "$PORTFORWARD_ADDRESS" ] || {
            soft_die "取不到 $PORTFORWARD_IFACE 的 IPv4 位址，請在設定檔填 PORTFORWARD_ADDRESS"
            PORTFORWARD_ADDRESS="<PORTFORWARD_ADDRESS>"
        }
    fi
    ok "連線位址 $PORTFORWARD_ADDRESS（$PORTFORWARD_IFACE）"
}

access_connect() {
    printf 'ssh student@%s -p %s\n' "$PORTFORWARD_ADDRESS" "$(access_port "$1")"
}

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
            "$DNAT_CHAIN" "$PORTFORWARD_SOURCES" "$(access_port "$sid")" "$ADDRESS"
    done
}

access_apply() {
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

access_remove() {
    step "移除連接埠轉發"
    iptables -t nat -D PREROUTING -i "$PORTFORWARD_IFACE" -p tcp -j "$DNAT_CHAIN" 2>/dev/null || true
    iptables -t nat -F "$DNAT_CHAIN" 2>/dev/null || true
    iptables -t nat -X "$DNAT_CHAIN" 2>/dev/null || true
    rm -f "$FORWARD_HOOK"
    ok "已刪除 $DNAT_CHAIN 和 $FORWARD_HOOK"
}
