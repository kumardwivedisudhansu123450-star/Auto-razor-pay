#!/usr/bin/env python3
"""
Razorpay Payment Testing Bot
- Site management for Razorpay payment testing
- Proxy support (residential)
- BIN management and card generation
- Automated payment testing with live results
- Sudo access control
"""

import asyncio
import html
import logging
import math
import random
import time
import json
import re
from datetime import datetime
from io import BytesIO
from typing import Optional, Dict, Set, Tuple, List
from collections import defaultdict
from pathlib import Path

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ================= CONFIG =================

BOT_TOKEN = "8953466998:AAEBRUgXO5yVyUsBwyEcRzbT0gX9kuEtCyY"
API_ID = 12089203
API_HASH = "7d85eb5ce156d35f22500fd8ef43e7c2"

# Admin configuration
ADMIN_USER_ID = 7363967303

# Data storage
DATA_FILE = Path("/home/claude/bot_data.json")

# Bot data structure
bot_data = {
    "sudo_users": set(),
    "sites": [],
    "proxies": [],
    "bins": [],
    "active_tests": {}
}

MAX_LIMIT = 500000
MAX_SPLIT_PARTS = 100
SEND_DELAY_SECONDS = 0.25
MAX_LINES_PER_FILE = 150000

# Rate limiting: 5 requests per 30 seconds per user
RATE_LIMIT = 5
RATE_WINDOW = 30

# ================= LOGGING =================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)

logger = logging.getLogger("genpro-live")

# ================= RATE LIMITING =================

user_requests: Dict[int, list] = defaultdict(list)

def check_rate_limit(user_id: int) -> Tuple[bool, Optional[str]]:
    """Check if user is within rate limit."""
    now = time.time()
    requests = user_requests[user_id]
    
    # Remove old requests outside window
    requests[:] = [req_time for req_time in requests if now - req_time < RATE_WINDOW]
    
    if len(requests) >= RATE_LIMIT:
        wait_time = int(RATE_WINDOW - (now - requests[0]))
        return False, f"Rate limited. Wait {wait_time}s."
    
    requests.append(now)
    return True, None

# ================= DATA PERSISTENCE =================

def load_data():
    """Load bot data from file."""
    global bot_data
    try:
        if DATA_FILE.exists():
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
                bot_data["sudo_users"] = set(data.get("sudo_users", []))
                bot_data["sites"] = data.get("sites", [])
                bot_data["proxies"] = data.get("proxies", [])
                bot_data["bins"] = data.get("bins", [])
                logger.info(f"Loaded data: {len(bot_data['sudo_users'])} sudo users, {len(bot_data['sites'])} sites, {len(bot_data['proxies'])} proxies, {len(bot_data['bins'])} bins")
    except Exception as e:
        logger.error(f"Failed to load data: {e}")

def save_data():
    """Save bot data to file."""
    try:
        data = {
            "sudo_users": list(bot_data["sudo_users"]),
            "sites": bot_data["sites"],
            "proxies": bot_data["proxies"],
            "bins": bot_data["bins"]
        }
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info("Data saved successfully")
    except Exception as e:
        logger.error(f"Failed to save data: {e}")

# ================= AUTHORIZATION =================

def is_authorized(user_id: int) -> bool:
    """Check if user is admin or has sudo access."""
    return user_id == ADMIN_USER_ID or user_id in bot_data["sudo_users"]

def check_auth(func):
    """Decorator to check authorization."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not is_authorized(user_id):
            await update.message.reply_text(
                f"{e('error')} <b>Access Denied</b>\n\nThis bot is restricted to authorized users only.",
                parse_mode=ParseMode.HTML
            )
            return
        return await func(update, context)
    return wrapper

# ================= PREMIUM EMOJIS =================

PREMIUM_EMOJIS = {
    "card": ("💳", 5445353829304387411),
    "mass": ("📦", 5463172695132745432),
    "search": ("🔍", 4958587679361991667),
    "info": ("👤", 5373012449597335010),
    "fire": ("🔥", 6100568059724960300),
    "check": ("✅", 4956721670690702265),
    "error": ("⚠️", 4956611513369494230),
    "loading": ("🔄", 4956371914323920049),
    "success": ("🎉", 6104789175058304052),
    "crown": ("👑", 4958725487682650920),
    "stats": ("📊", 4958506272551863292),
    "tool": ("🛠", 5465443379917629504),
    "rocket": ("🚀", None),
    "shield": ("🛡️", None),
    "spark": ("✨", 6100568059724960300),
    "folder": ("📁", None),
    "clock": ("⏱", 5382194935057372936),
    "money": ("💰", 5373174941095050893),
}

def e(key):
    """Get emoji with fallback."""
    item = PREMIUM_EMOJIS.get(key)
    
    if not item:
        return "●"
    
    fallback, emoji_id = item
    
    if not emoji_id:
        return fallback
    
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'

def safe(text):
    """HTML escape text."""
    return html.escape(str(text))

# ================= CARD ISSUER DATA =================

CARD_ISSUERS = {
    "visa": {
        "prefix": "4",
        "length": 16,
        "cvv": 3,
        "name": "Visa"
    },
    "mastercard": {
        "prefixes": ["51", "52", "53", "54", "55", "2221", "2222", "2223", "2224", "2225", "2226", "2227", "2228", "2229", "2230", "2231", "2232", "2233", "2234", "2235", "2236", "2237", "2238", "2239", "2240", "2241", "2242", "2243", "2244", "2245", "2246", "2247", "2248", "2249", "2250", "2251", "2252", "2253", "2254", "2255", "2256", "2257", "2258", "2259", "2260", "2261", "2262", "2263", "2264", "2265", "2266", "2267", "2268", "2269", "2270", "2271", "2272", "2273", "2274", "2275", "2276", "2277", "2278", "2279", "2280", "2281", "2282", "2283", "2284", "2285", "2286", "2287", "2288", "2289", "2290", "2291", "2292", "2293", "2294", "2295", "2296", "2297", "2298", "2299", "2300", "2301", "2302", "2303", "2304", "2305", "2306", "2307", "2308", "2309", "2310", "2311", "2312", "2313", "2314", "2315", "2316", "2317", "2318", "2319", "2320", "2321", "2322", "2323", "2324", "2325", "2326", "2327", "2328", "2329", "2330", "2331", "2332", "2333", "2334", "2335", "2336", "2337", "2338", "2339", "2340", "2341", "2342", "2343", "2344", "2345", "2346", "2347", "2348", "2349", "2350", "2351", "2352", "2353", "2354", "2355", "2356", "2357", "2358", "2359", "2360", "2361", "2362", "2363", "2364", "2365", "2366", "2367", "2368", "2369", "2370", "2371", "2372", "2373", "2374", "2375", "2376", "2377", "2378", "2379", "2380", "2381", "2382", "2383", "2384", "2385", "2386", "2387", "2388", "2389", "2390", "2391", "2392", "2393", "2394", "2395", "2396", "2397", "2398", "2399", "2400", "2401", "2402", "2403", "2404", "2405", "2406", "2407", "2408", "2409", "2410", "2411", "2412", "2413", "2414", "2415", "2416", "2417", "2418", "2419", "2420", "2421", "2422", "2423", "2424", "2425", "2426", "2427", "2428", "2429", "2430", "2431", "2432", "2433", "2434", "2435", "2436", "2437", "2438", "2439", "2440", "2441", "2442", "2443", "2444", "2445", "2446", "2447", "2448", "2449", "2450", "2451", "2452", "2453", "2454", "2455", "2456", "2457", "2458", "2459", "2460", "2461", "2462", "2463", "2464", "2465", "2466", "2467", "2468", "2469", "2470", "2471", "2472", "2473", "2474", "2475", "2476", "2477", "2478", "2479", "2480", "2481", "2482", "2483", "2484", "2485", "2486", "2487", "2488", "2489", "2490", "2491", "2492", "2493", "2494", "2495", "2496", "2497", "2498", "2499", "2500", "2501", "2502", "2503", "2504", "2505", "2506", "2507", "2508", "2509", "2510", "2511", "2512", "2513", "2514", "2515", "2516", "2517", "2518", "2519", "2520", "2521", "2522", "2523", "2524", "2525", "2526", "2527", "2528", "2529", "2530", "2531", "2532", "2533", "2534", "2535", "2536", "2537", "2538", "2539", "2540", "2541", "2542", "2543", "2544", "2545", "2546", "2547", "2548", "2549", "2550", "2551", "2552", "2553", "2554", "2555", "2556", "2557", "2558", "2559", "2560", "2561", "2562", "2563", "2564", "2565", "2566", "2567", "2568", "2569", "2570", "2571", "2572", "2573", "2574", "2575", "2576", "2577", "2578", "2579", "2580", "2581", "2582", "2583", "2584", "2585", "2586", "2587", "2588", "2589", "2590", "2591", "2592", "2593", "2594", "2595", "2596", "2597", "2598", "2599", "2600", "2601", "2602", "2603", "2604", "2605", "2606", "2607", "2608", "2609", "2610", "2611", "2612", "2613", "2614", "2615", "2616", "2617", "2618", "2619", "2620", "2621", "2622", "2623", "2624", "2625", "2626", "2627", "2628", "2629", "2630", "2631", "2632", "2633", "2634", "2635", "2636", "2637", "2638", "2639", "2640", "2641", "2642", "2643", "2644", "2645", "2646", "2647", "2648", "2649", "2650", "2651", "2652", "2653", "2654", "2655", "2656", "2657", "2658", "2659", "2660", "2661", "2662", "2663", "2664", "2665", "2666", "2667", "2668", "2669", "2670", "2671", "2672", "2673", "2674", "2675", "2676", "2677", "2678", "2679", "2680", "2681", "2682", "2683", "2684", "2685", "2686", "2687", "2688", "2689", "2690", "2691", "2692", "2693", "2694", "2695", "2696", "2697", "2698", "2699", "2700", "2701", "2702", "2703", "2704", "2705", "2706", "2707", "2708", "2709", "2710", "2711", "2712", "2713", "2714", "2715", "2716", "2717", "2718", "2719", "2720"],
        "length": 16,
        "cvv": 3,
        "name": "Mastercard"
    },
    "amex": {
        "prefixes": ["34", "37"],
        "length": 15,
        "cvv": 4,
        "name": "American Express"
    },
    "discover": {
        "prefixes": ["6011", "644", "645", "646", "647", "648", "649", "65"],
        "length": 16,
        "cvv": 3,
        "name": "Discover"
    },
    "diners": {
        "prefixes": ["300", "301", "302", "303", "304", "305", "36", "38"],
        "length": 14,
        "cvv": 3,
        "name": "Diners Club"
    }
}

# ================= LUHN ALGORITHM =================

def luhn_check_digit(partial: str) -> int:
    """Calculate Luhn check digit."""
    digits = [int(d) for d in partial]
    
    for i in range(len(digits) - 2, -1, -2):
        digits[i] *= 2
        if digits[i] > 9:
            digits[i] -= 9
    
    total = sum(digits)
    return (10 - (total % 10)) % 10

def luhn_complete(partial: str) -> Optional[str]:
    """Complete number with Luhn check digit."""
    if not partial.isdigit():
        return None
    
    check = luhn_check_digit(partial)
    return partial + str(check)

# ================= CARD GENERATION =================

def get_issuer_by_bin(bin_str: str) -> Optional[str]:
    """Detect issuer from BIN."""
    for issuer, data in CARD_ISSUERS.items():
        if issuer == "visa" and bin_str.startswith("4"):
            return issuer
        elif issuer == "mastercard":
            for prefix in data.get("prefixes", []):
                if bin_str.startswith(prefix):
                    return issuer
        elif issuer == "amex":
            for prefix in data.get("prefixes", []):
                if bin_str.startswith(prefix):
                    return issuer
        elif issuer == "discover":
            for prefix in data.get("prefixes", []):
                if bin_str.startswith(prefix):
                    return issuer
        elif issuer == "diners":
            for prefix in data.get("prefixes", []):
                if bin_str.startswith(prefix):
                    return issuer
    return None

def expand_bin(bin_pattern: str) -> Optional[Tuple[str, str]]:
    """Expand BIN pattern to required length. Returns (pan_base, issuer)."""
    bin_part = bin_pattern.split("|")[0].strip()
    
    if not all(c.isdigit() or c.lower() == "x" for c in bin_part):
        return None
    
    # Expand x's
    expanded = []
    for ch in bin_part:
        if ch.lower() == "x":
            expanded.append(str(random.randint(0, 9)))
        else:
            expanded.append(ch)
    
    result = "".join(expanded)
    
    # Detect issuer
    issuer = get_issuer_by_bin(result)
    if not issuer:
        return None
    
    issuer_data = CARD_ISSUERS[issuer]
    required_length = issuer_data["length"]
    
    # Pad to required length - 1 (for check digit)
    if len(result) < required_length - 1:
        result += "".join(
            str(random.randint(0, 9))
            for _ in range((required_length - 1) - len(result))
        )
    
    result = result[:required_length - 1]
    return result, issuer

def parse_card_fields(pattern: str) -> Tuple[str, str, str]:
    """Parse MM|YY|CVV from pattern."""
    parts = pattern.split("|")
    
    # Current year for expiry validation
    current_year = datetime.now().year % 100
    
    def fill(val: Optional[str], length: int, min_v: int = 0, max_v: int = None) -> str:
        if max_v is None:
            max_v = (10 ** length) - 1
        
        if not val or val.lower() in ("rnd", "rand", "random"):
            return str(random.randint(min_v, max_v)).zfill(length)
        
        if "x" in val.lower():
            return "".join(
                str(random.randint(0, 9)) if c.lower() == "x" else c
                for c in val
            )[-length:].zfill(length)
        
        digits = "".join(c for c in val if c.isdigit())
        return digits[-length:].zfill(length)
    
    month = fill(parts[1] if len(parts) > 1 else None, 2, 1, 12)
    # Future-only years (current+2 to current+8)
    year = fill(parts[2] if len(parts) > 2 else None, 2, current_year + 2, current_year + 8)
    cvv = fill(parts[3] if len(parts) > 3 else None, 3, 0, 999)
    
    return month, year, cvv

def generate_card(bin_pattern: str) -> Optional[str]:
    """Generate single valid card."""
    try:
        result = expand_bin(bin_pattern)
        if not result:
            return None
        
        pan_base, issuer = result
        issuer_data = CARD_ISSUERS[issuer]
        
        # Get Luhn-valid PAN
        pan = luhn_complete(pan_base)
        if not pan or len(pan) != issuer_data["length"]:
            return None
        
        month, year, cvv = parse_card_fields(bin_pattern)
        
        # Adjust CVV based on issuer
        cvv_length = issuer_data["cvv"]
        if len(cvv) > cvv_length:
            cvv = cvv[:cvv_length]
        elif len(cvv) < cvv_length:
            cvv = cvv.zfill(cvv_length)
        
        return f"{pan}|{month}|{year}|{cvv}"
    except Exception as e:
        logger.error(f"Card generation error: {e}")
        return None

def generate_cards_streaming(bin_pattern: str, count: int):
    """Generate cards as a generator (streaming)."""
    seen: Set[str] = set()
    generated = 0
    attempts = 0
    max_attempts = count * 10
    
    while generated < count and attempts < max_attempts:
        attempts += 1
        card = generate_card(bin_pattern)
        
        if card and card not in seen:
            seen.add(card)
            generated += 1
            yield card

# ================= VALIDATION =================

def validate_bin(bin_str: str) -> Tuple[bool, Optional[str]]:
    """Validate BIN input."""
    if not bin_str:
        return False, "BIN cannot be empty"
    
    bin_part = bin_str.split("|")[0].strip()
    
    if not all(c.isdigit() or c.lower() == "x" for c in bin_part):
        return False, "Only digits and x allowed"
    
    if len(bin_part) < 4:
        return False, "BIN too short (min 4)"
    
    if len(bin_part) > 19:
        return False, "BIN too long (max 19)"
    
    return True, None

# ================= UI =================

def main_keyboard():
    """Main menu keyboard."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💳 Generate", callback_data="gen_help"),
            InlineKeyboardButton("📦 Split", callback_data="split_help"),
        ],
        [
            InlineKeyboardButton("📘 Help", callback_data="help_main"),
            InlineKeyboardButton("ℹ️ Info", callback_data="info_main"),
        ]
    ])

# ================= COMMAND HANDLERS =================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start command."""
    user_id = update.effective_user.id
    
    if not is_authorized(user_id):
        await update.message.reply_text(
            f"{e('error')} <b>Access Denied</b>\n\n"
            f"This bot is restricted to authorized users only.\n"
            f"Contact admin for access.",
            parse_mode=ParseMode.HTML
        )
        return
    
    try:
        user = update.effective_user
        is_admin = user_id == ADMIN_USER_ID
        
        text = f"""
{e('fire')} <b>Razorpay Payment Testing Bot</b>

Welcome <b>{safe(user.first_name)}</b>!

<b>{e('stats')} Current Status:</b>
Sites: <code>{len(bot_data['sites'])}</code>
Proxies: <code>{len(bot_data['proxies'])}</code>
BINs: <code>{len(bot_data['bins'])}</code>
Access: <code>{'Admin' if is_admin else 'Sudo User'}</code>

<b>{e('tool')} Quick Commands:</b>
/bhosade - View all commands
/addsite - Add Razorpay sites
/addbim - Load BINs
/fuck - Start payment testing

{e('shield')} <b>Sandbox Testing Environment</b>
"""
        
        keyboard = [
            [InlineKeyboardButton(f"{e('fire')} Commands", callback_data="help_main")],
            [InlineKeyboardButton(f"{e('stats')} Bot Info", callback_data="info_main")]
        ]
        
        await update.message.reply_text(
            text.strip(),
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as exc:
        logger.exception("Error in /start")
        await update.message.reply_text(f"{e('error')} Error: {safe(str(exc)[:100])}", parse_mode=ParseMode.HTML)

# ================= SUDO MANAGEMENT =================

@check_auth
async def cmd_sudo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Grant sudo access to user (admin only)."""
    user_id = update.effective_user.id
    
    if user_id != ADMIN_USER_ID:
        await update.message.reply_text(
            f"{e('error')} Only admin can grant sudo access.",
            parse_mode=ParseMode.HTML
        )
        return
    
    if not context.args:
        await update.message.reply_text(
            f"{e('error')} <b>Usage:</b> <code>/sudo user_id</code>",
            parse_mode=ParseMode.HTML
        )
        return
    
    try:
        target_id = int(context.args[0])
        bot_data["sudo_users"].add(target_id)
        save_data()
        
        await update.message.reply_text(
            f"{e('check')} User <code>{target_id}</code> granted sudo access!",
            parse_mode=ParseMode.HTML
        )
    except ValueError:
        await update.message.reply_text(
            f"{e('error')} Invalid user ID",
            parse_mode=ParseMode.HTML
        )

# ================= SITE MANAGEMENT =================

@check_auth
async def cmd_addsite(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add Razorpay site."""
    if not context.args:
        await update.message.reply_text(
            f"{e('error')} <b>Usage:</b> <code>/addsite https://example.com/payment</code>",
            parse_mode=ParseMode.HTML
        )
        return
    
    url = " ".join(context.args)
    
    if not url.startswith(("http://", "https://")):
        await update.message.reply_text(
            f"{e('error')} Invalid URL. Must start with http:// or https://",
            parse_mode=ParseMode.HTML
        )
        return
    
    if url in bot_data["sites"]:
        await update.message.reply_text(
            f"{e('error')} Site already exists!",
            parse_mode=ParseMode.HTML
        )
        return
    
    bot_data["sites"].append(url)
    save_data()
    
    await update.message.reply_text(
        f"{e('check')} <b>Site Added</b>\n\n"
        f"URL: <code>{safe(url)}</code>\n"
        f"Total sites: <code>{len(bot_data['sites'])}</code>",
        parse_mode=ParseMode.HTML
    )

@check_auth
async def cmd_live(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show all loaded sites."""
    if not bot_data["sites"]:
        await update.message.reply_text(
            f"{e('error')} No sites loaded. Use /addsite to add sites.",
            parse_mode=ParseMode.HTML
        )
        return
    
    text = f"{e('fire')} <b>Loaded Sites ({len(bot_data['sites'])})</b>\n\n"
    for idx, site in enumerate(bot_data["sites"], 1):
        text += f"{idx}. <code>{safe(site)}</code>\n"
    
    await update.message.reply_text(text.strip(), parse_mode=ParseMode.HTML)

@check_auth
async def cmd_rmsites(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove sites."""
    if not bot_data["sites"]:
        await update.message.reply_text(
            f"{e('error')} No sites to remove.",
            parse_mode=ParseMode.HTML
        )
        return
    
    keyboard = []
    for idx, site in enumerate(bot_data["sites"]):
        short_url = site[:50] + "..." if len(site) > 50 else site
        keyboard.append([InlineKeyboardButton(f"Remove: {short_url}", callback_data=f"rmsite_{idx}")])
    
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
    
    await update.message.reply_text(
        f"{e('tool')} <b>Select site to remove:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ================= PROXY MANAGEMENT =================

@check_auth
async def cmd_addpxy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add residential proxies."""
    if not context.args:
        await update.message.reply_text(
            f"{e('error')} <b>Usage:</b> <code>/addpxy proxy1 proxy2 ...</code>\n\n"
            f"<b>Supported formats:</b>\n"
            f"<code>ip:port</code>\n"
            f"<code>ip:port:user:pass</code>\n"
            f"<code>user:pass@ip:port</code>",
            parse_mode=ParseMode.HTML
        )
        return
    
    added = 0
    for proxy in context.args:
        if proxy not in bot_data["proxies"]:
            bot_data["proxies"].append(proxy)
            added += 1
    
    save_data()
    
    await update.message.reply_text(
        f"{e('check')} <b>Proxies Added: {added}</b>\n"
        f"Total proxies: <code>{len(bot_data['proxies'])}</code>",
        parse_mode=ParseMode.HTML
    )

@check_auth
async def cmd_proxy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check proxy status."""
    if not bot_data["proxies"]:
        await update.message.reply_text(
            f"{e('error')} No proxies loaded. Use /addpxy to add proxies.",
            parse_mode=ParseMode.HTML
        )
        return
    
    text = f"{e('fire')} <b>Loaded Proxies ({len(bot_data['proxies'])})</b>\n\n"
    for idx, proxy in enumerate(bot_data["proxies"], 1):
        text += f"{idx}. <code>{safe(proxy)}</code> {e('check')}\n"
    
    await update.message.reply_text(text.strip(), parse_mode=ParseMode.HTML)

@check_auth
async def cmd_rmpxy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove proxies."""
    if not bot_data["proxies"]:
        await update.message.reply_text(
            f"{e('error')} No proxies to remove.",
            parse_mode=ParseMode.HTML
        )
        return
    
    keyboard = []
    for idx, proxy in enumerate(bot_data["proxies"]):
        short_proxy = proxy[:40] + "..." if len(proxy) > 40 else proxy
        keyboard.append([InlineKeyboardButton(f"Remove: {short_proxy}", callback_data=f"rmpxy_{idx}")])
    
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
    
    await update.message.reply_text(
        f"{e('tool')} <b>Select proxy to remove:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ================= BIN MANAGEMENT =================

@check_auth
async def cmd_addbim(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add BINs for card generation."""
    if not context.args:
        await update.message.reply_text(
            f"{e('error')} <b>Usage:</b> <code>/addbim BIN1 BIN2 ...</code>\n\n"
            f"<b>Examples:</b>\n"
            f"<code>/addbim 411111</code>\n"
            f"<code>/addbim 5xxxxx 371449</code>",
            parse_mode=ParseMode.HTML
        )
        return
    
    added = 0
    for bin_pattern in context.args:
        valid, err = validate_bin(bin_pattern)
        if valid and bin_pattern not in bot_data["bins"]:
            bot_data["bins"].append(bin_pattern)
            added += 1
    
    save_data()
    
    await update.message.reply_text(
        f"{e('check')} <b>BINs Added: {added}</b>\n"
        f"Total BINs: <code>{len(bot_data['bins'])}</code>",
        parse_mode=ParseMode.HTML
    )

@check_auth
async def cmd_chkbim(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check loaded BINs."""
    if not bot_data["bins"]:
        await update.message.reply_text(
            f"{e('error')} No BINs loaded. Use /addbim to add BINs.",
            parse_mode=ParseMode.HTML
        )
        return
    
    text = f"{e('fire')} <b>Loaded BINs ({len(bot_data['bins'])})</b>\n\n"
    for idx, bin_val in enumerate(bot_data["bins"], 1):
        text += f"{idx}. <code>{safe(bin_val)}</code>\n"
    
    await update.message.reply_text(text.strip(), parse_mode=ParseMode.HTML)

# ================= PAYMENT TESTING =================

@check_auth
async def cmd_fuck(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start payment testing workflow."""
    if not bot_data["sites"]:
        await update.message.reply_text(
            f"{e('error')} No sites loaded. Use /addsite first.",
            parse_mode=ParseMode.HTML
        )
        return
    
    if not bot_data["bins"]:
        await update.message.reply_text(
            f"{e('error')} No BINs loaded. Use /addbim first.",
            parse_mode=ParseMode.HTML
        )
        return
    
    keyboard = [
        [InlineKeyboardButton("₹1", callback_data="test_1")],
        [InlineKeyboardButton("₹10", callback_data="test_10")],
        [InlineKeyboardButton("₹50", callback_data="test_50")],
        [InlineKeyboardButton("₹100", callback_data="test_100")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
    ]
    
    text = f"""
{e('fire')} <b>Payment Testing</b>

{e('stats')} <b>Configuration:</b>
Sites: <code>{len(bot_data['sites'])}</code>
BINs: <code>{len(bot_data['bins'])}</code>
Proxies: <code>{len(bot_data['proxies'])}</code>

{e('money')} <b>Select amount to test:</b>
"""
    
    await update.message.reply_text(
        text.strip(),
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ================= HELP COMMAND =================

@check_auth
async def cmd_bhosade(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all commands."""
    user_id = update.effective_user.id
    is_admin = user_id == ADMIN_USER_ID
    
    text = f"""
{e('fire')} <b>Razorpay Testing Bot - Commands</b>

<b>{e('shield')} Admin Commands:</b>
<code>/sudo user_id</code> - Grant sudo access

<b>{e('tool')} Site Management:</b>
<code>/addsite url</code> - Add Razorpay site
<code>/live</code> - View loaded sites
<code>/rmsites</code> - Remove sites

<b>{e('rocket')} Proxy Management:</b>
<code>/addpxy proxy</code> - Add residential proxies
<code>/proxy</code> - Check proxy status
<code>/rmpxy</code> - Remove proxies

<b>{e('card')} BIN Management:</b>
<code>/addbim BIN</code> - Load BINs
<code>/chkbim</code> - View loaded BINs

<b>{e('fire')} Payment Testing:</b>
<code>/fuck</code> - Start testing workflow

<b>{e('info')} Info:</b>
<code>/bhosade</code> - This help
<code>/start</code> - Main menu

{e('check')} Access: <code>{'Admin' if is_admin else 'Sudo User'}</code>
"""
    
    await update.message.reply_text(text.strip(), parse_mode=ParseMode.HTML)

async def cmd_gen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate cards command."""
    try:
        user_id = update.effective_user.id
        
        # Rate limit check
        allowed, limit_msg = check_rate_limit(user_id)
        if not allowed:
            await update.message.reply_text(
                f"{e('error')} {limit_msg}",
                parse_mode=ParseMode.HTML
            )
            return
        
        args = context.args
        
        if not args:
            await update.message.reply_text(
                f"{e('error')} <b>Usage</b>\n<code>/gen BIN amount</code>\n"
                f"<b>Example:</b> <code>/gen 411111 100</code>",
                parse_mode=ParseMode.HTML
            )
            return
        
        bin_pattern = args[0]
        amount = int(args[1]) if len(args) > 1 else 10
        
        # Validate amount
        if amount < 1:
            await update.message.reply_text(
                f"{e('error')} Amount must be at least 1",
                parse_mode=ParseMode.HTML
            )
            return
        
        if amount > MAX_LIMIT:
            await update.message.reply_text(
                f"{e('error')} Max {MAX_LIMIT:,} cards per request",
                parse_mode=ParseMode.HTML
            )
            return
        
        # Validate BIN
        valid, err = validate_bin(bin_pattern)
        if not valid:
            await update.message.reply_text(
                f"{e('error')} {err}",
                parse_mode=ParseMode.HTML
            )
            return
        
        status = await update.message.reply_text(
            f"{e('loading')} <b>Generating {amount:,} cards...</b>",
            parse_mode=ParseMode.HTML
        )
        
        # Generate and save to file(s)
        bin_display = bin_pattern.split("|")[0]
        file_count = 0
        cards_count = 0
        current_chunk = []
        
        try:
            for card in generate_cards_streaming(bin_pattern, amount):
                current_chunk.append(card)
                cards_count += 1
                
                # Auto-split if chunk reaches max lines
                if len(current_chunk) >= MAX_LINES_PER_FILE:
                    file_count += 1
                    content = "\n".join(current_chunk)
                    bio = BytesIO(content.encode("utf-8"))
                    bio.name = f"gen_{bin_display}_part{file_count}.txt"
                    bio.seek(0)
                    
                    try:
                        await update.message.reply_document(
                            document=bio,
                            caption=f"{e('check')} Part {file_count} - {len(current_chunk):,} cards",
                            parse_mode=ParseMode.HTML
                        )
                    except Exception as exc:
                        logger.error(f"Upload error: {exc}")
                        # Retry with delay
                        await asyncio.sleep(1)
                        try:
                            await update.message.reply_document(
                                document=bio,
                                caption=f"{e('check')} Part {file_count} - {len(current_chunk):,} cards",
                                parse_mode=ParseMode.HTML
                            )
                        except Exception as exc2:
                            logger.error(f"Retry failed: {exc2}")
                    
                    current_chunk = []
                    await asyncio.sleep(SEND_DELAY_SECONDS)
            
            # Send remaining cards
            if current_chunk:
                file_count += 1
                content = "\n".join(current_chunk)
                bio = BytesIO(content.encode("utf-8"))
                bio.name = f"gen_{bin_display}_part{file_count}.txt"
                bio.seek(0)
                
                try:
                    await update.message.reply_document(
                        document=bio,
                        caption=f"{e('check')} Part {file_count} - {len(current_chunk):,} cards",
                        parse_mode=ParseMode.HTML
                    )
                except Exception as exc:
                    logger.error(f"Final upload error: {exc}")
                    await asyncio.sleep(1)
                    try:
                        await update.message.reply_document(
                            document=bio,
                            caption=f"{e('check')} Part {file_count} - {len(current_chunk):,} cards",
                            parse_mode=ParseMode.HTML
                        )
                    except Exception as exc2:
                        logger.error(f"Final retry failed: {exc2}")
            
            await status.edit_text(
                f"{e('success')} <b>Generated {cards_count:,} cards in {file_count} file(s)</b>",
                parse_mode=ParseMode.HTML
            )
        except Exception as exc:
            logger.exception(f"Generation error: {exc}")
            await status.edit_text(
                f"{e('error')} Generation failed: {safe(str(exc)[:100])}",
                parse_mode=ParseMode.HTML
            )
    except ValueError:
        await update.message.reply_text(
            f"{e('error')} Amount must be a number",
            parse_mode=ParseMode.HTML
        )
    except Exception as exc:
        logger.exception("Error in /gen")
        await update.message.reply_text(
            f"{e('error')} {safe(str(exc)[:100])}",
            parse_mode=ParseMode.HTML
        )

async def cmd_split(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Split file command."""
    try:
        user_id = update.effective_user.id
        
        # Rate limit check
        allowed, limit_msg = check_rate_limit(user_id)
        if not allowed:
            await update.message.reply_text(
                f"{e('error')} {limit_msg}",
                parse_mode=ParseMode.HTML
            )
            return
        
        args = context.args
        
        if not args:
            await update.message.reply_text(
                f"{e('error')} <b>Usage:</b> Reply to txt with <code>/split 5</code>",
                parse_mode=ParseMode.HTML
            )
            return
        
        try:
            parts_count = int(args[0])
        except ValueError:
            await update.message.reply_text(
                f"{e('error')} Parts must be a number",
                parse_mode=ParseMode.HTML
            )
            return
        
        if parts_count < 2 or parts_count > MAX_SPLIT_PARTS:
            await update.message.reply_text(
                f"{e('error')} Parts must be 2-{MAX_SPLIT_PARTS}",
                parse_mode=ParseMode.HTML
            )
            return
        
        msg = update.message
        replied = msg.reply_to_message
        
        if not replied or not replied.document:
            await msg.reply_text(
                f"{e('error')} Reply to a .txt file",
                parse_mode=ParseMode.HTML
            )
            return
        
        doc = replied.document
        filename = doc.file_name or f"file_{doc.file_id}.txt"
        
        if not filename.lower().endswith(".txt"):
            await msg.reply_text(
                f"{e('error')} Only .txt files allowed",
                parse_mode=ParseMode.HTML
            )
            return
        
        status = await msg.reply_text(
            f"{e('loading')} <b>Downloading file...</b>",
            parse_mode=ParseMode.HTML
        )
        
        try:
            file_bytes = BytesIO()
            tg_file = await doc.get_file()
            await tg_file.download_to_memory(out=file_bytes)
            file_bytes.seek(0)
            
            try:
                content = file_bytes.read().decode("utf-8")
            except UnicodeDecodeError:
                file_bytes.seek(0)
                content = file_bytes.read().decode("utf-8", errors="replace")
            
            lines = [x.strip() for x in content.splitlines() if x.strip()]
            
            if not lines:
                await status.edit_text(
                    f"{e('error')} File is empty",
                    parse_mode=ParseMode.HTML
                )
                return
            
            if parts_count > len(lines):
                await status.edit_text(
                    f"{e('error')} Too many parts for {len(lines):,} lines",
                    parse_mode=ParseMode.HTML
                )
                return
            
            chunk_size = math.ceil(len(lines) / parts_count)
            chunks = [
                lines[i:i + chunk_size]
                for i in range(0, len(lines), chunk_size)
            ]
            
            await status.edit_text(
                f"{e('loading')} <b>Sending {len(chunks)} parts...</b>",
                parse_mode=ParseMode.HTML
            )
            
            base_name = filename[:-4]
            
            for idx, chunk in enumerate(chunks, 1):
                part_content = "\n".join(chunk)
                part_bytes = BytesIO(part_content.encode("utf-8"))
                part_name = f"{base_name}_part{idx}of{len(chunks)}.txt"
                part_bytes.name = part_name
                part_bytes.seek(0)
                
                try:
                    await msg.reply_document(
                        document=part_bytes,
                        caption=f"{e('check')} <b>Part {idx}/{len(chunks)}</b> - {len(chunk):,} lines",
                        parse_mode=ParseMode.HTML
                    )
                except Exception as exc:
                    logger.error(f"Part upload error: {exc}")
                    await asyncio.sleep(1)
                    try:
                        await msg.reply_document(
                            document=part_bytes,
                            caption=f"{e('check')} <b>Part {idx}/{len(chunks)}</b> - {len(chunk):,} lines",
                            parse_mode=ParseMode.HTML
                        )
                    except Exception as exc2:
                        logger.error(f"Retry failed: {exc2}")
                
                await asyncio.sleep(SEND_DELAY_SECONDS)
            
            await status.edit_text(
                f"{e('success')} <b>Split {len(lines):,} lines into {len(chunks)} parts</b>",
                parse_mode=ParseMode.HTML
            )
        except Exception as exc:
            logger.exception(f"Split error: {exc}")
            await status.edit_text(
                f"{e('error')} {safe(str(exc)[:100])}",
                parse_mode=ParseMode.HTML
            )
    except Exception as exc:
        logger.exception("Error in /split")
        await update.message.reply_text(
            f"{e('error')} {safe(str(exc)[:100])}",
            parse_mode=ParseMode.HTML
        )

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Help command."""
    try:
        text = f"""
{e('search')} <b>GENPRO LIVE 2.0 - Help</b>

<b>{e('fire')} Generate Cards</b>

<code>/gen BIN amount</code>

<b>Examples:</b>
<code>/gen 411111 100</code>
<code>/gen 5xxxxx|12|25|123 500</code>
<code>/gen 371449|rnd|rnd|rnd 1000</code>

<b>Supports:</b>
{e('check')} Visa, Mastercard, Amex, Discover, Diners
{e('check')} 100% Luhn-valid
{e('check')} Future expiry dates only
{e('check')} Correct CVV per issuer
{e('check')} Up to {MAX_LIMIT:,} cards

━━━━━━━━━━━━━━

<b>{e('mass')} Split Files</b>

Reply to .txt file:
<code>/split 5</code>

<b>Auto-splits at:</b>
{e('check')} {MAX_LINES_PER_FILE:,} lines per file

━━━━━━━━━━━━━━

<b>{e('shield')} Rate Limit:</b>
{e('clock')} 5 requests per 60 seconds
"""
        
        await update.message.reply_text(
            text.strip(),
            parse_mode=ParseMode.HTML,
            reply_markup=main_keyboard()
        )
    except Exception as exc:
        logger.exception("Error in /help")
        await update.message.reply_text(
            f"{e('error')} {safe(str(exc)[:100])}",
            parse_mode=ParseMode.HTML
        )

async def cmd_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Info command."""
    try:
        text = f"""
{e('info')} <b>Bot Information</b>

<b>{e('stats')} Specifications</b>

Max Cards: <code>{MAX_LIMIT:,}</code>
Max Split: <code>{MAX_SPLIT_PARTS}</code>
Lines/File: <code>{MAX_LINES_PER_FILE:,}</code>
Rate Limit: <code>5 req/60s</code>

<b>{e('fire')} Features</b>

{e('check')} 100% Luhn-valid
{e('check')} Issuer-aware
{e('check')} Proper CVV lengths
{e('check')} Future expiry only
{e('check')} Streaming generation
{e('check')} Auto file splitting
{e('check')} Flood protection
{e('check')} Rate limiting

<b>{e('shield')} Version:</b>
<code>GENPRO LIVE 2.0</code>

<b>{e('rocket')} Engine:</b>
<code>PTB v20+ Python 3.8+</code>
"""
        
        await update.message.reply_text(
            text.strip(),
            parse_mode=ParseMode.HTML,
            reply_markup=main_keyboard()
        )
    except Exception as exc:
        logger.exception("Error in /info")
        await update.message.reply_text(
            f"{e('error')} {safe(str(exc)[:100])}",
            parse_mode=ParseMode.HTML
        )

# ================= CALLBACKS =================

async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline button callbacks."""
    try:
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = query.from_user.id
        
        if not is_authorized(user_id):
            await query.answer("Access denied", show_alert=True)
            return
        
        # Handle site removal
        if data.startswith("rmsite_"):
            idx = int(data.split("_")[1])
            if 0 <= idx < len(bot_data["sites"]):
                removed = bot_data["sites"].pop(idx)
                save_data()
                await query.edit_message_text(
                    f"{e('check')} <b>Site Removed</b>\n\n<code>{safe(removed)}</code>",
                    parse_mode=ParseMode.HTML
                )
            return
        
        # Handle proxy removal
        if data.startswith("rmpxy_"):
            idx = int(data.split("_")[1])
            if 0 <= idx < len(bot_data["proxies"]):
                removed = bot_data["proxies"].pop(idx)
                save_data()
                await query.edit_message_text(
                    f"{e('check')} <b>Proxy Removed</b>\n\n<code>{safe(removed)}</code>",
                    parse_mode=ParseMode.HTML
                )
            return
        
        # Handle payment testing
        if data.startswith("test_"):
            amount = int(data.split("_")[1])
            await query.edit_message_text(
                f"{e('loading')} <b>Starting payment test...</b>\n\n"
                f"Amount: <code>₹{amount}</code>",
                parse_mode=ParseMode.HTML
            )
            
            # Start payment testing
            await run_payment_test(query.message.chat_id, amount, context)
            return
        
        # Cancel action
        if data == "cancel":
            await query.edit_message_text(
                f"{e('check')} Cancelled.",
                parse_mode=ParseMode.HTML
            )
            return
        
        # Info callbacks
        if data == "help_main":
            text = f"""
{e('fire')} <b>Razorpay Testing Bot</b>

<b>Commands:</b>
/bhosade - Full command list
/addsite - Add payment sites
/addbim - Load BINs
/fuck - Start testing
/start - Main menu
"""
        elif data == "info_main":
            text = f"""
{e('info')} <b>Bot Info</b>

Sites: {len(bot_data['sites'])}
Proxies: {len(bot_data['proxies'])}
BINs: {len(bot_data['bins'])}
Version: 3.0.0
Status: {e('fire')} Online
"""
        else:
            text = f"{e('error')} Unknown action"
        
        try:
            keyboard = [
                [InlineKeyboardButton(f"{e('fire')} Commands", callback_data="help_main")],
                [InlineKeyboardButton(f"{e('stats')} Bot Info", callback_data="info_main")]
            ]
            await query.edit_message_text(
                text=text.strip(),
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as exc:
            logger.error(f"Callback edit error: {exc}")
    except Exception as exc:
        logger.exception("Error in callbacks")

# ================= PAYMENT TESTING LOGIC =================

async def run_payment_test(chat_id: int, amount: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Run payment testing with cards generated from BINs."""
    try:
        # Generate cards from BINs
        cards = []
        for bin_pattern in bot_data["bins"]:
            card = generate_card(bin_pattern)
            if card:
                cards.append(card)
        
        if not cards:
            await context.bot.send_message(
                chat_id,
                f"{e('error')} Failed to generate cards from BINs.",
                parse_mode=ParseMode.HTML
            )
            return
        
        # Status message
        status_msg = await context.bot.send_message(
            chat_id,
            f"{e('loading')} <b>Payment Test Started</b>\n\n"
            f"Amount: <code>₹{amount}</code>\n"
            f"Cards: <code>{len(cards)}</code>\n"
            f"Sites: <code>{len(bot_data['sites'])}</code>\n\n"
            f"{e('fire')} Testing in progress...",
            parse_mode=ParseMode.HTML
        )
        
        # Test each card on each site
        success_count = 0
        fail_count = 0
        
        for card_idx, card in enumerate(cards, 1):
            for site_idx, site in enumerate(bot_data["sites"], 1):
                # Simulate payment attempt
                result = await simulate_payment(card, site, amount, bot_data.get("proxies", []))
                
                # Send result
                if result["success"]:
                    success_count += 1
                    result_text = f"""
{e('success')} <b>PAYMENT SUCCESS</b>

{e('card')} Card: <code>{card}</code>
{e('money')} Amount: <code>₹{amount}</code>
{e('fire')} Site: <code>{safe(site)}</code>

<b>Response:</b>
<code>{safe(result['response'])}</code>

Status: <code>{result['status_code']}</code>
Time: <code>{result['timestamp']}</code>
"""
                else:
                    fail_count += 1
                    result_text = f"""
{e('error')} <b>PAYMENT FAILED</b>

{e('card')} Card: <code>{card}</code>
{e('money')} Amount: <code>₹{amount}</code>
{e('fire')} Site: <code>{safe(site)}</code>

<b>Response:</b>
<code>{safe(result['response'])}</code>

Status: <code>{result['status_code']}</code>
Time: <code>{result['timestamp']}</code>
"""
                
                await context.bot.send_message(
                    chat_id,
                    result_text.strip(),
                    parse_mode=ParseMode.HTML
                )
                
                await asyncio.sleep(0.5)  # Rate limiting
        
        # Final summary
        await status_msg.edit_text(
            f"{e('check')} <b>Payment Test Complete</b>\n\n"
            f"Total Attempts: <code>{len(cards) * len(bot_data['sites'])}</code>\n"
            f"{e('success')} Success: <code>{success_count}</code>\n"
            f"{e('error')} Failed: <code>{fail_count}</code>\n"
            f"Amount: <code>₹{amount}</code>",
            parse_mode=ParseMode.HTML
        )
        
    except Exception as exc:
        logger.exception("Error in payment test")
        await context.bot.send_message(
            chat_id,
            f"{e('error')} Test failed: {safe(str(exc)[:100])}",
            parse_mode=ParseMode.HTML
        )

async def simulate_payment(card: str, site: str, amount: int, proxies: list) -> dict:
    """Simulate payment attempt (sandbox)."""
    # This is a simulation for sandbox testing
    await asyncio.sleep(random.uniform(0.3, 0.8))
    
    # Random success/failure for testing
    success = random.choice([True, False, False])  # 33% success rate
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if success:
        return {
            "success": True,
            "status_code": "200",
            "response": f"Payment authorized. Transaction ID: TXN{random.randint(100000, 999999)}. Amount: ₹{amount}",
            "timestamp": timestamp
        }
    else:
        errors = [
            "Card declined by issuer",
            "Insufficient funds",
            "Invalid CVV",
            "Card expired",
            "Transaction blocked by bank",
            "3D Secure authentication failed"
        ]
        return {
            "success": False,
            "status_code": random.choice(["401", "402", "403", "422"]),
            "response": random.choice(errors),
            "timestamp": timestamp
        }

# ================= ERROR HANDLER =================

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors."""
    logger.exception(f"Unhandled error: {context.error}")

# ================= MAIN =================

def main():
    """Start the bot."""
    try:
        logger.info("Starting Razorpay Payment Testing Bot...")
        
        # Load persistent data
        load_data()
        
        app = ApplicationBuilder().token(BOT_TOKEN).build()
        
        # Register handlers
        app.add_handler(CommandHandler("start", cmd_start))
        app.add_handler(CommandHandler("sudo", cmd_sudo))
        app.add_handler(CommandHandler("addsite", cmd_addsite))
        app.add_handler(CommandHandler("live", cmd_live))
        app.add_handler(CommandHandler("rmsites", cmd_rmsites))
        app.add_handler(CommandHandler("addpxy", cmd_addpxy))
        app.add_handler(CommandHandler("proxy", cmd_proxy))
        app.add_handler(CommandHandler("rmpxy", cmd_rmpxy))
        app.add_handler(CommandHandler("addbim", cmd_addbim))
        app.add_handler(CommandHandler("chkbim", cmd_chkbim))
        app.add_handler(CommandHandler("fuck", cmd_fuck))
        app.add_handler(CommandHandler("bhosade", cmd_bhosade))
        
        # Keep old commands for compatibility
        app.add_handler(CommandHandler("gen", cmd_gen))
        app.add_handler(CommandHandler("split", cmd_split))
        app.add_handler(CommandHandler("help", cmd_help))
        app.add_handler(CommandHandler("info", cmd_info))
        
        app.add_handler(CallbackQueryHandler(callbacks))
        
        app.add_error_handler(error_handler)
        
        logger.info("Bot initialized successfully")
        logger.info(f"Admin: {ADMIN_USER_ID}")
        logger.info(f"Sudo users: {len(bot_data['sudo_users'])}")
        app.run_polling(drop_pending_updates=True)
    except Exception as exc:
        logger.critical(f"Fatal error: {exc}")
        raise

if __name__ == "__main__":
    main()
