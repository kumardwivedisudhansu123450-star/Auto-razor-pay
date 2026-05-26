"""
core/bin_lookup.py — BIN lookup with VBV/3DS analysis
"""
import logging
from typing import Dict

import aiohttp

logger = logging.getLogger("nagu.bin")

_VBV_NETS = {"visa", "mastercard", "amex"}

_EMPTY = {
    "scheme":    "UNKNOWN",
    "type":      "UNKNOWN",
    "brand":     "",
    "level":     "UNKNOWN",
    "bank":      "Unknown",
    "country":   "Unknown",
    "flag":      "",
    "prepaid":   "No",
    "vbv_type":  "3DS",
    "needs_3ds": True,
    "ease":      "unknown",
}


async def lookup_bin(bin6: str) -> Dict[str, str]:
    """Query binlist.net for BIN info. Returns a safe dict — never raises."""
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(
                f"https://lookup.binlist.net/{bin6[:8]}",
                headers={"Accept-Version": "3"},
                timeout=aiohttp.ClientTimeout(total=6),
            ) as r:
                if r.status != 200:
                    return dict(_EMPTY)
                d = await r.json()

        scheme  = d.get("scheme", "unknown").lower()
        typ     = d.get("type",   "unknown")
        brand   = d.get("brand",  "")
        bank    = d.get("bank",    {}).get("name",  "Unknown")
        country = d.get("country", {}).get("name",  "Unknown")
        flag    = d.get("country", {}).get("emoji", "")
        prepaid = d.get("prepaid", False)

        # Card level from brand string
        level = "UNKNOWN"
        if brand:
            bl = brand.upper()
            for kw in (
                "PLATINUM", "GOLD", "BLACK", "INFINITE", "WORLD",
                "SIGNATURE", "CLASSIC", "STANDARD", "BUSINESS", "CORPORATE",
            ):
                if kw in bl:
                    level = kw
                    break

        needs_3ds = scheme in _VBV_NETS
        vbv_type  = (
            "VBV"     if scheme == "visa"       else
            "3DS"     if scheme == "mastercard" else
            "SafeKey" if scheme == "amex"       else
            "3DS"
        )
        ease = "harder to charge" if needs_3ds else "easier to charge"

        return {
            "scheme":    scheme.upper(),
            "type":      typ.upper(),
            "brand":     brand,
            "level":     level,
            "bank":      bank,
            "country":   country,
            "flag":      flag,
            "prepaid":   "Yes" if prepaid else "No",
            "vbv_type":  vbv_type,
            "needs_3ds": needs_3ds,
            "ease":      ease,
        }
    except Exception as ex:
        logger.debug(f"lookup_bin({bin6}): {ex}")
        return dict(_EMPTY)
