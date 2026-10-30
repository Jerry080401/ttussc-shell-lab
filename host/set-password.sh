#!/bin/bash
# 設定學生在 VM 裡的登入密碼。密碼從 stdin 讀，不放在參數裡。
# 用法（在實驗主機上）：sudo set-password.sh student01 < password
#                       sudo set-password.sh all < 每行「學生ID 密碼」（make passwords 會接好）
set -euo pipefail
here=$(dirname "$(readlink -f "$0")")
# shellcheck source=common.sh
. "$here/common.sh"

if [ "${1:-}" = all ]; then
    for_each_line "$0"
    exit
fi

sid=${1:?usage: set-password.sh studentNN|all}
IFS= read -r password || true
[ -n "$password" ] || die "$sid: no password on stdin"
name=$(labctl vm "$sid" name)
printf 'student:%s\n' "$password" | incus exec "$name" -- chpasswd
echo "$name: password set"
