#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════╗
║           NAGU ULTRA BOT v7.0 — Repository Edition                      ║
║  Razorpay • Redis • Keys • Plans • Mass • Hit Log • Channel Guard       ║
║  Creator: @bhosade  |  Owner: 7363967303                                ║
╚══════════════════════════════════════════════════════════════════════════╝

bot.py — Main entry point.
- Registers all handlers
- Attaches auto-delete middleware for command messages (CMD_DELETE_AFTER seconds)
- Starts polling
"""
import asyncio
import logging
import sys

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import BOT_CREATOR, BOT_TOKEN, CMD_DELETE_AFTER

# ── Handlers ──────────────────────────────────────────────────────────────────
from handlers.admin import (
    cmd_addpxy, cmd_addbim, cmd_addplan, cmd_addsite,
    cmd_autohit, cmd_ban, cmd_banlist, cmd_bhosade,
    cmd_chkbim, cmd_checksite, cmd_clrpxy, cmd_fuck,
    cmd_genkey, cmd_live, cmd_proxy, cmd_rmbin, cmd_rmpxy,
    cmd_rmsite, cmd_stats, cmd_stop_test, cmd_sudo_add,
    cmd_sudolist, cmd_testpxy, cmd_unban, cmd_unsudo,
)
from handlers.callbacks import handle_callbacks
from handlers.checker import cmd_mrz, cmd_mrzstop, cmd_rz
from handlers.generator import cmd_gen, cmd_split
from handlers.public import (
    cmd_bin, cmd_help, cmd_plans, cmd_profile, cmd_redeem, cmd_start,
)

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("nagu-v7")


# ── Auto-delete middleware ────────────────────────────────────────────────────

async def _auto_delete_cmd(message, delay: int) -> None:
    """Delete a command message after `delay` seconds (silently)."""
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception:
        pass


def make_auto_delete_wrapper(handler_func, delay: int = CMD_DELETE_AFTER):
    """
    Wrap a command handler so the user's command message is scheduled
    for deletion after `delay` seconds.
    """
    import functools

    @functools.wraps(handler_func)
    async def wrapped(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        # Schedule deletion of the user's command message
        if update.message:
            asyncio.create_task(_auto_delete_cmd(update.message, delay))
        return await handler_func(update, ctx)

    return wrapped


# ── App builder ───────────────────────────────────────────────────────────────

def main() -> None:
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # ── Public ────────────────────────────────────────────────────────────────
    app.add_handler(CommandHandler("start",   make_auto_delete_wrapper(cmd_start)))
    app.add_handler(CommandHandler("help",    make_auto_delete_wrapper(cmd_help)))
    app.add_handler(CommandHandler("cmds",    make_auto_delete_wrapper(cmd_help)))
    app.add_handler(CommandHandler("plans",   make_auto_delete_wrapper(cmd_plans)))
    app.add_handler(CommandHandler("redeem",  make_auto_delete_wrapper(cmd_redeem)))
    app.add_handler(CommandHandler("profile", make_auto_delete_wrapper(cmd_profile)))
    app.add_handler(CommandHandler("bin",     make_auto_delete_wrapper(cmd_bin)))

    # ── Checker (free + premium) ──────────────────────────────────────────────
    app.add_handler(CommandHandler("rz",      make_auto_delete_wrapper(cmd_rz)))

    # ── Premium only ──────────────────────────────────────────────────────────
    app.add_handler(CommandHandler("mrz",     make_auto_delete_wrapper(cmd_mrz)))
    app.add_handler(CommandHandler("mrzstop", make_auto_delete_wrapper(cmd_mrzstop)))
    app.add_handler(CommandHandler("gen",     make_auto_delete_wrapper(cmd_gen)))
    app.add_handler(CommandHandler("split",   make_auto_delete_wrapper(cmd_split)))

    # ── Sudo / Admin ──────────────────────────────────────────────────────────
    app.add_handler(CommandHandler("sudo",      make_auto_delete_wrapper(cmd_sudo_add)))
    app.add_handler(CommandHandler("unsudo",    make_auto_delete_wrapper(cmd_unsudo)))
    app.add_handler(CommandHandler("sudolist",  make_auto_delete_wrapper(cmd_sudolist)))
    app.add_handler(CommandHandler("ban",       make_auto_delete_wrapper(cmd_ban)))
    app.add_handler(CommandHandler("unban",     make_auto_delete_wrapper(cmd_unban)))
    app.add_handler(CommandHandler("banlist",   make_auto_delete_wrapper(cmd_banlist)))
    app.add_handler(CommandHandler("addplan",   make_auto_delete_wrapper(cmd_addplan)))
    app.add_handler(CommandHandler("genkey",    make_auto_delete_wrapper(cmd_genkey)))
    app.add_handler(CommandHandler("stats",     make_auto_delete_wrapper(cmd_stats)))
    app.add_handler(CommandHandler("addsite",   make_auto_delete_wrapper(cmd_addsite)))
    app.add_handler(CommandHandler("live",      make_auto_delete_wrapper(cmd_live)))
    app.add_handler(CommandHandler("checksite", make_auto_delete_wrapper(cmd_checksite)))
    app.add_handler(CommandHandler("rmsite",    make_auto_delete_wrapper(cmd_rmsite)))
    app.add_handler(CommandHandler("addpxy",    make_auto_delete_wrapper(cmd_addpxy)))
    app.add_handler(CommandHandler("proxy",     make_auto_delete_wrapper(cmd_proxy)))
    app.add_handler(CommandHandler("testpxy",   make_auto_delete_wrapper(cmd_testpxy)))
    app.add_handler(CommandHandler("rmpxy",     make_auto_delete_wrapper(cmd_rmpxy)))
    app.add_handler(CommandHandler("clrpxy",    make_auto_delete_wrapper(cmd_clrpxy)))
    app.add_handler(CommandHandler("addbim",    make_auto_delete_wrapper(cmd_addbim)))
    app.add_handler(CommandHandler("chkbim",    make_auto_delete_wrapper(cmd_chkbim)))
    app.add_handler(CommandHandler("rmbin",     make_auto_delete_wrapper(cmd_rmbin)))

    # ── Completely hidden (sudo only, silent fail) ────────────────────────────
    app.add_handler(CommandHandler("fuck",     make_auto_delete_wrapper(cmd_fuck)))
    app.add_handler(CommandHandler("autohit",  make_auto_delete_wrapper(cmd_autohit)))
    app.add_handler(CommandHandler("stoptest", make_auto_delete_wrapper(cmd_stop_test)))
    app.add_handler(CommandHandler("bhosade",  make_auto_delete_wrapper(cmd_bhosade)))

    # ── Callbacks ─────────────────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(handle_callbacks))

    logger.info("══════════════════════════════════════════════")
    logger.info("  NAGU ULTRA BOT v7.0 — Repo Edition")
    logger.info(f"  Creator: {BOT_CREATOR}")
    logger.info("  CMD auto-delete: %ds", CMD_DELETE_AFTER)
    logger.info("══════════════════════════════════════════════")

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
