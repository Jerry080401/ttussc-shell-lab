"""Render per-VM cloud-init user-data from a planned instance.

The output contains no passwords, keys or setup keys: user-data stays readable
inside the guest. Credentials are set later over stdin by the host tooling.
"""

import json

PACKAGES = [
    # 映像只有最小系統（ubuntu-minimal），ubuntu-standard 補上一般 Ubuntu Server 的常用工具。
    "ubuntu-standard",
    "openssh-server",
    "tree",
    "unzip",
    "xxd",  # 看檔案的位元組（「檔案格式」一章示範用），vim 只把它列為建議套件
    "man-db",
    "vim",
    "git",
    "less",
    "file",
    "python3",
    "curl",
    "ca-certificates",
    "gnupg",
]

# 繁體中文的 --help（gettext 翻譯）與 man page，GUEST_LOCALE 是 zh_TW 時才裝。
CHINESE_PACKAGES = ["language-pack-zh-hant", "manpages-zh"]

# Ubuntu 26.04 預設的 coreutils 是 uutils（Rust 版），ls、cp、chmod 等的 --help 和錯誤訊息只有英文。
# 24.04 本來就是 GNU 版，不用換。
# 換回 GNU coreutils 才會用語言包的中文翻譯。coreutils-from-uutils 標成 Protected，
# packages 清單移不掉它，所以在 runcmd 明確移除，而且要加 --allow-remove-essential。
# 開機時 apt 可能還被自動更新占用，Lock::Timeout 讓它等鎖，不會直接失敗。
SWITCH_TO_GNU_COREUTILS = [
    "env",
    "DEBIAN_FRONTEND=noninteractive",
    "apt-get",
    "install",
    "-y",
    "-o",
    "DPkg::Lock::Timeout=300",
    "--allow-remove-essential",
    "coreutils-from-gnu",
    "coreutils-from-uutils-",
]


def _sshd_dropin():
    # 放在 00- 開頭：sshd 對同一設定採第一次出現的值，優先於 cloud-init 的 50-cloud-init.conf。
    return (
        "\n".join(
            [
                "# Managed by labctl.",
                "PermitRootLogin no",
                "PasswordAuthentication yes",
                "KbdInteractiveAuthentication no",
                "AllowUsers student",
                "DisableForwarding yes",
                "PermitTunnel no",
                "PermitUserRC no",
            ]
        )
        + "\n"
    )


def _locale_profile(locale):
    lines = ["# 學生登入時的語系。要看英文原文可執行：export LANG=C.UTF-8 LANGUAGE=", f"export LANG={locale}"]
    if locale.startswith("zh_TW"):
        lines.append("export LANGUAGE=zh_TW:zh")
    return "\n".join(lines) + "\n"


def render_user_data(instance):
    """Return the #cloud-config document for one planned instance."""
    locale = instance["locale"]
    packages = PACKAGES + (CHINESE_PACKAGES if locale.startswith("zh_TW") else [])
    student = {"name": "student", "shell": "/bin/bash", "lock_passwd": True}
    if instance["sudo"]:
        # 跟一般 Ubuntu 一樣：加入 sudo 群組，使用 sudo 時輸入自己的密碼（不設 NOPASSWD）。
        student["groups"] = ["sudo"]
    doc = {
        "hostname": instance["hostname"],
        "manage_etc_hosts": True,
        "locale": locale,
        "timezone": instance["timezone"],
        # 不含 "default"：不建立映像預設的 ubuntu 帳號。
        "users": [student],
        "disable_root": True,
        "ssh_pwauth": True,
        "bootcmd": [["rm", "-f", "/etc/dpkg/dpkg.cfg.d/excludes"]],
        "package_update": True,
        "packages": packages,
        "write_files": [
            {
                "path": "/etc/ssh/sshd_config.d/00-ttussc-lab.conf",
                "owner": "root:root",
                "permissions": "0644",
                "content": _sshd_dropin(),
            },
            {
                "path": "/etc/profile.d/ttussc-locale.sh",
                "owner": "root:root",
                "permissions": "0644",
                "content": _locale_profile(locale),
            },
        ],
        # runcmd 在套件安裝之後才執行。
        "runcmd": [
            *([SWITCH_TO_GNU_COREUTILS] if instance["guest_os"] == "ubuntu-26.04" else []),
            ["install", "-d", "-m", "0700", "-o", "student", "-g", "student", "/home/student/lab"],
            ["sh", "-c", "/usr/sbin/sshd -t && systemctl restart ssh"],
        ],
    }
    # JSON 是合法的 YAML。用 json.dumps 產生，避免手寫 YAML 的引號與縮排錯誤。
    return "#cloud-config\n" + json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
