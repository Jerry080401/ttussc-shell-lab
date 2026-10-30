"""Small `./check` programs for labs whose answer is not the flag itself.

The flag is stored XOR-ed with a key derived from the correct answer, so it can
only be printed after the right answer is given. This keeps the flag out of
plain `grep`, although a determined student can still reverse the script
(teaching mode).
"""

import hashlib

CHECK_TEMPLATE = '''\
#!/usr/bin/env python3
"""{usage_doc}"""
import hashlib
import sys

SALT = "{salt}"
ANSWER_SHA256 = "{answer_sha256}"
SEALED_FLAG = "{sealed}"
PICTURE = {picture}


def normalize(text):
{normalize_body}

def main():
{read_answer}
    answer = normalize(answer)
    if hashlib.sha256((SALT + answer).encode("utf-8")).hexdigest() != ANSWER_SHA256:
        print("{wrong_message}")
        return 1
    key = hashlib.sha256((SALT + ":key:" + answer).encode("utf-8")).digest()
    sealed = bytes.fromhex(SEALED_FLAG)
    flag = bytes(b ^ key[i % len(key)] for i, b in enumerate(sealed)).decode("utf-8")
    print(PICTURE, end="")
    print("答對了！flag：" + flag)
    return 0


raise SystemExit(main())
'''


def seal(flag, answer, salt):
    key = hashlib.sha256((salt + ":key:" + answer).encode("utf-8")).digest()
    data = flag.encode("utf-8")
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data)).hex()


def render_check(flag, answer, salt, usage_doc, normalize_body, read_answer, wrong_message, picture):
    """Return the source of a check script. `answer` must already be normalized.

    `picture` (labctl.labs.art) is printed with the flag on a right answer.
    """
    return CHECK_TEMPLATE.format(
        usage_doc=usage_doc,
        salt=salt,
        answer_sha256=hashlib.sha256((salt + answer).encode("utf-8")).hexdigest(),
        sealed=seal(flag, answer, salt),
        normalize_body=normalize_body,
        read_answer=read_answer,
        wrong_message=wrong_message,
        picture=repr(picture),
    )
