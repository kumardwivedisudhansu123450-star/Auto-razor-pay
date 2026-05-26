"""
handlers/generator.py — /gen and /split (premium only)
"""
import asyncio
import math
from io import BytesIO
from typing import List

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from config import MAX_LIMIT, MAX_LINES_PER_FILE, MAX_SPLIT_PARTS, RK_STATS, SEND_DELAY
from core.bin_lookup import lookup_bin
from core.card_utils import gen_cards, validate_bin
from core.redis_client import redis
from utils.decorators import need_premium
from utils.emojis import e, safe
from utils.helpers import send_file
from utils.state import check_rate


@need_premium
async def cmd_gen(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = u.effective_user.id
    ok, msg_r = check_rate(uid)
    if not ok:
        await u.message.reply_text(
            f"{e('cooldown')} {e('timer')} Cooldown — wait {msg_r}",
            parse_mode=ParseMode.HTML,
        )
        return

    if not ctx.args:
        await u.message.reply_text(
            f"{e('card')} /gen BIN amount\n  ex: <code>/gen 411111 100</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    bp = ctx.args[0]
    try:
        count = int(ctx.args[1]) if len(ctx.args) > 1 else 10
    except ValueError:
        count = 10
    count = max(1, min(count, MAX_LIMIT))

    ok2, err = validate_bin(bp)
    if not ok2:
        await u.message.reply_text(f"{e('error')} {err}", parse_mode=ParseMode.HTML)
        return

    bin6  = bp.split("|")[0][:8]
    binfo = await lookup_bin(bin6)

    st = await u.message.reply_text(
        f"{e('loading')} Generating <code>{count:,}</code> cards...\n"
        f"  {e('bin')} {bin6} · {binfo['scheme']} · "
        f"{safe(binfo['bank'])} · {safe(binfo['country'])} {binfo['flag']}",
        parse_mode=ParseMode.HTML,
    )

    fc = gen_ct = 0
    chunk: List[str] = []

    try:
        for card in gen_cards(bp, count):
            chunk.append(card)
            gen_ct += 1
            if len(chunk) >= MAX_LINES_PER_FILE:
                fc += 1
                await send_file(
                    u.message,
                    "\n".join(chunk),
                    f"gen_{bin6}_p{fc}.txt",
                    f"{e('check')} <b>Part {fc}</b> — {len(chunk):,} cards",
                )
                chunk = []
                await asyncio.sleep(SEND_DELAY)

        if chunk:
            fc += 1
            await send_file(
                u.message,
                "\n".join(chunk),
                f"gen_{bin6}_p{fc}.txt",
                f"{e('check')} <b>Part {fc}</b> — {len(chunk):,} cards",
            )

        await redis.hincrby(RK_STATS, "total_generated", gen_ct)
        await st.edit_text(
            f"{e('check')} Generated <code>{gen_ct:,}</code> cards in {fc} file(s)\n"
            f"  {e('bin')} {bin6} · {binfo['scheme']} · "
            f"{safe(binfo['country'])} {binfo['flag']}",
            parse_mode=ParseMode.HTML,
        )
    except Exception as ex:
        await st.edit_text(
            f"{e('error')} {safe(str(ex)[:80])}", parse_mode=ParseMode.HTML
        )


@need_premium
async def cmd_split(u: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = u.effective_user.id
    ok, msg_r = check_rate(uid)
    if not ok:
        await u.message.reply_text(
            f"{e('cooldown')} {msg_r}", parse_mode=ParseMode.HTML
        )
        return

    if not ctx.args:
        await u.message.reply_text(
            f"{e('file')} Reply to .txt with <code>/split 5</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    try:
        n = int(ctx.args[0])
    except ValueError:
        await u.message.reply_text(
            f"{e('error')} Parts must be a number.", parse_mode=ParseMode.HTML
        )
        return

    if not 2 <= n <= MAX_SPLIT_PARTS:
        await u.message.reply_text(
            f"{e('error')} Parts: 2–{MAX_SPLIT_PARTS}.", parse_mode=ParseMode.HTML
        )
        return

    rep = u.message.reply_to_message
    if not rep or not rep.document:
        await u.message.reply_text(
            f"{e('error')} Reply to a .txt file.", parse_mode=ParseMode.HTML
        )
        return

    doc = rep.document
    if not (doc.file_name or "").lower().endswith(".txt"):
        await u.message.reply_text(
            f"{e('error')} Only .txt files.", parse_mode=ParseMode.HTML
        )
        return

    st = await u.message.reply_text(
        f"{e('loading')} Processing...", parse_mode=ParseMode.HTML
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

        lines = [x.strip() for x in content.splitlines() if x.strip()]
        if not lines:
            await st.edit_text(f"{e('error')} File is empty.", parse_mode=ParseMode.HTML)
            return
        if n > len(lines):
            await st.edit_text(
                f"{e('error')} Only {len(lines):,} lines, can't split into {n}.",
                parse_mode=ParseMode.HTML,
            )
            return

        cs     = math.ceil(len(lines) / n)
        chunks = [lines[i : i + cs] for i in range(0, len(lines), cs)]
        base   = (doc.file_name or "file")[:-4]

        await st.edit_text(
            f"{e('loading')} Sending {len(chunks)} parts...",
            parse_mode=ParseMode.HTML,
        )
        for idx, chunk in enumerate(chunks, 1):
            await send_file(
                u.message,
                "\n".join(chunk),
                f"{base}_p{idx}of{len(chunks)}.txt",
                f"{e('check')} <b>Part {idx}/{len(chunks)}</b> — {len(chunk):,} lines",
            )
            await asyncio.sleep(SEND_DELAY)

        await st.edit_text(
            f"{e('check')} Split <code>{len(lines):,}</code> lines into "
            f"<b>{len(chunks)}</b> parts.",
            parse_mode=ParseMode.HTML,
        )
    except Exception as ex:
        await st.edit_text(
            f"{e('error')} {safe(str(ex)[:80])}", parse_mode=ParseMode.HTML
        )
