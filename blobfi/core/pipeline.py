"""
core/pipeline.py

BlobFi snapshot pipeline.
Runs on a schedule: fetch Sui yields → AI report → store on Walrus → record blob ID.
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

logger = get_logger(__name__)

# In-memory snapshot history (persists for session, shown in frontend)
# In production you'd back this with SQLite
_snapshot_history: List[Dict[str, Any]] = []
_latest_protocols: List[Dict[str, Any]] = []
_running = False


async def run_snapshot() -> Dict[str, Any]:
    """
    Execute one full BlobFi snapshot cycle:
    1. Fetch live Sui yields from DefiLlama
    2. Fetch Sui chain TVL
    3. Generate AI report via Claude
    4. Store snapshot blob on Walrus
    5. Record blob ID in memory (+ log for on-chain anchoring)
    6. Return full snapshot with blob_id
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

    # Step 6: Keep in memory history
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
    _snapshot_history.insert(0, summary)
    if len(_snapshot_history) > 50:
        _snapshot_history.pop()

    duration = (datetime.now(timezone.utc) - started_at).total_seconds()
    logger.info("=== Snapshot complete in %.1fs | blob_id=%s ===", duration, snapshot.get("blob_id"))

    return summary


async def start_pipeline():
    """Background task: run snapshots on interval."""
    global _running
    _running = True
    logger.info("BlobFi pipeline started | interval=%ds", settings.snapshot_interval_seconds)

    while _running:
        try:
            await run_snapshot()
        except Exception as e:
            logger.error("Pipeline cycle failed: %s", e)

        await asyncio.sleep(settings.snapshot_interval_seconds)


def stop_pipeline():
    global _running
    _running = False
    logger.info("BlobFi pipeline stopped")


def get_snapshot_history() -> List[Dict[str, Any]]:
    return _snapshot_history.copy()


def get_latest_protocols() -> List[Dict[str, Any]]:
    return _latest_protocols.copy()
