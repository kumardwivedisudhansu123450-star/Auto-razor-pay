"""
utils/keyboards.py — Inline keyboard builders
"""
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from config import CHANNEL_LINK, GROUP_LINK
from utils.emojis import e
from utils.state import mrz_results


def btn(label: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(label, callback_data=data)


def url_btn(label: str, url: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(label, url=url)


# ─── Main keyboards ───────────────────────────────────────────────────────────

def kb_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [btn(f"{e('card')} Check CC",   "kb_rz"),     btn(f"{e('mass')} Mass Check", "kb_mrz")],
        [btn(f"{e('user')} Profile",    "kb_profile"), btn(f"{e('plan')} Plans",      "kb_plans")],
        [btn(f"{e('bin')} BIN Lookup",  "kb_bin"),     btn(f"{e('info')} Help",        "kb_help")],
        [url_btn(f"{e('channel')} Channel", CHANNEL_LINK),
         url_btn(f"{e('group')} Group",     GROUP_LINK)],
    ])


def kb_admin() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [btn(f"{e('card')} Check CC",   "kb_rz"),     btn(f"{e('mass')} Mass Check", "kb_mrz")],
        [btn(f"{e('user')} Profile",    "kb_profile"), btn(f"{e('stats')} Stats",     "kb_stats")],
        [btn(f"{e('bin')} BIN Lookup",  "kb_bin"),     btn(f"{e('info')} Help",        "kb_help")],
        [btn(f"{e('gear')} Admin Panel", "kb_admin_panel")],
        [url_btn(f"{e('channel')} Channel", CHANNEL_LINK),
         url_btn(f"{e('group')} Group",     GROUP_LINK)],
    ])


def kb_verify() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [url_btn(f"{e('channel')} Join Channel", CHANNEL_LINK)],
        [url_btn(f"{e('group')} Join Group",     GROUP_LINK)],
        [btn(f"{e('check')} I Joined — Verify",  "verify_join")],
    ])


# ─── MRZ download keyboard ────────────────────────────────────────────────────

def kb_mrz_results(uid: int) -> Optional[InlineKeyboardMarkup]:
    r = mrz_results.get(uid)
    if not r:
        return None
    rows = []
    ch = r.get("charged", [])
    ap = r.get("approved", [])
    de = r.get("dead", [])
    er = r.get("errors", [])
    if ch:
        rows.append([btn(f"💰 Charged ({len(ch)})",   f"dl_charged_{uid}")])
    if ap:
        rows.append([btn(f"✅ Approved ({len(ap)})",  f"dl_approved_{uid}")])
    if de:
        rows.append([btn(f"❌ Dead ({len(de)})",       f"dl_dead_{uid}")])
    if er:
        rows.append([btn(f"⚠️ Errors ({len(er)})",    f"dl_errors_{uid}")])
    rows.append([btn(f"📦 Download All", f"dl_all_{uid}")])
    return InlineKeyboardMarkup(rows) if rows else None
