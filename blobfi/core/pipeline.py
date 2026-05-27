"""
core/pipeline.py

BlobFi snapshot pipeline.
Auto-runs every 30 minutes. Manual triggers subject to IP rate limiting.
All snapshots persisted to SQLite — shared across all visitors.
"""

import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from agents.defillama import fetch_sui_yields, fetch_sui_tvl
from agents.agent import blobfi_agent
from walrus.client import walrus, snapshot_builder
from sui.rpc import sui_rpc
from core.logger import get_logger
from core.config import settings
from core.database import save_snapshot, load_snapshots, init_db

logger = get_logger(__name__)

_latest_protocols: List[Dict[str, Any]] = []
_running = False
# 30 minutes auto interval
AUTO_INTERVAL_SECONDS = 1800


async def run_snapshot() -> Dict[str, Any]:
    """
    Full BlobFi snapshot cycle:
    1. Fetch live Sui yields from DefiLlama
    2. Fetch Sui chain TVL
    3. Generate AI report via Claude
    4. Store snapshot blob on Walrus
    5. Persist to SQLite
    6. Return summary
    """
    global _latest_protocols

    logger.info("=== BlobFi Snapshot Starting ===")
    started_at = datetime.now(timezone.utc)

    # Step 1 + 2: Fetch data
    protocols, chain_tvl = await asyncio.gather(
        fetch_sui_yields(),
        fetch_sui_tvl(),
    )
    _latest_protocols = protocols
    logger.info("Fetched %d protocols | Sui TVL: $%s", len(protocols), f"{chain_tvl.get('tvl_usd', 0):,.0f}")

    # Step 3: AI report
    ai_report = await blobfi_agent.generate_snapshot_report(protocols, chain_tvl)
    logger.info("AI report generated")

    # Step 4: Build snapshot payload
    snapshot_id = f"blobfi-{int(started_at.timestamp())}"
    snapshot = snapshot_builder.build(
        protocols=protocols,
        ai_report=ai_report,
        chain_tvl=chain_tvl,
        snapshot_id=snapshot_id,
    )

    # Step 5: Store on Walrus
    blob_result = None
    try:
        blob_result = await walrus.store_snapshot(snapshot)
        snapshot["blob_id"] = blob_result["blob_id"]
        snapshot["walrus_stored_at"] = blob_result["stored_at"]
        snapshot["size_bytes"] = blob_result["size_bytes"]
        logger.info("Walrus blob stored | blob_id=%s", blob_result["blob_id"])
    except Exception as e:
        logger.warning("Walrus store failed (snapshot saved locally): %s", e)
        snapshot["blob_id"] = None
        snapshot["walrus_error"] = str(e)

    summary = {
        "snapshot_id": snapshot_id,
        "blob_id": snapshot.get("blob_id"),
        "timestamp": started_at.isoformat(),
        "protocols_tracked": len(protocols),
        "top_protocol": snapshot["top_protocol"],
        "top_apy": snapshot["top_apy"],
        "avg_apy": snapshot["avg_apy"],
        "chain_tvl_usd": chain_tvl.get("tvl_usd", 0),
        "ai_report": ai_report,
        "walrus_stored": blob_result is not None,
    }

    # Step 6: Persist to SQLite
    try:
        await save_snapshot(summary)
        logger.info("Snapshot saved to SQLite")
    except Exception as e:
        logger.error("SQLite save failed: %s", e)

    duration = (datetime.now(timezone.utc) - started_at).total_seconds()
    logger.info("=== Snapshot complete in %.1fs | blob_id=%s ===", duration, snapshot.get("blob_id"))

    return summary


async def start_pipeline():
    """Background task: initialize DB, run first snapshot, then auto every 30 mins."""
    global _running
    _running = True

    # Init DB on startup
    await init_db()
    logger.info("BlobFi auto-pipeline started | interval=30min")

    while _running:
        try:
            await run_snapshot()
        except Exception as e:
            logger.error("Pipeline cycle failed: %s", e)
        await asyncio.sleep(AUTO_INTERVAL_SECONDS)


def stop_pipeline():
    global _running
    _running = False
    logger.info("BlobFi pipeline stopped")


async def get_snapshot_history(limit: int = 50) -> List[Dict[str, Any]]:
    """Load from SQLite — persists across restarts, shared across visitors."""
    try:
        return await load_snapshots(limit)
    except Exception as e:
        logger.error("Failed to load snapshots: %s", e)
        return []


def get_latest_protocols() -> List[Dict[str, Any]]:
    return _latest_protocols.copy()
