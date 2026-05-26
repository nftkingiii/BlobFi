"""
agents/defillama.py

Fetches live yield data for Sui protocols from DefiLlama.
Adapted from MantleYield — chain filter swapped to Sui ecosystem.
"""

import httpx
import asyncio
from typing import List, Dict, Any
from core.config import settings
from core.logger import get_logger

logger = get_logger(__name__)

# Known Sui protocol names on DefiLlama (chain field = "Sui")
SUI_PROTOCOLS = {
    "cetus",
    "turbos",
    "scallop",
    "navi protocol",
    "aftermath finance",
    "bluefin",
    "bucket protocol",
    "suilend",
    "flowx finance",
    "kai finance",
}

CATEGORY_MAP = {
    "Dexes": "DEX",
    "Lending": "Lending",
    "Liquid Staking": "Staking",
    "Yield": "Vault",
    "CDP": "CDP",
    "Derivatives": "Derivatives",
    "RWA": "RWA",
}


async def fetch_sui_yields() -> List[Dict[str, Any]]:
    """
    Pull all yield pools from DefiLlama and filter to Sui chain.
    Returns a normalized list sorted by APY descending.
    """
    url = f"{settings.defillama_yields_url}/pools"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()

        pools = data.get("data", [])
        sui_pools = [p for p in pools if _is_sui_pool(p)]

        normalized = [_normalize(p) for p in sui_pools]
        normalized.sort(key=lambda x: x["apy"], reverse=True)

        logger.info("Fetched %d Sui yield pools from DefiLlama", len(normalized))
        return normalized[:settings.top_protocols_count]

    except Exception as e:
        logger.error("DefiLlama fetch failed: %s", e)
        return _fallback_data()


def _is_sui_pool(pool: Dict) -> bool:
    chain = (pool.get("chain") or "").lower()
    project = (pool.get("project") or "").lower()
    if chain == "sui":
        return True
    # Some pools list chain as a variant
    if "sui" in chain:
        return True
    return False


def _normalize(pool: Dict) -> Dict[str, Any]:
    apy = pool.get("apy") or 0.0
    apy_base = pool.get("apyBase") or 0.0
    apy_reward = pool.get("apyReward") or 0.0
    tvl = pool.get("tvlUsd") or 0.0
    project = pool.get("project") or "Unknown"
    symbol = pool.get("symbol") or ""
    category = CATEGORY_MAP.get(pool.get("category") or "", "Other")

    return {
        "pool_id": pool.get("pool", ""),
        "protocol": _clean_name(project),
        "symbol": symbol,
        "apy": round(apy, 2),
        "apy_base": round(apy_base, 2),
        "apy_reward": round(apy_reward, 2),
        "tvl_usd": round(tvl, 2),
        "category": category,
        "chain": "Sui",
        "il_risk": pool.get("ilRisk") or "none",
        "stablecoin": pool.get("stablecoin") or False,
        "url": pool.get("url") or "",
    }


def _clean_name(name: str) -> str:
    replacements = {
        "navi-protocol": "NAVI Protocol",
        "cetus-amm": "Cetus",
        "turbos-finance": "Turbos Finance",
        "scallop-lend": "Scallop",
        "aftermath-finance": "Aftermath Finance",
        "bluefin": "Bluefin",
        "bucket-protocol": "Bucket Protocol",
        "suilend": "SuiLend",
        "flowx-finance": "FlowX Finance",
    }
    return replacements.get(name.lower(), name.title())


def _fallback_data() -> List[Dict[str, Any]]:
    """Static fallback if DefiLlama is unreachable during demo."""
    return [
        {"pool_id": "sui-cetus-1", "protocol": "Cetus", "symbol": "SUI/USDC", "apy": 24.5, "apy_base": 18.2, "apy_reward": 6.3, "tvl_usd": 18_500_000, "category": "DEX", "chain": "Sui", "il_risk": "medium", "stablecoin": False, "url": ""},
        {"pool_id": "sui-navi-1", "protocol": "NAVI Protocol", "symbol": "SUI", "apy": 12.8, "apy_base": 12.8, "apy_reward": 0, "tvl_usd": 42_000_000, "category": "Lending", "chain": "Sui", "il_risk": "low", "stablecoin": False, "url": ""},
        {"pool_id": "sui-scallop-1", "protocol": "Scallop", "symbol": "USDC", "apy": 8.4, "apy_base": 8.4, "apy_reward": 0, "tvl_usd": 31_200_000, "category": "Lending", "chain": "Sui", "il_risk": "none", "stablecoin": True, "url": ""},
        {"pool_id": "sui-turbos-1", "protocol": "Turbos Finance", "symbol": "SUI/USDT", "apy": 19.1, "apy_base": 14.5, "apy_reward": 4.6, "tvl_usd": 9_800_000, "category": "DEX", "chain": "Sui", "il_risk": "medium", "stablecoin": False, "url": ""},
        {"pool_id": "sui-aftermath-1", "protocol": "Aftermath Finance", "symbol": "afSUI", "apy": 6.2, "apy_base": 6.2, "apy_reward": 0, "tvl_usd": 55_000_000, "category": "Staking", "chain": "Sui", "il_risk": "low", "stablecoin": False, "url": ""},
        {"pool_id": "sui-bluefin-1", "protocol": "Bluefin", "symbol": "BTC/USDC", "apy": 31.7, "apy_base": 22.0, "apy_reward": 9.7, "tvl_usd": 7_100_000, "category": "DEX", "chain": "Sui", "il_risk": "high", "stablecoin": False, "url": ""},
        {"pool_id": "sui-bucket-1", "protocol": "Bucket Protocol", "symbol": "BUCK/USDC", "apy": 9.5, "apy_base": 9.5, "apy_reward": 0, "tvl_usd": 14_300_000, "category": "CDP", "chain": "Sui", "il_risk": "low", "stablecoin": True, "url": ""},
    ]


async def fetch_sui_tvl() -> Dict[str, Any]:
    """Fetch overall Sui chain TVL from DefiLlama."""
    url = f"{settings.defillama_base_url}/v2/chains"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            chains = resp.json()
        sui = next((c for c in chains if c.get("name", "").lower() == "sui"), None)
        return {"tvl_usd": sui.get("tvl", 0) if sui else 0, "chain": "Sui"}
    except Exception as e:
        logger.warning("TVL fetch failed: %s", e)
        return {"tvl_usd": 0, "chain": "Sui"}
