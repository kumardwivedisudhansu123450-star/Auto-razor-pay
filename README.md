# NAGU ULTRA BOT v7.0 — Repository Edition

> Razorpay · Redis · Keys · Plans · Mass Check · Channel Guard

---

## Features

| Feature | Free | Premium |
|---|---|---|
| `/rz` — Single CC check | ✅ | ✅ |
| `/bin` — BIN lookup (VBV/3DS info) | ✅ | ✅ |
| `/mrz` — Mass check (up to 6,000 cards) | ❌ | ✅ |
| `/gen` — Card generation | ❌ | ✅ |
| `/split` — Split .txt file | ❌ | ✅ |
| Plans & key redemption | ✅ | ✅ |

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/youruser/nagu-ultra-bot.git
cd nagu-ultra-bot
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your values
```

Key values to set:
- `BOT_TOKEN` — from @BotFather
- `ADMIN_USER_ID` — your Telegram user ID
- `API_ID` / `API_HASH` — from https://my.telegram.org
- `CHANNEL_ID` / `GROUP_ID` — your channel and group IDs
- `REDIS_URL` / `REDIS_TOKEN` — Upstash Redis credentials

### 3. Install and run

**Plain Python:**
```bash
pip install -r requirements.txt
python bot.py
```

**Docker:**
```bash
docker-compose up -d
```

---

## Directory Structure

```
nagu-ultra-bot/
├── bot.py                  # Main entry point
├── config.py               # All config loaded from .env
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── core/
│   ├── redis_client.py     # Upstash Redis async client
│   ├── card_utils.py       # Luhn, gen, parse, BIN brand
│   ├── bin_lookup.py       # binlist.net BIN lookup
│   ├── proxy_utils.py      # Proxy testing + auto-removal
│   ├── site_utils.py       # Razorpay page loader + auto-removal
│   └── razorpay_engine.py  # Full 9-step Razorpay flow
├── utils/
│   ├── emojis.py           # Premium Telegram emoji system
│   ├── state.py            # In-memory state (MRZ, rate limits)
│   ├── auth.py             # Auth, plans, key management
│   ├── decorators.py       # @need_join, @need_premium, @need_sudo
│   ├── keyboards.py        # Inline keyboard builders
│   └── helpers.py          # File sender, hit logger (no CC in logs)
└── handlers/
    ├── public.py           # /start /help /plans /redeem /profile /bin
    ├── checker.py          # /rz /mrz /mrzstop
    ├── generator.py        # /gen /split
    ├── admin.py            # All sudo/admin commands
    └── callbacks.py        # All inline button callbacks
```

---

## Admin Commands

Available via `/bhosade` (sudo only, silently ignored for others):

**Users:** `/ban` `/unban` `/banlist` `/addplan` `/genkey` `/sudo` `/unsudo` `/sudolist`

**Gates:** `/addsite` `/live` `/checksite` `/rmsite`

**Proxies:** `/addpxy` `/proxy` `/testpxy` `/rmpxy` `/clrpxy`

**BINs:** `/addbim` `/chkbim` `/rmbin`

**Payment (hidden):** `/fuck` (real charge) · `/autohit` (cancel mode) · `/stoptest`

---

## Privacy / Log Policy

- **Group logs:** CC numbers are **completely removed**. Only BIN6 + network is shown.
- **DMs:** Full card details are shown as-is to the user.
- **Charged verdict:** Only issued when Razorpay returns `razorpay_payment_id` in the cancel-step response — meaning the payment actually went through before cancellation.

---

## Notes

- Commands auto-delete after **5 minutes** (configurable via `CMD_DELETE_AFTER` in `.env`)
- Dead proxies and dead sites are auto-removed from Redis on every check
- Mass checker supports up to **6,000 cards** (premium only)
- Bot requires users to join **channel + group** before use

---

Creator: @bhosade
