#!/bin/bash
# 替學生產生全部題目，放進他 VM 的 ~/lab。~/lab 已經有東西就跳過，不覆蓋學生的作業。
# 題目資料由 LAB_SECRET 推導，同一位學生每次產生的內容都一樣。
# 用法（在實驗主機上）：sudo seed-labs.sh student01
#                       sudo seed-labs.sh all
set -euo pipefail
here=$(dirname "$(readlink -f "$0")")
# shellcheck source=common.sh
. "$here/common.sh"

if [ "${1:-}" = all ]; then
    for_each_student "$0"
    exit
fi

sid=${1:?usage: seed-labs.sh studentNN|all}
name=$(labctl vm "$sid" name)

# shellcheck disable=SC2016  # $(...) 要在 VM 裡展開
if ! incus exec "$name" -- sh -c '[ ! -L /home/student/lab ] && { [ ! -e /home/student/lab ] || [ -z "$(ls -A /home/student/lab)" ]; }' </dev/null; then
    echo "$name: ~/lab is not empty, skipped"
    exit 0
fi

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
labctl labs build "$sid" --out "$tmp/lab" >/dev/null
tar -C "$tmp/lab" -cf - . | incus exec "$name" -- sh -c \
    'mkdir -p /home/student/lab && tar -C /home/student/lab --no-same-owner -xf - && chown -R student:student /home/student/lab'
count=$(incus exec "$name" -- find /home/student/lab -mindepth 1 -maxdepth 1 -type d </dev/null | wc -l)
echo "$name: seeded $count labs"
