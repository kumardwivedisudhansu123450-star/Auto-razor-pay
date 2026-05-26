"""
core/site_utils.py — Razorpay payment-page site loader with auto-removal
"""
import json
import logging
import random
from typing import Dict, List, Optional

import aiohttp

from config import RK_SITES, SITE_TIMEOUT
from core.redis_client import redis

logger = logging.getLogger("nagu.sites")


def _gen_ua() -> str:
    import random
    maj  = random.randint(120, 148)
    bld  = random.randint(5000, 7000)
    ptch = random.randint(50, 250)
    return (
        f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        f"AppleWebKit/537.36 (KHTML, like Gecko) "
        f"Chrome/{maj}.0.{bld}.{ptch} Safari/537.36"
    )


def _extract_json_var(content: str, var_name: str) -> str:
    prefix = f"var {var_name} ="
    idx = content.find(prefix)
    if idx == -1:
        return ""
    idx += len(prefix)
    while idx < len(content) and content[idx] in " \t\n\r":
        idx += 1
    if idx >= len(content) or content[idx] != "{":
        return ""
    depth = 0
    in_s = False
    esc = False
    for i in range(idx, len(content)):
        c = content[i]
        if esc:
            esc = False
            continue
        if c == "\\" and in_s:
            esc = True
            continue
        if c == '"':
            in_s = not in_s
            continue
        if in_s:
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return content[idx : i + 1]
    return ""


async def load_site_data(
    url: str,
    ua: str,
    proxy_url: Optional[str] = None,
    auto_remove: bool = True,
) -> Optional[Dict]:
    """Load and parse a Razorpay payment-page site. Auto-removes bad sites."""
    try:
        kw = {"proxy": proxy_url} if proxy_url else {}
        conn = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=conn) as sess:
            async with sess.get(
                url,
                headers={"User-Agent": ua, "Accept": "text/html,*/*"},
                timeout=aiohttp.ClientTimeout(total=SITE_TIMEOUT),
                **kw,
            ) as r:
                if r.status != 200:
                    if auto_remove:
                        await redis.lrem(RK_SITES, 0, url)
                        logger.info(f"Auto-removed dead site [{r.status}]: {url[:50]}")
                    return None
                body = await r.text(errors="replace")

        js = _extract_json_var(body, "data")
        if not js:
            if auto_remove:
                await redis.lrem(RK_SITES, 0, url)
                logger.info(f"Auto-removed no-data site: {url[:50]}")
            return None

        d = json.loads(js)
        if d.get("error_code") or d.get("message"):
            if auto_remove:
                await redis.lrem(RK_SITES, 0, url)
                logger.info(f"Auto-removed error site: {url[:50]}")
            return None

        key_id = d.get("key_id", "") or d.get("key", "")
        if not key_id:
            return None

        pl    = d.get("payment_link") or d.get("payment_page") or {}
        plink = pl.get("id", "")
        items = pl.get("payment_page_items", [])
        ppid  = items[0].get("id", "") if items else ""
        if not plink:
            return None

        return {
            "url":     url,
            "key_id":  key_id,
            "plink":   plink,
            "ppid":    ppid,
            "keyless": d.get("keyless_header", ""),
        }
    except Exception as ex:
        logger.debug(f"load_site_data({url[:40]}): {ex}")
        return None


async def get_live_sites(proxy_urls: List[str]) -> List[Dict]:
    """Load all sites from Redis, auto-remove dead/invalid, return live dicts."""
    import asyncio
    raw_sites = await redis.lrange(RK_SITES, 0, -1)
    if not raw_sites:
        return []

    ua   = _gen_ua()
    conn = aiohttp.TCPConnector(ssl=False, limit=8)
    tasks = []
    async with aiohttp.ClientSession(connector=conn):
        for i, site in enumerate(raw_sites):
            px = proxy_urls[i % len(proxy_urls)] if proxy_urls else None
            tasks.append(load_site_data(site, ua, px, auto_remove=True))
        results = await asyncio.gather(*tasks, return_exceptions=True)

    return [r for r in results if isinstance(r, dict)]
