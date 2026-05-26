"""
api/app.py

BlobFi FastAPI application.
Routes: /health, /snapshot, /snapshots, /protocols, /query, /blob/{blob_id}
"""

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Optional

from core.config import settings
from core.logger import get_logger
from core.pipeline import (
    run_snapshot,
    start_pipeline,
    stop_pipeline,
    get_snapshot_history,
    get_latest_protocols,
)
from walrus.client import walrus
from sui.rpc import sui_rpc
from agents.agent import blobfi_agent

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start background pipeline on startup."""
    logger.info("BlobFi starting up...")
    # Run first snapshot immediately, then start polling loop
    asyncio.create_task(run_snapshot())
    asyncio.create_task(start_pipeline())
    yield
    stop_pipeline()
    logger.info("BlobFi shutting down.")


app = FastAPI(
    title="BlobFi",
    description="AI-powered Sui yield intelligence, stored permanently on Walrus",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request/Response Models ──────────────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    answer: str
    intent: str = "general"


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root():
    return """
    <html><body style="background:#060910;color:#D8E0FF;font-family:monospace;padding:40px;">
    <h1 style="color:#00D4BE;">BlobFi ⚡</h1>
    <p>AI-powered Sui yield intelligence, stored permanently on Walrus.</p>
    <ul>
      <li><a href="/docs" style="color:#7B5CF6;">/docs</a> — API docs</li>
      <li><a href="/health" style="color:#7B5CF6;">/health</a> — Health check</li>
      <li><a href="/snapshots" style="color:#7B5CF6;">/snapshots</a> — Snapshot history</li>
      <li><a href="/protocols" style="color:#7B5CF6;">/protocols</a> — Live Sui yields</li>
    </ul>
    </body></html>
    """


@app.get("/health")
async def health():
    """Health check — verifies Sui RPC (Tatum) connectivity."""
    sui_status = await sui_rpc.health_check()
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": "1.0.0",
        "network": settings.sui_network,
        "sui_rpc": sui_status,
        "snapshot_history_count": len(get_snapshot_history()),
    }


@app.get("/protocols")
async def get_protocols():
    """Return the latest fetched Sui yield protocols."""
    protocols = get_latest_protocols()
    if not protocols:
        raise HTTPException(status_code=503, detail="No protocol data yet — pipeline starting up")
    return {
        "chain": "Sui",
        "count": len(protocols),
        "protocols": protocols,
    }


@app.post("/snapshot")
async def trigger_snapshot():
    """
    Manually trigger a snapshot cycle:
    fetch yields → AI report → store on Walrus.
    """
    logger.info("Manual snapshot triggered via API")
    summary = await run_snapshot()
    return {
        "message": "Snapshot complete",
        "snapshot": summary,
    }


@app.get("/snapshots")
async def list_snapshots(limit: int = 20):
    """
    Return snapshot history with Walrus blob IDs.
    Each entry includes blob_id for on-chain retrieval.
    """
    history = get_snapshot_history()
    return {
        "count": len(history),
        "snapshots": history[:limit],
    }


@app.get("/snapshots/latest")
async def latest_snapshot():
    """Return the most recent snapshot."""
    history = get_snapshot_history()
    if not history:
        raise HTTPException(status_code=404, detail="No snapshots yet")
    return history[0]


@app.get("/blob/{blob_id}")
async def get_blob(blob_id: str):
    """
    Retrieve a stored snapshot directly from Walrus by blob_id.
    Proves permanent, trustless storage on Walrus.
    """
    data = await walrus.retrieve_snapshot(blob_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"Blob {blob_id} not found on Walrus")
    return data


@app.post("/query", response_model=QueryResponse)
async def query_agent(body: QueryRequest):
    """
    Ask the BlobFi AI agent a question about Sui yields.
    Uses live protocol data fetched in the last pipeline cycle.
    """
    protocols = get_latest_protocols()
    if not protocols:
        raise HTTPException(status_code=503, detail="Protocol data not ready yet")

    from agents.agent import classify_intent
    intent = classify_intent(body.question)
    answer = await blobfi_agent.query(body.question, protocols)
    return QueryResponse(answer=answer, intent=intent)


@app.get("/sui/status")
async def sui_status():
    """Return live Sui RPC status via Tatum."""
    return await sui_rpc.health_check()
