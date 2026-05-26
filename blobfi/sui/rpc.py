"""
sui/rpc.py

Sui RPC client powered by Tatum endpoints.
Used to record Walrus blob IDs on-chain and query Sui state.
"""

import httpx
from typing import Any, Dict, Optional
from core.config import settings
from core.logger import get_logger

logger = get_logger(__name__)


class SuiRpcClient:
    """
    JSON-RPC client for Sui, routed through Tatum's infrastructure.
    Tatum docs: https://docs.tatum.io/reference/rpc-sui
    """

    def __init__(self):
        self.rpc_url = settings.sui_rpc_url
        self.api_key = settings.tatum_api_key
        self._id = 0

    def _next_id(self) -> int:
        self._id += 1
        return self._id

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    async def call(self, method: str, params: list = None) -> Any:
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
            "params": params or [],
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    self.rpc_url,
                    json=payload,
                    headers=self._headers(),
                )
                resp.raise_for_status()
                data = resp.json()

            if "error" in data:
                logger.error("Sui RPC error [%s]: %s", method, data["error"])
                return None

            return data.get("result")

        except Exception as e:
            logger.error("Sui RPC call failed [%s]: %s", method, e)
            return None

    async def get_latest_checkpoint(self) -> Optional[Dict]:
        """Get the latest Sui checkpoint (proves RPC is live)."""
        return await self.call("sui_getLatestCheckpointSequenceNumber")

    async def get_chain_identifier(self) -> Optional[str]:
        """Returns the chain ID string (mainnet/testnet)."""
        return await self.call("sui_getChainIdentifier")

    async def get_reference_gas_price(self) -> Optional[int]:
        """Current reference gas price in MIST."""
        result = await self.call("suix_getReferenceGasPrice")
        try:
            return int(result) if result else None
        except (ValueError, TypeError):
            return None

    async def get_object(self, object_id: str) -> Optional[Dict]:
        """Fetch a Sui object by ID."""
        return await self.call("sui_getObject", [
            object_id,
            {"showContent": True, "showOwner": True, "showType": True}
        ])

    async def health_check(self) -> Dict[str, Any]:
        """
        Quick health check — verifies Tatum RPC is reachable.
        Returns chain identifier + latest checkpoint.
        """
        chain_id = await self.get_chain_identifier()
        checkpoint = await self.get_latest_checkpoint()
        gas_price = await self.get_reference_gas_price()

        return {
            "chain_identifier": chain_id,
            "latest_checkpoint": checkpoint,
            "reference_gas_price_mist": gas_price,
            "rpc_url": self.rpc_url,
            "network": settings.sui_network,
            "tatum_key_set": bool(self.api_key),
        }


# Singleton
sui_rpc = SuiRpcClient()
