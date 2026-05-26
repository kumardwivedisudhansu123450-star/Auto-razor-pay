"""
core/card_utils.py — Card parsing, generation (Luhn), BIN brand detection
"""
import random
import secrets
import string
from datetime import datetime
from typing import Dict, Generator, List, Optional, Set, Tuple

# ─── Card network detection ───────────────────────────────────────────────────

ISSUERS: Dict[str, dict] = {
    "visa":       {"pfx": ["4"],                       "len": 16, "cvv": 3},
    "mastercard": {"pfx": ["51", "52", "53", "54", "55", "2221", "2720"],
                   "len": 16, "cvv": 3},
    "amex":       {"pfx": ["34", "37"],                "len": 15, "cvv": 4},
    "discover":   {"pfx": ["6011", "65"],              "len": 16, "cvv": 3},
    "rupay":      {"pfx": ["508528", "6069", "6521"],  "len": 16, "cvv": 3},
}


def get_brand(cc: str) -> str:
    if cc.startswith("4"):
        return "visa"
    if cc[:2] in ("51", "52", "53", "54", "55") or cc[:4] in ("2221", "2720"):
        return "mastercard"
    if cc[:2] in ("34", "37"):
        return "amex"
    if cc.startswith("6011") or cc.startswith("65"):
        return "discover"
    return "unknown"


def net_display(cc: str) -> str:
    b = get_brand(cc)
    return {
        "visa":       "🟦 VISA",
        "mastercard": "🟥 MC",
        "amex":       "🟨 AMEX",
        "discover":   "🟩 DISC",
    }.get(b, "⬛ UNK")


def _issuer(b: str) -> Optional[str]:
    for name, d in ISSUERS.items():
        if any(b.startswith(p) for p in d["pfx"]):
            return name
    return None


# ─── Luhn ─────────────────────────────────────────────────────────────────────

def luhn(partial: str) -> Optional[str]:
    if not partial.isdigit():
        return None
    digits = [int(c) for c in partial]
    for i in range(len(digits) - 2, -1, -2):
        digits[i] *= 2
        if digits[i] > 9:
            digits[i] -= 9
    chk = (10 - sum(digits) % 10) % 10
    return partial + str(chk)


# ─── Card generation ──────────────────────────────────────────────────────────

def gen_card(bp: str) -> Optional[str]:
    try:
        part = bp.split("|")[0].strip().lower()
        if not all(c.isdigit() or c == "x" for c in part):
            return None

        result = "".join(
            str(random.randint(0, 9)) if c == "x" else c
            for c in part
        )
        issuer = _issuer(result)
        if not issuer:
            return None

        req = ISSUERS[issuer]["len"]
        while len(result) < req - 1:
            result += str(random.randint(0, 9))

        pan = luhn(result[: req - 1])
        if not pan or len(pan) != req:
            return None

        parts = bp.split("|")
        cy = datetime.now().year % 100

        def rnd(val, ln, lo, hi):
            if not val or val.lower() in ("rnd", "x", ""):
                return str(random.randint(lo, hi)).zfill(ln)
            if "x" in val.lower():
                return "".join(
                    str(random.randint(0, 9)) if c.lower() == "x" else c
                    for c in val
                )[-ln:].zfill(ln)
            return ("".join(c for c in val if c.isdigit()))[-ln:].zfill(ln)

        mm  = rnd(parts[1] if len(parts) > 1 else None, 2, 1, 12)
        yy  = rnd(parts[2] if len(parts) > 2 else None, 2, cy + 2, cy + 8)
        cvv = rnd(
            parts[3] if len(parts) > 3 else None,
            ISSUERS[issuer]["cvv"],
            0,
            10 ** ISSUERS[issuer]["cvv"] - 1,
        )
        return f"{pan}|{mm}|{yy}|{cvv}"
    except Exception:
        return None


def gen_cards(bp: str, count: int) -> Generator[str, None, None]:
    seen: Set[str] = set()
    att = 0
    while len(seen) < count and att < count * 15:
        att += 1
        c = gen_card(bp)
        if c and c not in seen:
            seen.add(c)
            yield c


# ─── Card parsing ─────────────────────────────────────────────────────────────

def parse_cc(s: str) -> Optional[Tuple[str, str, str, str]]:
    """Parse a card string in cc|mm|yy|cvv (or /,:, space) format."""
    for sep in ["|", "/", ":", " "]:
        p = s.strip().split(sep)
        if len(p) >= 4:
            cc  = "".join(x for x in p[0] if x.isdigit())
            mm  = "".join(x for x in p[1] if x.isdigit())
            yy  = "".join(x for x in p[2] if x.isdigit())
            cvv = "".join(x for x in p[3] if x.isdigit())
            if len(cc) >= 13 and 1 <= int(mm or "0") <= 12:
                return cc, mm, yy, cvv
    return None


# ─── BIN validation ───────────────────────────────────────────────────────────

def validate_bin(b: str) -> Tuple[bool, str]:
    part = b.split("|")[0].strip()
    if not all(c.isdigit() or c.lower() == "x" for c in part):
        return False, "Only digits and x"
    if len(part) < 4:
        return False, "Too short (min 4)"
    if len(part) > 19:
        return False, "Too long (max 19)"
    return True, ""


# ─── CC masking (for group logs — shows only BIN6 + last 2) ──────────────────

def mask_cc(cc: str) -> str:
    """Mask CC for logs — BIN6 visible, rest hidden."""
    if len(cc) >= 10:
        return f"{cc[:6]}{'●' * (len(cc) - 8)}{cc[-2:]}"
    return f"{cc[:4]}{'●' * (len(cc) - 4)}"
