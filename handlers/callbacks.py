"""
handlers/callbacks.py — All InlineKeyboard callback handling
"""
import asyncio
import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from config import CHANNEL_LINK, GROUP_LINK, MAX_MRZ_CARDS, RK_BINS, RK_PROXIES, RK_SITES, RK_STATS
from core.redis_client import redis
from handlers.admin import run_autohit
from utils.auth import get_role, is_admin, is_auth, is_sudo
from utils.decorators import check_joined
from utils.emojis import e, safe
from utils.helpers import send_file
from utils.keyboards import kb_admin, kb_main
from utils.state import mrz_results


async def handle_callbacks(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    q    = u.callback_query
    await q.answer()
    data = q.data
    uid  = q.from_user.id
    user = q.from_user

    # ── Join verify ───────────────────────────────────────────────────────────
    if data == "verify_join":
        ch, gr = await check_joined(ctx.bot, uid)
        if ch and gr:
            await q.edit_message_text(
                f"{e('check')} <b>Verified!</b>\n\n"
                f"{e('sparkle')} You can now use all commands.\n"
                f"Use /start to begin!",
                parse_mode=ParseMode.HTML,
            )
        else:
            rows = []
            if not ch:
                rows.append([InlineKeyboardButton(
                    f"{e('channel')} Join Channel", url=CHANNEL_LINK
                )])
            if not gr:
                rows.append([InlineKeyboardButton(
                    f"{e('group')} Join Group", url=GROUP_LINK
                )])
            rows.append([InlineKeyboardButton(
                f"{e('check')} Check Again", callback_data="verify_join"
            )])
            await q.edit_message_text(
                f"{e('cross')} Still not joined!\n\n"
                f"{'❌' if not ch else '✅'} Channel\n"
                f"{'❌' if not gr else '✅'} Group",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(rows),
            )
        return

    # ── Generic cancel ────────────────────────────────────────────────────────
    if data == "cancel":
        try:
            await q.edit_message_text(f"{e('cross')} Cancelled.", parse_mode=ParseMode.HTML)
        except Exception:
            pass
        return

    # ── Plans buy ─────────────────────────────────────────────────────────────
    if data == "plans_buy":
        await q.answer(
            "Contact @bhosade to purchase a plan!", show_alert=True
        )
        return

    # ── Download MRZ results ──────────────────────────────────────────────────
    if data.startswith("dl_"):
        parts = data.split("_", 2)
        if len(parts) < 3:
            return
        dl_type = parts[1]
        try:
            target_uid = int(parts[2])
        except Exception:
            return
        if uid != target_uid and not await is_sudo(uid):
            await q.answer("Not your results.", show_alert=True)
            return
        results = mrz_results.get(target_uid, {})
        if dl_type == "all":
            all_lines = (
                ["# === CHARGED ==="]  + results.get("charged", []) +
                ["# === APPROVED ==="] + results.get("approved", []) +
                ["# === DEAD ==="]     + results.get("dead", []) +
                ["# === ERRORS ==="]   + results.get("errors", [])
            )
            content = "\n".join(all_lines)
            fname   = f"all_results_{target_uid}.txt"
            cap     = f"{e('folder')} <b>All Results</b> — {len(all_lines)} lines"
        else:
            cards_list = results.get(dl_type, [])
            if not cards_list:
                await q.answer(f"No {dl_type} cards.", show_alert=True)
                return
            content = "\n".join(cards_list)
            fname   = f"{dl_type}_{target_uid}.txt"
            cap     = f"{e('folder')} <b>{dl_type.title()} Cards</b> — {len(cards_list)} cards"
        await send_file(q.message, content, fname, cap)
        return

    # ── Navigation: Check CC info ─────────────────────────────────────────────
    if data == "kb_rz":
        await q.edit_message_text(
            f"{e('card')} <b>Single CC Check</b>\n\n"
            f"  cmd · <code>/rz cc|mm|yy|cvv</code>\n"
            f"  txt · reply to a card with /rz\n"
            f"  ex · <code>/rz 4111111111111111|12|26|123</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{e('back')} Back", callback_data="back_main")],
            ]),
        )
        return

    if data == "kb_mrz":
        await q.edit_message_text(
            f"{e('mass')} <b>Mass Razorpay Check</b> — Premium\n\n"
            f"  cmd · <code>/mrz</code>\n"
            f"  txt · reply or attach .txt with /mrz\n\n"
            f"{e('star')} Max: <code>{MAX_MRZ_CARDS:,} cards</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{e('back')} Back", callback_data="back_main")],
            ]),
        )
        return

    if data == "kb_bin":
        await q.edit_message_text(
            f"{e('bin')} <b>BIN Lookup</b>\n\n"
            f"  cmd · <code>/bin 438854</code>\n"
            f"  ex · <code>/bin 220040</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{e('back')} Back", callback_data="back_main")],
            ]),
        )
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
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{e('back')} Back", callback_data="back_main")],
                [InlineKeyboardButton(f"{e('channel')} Channel", url=CHANNEL_LINK),
                 InlineKeyboardButton(f"{e('group')} Group",     url=GROUP_LINK)],
            ]),
        )
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
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{e('key')} Buy Premium", callback_data="plans_buy")],
                [InlineKeyboardButton(f"{e('back')} Back",       callback_data="back_main")],
            ]),
        )
        return

    if data == "kb_profile":
        ud   = await redis.hgetall(f"bot:u:{uid}")
        rle  = await get_role(uid)
        pln  = ud.get("plan_name", "Free")
        exp  = ud.get("plan_exp", "")
        exp_str = "—"
        if exp:
            try:
                rem = float(exp) - time.time()
                if rem > 0:
                    d2, r2 = divmod(int(rem), 86400)
                    exp_str = f"{d2}d {r2 // 3600}h"
                else:
                    exp_str = "Expired"
            except Exception:
                pass
        await q.edit_message_text(
            f"{e('star')} <b>Profile</b>\n\n"
            f"  ► name · {safe(user.first_name)}\n"
            f"  ► id · <code>{uid}</code>\n"
            f"  ► rank · <b>{safe(rle)}</b>\n"
            f"  ► plan · <b>{safe(pln)}</b>\n"
            f"  ► exp · <code>{exp_str}</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{e('back')} Back", callback_data="back_main")],
            ]),
        )
        return

    if data == "kb_stats":
        if not await is_sudo(uid):
            return
        hits = await redis.hget(RK_STATS, "total_hits")     or "0"
        ch   = await redis.hget(RK_STATS, "total_charged")  or "0"
        ap   = await redis.hget(RK_STATS, "total_approved") or "0"
        gen  = await redis.hget(RK_STATS, "total_generated") or "0"
        s    = await redis.llen(RK_SITES)
        p    = await redis.llen(RK_PROXIES)
        await q.edit_message_text(
            f"{e('stats')} <b>Stats</b>\n\n"
            f"  Gates: {s} · Proxies: {p}\n"
            f"  Hits: {hits} · Charged: {ch}\n"
            f"  Approved: {ap} · Generated: {gen}",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{e('back')} Back", callback_data="back_main")],
            ]),
        )
        return

    if data == "kb_admin_panel":
        if not await is_sudo(uid):
            return
        await q.edit_message_text(
            f"{e('gear')} <b>Admin Panel</b>\n\n"
            f"Use /bhosade for full command list.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{e('back')} Back", callback_data="back_main")],
            ]),
        )
        return

    if data == "back_main":
        role = await get_role(uid)
        kb   = kb_admin() if (is_admin(uid) or await is_sudo(uid)) else kb_main()
        await q.edit_message_text(
            f"{e('fire')} <b>NAGU ULTRA BOT</b>\n\n"
            f"{e('user')} <b>{safe(user.first_name)}</b> — <b>{safe(role)}</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=kb,
        )
        return

    # ── Sudo-only callbacks ───────────────────────────────────────────────────
    if not await is_sudo(uid):
        await q.answer("Access denied.", show_alert=True)
        return

    if data.startswith("fuck_"):
        amt = int(data.split("_")[1])
        await q.edit_message_text(
            f"{e('fire')} Starting real charge test ₹{amt // 100}...",
            parse_mode=ParseMode.HTML,
        )
        asyncio.create_task(run_autohit(q.message.chat_id, amt, ctx, False, user))
        return

    if data.startswith("auto_"):
        amt = int(data.split("_")[1])
        await q.edit_message_text(
            f"{e('bolt')} Starting auto-hit ₹{amt // 100}...",
            parse_mode=ParseMode.HTML,
        )
        asyncio.create_task(run_autohit(q.message.chat_id, amt, ctx, True, user))
        return

    if data.startswith("rmsite_"):
        idx   = int(data.split("_")[1])
        sites = await redis.lrange(RK_SITES, 0, -1)
        if 0 <= idx < len(sites):
            await redis.lrem(RK_SITES, 0, sites[idx])
            await q.edit_message_text(
                f"{e('check')} Site #{idx + 1} removed.", parse_mode=ParseMode.HTML
            )
        return

    if data.startswith("rmpxy_"):
        idx     = int(data.split("_")[1])
        proxies = await redis.lrange(RK_PROXIES, 0, -1)
        if 0 <= idx < len(proxies):
            await redis.lrem(RK_PROXIES, 0, proxies[idx])
            await q.edit_message_text(
                f"{e('check')} Proxy #{idx + 1} removed.", parse_mode=ParseMode.HTML
            )
        return

    if data.startswith("rmbin_"):
        idx  = int(data.split("_")[1])
        bins = await redis.lrange(RK_BINS, 0, -1)
        if 0 <= idx < len(bins):
            await redis.lrem(RK_BINS, 0, bins[idx])
            await q.edit_message_text(
                f"{e('check')} BIN #{idx + 1} removed.", parse_mode=ParseMode.HTML
            )
        return
