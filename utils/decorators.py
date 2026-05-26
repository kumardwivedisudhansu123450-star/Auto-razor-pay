"""
utils/decorators.py — Handler decorators: need_join, need_premium, need_sudo
"""
import asyncio
import functools

from telegram import ChatMember, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from config import CHANNEL_ID, CHANNEL_LINK, GROUP_ID, GROUP_LINK
from utils.auth import is_admin, is_auth, is_banned, is_sudo
from utils.emojis import e


# ─── Join enforcement ─────────────────────────────────────────────────────────

async def check_joined(bot, uid: int):
    """Returns (channel_joined, group_joined)."""
    ch = gr = True
    if CHANNEL_ID and CHANNEL_ID != -1001234567890:
        try:
            m  = await bot.get_chat_member(CHANNEL_ID, uid)
            ch = m.status not in (ChatMember.BANNED, ChatMember.LEFT)
        except Exception:
            ch = True
    if GROUP_ID and GROUP_ID != -1009876543210:
        try:
            m  = await bot.get_chat_member(GROUP_ID, uid)
            gr = m.status not in (ChatMember.BANNED, ChatMember.LEFT)
        except Exception:
            gr = True
    return ch, gr


async def enforce_join(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    uid = update.effective_user.id
    if is_admin(uid) or await is_sudo(uid):
        return True
    ch, gr = await check_joined(ctx.bot, uid)
    if ch and gr:
        return True

    rows = []
    if not ch:
        rows.append([InlineKeyboardButton(f"{e('channel')} Join Channel", url=CHANNEL_LINK)])
    if not gr:
        rows.append([InlineKeyboardButton(f"{e('group')} Join Group", url=GROUP_LINK)])
    rows.append([
        InlineKeyboardButton(f"{e('check')} I Joined — Verify", callback_data="verify_join"),
    ])

    await update.message.reply_text(
        f"{e('lock')} <b>Join Required!</b>\n\n"
        f"{'❌' if not ch else '✅'} Channel\n"
        f"{'❌' if not gr else '✅'} Group\n\n"
        f"Join both then press <b>Verify</b>.",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(rows),
    )
    return False


# ─── Decorators ───────────────────────────────────────────────────────────────

def need_join(func):
    @functools.wraps(func)
    async def wrap(u: Update, c: ContextTypes.DEFAULT_TYPE):
        uid = u.effective_user.id
        if await is_banned(uid):
            await u.message.reply_text(
                f"{e('ban')} <b>Banned.</b>", parse_mode=ParseMode.HTML
            )
            return
        if not await enforce_join(u, c):
            return
        return await func(u, c)
    return wrap


def need_premium(func):
    @functools.wraps(func)
    async def wrap(u: Update, c: ContextTypes.DEFAULT_TYPE):
        uid = u.effective_user.id
        if await is_banned(uid):
            await u.message.reply_text(
                f"{e('ban')} <b>Banned.</b>", parse_mode=ParseMode.HTML
            )
            return
        if not await enforce_join(u, c):
            return
        if not await is_auth(uid):
            await u.message.reply_text(
                f"{e('lock')} <b>Premium Required</b>\n\n"
                f"{e('plan')} Use <code>/plans</code> to see plans\n"
                f"{e('key')} Use <code>/redeem KEY</code> to activate",
                parse_mode=ParseMode.HTML,
            )
            return
        return await func(u, c)
    return wrap


def need_sudo(func):
    @functools.wraps(func)
    async def wrap(u: Update, c: ContextTypes.DEFAULT_TYPE):
        uid = u.effective_user.id
        if await is_banned(uid):
            await u.message.reply_text(
                f"{e('ban')} <b>Banned.</b>", parse_mode=ParseMode.HTML
            )
            return
        if not await is_sudo(uid):
            await u.message.reply_text(
                f"{e('lock')} <b>Access Denied</b>\n{e('crown')} Sudo only.",
                parse_mode=ParseMode.HTML,
            )
            return
        return await func(u, c)
    return wrap
