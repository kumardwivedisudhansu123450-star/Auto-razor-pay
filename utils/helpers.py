"""
utils/helpers.py — Shared helper functions (file send, hit logger, etc.)
"""
import asyncio
import logging
from datetime import datetime
from io import BytesIO
from typing import Optional

from telegram import Message
from telegram.constants import ParseMode

from config import (
    BOT_CREATOR, BOT_NAME, GROUP_ID, RK_STATS,
)
from core.card_utils import net_display
from core.redis_client import redis
from utils.emojis import e, safe

logger = logging.getLogger("nagu.helpers")


# ─── File sending ─────────────────────────────────────────────────────────────

async def send_file(
    message: Message,
    content: str,
    filename: str,
    caption: str,
) -> None:
    bio = BytesIO(content.encode())
    bio.name = filename
    for attempt in range(2):
        try:
            bio.seek(0)
            await message.reply_document(
                document=bio,
                caption=caption,
                parse_mode=ParseMode.HTML,
            )
            return
        except Exception as ex:
            logger.error(f"File send attempt {attempt + 1}: {ex}")
            if attempt == 0:
                await asyncio.sleep(1.5)


# ─── Hit logger — NO CC details in group logs ─────────────────────────────────

async def log_hit(
    bot,
    hit_type: str,
    card: str,
    amount_inr: int,
    user,
    response: str,
) -> None:
    """
    Log a CHARGED or APPROVED hit to the group.
    CC number is intentionally excluded from logs — only BIN6 and network shown.
    """
    if not GROUP_ID or GROUP_ID == -1009876543210:
        return
    try:
        parts  = card.split("|")
        cc_raw = parts[0] if parts else card
        bin6   = cc_raw[:6]
        net    = net_display(cc_raw)
        ulink  = f'<a href="tg://user?id={user.id}">{safe(user.first_name)}</a>'
        ts     = datetime.now().strftime("%H:%M · %d %b")

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
        else:  # APPROVED
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

        await bot.send_message(GROUP_ID, text, parse_mode=ParseMode.HTML)
        await redis.hincrby(RK_STATS, "total_hits", 1)

    except Exception as ex:
        logger.warning(f"log_hit failed: {ex}")
