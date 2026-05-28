"""
walrus/client.py

Walrus blob storage integration for BlobFi.
Stores immutable yield snapshots on Walrus decentralized storage.
"""

import httpx
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from dataclasses import dataclass
from core.config import settings
from core.logger import get_logger

logger = get_logger(__name__)


class SnapshotBuilder:
    """Builds snapshot payloads before storing on Walrus."""

    def build(
        self,
        protocols: list,
        ai_report: str,
        chain_tvl: Dict[str, Any],
        snapshot_id: str,
    ) -> Dict[str, Any]:
        """
        Construct the complete snapshot payload.
        This will be serialized to JSON and uploaded to Walrus.
        """
        top_protocol = max(protocols, key=lambda p: p["apy"]) if protocols else None
        avg_apy = sum(p["apy"] for p in protocols) / len(protocols) if protocols else 0

        return {
            "snapshot_id": snapshot_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "chain": "Sui",
            "protocols": protocols,
            "chain_tvl": chain_tvl,
            "ai_report": ai_report,
            "top_protocol": top_protocol["protocol"] if top_protocol else None,
            "top_apy": round(top_protocol["apy"], 2) if top_protocol else 0,
            "avg_apy": round(avg_apy, 2),
            "protocol_count": len(protocols),
        }


class WalrusClient:
    """Handles all Walrus blob storage operations."""

    def __init__(self):
        self.publisher_url = settings.walrus_publisher_url
        self.aggregator_url = settings.walrus_aggregator_url
        self.epochs = settings.walrus_epochs

    async def store_snapshot(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """
        Upload snapshot blob to Walrus.
        Returns {"blob_id": str, "stored_at": str, "size_bytes": int}
        """
        payload = json.dumps(snapshot).encode("utf-8")
        size = len(payload)

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # POST blob to Walrus publisher
                resp = await client.post(
                    f"{self.publisher_url}/v1/blobs",
                    content=payload,
                    params={"epochs": self.epochs},
                    headers={"Content-Type": "application/json"},
                )
                resp.raise_for_status()
                data = resp.json()

                blob_id = data.get("blob_id")
                if not blob_id:
                    raise ValueError("No blob_id returned from Walrus")

                logger.info(f"Snapshot stored on Walrus | blob_id={blob_id} | size={size} bytes")

                return {
                    "blob_id": blob_id,
                    "stored_at": datetime.now(timezone.utc).isoformat(),
                    "size_bytes": size,
                }

        except httpx.HTTPError as e:
            logger.error(f"Walrus storage failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Walrus client error: {e}")
            raise

    async def retrieve_snapshot(self, blob_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a snapshot from Walrus by blob_id.
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.aggregator_url}/v1/blobs/{blob_id}",
                )
                resp.raise_for_status()
                data = resp.json()
                logger.info(f"Retrieved snapshot from Walrus | blob_id={blob_id}")
                return data

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"Blob not found on Walrus: {blob_id}")
                return None
            logger.error(f"Walrus retrieval error: {e}")
            raise
        except Exception as e:
            logger.error(f"Walrus client error: {e}")
            return None


# Global instances
walrus = WalrusClient()
snapshot_builder = SnapshotBuilder()
