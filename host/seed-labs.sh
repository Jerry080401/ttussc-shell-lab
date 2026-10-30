#!/bin/bash
# 替學生產生全部題目，放進他 VM 的 ~/lab。~/lab 已經有東西就跳過，不覆蓋學生的作業。
# 指定一題時只重設那一題，舊的資料夾改名留在 ~/lab。
# 題目資料由 LAB_SECRET 推導，同一位學生每次產生的內容都一樣。
# 用法（在實驗主機上）：sudo seed-labs.sh student01
#                       sudo seed-labs.sh student01 05-organize
#                       sudo seed-labs.sh all
set -euo pipefail
here=$(dirname "$(readlink -f "$0")")
# shellcheck source=common.sh
. "$here/common.sh"

if [ "${1:-}" = all ]; then
    for_each_student "$0"
    exit
fi

sid=${1:?usage: seed-labs.sh studentNN [lab] | all}
lab=${2:-}
if [ -n "$lab" ] && ! [[ $lab =~ ^[0-9]{2}-[a-z0-9-]+$ ]]; then
    die "invalid lab name: $lab"
fi
name=$(labctl vm "$sid" name)

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
labctl labs build "$sid" --out "$tmp/lab" >/dev/null

# 用學生自己的身分解開檔案，學生在 ~/lab 裡放的連結就指不到別的地方。
as_student() {
    incus exec "$name" -- runuser -u student -- "$@"
}

if [ -n "$lab" ]; then
    [ -d "$tmp/lab/$lab" ] || die "no such lab: $lab"
    old=".$lab.old-$(date +%Y%m%d-%H%M%S)"
    # shellcheck disable=SC2016  # $1、$2 要在 VM 裡展開
    tar -C "$tmp/lab" -cf - "$lab" | as_student sh -c \
        'cd /home/student/lab && if [ -e "$1" ] || [ -L "$1" ]; then mv "$1" "$2"; fi && tar -xpf -' sh "$lab" "$old"
    echo "$name: reset $lab, the old copy is ~/lab/$old"
    exit 0
fi

# shellcheck disable=SC2016  # $(...) 要在 VM 裡展開
if ! incus exec "$name" -- sh -c '[ ! -L /home/student/lab ] && { [ ! -e /home/student/lab ] || [ -z "$(ls -A /home/student/lab)" ]; }' </dev/null; then
    echo "$name: ~/lab is not empty, skipped"
    exit 0
fi
tar -C "$tmp/lab" -cf - . | as_student sh -c 'mkdir -p /home/student/lab && tar -C /home/student/lab -xpf -'
count=$(incus exec "$name" -- find /home/student/lab -mindepth 1 -maxdepth 1 -type d </dev/null | wc -l)
echo "$name: seeded $count labs"
