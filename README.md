# BlobFi ⬡

> AI-powered Sui yield intelligence, stored permanently on Walrus.

BlobFi tracks every DeFi yield opportunity across the Sui ecosystem in real time, generates AI-written intelligence reports via Claude, and stores each snapshot as an immutable blob on Walrus decentralized storage — provable, retrievable, and permanent.


---

## The Problem

DeFi yield data is ephemeral. APYs shift every block, protocols come and go, and there's no trustless historical record of what the market looked like at any point in time. Analysts and traders rely on centralized dashboards that can go offline, be edited, or simply disappear.

## The Solution

BlobFi solves this with a three-layer architecture:

1. **Fetch** — Live yield data pulled from DefiLlama across all Sui protocols
2. **Analyze** — Claude AI generates a structured yield intelligence report
3. **Store** — The full snapshot is written to Walrus as an immutable blob, with the blob ID logged on Sui via Tatum RPC

Every snapshot is permanently retrievable by its blob ID. No servers. No trust.

---

## Demo

> **Frontend:** `http://localhost:5173`
> **Backend API:** `http://localhost:8000`
> **API Docs:** `http://localhost:8000/docs`

---

## How It Uses Tatum + Walrus

### Tatum
BlobFi uses Tatum's enterprise-grade Sui RPC endpoints for all on-chain interactions:
- Querying the latest Sui checkpoint to verify network liveness
- Fetching reference gas price
- Recording Walrus blob IDs anchored to Sui state

```
Mainnet RPC: https://sui-mainnet.gateway.tatum.io
```

### Walrus
Every yield snapshot is stored as a blob on Walrus:
- Snapshots are serialized to JSON and uploaded via the Walrus HTTP publisher API
- Each blob returns a unique `blob_id` — permanently retrievable via the aggregator
- Blob IDs are displayed in the frontend with one-click copy
- Retrieve any snapshot: `GET /blob/{blob_id}`

```
Publisher:  https://publisher.walrus-testnet.walrus.space
Aggregator: https://aggregator.walrus-testnet.walrus.space
```

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    React Frontend                    │
│         Yields · Metrics · History · Ask AI         │
└─────────────────────┬───────────────────────────────┘
                      │ HTTP
┌─────────────────────▼───────────────────────────────┐
│                  FastAPI Backend                     │
│                                                      │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │  DefiLlama  │  │ Claude Agent │  │  Tatum RPC │  │
│  │   Fetcher   │  │ (LangChain)  │  │  Sui RPC   │  │
│  └──────┬──────┘  └──────┬───────┘  └─────┬──────┘  │
│         │                │                │          │
│  ┌──────▼────────────────▼───────────────▼───────┐  │
│  │              Snapshot Pipeline                 │  │
│  │    fetch → analyze → store → record blob ID   │  │
│  └──────────────────────┬────────────────────────┘  │
└─────────────────────────┼───────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────┐
│                 Walrus Storage                       │
│         Immutable blob per snapshot cycle            │
└─────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React + Vite |
| Backend | FastAPI (Python) |
| AI Agent | Claude (Anthropic) |
| Yield Data | DefiLlama API |
| Sui RPC | Tatum |
| Storage | Walrus |
| Scheduling | asyncio background tasks |

---

## Features

- **157+ live Sui pools** fetched directly from DefiLlama, refreshed every 5 minutes
- **Protocol card grid** — all pools ranked by TVL, filterable by category (DEX, Lending, LST, CDP, Perps, RWA)
- **AI yield reports** — Claude generates a structured analysis per snapshot covering risk-adjusted picks, anomalies, and recommendations
- **Walrus snapshot history** — every snapshot stored permanently with its blob ID visible and copyable
- **Sui network metrics** — TVL, 24h/7d change, volume, fees, stablecoin mcap
- **Ask AI** — natural language queries answered against live protocol data
- **Blob retrieval** — any historical snapshot retrievable via `GET /blob/{blob_id}`

---

## Getting Started

### Prerequisites

- Python 3.12
- Node.js 18+
- Tatum API key — [dashboard.tatum.io](https://dashboard.tatum.io)
- Anthropic API key — [console.anthropic.com](https://console.anthropic.com)

### Backend

```bash
# Clone the repo
git clone https://github.com/nftkingiii/BlobFi.git
cd BlobFi

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your TATUM_API_KEY and ANTHROPIC_API_KEY

# Run
python main.py
```

Backend runs at `http://localhost:8000`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:5173`

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Health check + Tatum RPC status |
| GET | `/protocols` | Live Sui yield protocols |
| POST | `/snapshot` | Trigger a snapshot cycle |
| GET | `/snapshots` | Snapshot history with blob IDs |
| GET | `/snapshots/latest` | Most recent snapshot |
| GET | `/blob/{blob_id}` | Retrieve snapshot from Walrus |
| POST | `/query` | Ask the AI agent a question |
| GET | `/sui/status` | Live Sui RPC status via Tatum |

---

## Environment Variables

```env
# Tatum (get free key at dashboard.tatum.io)
TATUM_API_KEY=your_key_here
SUI_NETWORK=mainnet

# Anthropic
ANTHROPIC_API_KEY=your_key_here

# Walrus
WALRUS_PUBLISHER_URL=https://publisher.walrus-testnet.walrus.space
WALRUS_AGGREGATOR_URL=https://aggregator.walrus-testnet.walrus.space
WALRUS_EPOCHS=5

# Pipeline
SNAPSHOT_INTERVAL_SECONDS=300
TOP_PROTOCOLS_COUNT=10
```

---

## Project Structure

```
BlobFi/
├── main.py                  # Entry point
├── requirements.txt
├── .env.example
├── core/
│   ├── config.py            # Settings
│   ├── logger.py            # Logging
│   └── pipeline.py          # Snapshot orchestration
├── agents/
│   ├── defillama.py         # DefiLlama fetcher
│   └── agent.py             # Claude AI agent
├── walrus/
│   └── client.py            # Walrus blob storage
├── sui/
│   └── rpc.py               # Tatum Sui RPC client
├── api/
│   └── app.py               # FastAPI routes
└── frontend/
    └── src/
        └── App.jsx          # React dashboard
```

---

## How a Snapshot Works

```
1. DefiLlama fetch    →  All Sui yield pools pulled
2. Claude analysis   →  AI report generated
3. Snapshot built    →  JSON payload assembled
4. Walrus store      →  PUT /v1/blobs → blob_id returned
5. History updated   →  Snapshot + blob_id stored in session
6. Retrievable       →  GET /blob/{blob_id} returns full snapshot
```

---

## Built With

- [Tatum](https://tatum.io) — Sui RPC infrastructure
- [Walrus](https://wal.app) — Decentralized blob storage on Sui
- [DefiLlama](https://defillama.com) — DeFi yield data
- [Anthropic Claude](https://anthropic.com) — AI yield analysis
- [FastAPI](https://fastapi.tiangolo.com) — Python web framework
- [React](https://react.dev) + [Vite](https://vitejs.dev) — Frontend

---

## License

MIT

---

*Submitted to the Tatum × Walrus Hackathon 2026 · Built by [@NFTKINGIII](https://x.com/NFTKINGIII)*
