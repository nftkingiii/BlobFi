"""
agents/agent.py

BlobFi AI agent — powered by Claude.
Analyzes live Sui yield data and generates the report stored on Walrus.
Adapted from MantleYield's MantleYieldAgent.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

import anthropic

from core.config import settings
from core.logger import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are BlobFi's AI yield analyst for the Sui blockchain ecosystem.

Your job is to analyze live DeFi yield data from Sui protocols and produce clear, 
actionable intelligence reports. You are direct, data-driven, and concise.

When writing reports:
- Lead with the most important insight
- Compare current APYs to identify outliers
- Flag any unusually high yields that warrant risk caution
- Note which protocols dominate by TVL vs APY
- Keep reports under 250 words
- Use protocol names exactly as given
- Format numbers cleanly (e.g. 24.5% APY, $18.5M TVL)

You understand Sui DeFi: Cetus (DEX/AMM), NAVI Protocol (lending), 
Scallop (lending), Aftermath Finance (liquid staking), Turbos Finance (DEX),
Bluefin (perps/DEX), Bucket Protocol (CDP stablecoin), SuiLend.
"""

SUI_INTENT_PATTERNS = {
    "top_yields": r"\b(best|top|highest|recommend|where should|what yield)\b",
    "market": r"\b(summary|overview|market|snapshot|what.s happening|how.s sui)\b",
    "risk": r"\b(safe|low.?risk|conservative|safest|no risk|stable)\b",
    "compare": r"\b(vs|versus|compare|which is better|difference between)\b",
    "estimate": r"\b(\$[\d,]+|how much|earn|make|return|profit)\b",
    "category_dex": r"\b(dex|amm|lp|liquidity|swap|cetus|turbos|bluefin)\b",
    "category_lend": r"\b(lending|borrow|supply|navi|scallop|suilend)\b",
    "category_stake": r"\b(staking|stake|lst|liquid staking|aftermath|afsui)\b",
    "category_cdp": r"\b(cdp|stablecoin|buck|bucket)\b",
}


def classify_intent(query: str) -> str:
    q = query.lower()
    for intent, pattern in SUI_INTENT_PATTERNS.items():
        if re.search(pattern, q):
            return intent
    return "general"


@dataclass
class BlobFiAgent:
    """
    AI agent that analyzes Sui yield data and generates
    structured reports for Walrus storage.
    """
    _client: anthropic.Anthropic = field(default=None, init=False)

    def __post_init__(self):
        if settings.anthropic_api_key:
            self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    async def generate_snapshot_report(
        self,
        protocols: List[Dict[str, Any]],
        chain_tvl: Dict[str, Any],
    ) -> str:
        """
        Generate the AI yield intelligence report that gets stored on Walrus.
        This is the core value-add over raw data.
        """
        if not self._client:
            return self._fallback_report(protocols, chain_tvl)

        data_summary = self._format_for_prompt(protocols, chain_tvl)

        prompt = f"""Here is the current live yield data for Sui DeFi protocols:

{data_summary}

Write a yield intelligence report covering:
1. Overall Sui DeFi market health (TVL + activity)
2. Top 3 yield opportunities ranked by risk-adjusted return
3. Any notable anomalies (unusually high/low APYs vs recent norms)
4. One-sentence recommendation for conservative, moderate, and aggressive risk profiles

Be specific with numbers. This report will be stored permanently on Walrus as an immutable snapshot."""

        try:
            message = self._client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=400,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            report = message.content[0].text
            logger.info("AI report generated (%d chars)", len(report))
            return report

        except Exception as e:
            logger.error("Claude API failed: %s", e)
            return self._fallback_report(protocols, chain_tvl)

    def _format_for_prompt(
        self,
        protocols: List[Dict[str, Any]],
        chain_tvl: Dict[str, Any],
    ) -> str:
        lines = [f"Chain TVL: ${chain_tvl.get('tvl_usd', 0):,.0f}"]
        lines.append(f"Protocols tracked: {len(protocols)}\n")
        lines.append("Protocol | Category | APY | Base APY | Reward APY | TVL | IL Risk")
        lines.append("-" * 80)
        for p in protocols:
            lines.append(
                f"{p['protocol']} | {p['category']} | {p['apy']}% | "
                f"{p['apy_base']}% | {p['apy_reward']}% | "
                f"${p['tvl_usd']:,.0f} | {p['il_risk']}"
            )
        return "\n".join(lines)

    def _fallback_report(
        self,
        protocols: List[Dict[str, Any]],
        chain_tvl: Dict[str, Any],
    ) -> str:
        """Static report used if Claude API is unavailable."""
        top = protocols[:3] if protocols else []
        top_str = ", ".join(
            f"{p['protocol']} ({p['apy']}% APY)" for p in top
        )
        return (
            f"BlobFi Snapshot — Sui DeFi | "
            f"Chain TVL: ${chain_tvl.get('tvl_usd', 0):,.0f} | "
            f"Top yields: {top_str} | "
            f"Snapshot generated at {datetime.now(timezone.utc).isoformat()}"
        )

    async def query(self, user_query: str, protocols: List[Dict[str, Any]]) -> str:
        """
        Answer a user question about current Sui yields.
        Used for the chat interface on the frontend.
        """
        if not self._client:
            return "AI agent unavailable — check ANTHROPIC_API_KEY."

        intent = classify_intent(user_query)
        filtered = self._filter_by_intent(protocols, intent)
        data = self._format_for_prompt(filtered or protocols, {})

        prompt = (
            f"Live Sui yield data:\n{data}\n\n"
            f"User question: {user_query}\n\n"
            f"Answer using only the data above. Be direct and specific. Under 150 words."
        )

        try:
            message = self._client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=300,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            return message.content[0].text
        except Exception as e:
            logger.error("Agent query failed: %s", e)
            return "Unable to process query at this time."

    def _filter_by_intent(
        self, protocols: List[Dict], intent: str
    ) -> List[Dict]:
        cat_map = {
            "category_dex": "DEX",
            "category_lend": "Lending",
            "category_stake": "Staking",
            "category_cdp": "CDP",
        }
        if intent in cat_map:
            return [p for p in protocols if p.get("category") == cat_map[intent]]
        if intent == "risk":
            return [p for p in protocols if p.get("il_risk") in ("none", "low")]
        if intent == "top_yields":
            return sorted(protocols, key=lambda x: x["apy"], reverse=True)[:5]
        return protocols


# Singleton
blobfi_agent = BlobFiAgent()
