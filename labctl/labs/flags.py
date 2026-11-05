"""Per-student, per-lab data seeds derived from the teacher's secret.

The secret is LAB_SECRET in .env, outside Git. Seeds are reproducible, so
rebuilding a student's labs gives the same data. Bump `round_` for fresh data.
Flags are not derived: each lab has one fixed sentence (`FLAG` in its module), wrapped in FLAG_PREFIX{...}.
Decoys in labs 06 and 08 are sentences too, so only the lab's own conditions find the real one.
"""

import hashlib
import hmac

MIN_SECRET_BYTES = 32
DECOY_SUBJECTS = ("silk", "water", "rain", "wind", "leaf", "tree", "amy", "ben", "cindy", "david")
DECOY_VERBS = ("holds", "follows", "guards", "finds", "crosses", "pulls", "shakes", "helps")
DECOY_OBJECTS = ("branch", "bridge", "corner", "door", "leaf", "lamp", "lake", "circle", "line", "tree")


def _mac(secret, purpose, cohort, student_id, lab_id, round_):
    if len(secret) < MIN_SECRET_BYTES:
        raise ValueError(f"lab secret must be at least {MIN_SECRET_BYTES} bytes")
    message = "\0".join([purpose, cohort, student_id, lab_id, str(round_)]).encode()
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def derive_seed(secret, cohort, student_id, lab_id, round_=1):
    return int(_mac(secret, "seed", cohort, student_id, lab_id, round_)[:16], 16)


def decoy_flag(rng, real_flag):
    """A fake flag with the same prefix as `real_flag`, shaped like the real sentences."""
    prefix = real_flag.partition("{")[0]
    return f"{prefix}{{{rng.choice(DECOY_SUBJECTS)}_{rng.choice(DECOY_VERBS)}_the_{rng.choice(DECOY_OBJECTS)}}}"
