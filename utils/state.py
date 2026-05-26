"""
utils/state.py — In-memory state for active tests, MRZ jobs, rate limits
"""
import asyncio
import time
from collections import defaultdict
from typing import Dict, List, Optional

# ─── Rate limiting ─────────────────────────────────────────────────────────────
_rate_map: Dict[int, List[float]] = defaultdict(list)


def check_rate(uid: int, limit: int = 5, window: int = 30):
    now  = time.time()
    reqs = _rate_map[uid]
    reqs[:] = [t for t in reqs if now - t < window]
    if len(reqs) >= limit:
        return False, f"Wait {int(window - (now - reqs[0]))}s"
    reqs.append(now)
    return True, None


# ─── Active jobs ──────────────────────────────────────────────────────────────
active_tests: Dict[int, bool]              = {}
active_mrz:   Dict[int, asyncio.Event]     = {}

# uid → { "charged": [...], "approved": [...], "dead": [...], "errors": [...] }
mrz_results:  Dict[int, Dict[str, List[str]]] = {}

# ─── Spinner / progress helpers ───────────────────────────────────────────────
ANIM_FRAMES = ["⠋", "⠙", "⠸", "⠴", "⠦", "⠇"]
_frame_idx: Dict[int, int] = defaultdict(int)


def spin(uid: int) -> str:
    f = ANIM_FRAMES[_frame_idx[uid] % len(ANIM_FRAMES)]
    _frame_idx[uid] += 1
    return f


def progress_bar(done: int, total: int, width: int = 16) -> str:
    if total == 0:
        return "░" * width
    filled = int(width * done / total)
    return "█" * filled + "░" * (width - filled)
