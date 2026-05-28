"""
sui/rpc.py

Sui RPC client via Tatum for network health checks and gas price queries.
"""

import httpx
from typing import Dict, Any, Optional
from core.config import settings
from core.logger import get_logger

logger = get_logger(__name__)


class SuiRpcClient:
    """Interfaces with Sui blockchain via Tatum's RPC gateway."""

    def __init__(self):
        self.rpc_url = settings.sui_rpc_url
        self.tatum_key = settings.tatum_api_key
        self.network = settings.sui_network

    async def health_check(self) -> Dict[str, Any]:
        """
        Check Sui network health via Tatum RPC.
        Returns {"status": str, "network": str, "rpc_online": bool, ...}
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Simple RPC call to check node health
                resp = await client.post(
                    self.rpc_url,
                    json={
                        "jsonrpc": "2.0",
                        "method": "sui_getLatestCheckpointSequenceNumber",
                        "params": [],
                        "id": 1,
                    },
                    headers={"x-api-key": self.tatum_key} if self.tatum_key else {},
                )
                resp.raise_for_status()
                data = resp.json()

                # Check if we got a valid response
                if "result" in data:
                    checkpoint = data["result"]
                    logger.info(f"Sui RPC healthy | checkpoint={checkpoint}")
                    return {
                        "status": "ok",
                        "network": self.network,
                        "rpc_online": True,
                        "latest_checkpoint": checkpoint,
                    }
                else:
                    logger.warning(f"Sui RPC response missing result: {data}")
                    return {
                        "status": "degraded",
                        "network": self.network,
                        "rpc_online": False,
                        "error": data.get("error", "Unknown error"),
                    }

        except httpx.HTTPError as e:
            logger.error(f"Sui RPC HTTP error: {e}")
            return {
                "status": "offline",
                "network": self.network,
                "rpc_online": False,
                "error": str(e),
            }
        except Exception as e:
            logger.error(f"Sui RPC client error: {e}")
            return {
                "status": "error",
                "network": self.network,
                "rpc_online": False,
                "error": str(e),
            }

    async def get_gas_price(self) -> Optional[int]:
        """
        Fetch current reference gas price from Sui network.
        Returns gas price in MIST per unit, or None if unavailable.
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    self.rpc_url,
                    json={
                        "jsonrpc": "2.0",
                        "method": "suix_getReferenceGasPrice",
                        "params": [],
                        "id": 1,
                    },
                    headers={"x-api-key": self.tatum_key} if self.tatum_key else {},
                )
                resp.raise_for_status()
                data = resp.json()

                if "result" in data:
                    gas_price = int(data["result"])
                    logger.debug(f"Sui gas price: {gas_price} MIST")
                    return gas_price
                else:
                    logger.warning(f"Sui gas price query failed: {data}")
                    return None

        except Exception as e:
            logger.error(f"Failed to fetch gas price: {e}")
            return None


# Global instance
sui_rpc = SuiRpcClient()
