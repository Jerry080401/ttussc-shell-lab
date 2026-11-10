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
#
# 規則由 labctl pve render-access 產生：獨立的 nft table，一條規則查 map（埠 → 容器），
# 整張 table 一次替換，重跑不會重複。開機時由 systemd 在容器啟動前載入。

ACCESS_RULES=/etc/shell-lab/pve-access.nft
ACCESS_UNIT=shell-lab-pve-access.service
ACCESS_TABLE="ip shell_lab_access"

access_port() {
    labctl pve ct "$1" port
}

access_prepare() {
    command -v nft >/dev/null || soft_die "找不到 nft，請先安裝：apt install nftables"
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

access_unit() {
    cat <<EOF
# 由 shell-lab-setup.sh 產生：載入 shell-lab 的連接埠轉發規則（nftables table $ACCESS_TABLE）。
[Unit]
Description=shell-lab port forwarding to containers
Before=pve-guests.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/sbin/nft -f $ACCESS_RULES
ExecStop=/usr/sbin/nft delete table $ACCESS_TABLE

[Install]
WantedBy=multi-user.target
EOF
}

access_apply() {
    local last=$((PORTFORWARD_PORT_START + STUDENT_COUNT - 1))
    step "連接埠轉發 $PORTFORWARD_IFACE:$PORTFORWARD_PORT_START-$last → 容器:22（來源 $PORTFORWARD_SOURCES）"
    if $DRY_RUN; then
        printf '    %s[dry-run]%s 寫入 %s：\n' "$C_DIM" "$C_RESET" "$ACCESS_RULES"
        labctl pve render-access | sed 's/^/        /'
        printf '    %s[dry-run]%s 寫入 /etc/systemd/system/%s 並啟用：\n' "$C_DIM" "$C_RESET" "$ACCESS_UNIT"
        access_unit | sed 's/^/        /'
        return
    fi
    install -d -m 0700 "$(dirname "$ACCESS_RULES")"
    labctl pve render-access >"$ACCESS_RULES.new"
    nft -c -f "$ACCESS_RULES.new"
    mv "$ACCESS_RULES.new" "$ACCESS_RULES"
    access_unit >"/etc/systemd/system/$ACCESS_UNIT"
    systemctl daemon-reload
    systemctl enable "$ACCESS_UNIT" >/dev/null 2>&1
    # 已經在執行時 restart 會先 ExecStop 刪表再重新載入；直接 nft -f 是原子替換，不會有空窗。
    if systemctl -q is-active "$ACCESS_UNIT"; then
        nft -f "$ACCESS_RULES"
    else
        systemctl start "$ACCESS_UNIT"
    fi
    ok "規則已載入（nft table $ACCESS_TABLE），開機時由 $ACCESS_UNIT 自動載入"
}

access_remove() {
    step "移除連接埠轉發"
    if systemctl -q is-enabled "$ACCESS_UNIT" 2>/dev/null; then
        systemctl disable --now "$ACCESS_UNIT" >/dev/null 2>&1
    fi
    nft delete table "$ACCESS_TABLE" 2>/dev/null || true
    rm -f "/etc/systemd/system/$ACCESS_UNIT" "$ACCESS_RULES"
    systemctl daemon-reload
    ok "已刪除 nft table $ACCESS_TABLE 和 $ACCESS_UNIT"
}
