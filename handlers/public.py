"""
handlers/public.py — /start /help /plans /redeem /profile /bin
All use @need_join decorator and send premium-emoji messages.
"""
import time
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from config import BOT_CREATOR, BOT_NAME, CHANNEL_LINK, GROUP_LINK, RK_STATS
from core.bin_lookup import lookup_bin
from core.redis_client import redis
from utils.auth import (
    get_role, has_plan, is_admin, is_auth, is_banned, is_sudo, redeem_key,
)
from utils.decorators import enforce_join, need_join
from utils.emojis import e, safe
from utils.keyboards import kb_admin, kb_main


# ─── /start ───────────────────────────────────────────────────────────────────

async def cmd_start(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid  = u.effective_user.id
    user = u.effective_user
    if await is_banned(uid):
        await u.message.reply_text(
            f"{e('ban')} <b>Banned.</b>", parse_mode=ParseMode.HTML
        )
        return
    if not await enforce_join(u, ctx):
        return

    role      = await get_role(uid)
    auth_ok   = await is_auth(uid)
    ud        = await redis.hgetall(f"bot:u:{uid}")
    plan_nm   = ud.get("plan_name", "Free")
    plan_exp  = ud.get("plan_exp", "")
    exp_str   = "—"
    if plan_exp:
        try:
            rem = float(plan_exp) - time.time()
            if rem > 0:
                d, rem = divmod(int(rem), 86400)
                h = rem // 3600
                exp_str = f"{d}d {h}h"
            else:
                exp_str = "Expired"
        except Exception:
            exp_str = "—"

    total_hits = await redis.hget(RK_STATS, "total_hits") or "0"

    ri = (
        e("crown") if is_admin(uid) else
        e("star")  if await is_sudo(uid) else
        e("star")  if auth_ok else
        e("eye")
    )

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
        f"  ► total hits · <code>{total_hits}</code>\n\n"
        f"{e('sparkle')} keep grinding · hits matter",
        parse_mode=ParseMode.HTML,
        reply_markup=kb,
        disable_web_page_preview=True,
    )


# ─── /profile ─────────────────────────────────────────────────────────────────

@need_join
async def cmd_profile(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid  = u.effective_user.id
    user = u.effective_user
    ud   = await redis.hgetall(f"bot:u:{uid}")
    role     = await get_role(uid)
    plan_nm  = ud.get("plan_name", "Free")
    plan_exp = ud.get("plan_exp", "")
    exp_str  = "No active plan"
    valid    = False
    age_str  = "—"

    if plan_exp:
        try:
            exp_ts  = float(plan_exp)
            exp_dt  = datetime.fromtimestamp(exp_ts)
            exp_str = exp_dt.strftime("%Y-%m-%d %H:%M UTC")
            valid   = exp_ts > time.time()
            act_ts  = ud.get("activated", "")
            if act_ts:
                age_days = (time.time() - float(act_ts)) / 86400
                age_str  = f"{int(age_days)}d"
        except Exception:
            pass

    ri = (
        e("crown") if is_admin(uid) else
        e("star")  if await is_sudo(uid) else
        e("star")  if valid else
        e("eye")
    )
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
        parse_mode=ParseMode.HTML,
        reply_markup=kb_main(),
    )


# ─── /plans ───────────────────────────────────────────────────────────────────

async def cmd_plans(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = u.effective_user.id
    if await is_banned(uid):
        return
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
        f"{e('channel')} <a href='{CHANNEL_LINK}'>Channel</a> · "
        f"<a href='{GROUP_LINK}'>Group</a>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{e('key')} Buy Premium",  callback_data="plans_buy")],
            [InlineKeyboardButton(f"{e('star')} My Plan",     callback_data="kb_profile")],
        ]),
        disable_web_page_preview=True,
    )


# ─── /redeem ──────────────────────────────────────────────────────────────────

@need_join
async def cmd_redeem(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = u.effective_user.id
    if not ctx.args:
        await u.message.reply_text(
            f"{e('key')} Usage: <code>/redeem NAGU-XXXX-XXXX-XXXX</code>",
            parse_mode=ParseMode.HTML,
        )
        return
    key = ctx.args[0].upper().strip()
    msg = await u.message.reply_text(
        f"{e('loading')} Validating key...", parse_mode=ParseMode.HTML
    )
    ok, info = await redeem_key(key, uid)
    if ok:
        await msg.edit_text(
            f"{e('check')} <b>Key Activated!</b>\n\n"
            f"{e('key')}  Key: <code>{safe(key)}</code>\n"
            f"{e('plan')} {safe(info)}\n\n"
            f"{e('sparkle')} Premium unlocked!",
            parse_mode=ParseMode.HTML,
        )
    else:
        await msg.edit_text(
            f"{e('cross')} <b>Failed:</b> {safe(info)}\n\n"
            f"Contact {BOT_CREATOR} for a valid key.",
            parse_mode=ParseMode.HTML,
        )


# ─── /bin ─────────────────────────────────────────────────────────────────────

@need_join
async def cmd_bin(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid  = u.effective_user.id
    bin6 = ctx.args[0] if ctx.args else None
    if not bin6:
        await u.message.reply_text(
            f"{e('bin')} Usage: <code>/bin 411111</code>",
            parse_mode=ParseMode.HTML,
        )
        return
    bin6 = "".join(c for c in bin6 if c.isdigit())[:8]
    if len(bin6) < 4:
        await u.message.reply_text(
            f"{e('error')} BIN too short.", parse_mode=ParseMode.HTML
        )
        return
    msg  = await u.message.reply_text(
        f"{e('loading')} Looking up <code>{bin6}</code>...",
        parse_mode=ParseMode.HTML,
    )
    info = await lookup_bin(bin6)
    flag = info.get("flag", "")
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
        parse_mode=ParseMode.HTML,
    )


# ─── /help ────────────────────────────────────────────────────────────────────

@need_join
async def cmd_help(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
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
        f"{e('channel')} <a href='{CHANNEL_LINK}'>Channel</a> · "
        f"<a href='{GROUP_LINK}'>Group</a>",
        parse_mode=ParseMode.HTML,
        reply_markup=kb_main(),
        disable_web_page_preview=True,
    )
