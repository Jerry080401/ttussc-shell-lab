"""Per-student, per-lab data seeds derived from the teacher's secret.

The secret is LAB_SECRET in .env, outside Git. Seeds are reproducible, so
rebuilding a student's labs gives the same data. Bump `round_` for fresh data.
Flags are not derived: each lab has one fixed sentence (`FLAG` in its module).
"""

import hashlib
import hmac

MIN_SECRET_BYTES = 32


def _mac(secret, purpose, cohort, student_id, lab_id, round_):
    if len(secret) < MIN_SECRET_BYTES:
        raise ValueError(f"lab secret must be at least {MIN_SECRET_BYTES} bytes")
    message = "\0".join([purpose, cohort, student_id, lab_id, str(round_)]).encode()
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def derive_seed(secret, cohort, student_id, lab_id, round_=1):
    return int(_mac(secret, "seed", cohort, student_id, lab_id, round_)[:16], 16)
