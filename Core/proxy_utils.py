"""
core/proxy_utils.py — Proxy parsing, testing, auto-removal of dead proxies
"""
import asyncio
import logging
import random
from typing import List, Optional, Tuple

import aiohttp

from config import PROXY_TIMEOUT, RK_PROXIES
from core.redis_client import redis

logger = logging.getLogger("nagu.proxy")


def parse_proxy(raw: str) -> Optional[str]:
    """Normalize any proxy format to aiohttp-compatible URL."""
    raw = raw.strip()
    if not raw:
        return None
    if "://" in raw:
        return raw
    parts = raw.split(":")
    if len(parts) == 4:
        return f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
    if len(parts) == 2:
        return f"http://{parts[0]}:{parts[1]}"
    if "@" in raw:
        creds, addr = raw.rsplit("@", 1)
        return f"http://{creds}@{addr}"
    return None


async def test_proxy_raw(raw: str) -> Tuple[bool, float]:
    """Test a single proxy. Returns (is_alive, latency_ms)."""
    url = parse_proxy(raw)
    if not url:
        return False, 0.0
    import time
    t0 = time.monotonic()
    try:
        conn = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=conn) as s:
            async with s.get(
                "http://ip-api.com/json",
                proxy=url,
                timeout=aiohttp.ClientTimeout(total=PROXY_TIMEOUT),
            ) as r:
                lat = (time.monotonic() - t0) * 1000
                return r.status == 200, round(lat, 1)
    except Exception:
        return False, 0.0


async def get_live_proxies(auto_remove: bool = True) -> List[str]:
    """Return list of working proxy URL strings. Auto-removes dead ones."""
    raw_list = await redis.lrange(RK_PROXIES, 0, -1)
    if not raw_list:
        return []

    async def _check(raw: str) -> Optional[str]:
        ok, _ = await test_proxy_raw(raw)
        if not ok:
            if auto_remove:
                await redis.lrem(RK_PROXIES, 0, raw)
                logger.info(f"Auto-removed dead proxy: {raw[:30]}")
            return None
        return parse_proxy(raw)

    results = await asyncio.gather(*[_check(p) for p in raw_list], return_exceptions=True)
    return [r for r in results if isinstance(r, str)]


def pick_proxy(proxies: List[str]) -> Optional[str]:
    return random.choice(proxies) if proxies else None
