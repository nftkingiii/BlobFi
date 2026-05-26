"""
walrus/client.py

Handles all Walrus blob storage operations for BlobFi.
Each yield snapshot is stored as an immutable blob on Walrus.
"""

import httpx
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from core.config import settings
from core.logger import get_logger

logger = get_logger(__name__)


class WalrusClient:
    """
    Thin async client for the Walrus HTTP publisher/aggregator API.
    Docs: https://docs.wal.app
    """

    def __init__(self):
        self.publisher = settings.walrus_publisher_url.rstrip("/")
        self.aggregator = settings.walrus_aggregator_url.rstrip("/")
        self.epochs = settings.walrus_epochs

    async def store_snapshot(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """
        Serialize a yield snapshot to JSON and store it on Walrus.
        Returns the blob_id plus metadata on success.
        """
        payload = json.dumps(snapshot, default=str).encode("utf-8")
        url = f"{self.publisher}/v1/blobs?epochs={self.epochs}"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.put(
                    url,
                    content=payload,
                    headers={"Content-Type": "application/octet-stream"},
                )
                resp.raise_for_status()
                result = resp.json()

            blob_id = self._extract_blob_id(result)
            logger.info("Stored snapshot on Walrus | blob_id=%s", blob_id)

            return {
                "blob_id": blob_id,
                "stored_at": datetime.now(timezone.utc).isoformat(),
                "size_bytes": len(payload),
                "epochs": self.epochs,
                "walrus_response": result,
            }

        except httpx.HTTPStatusError as e:
            logger.error("Walrus store failed [HTTP %s]: %s", e.response.status_code, e)
            raise
        except Exception as e:
            logger.error("Walrus store failed: %s", e)
            raise

    async def retrieve_snapshot(self, blob_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a stored yield snapshot by blob_id from Walrus aggregator.
        """
        url = f"{self.aggregator}/v1/blobs/{blob_id}"
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = json.loads(resp.content)
            logger.info("Retrieved snapshot from Walrus | blob_id=%s", blob_id)
            return data
        except Exception as e:
            logger.error("Walrus retrieve failed for blob_id=%s: %s", blob_id, e)
            return None

    def _extract_blob_id(self, response: Dict) -> str:
        """
        Parse blob_id from Walrus publisher response.
        Handles both 'newlyCreated' and 'alreadyCertified' response shapes.
        """
        if "newlyCreated" in response:
            return response["newlyCreated"]["blobObject"]["blobId"]
        if "alreadyCertified" in response:
            return response["alreadyCertified"]["blobId"]
        # Fallback — some versions return blobId directly
        return response.get("blobId", response.get("blob_id", "unknown"))


class SnapshotBuilder:
    """
    Constructs a standardized yield snapshot payload for Walrus storage.
    """

    @staticmethod
    def build(
        protocols: List[Dict[str, Any]],
        ai_report: str,
        chain_tvl: Dict[str, Any],
        snapshot_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        top = protocols[0] if protocols else {}

        return {
            "snapshot_id": snapshot_id or f"blobfi-{int(now.timestamp())}",
            "project": "BlobFi",
            "chain": "Sui",
            "timestamp": now.isoformat(),
            "timestamp_unix": int(now.timestamp()),
            "chain_tvl_usd": chain_tvl.get("tvl_usd", 0),
            "protocols_tracked": len(protocols),
            "top_protocol": top.get("protocol", ""),
            "top_apy": top.get("apy", 0),
            "avg_apy": round(
                sum(p["apy"] for p in protocols) / len(protocols), 2
            ) if protocols else 0,
            "protocols": protocols,
            "ai_report": ai_report,
            "metadata": {
                "generator": "BlobFi AI Agent",
                "version": "1.0.0",
                "source": "DefiLlama",
                "storage": "Walrus",
            },
        }


# Singleton
walrus = WalrusClient()
snapshot_builder = SnapshotBuilder()
