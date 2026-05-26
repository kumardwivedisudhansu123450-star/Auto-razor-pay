"""
utils/auth.py — Authorization helpers (admin, sudo, plan, ban)
"""
import time
from datetime import datetime
from typing import List, Optional, Tuple

from config import ADMIN_USER_ID, RK_BANNED, RK_KEYS, RK_SUDO
from core.redis_client import redis


def is_admin(uid: int) -> bool:
    return uid == ADMIN_USER_ID


async def is_sudo(uid: int) -> bool:
    if is_admin(uid):
        return True
    return await redis.sismember(RK_SUDO, str(uid))


async def is_banned(uid: int) -> bool:
    return await redis.sismember(RK_BANNED, str(uid))


async def has_plan(uid: int) -> bool:
    exp = await redis.hget(f"bot:u:{uid}", "plan_exp")
    if not exp:
        return False
    try:
        return float(exp) > time.time()
    except Exception:
        return False


async def is_auth(uid: int) -> bool:
    if is_admin(uid) or await is_sudo(uid):
        return True
    return await has_plan(uid)


async def get_role(uid: int) -> str:
    if is_admin(uid):
        return "Owner"
    if await is_sudo(uid):
        return "Sudo"
    if await has_plan(uid):
        return await redis.hget(f"bot:u:{uid}", "plan_name") or "Premium"
    return "Free"


# ─── Key / Plan management ────────────────────────────────────────────────────

import secrets
import string


def _gen_key() -> str:
    chars = string.ascii_uppercase + string.digits
    s = lambda: "".join(secrets.choice(chars) for _ in range(4))
    return f"NAGU-{s()}-{s()}-{s()}"


async def create_keys(days: int, count: int, by: int) -> List[str]:
    keys = []
    for _ in range(count):
        k = _gen_key()
        await redis.hset(f"bot:key:{k}", "days",    str(days))
        await redis.hset(f"bot:key:{k}", "made_at", str(int(time.time())))
        await redis.hset(f"bot:key:{k}", "made_by", str(by))
        await redis.hset(f"bot:key:{k}", "used_by", "")
        await redis.sadd(RK_KEYS, k)
        keys.append(k)
    return keys


async def redeem_key(key: str, uid: int) -> Tuple[bool, str]:
    key = key.upper().strip()
    kd  = await redis.hgetall(f"bot:key:{key}")
    if not kd:
        return False, "Key not found."
    if kd.get("used_by"):
        return False, "Already redeemed."
    if key not in await redis.smembers(RK_KEYS):
        return False, "Key expired or invalid."
    days = int(kd.get("days", 0))
    if days <= 0:
        return False, "Invalid key (0 days)."
    expiry   = time.time() + days * 86400
    plan_nm  = f"{days}-Day Premium"
    await redis.hset(f"bot:key:{key}", "used_by", str(uid))
    await redis.srem(RK_KEYS, key)
    await redis.hset(f"bot:u:{uid}", "plan_name", plan_nm)
    await redis.hset(f"bot:u:{uid}", "plan_exp",  str(expiry))
    await redis.hset(f"bot:u:{uid}", "activated",  str(int(time.time())))
    exp_str = datetime.fromtimestamp(expiry).strftime("%Y-%m-%d %H:%M UTC")
    return True, f"{plan_nm} — expires {exp_str}"


async def give_plan(uid: int, days: int, name: str, by: int) -> str:
    expiry = time.time() + days * 86400
    await redis.hset(f"bot:u:{uid}", "plan_name", name)
    await redis.hset(f"bot:u:{uid}", "plan_exp",  str(expiry))
    await redis.hset(f"bot:u:{uid}", "given_by",  str(by))
    return datetime.fromtimestamp(expiry).strftime("%Y-%m-%d %H:%M UTC")
