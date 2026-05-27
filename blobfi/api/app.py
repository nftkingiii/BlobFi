"""
api/app.py

BlobFi FastAPI application.
- Auto snapshots every 30 minutes
- IP-based rate limiting (1 manual snapshot per hour per IP)
- SQLite persistence (shared across all visitors)
- Blob ID search endpoint
- Snapshot progress via SSE
"""

import asyncio
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional

from core.config import settings
from core.logger import get_logger
from core.pipeline import (
    run_snapshot,
    start_pipeline,
    stop_pipeline,
    get_snapshot_history,
    get_latest_protocols,
)
from core.database import init_db, check_rate_limit, record_rate_limit
from walrus.client import walrus
from sui.rpc import sui_rpc
from agents.agent import blobfi_agent

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("BlobFi starting up...")
    await init_db()
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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_client_ip(request: Request) -> str:
    """Extract real client IP, handling proxies."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class QueryRequest(BaseModel):
    question: str

class QueryResponse(BaseModel):
    answer: str
    intent: str = "general"


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root():
    return """
    <html><body style="background:#0a0a0a;color:#fff;font-family:monospace;padding:40px;">
    <h1>BlobFi ⬡</h1>
    <p>AI-powered Sui yield intelligence, stored permanently on Walrus.</p>
    <ul>
      <li><a href="/docs" style="color:#22C55E;">/docs</a> — API docs</li>
      <li><a href="/health" style="color:#22C55E;">/health</a> — Health check</li>
      <li><a href="/snapshots" style="color:#22C55E;">/snapshots</a> — Snapshot history</li>
      <li><a href="/protocols" style="color:#22C55E;">/protocols</a> — Live Sui yields</li>
    </ul>
    </body></html>
    """


@app.get("/health")
async def health():
    sui_status = await sui_rpc.health_check()
    history = await get_snapshot_history(1)
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": "1.0.0",
        "network": settings.sui_network,
        "sui_rpc": sui_status,
        "snapshot_count": len(await get_snapshot_history()),
        "latest_snapshot": history[0].get("timestamp") if history else None,
    }


@app.get("/protocols")
async def get_protocols():
    protocols = get_latest_protocols()
    if not protocols:
        raise HTTPException(status_code=503, detail="No protocol data yet — pipeline starting up")
    return {"chain": "Sui", "count": len(protocols), "protocols": protocols}


@app.post("/snapshot")
async def trigger_snapshot(request: Request):
    """
    Manual snapshot trigger with IP rate limiting.
    Each IP is limited to 1 manual snapshot per hour.
    """
    ip = get_client_ip(request)
    rate = await check_rate_limit(ip, max_per_hour=1)

    if not rate["allowed"]:
        raise HTTPException(
            status_code=429,
            detail={
                "message": f"Rate limit reached. Next snapshot available in {rate['wait_minutes']} minutes.",
                "wait_minutes": rate["wait_minutes"],
            }
        )

    await record_rate_limit(ip)
    logger.info("Manual snapshot triggered | ip=%s", ip)
    summary = await run_snapshot()
    return {"message": "Snapshot complete", "snapshot": summary}


@app.get("/snapshot/stream")
async def snapshot_stream(request: Request):
    """
    SSE endpoint — streams snapshot progress steps to the frontend.
    Frontend listens to this for the step-by-step progress indicator.
    """
    ip = get_client_ip(request)
    rate = await check_rate_limit(ip, max_per_hour=1)

    async def event_generator():
        if not rate["allowed"]:
            yield f"data: {json.dumps({'step': 'error', 'message': f'Rate limit. Wait {rate[\"wait_minutes\"]}m.'})}\n\n"
            return

        await record_rate_limit(ip)

        steps = [
            ("fetching", "Fetching live Sui yields…"),
            ("analyzing", "Generating AI report…"),
            ("storing", "Storing on Walrus…"),
            ("done", "Snapshot complete"),
        ]

        for step, message in steps:
            yield f"data: {json.dumps({'step': step, 'message': message})}\n\n"
            await asyncio.sleep(0.1)

        try:
            summary = await run_snapshot()
            yield f"data: {json.dumps({'step': 'complete', 'snapshot': summary})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'step': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/snapshots")
async def list_snapshots(limit: int = 50):
    history = await get_snapshot_history(limit)
    return {"count": len(history), "snapshots": history}


@app.get("/snapshots/latest")
async def latest_snapshot():
    history = await get_snapshot_history(1)
    if not history:
        raise HTTPException(status_code=404, detail="No snapshots yet")
    return history[0]


@app.get("/snapshots/search/{blob_id}")
async def search_snapshot_by_blob(blob_id: str):
    """
    Search snapshot history by blob ID.
    Returns the matching snapshot from SQLite if found.
    """
    history = await get_snapshot_history(200)
    match = next((s for s in history if s.get("blob_id") == blob_id), None)
    if match:
        return match
    # Fall back to Walrus direct retrieval
    data = await walrus.retrieve_snapshot(blob_id)
    if data:
        return data
    raise HTTPException(status_code=404, detail=f"No snapshot found for blob_id: {blob_id}")


@app.get("/blob/{blob_id}")
async def get_blob(blob_id: str):
    """Retrieve snapshot directly from Walrus by blob_id."""
    data = await walrus.retrieve_snapshot(blob_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"Blob {blob_id} not found on Walrus")
    return data


@app.get("/rate-limit")
async def rate_limit_status(request: Request):
    """Check current IP's rate limit status."""
    ip = get_client_ip(request)
    return await check_rate_limit(ip, max_per_hour=1)


@app.post("/query", response_model=QueryResponse)
async def query_agent(body: QueryRequest):
    protocols = get_latest_protocols()
    if not protocols:
        raise HTTPException(status_code=503, detail="Protocol data not ready yet")
    from agents.agent import classify_intent
    intent = classify_intent(body.question)
    answer = await blobfi_agent.query(body.question, protocols)
    return QueryResponse(answer=answer, intent=intent)


@app.get("/sui/status")
async def sui_status():
    return await sui_rpc.health_check()
