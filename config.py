"""
config.py — Central configuration for NAGU ULTRA BOT v7.0
All sensitive values loaded from environment variables with .env fallback.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ─── Bot Core ────────────────────────────────────────────────────────────────
BOT_TOKEN     = os.getenv("BOT_TOKEN", "8995125106:AAGy9CoHcdlW2u-VGli3ztPT5vxeWdtogxU")
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "7363967303"))
BOT_CREATOR   = os.getenv("BOT_CREATOR", "@bhosade")
BOT_NAME      = os.getenv("BOT_NAME", "xLavenderBot")

# ─── Telegram API (Pyrogram / Telethon — for future use) ─────────────────────
API_ID        = int(os.getenv("API_ID", "12089203"))
API_HASH      = os.getenv("API_HASH", "7d85eb5ce156d35f22500fd8ef43e7c2")

# ─── Channel / Group ─────────────────────────────────────────────────────────
CHANNEL_LINK  = os.getenv("CHANNEL_LINK", "https://t.me/+Yc-sBot49rM2OGM1")
GROUP_LINK    = os.getenv("GROUP_LINK",   "https://t.me/+Yc-sBot49rM2OGM1")
CHANNEL_ID    = int(os.getenv("CHANNEL_ID", "-1003988595535"))
GROUP_ID      = int(os.getenv("GROUP_ID",   "-1004295609000"))

# ─── Redis (Upstash) ─────────────────────────────────────────────────────────
REDIS_URL     = os.getenv("REDIS_URL",   "https://in-swine-133213.upstash.io")
REDIS_TOKEN   = os.getenv("REDIS_TOKEN", "gQAAAAAAAghdAAIgcDE2YzJmMjQ4OGM1N2Y0YmIxYmI4MWVjYzczMTY4ZmIyNA")

# ─── Redis Keys ───────────────────────────────────────────────────────────────
RK_SUDO    = "bot:sudo"
RK_SITES   = "bot:sites"
RK_PROXIES = "bot:proxies"
RK_BINS    = "bot:bins"
RK_STATS   = "bot:stats"
RK_BANNED  = "bot:banned"
RK_KEYS    = "bot:keys_active"

# ─── Razorpay Build Hashes (DO NOT CHANGE unless Razorpay updates) ────────────
RZP_BUILD    = "9cb57fdf457e44eac4384e182f925070ff5488d9"
RZP_BUILD_V1 = "715e3c0a534a4e4fa59a19e1d2a3cc3daf1837e2"
FORCE_AMOUNT = int(os.getenv("FORCE_AMOUNT", "100"))   # ₹1 in paise

# ─── Limits & Timings ────────────────────────────────────────────────────────
MAX_LIMIT          = int(os.getenv("MAX_LIMIT",          "1500000"))
MAX_SPLIT_PARTS    = int(os.getenv("MAX_SPLIT_PARTS",    "100"))
MAX_LINES_PER_FILE = int(os.getenv("MAX_LINES_PER_FILE", "500000"))
MAX_MRZ_CARDS      = int(os.getenv("MAX_MRZ_CARDS",      "6000"))
MASS_CONCURRENT    = int(os.getenv("MASS_CONCURRENT",    "10"))
SEND_DELAY         = float(os.getenv("SEND_DELAY",       "0.30"))
BATCH_SIZE         = int(os.getenv("BATCH_SIZE",         "7"))
BATCH_DELAY        = float(os.getenv("BATCH_DELAY",      "2.0"))
PROXY_TIMEOUT      = int(os.getenv("PROXY_TIMEOUT",      "10"))
SITE_TIMEOUT       = int(os.getenv("SITE_TIMEOUT",       "15"))
CARD_TIMEOUT       = int(os.getenv("CARD_TIMEOUT",       "25"))
RATE_LIMIT         = int(os.getenv("RATE_LIMIT",         "5"))
RATE_WINDOW        = int(os.getenv("RATE_WINDOW",        "30"))

# ─── Command auto-delete (seconds) ───────────────────────────────────────────
CMD_DELETE_AFTER   = int(os.getenv("CMD_DELETE_AFTER", "300"))  # 5 minutes
