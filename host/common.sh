# shellcheck shell=bash
# host/ 底下的腳本共用：程式和設定的位置、labctl，還有「全班一起跑」的迴圈。

LAB_DIR=${LAB_DIR:-/opt/ttussc/labs}
LAB_ENV=${LAB_ENV:-/etc/ttussc/lab.env}

labctl() {
    PYTHONPATH="$LAB_DIR" python3 -m labctl --env "$LAB_ENV" "$@"
}

die() {
    echo "$*" >&2
    exit 1
}

report_failures() {
    [ "$#" -eq 0 ] && return 0
    echo "失敗：$*" >&2
    return 1
}

# 對每位學生各跑一次 "$@" 學生ID。每次都是新的 process，set -e 才會生效。
for_each_student() {
    local list sid failed=()
    list=$(labctl students)
    for sid in $list; do
        "$@" "$sid" </dev/null || failed+=("$sid")
    done
    report_failures "${failed[@]}"
}

# stdin 每行「學生ID 值」。值從 stdin 交給 "$@" 學生ID，不放進參數，用 ps 看不到。
for_each_line() {
    local sid value failed=()
    while read -r sid value; do
        [ -n "$sid" ] || continue
        printf '%s\n' "$value" | "$@" "$sid" || failed+=("$sid")
    done
    report_failures "${failed[@]}"
}
