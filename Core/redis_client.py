"""
core/redis_client.py — Upstash Redis async client
"""
import logging
from typing import Any, List, Optional
import httpx

from config import REDIS_URL, REDIS_TOKEN

logger = logging.getLogger("nagu.redis")


class RedisClient:
    def __init__(self, url: str, token: str):
        self._url = url.rstrip("/")
        self._hdr = {
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
        }

    async def _req(self, *args) -> Any:
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.post(
                    f"{self._url}/pipeline",
                    headers=self._hdr,
                    json=[list(args)],
                )
                r.raise_for_status()
                d = r.json()
                if isinstance(d, list) and d:
                    return d[0].get("result")
                return d.get("result") if isinstance(d, dict) else None
        except Exception as ex:
            logger.error(f"Redis [{args[0]}]: {ex}")
            return None

    # ── String ────────────────────────────────────────────────────────────────
    async def get(self, k: str) -> Optional[str]:
        return await self._req("GET", k)

    async def set(self, k: str, v: str) -> bool:
        return await self._req("SET", k, v) == "OK"

    async def incr(self, k: str) -> int:
        return await self._req("INCR", k) or 0

    async def delete(self, *k: str) -> int:
        return await self._req("DEL", *k) or 0

    async def exists(self, k: str) -> bool:
        return bool(await self._req("EXISTS", k))

    # ── Set ───────────────────────────────────────────────────────────────────
    async def sadd(self, k: str, *m: str) -> int:
        return await self._req("SADD", k, *m) or 0

    async def srem(self, k: str, *m: str) -> int:
        return await self._req("SREM", k, *m) or 0

    async def smembers(self, k: str) -> set:
        r = await self._req("SMEMBERS", k)
        return set(r) if r else set()

    async def sismember(self, k: str, m: str) -> bool:
        return bool(await self._req("SISMEMBER", k, m))

    # ── List ──────────────────────────────────────────────────────────────────
    async def lpush(self, k: str, *v: str) -> int:
        return await self._req("LPUSH", k, *v) or 0

    async def lrange(self, k: str, s: int, e: int) -> List[str]:
        r = await self._req("LRANGE", k, s, e)
        return r if r else []

    async def lrem(self, k: str, c: int, el: str) -> int:
        return await self._req("LREM", k, c, el) or 0

    async def llen(self, k: str) -> int:
        return await self._req("LLEN", k) or 0

    # ── Hash ──────────────────────────────────────────────────────────────────
    async def hset(self, k: str, f: str, v: str) -> int:
        return await self._req("HSET", k, f, v) or 0

    async def hget(self, k: str, f: str) -> Optional[str]:
        return await self._req("HGET", k, f)

    async def hgetall(self, k: str) -> dict:
        r = await self._req("HGETALL", k)
        if not r:
            return {}
        it = iter(r)
        return {kk: vv for kk, vv in zip(it, it)}

    async def hdel(self, k: str, *f: str) -> int:
        return await self._req("HDEL", k, *f) or 0

    async def hincrby(self, k: str, f: str, n: int) -> int:
        return await self._req("HINCRBY", k, f, n) or 0


# ── Singleton ─────────────────────────────────────────────────────────────────
redis = RedisClient(REDIS_URL, REDIS_TOKEN)
