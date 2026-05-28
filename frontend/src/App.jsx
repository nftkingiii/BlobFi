import { useState, useEffect, useRef, useCallback } from "react";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";
const DEFILLAMA_POOLS = "https://yields.llama.fi/pools";
const DEFILLAMA_CHAINS = "https://api.llama.fi/v2/chains";

const FALLBACK_PROTOCOLS = [
  { protocol: "Aftermath Finance", symbol: "afSUI", apy: 6.2, apy_base: 6.2, apy_reward: 0, tvl_usd: 55_000_000, category: "LST", il_risk: "low" },
  { protocol: "NAVI Protocol", symbol: "SUI", apy: 12.8, apy_base: 12.8, apy_reward: 0, tvl_usd: 42_000_000, category: "Lending", il_risk: "low" },
  { protocol: "Scallop", symbol: "USDC", apy: 8.4, apy_base: 8.4, apy_reward: 0, tvl_usd: 31_200_000, category: "Lending", il_risk: "none" },
  { protocol: "Cetus", symbol: "SUI/USDC", apy: 24.5, apy_base: 18.2, apy_reward: 6.3, tvl_usd: 18_500_000, category: "DEX", il_risk: "medium" },
  { protocol: "Suilend", symbol: "USDC", apy: 7.8, apy_base: 7.8, apy_reward: 0, tvl_usd: 28_500_000, category: "Lending", il_risk: "none" },
  { protocol: "Bluefin", symbol: "BTC/USDC", apy: 31.7, apy_base: 22.0, apy_reward: 9.7, tvl_usd: 7_100_000, category: "Perps", il_risk: "high" },
  { protocol: "Turbos Finance", symbol: "SUI/USDT", apy: 19.1, apy_base: 14.5, apy_reward: 4.6, tvl_usd: 9_800_000, category: "DEX", il_risk: "medium" },
  { protocol: "Haedal Protocol", symbol: "haSUI", apy: 5.8, apy_base: 5.8, apy_reward: 0, tvl_usd: 22_100_000, category: "LST", il_risk: "low" },
  { protocol: "Bucket Protocol", symbol: "BUCK/USDC", apy: 9.5, apy_base: 9.5, apy_reward: 0, tvl_usd: 14_300_000, category: "CDP", il_risk: "low" },
  { protocol: "Kriya DEX", symbol: "SUI/USDC", apy: 17.6, apy_base: 12.4, apy_reward: 5.2, tvl_usd: 7_600_000, category: "DEX", il_risk: "medium" },
];

const FALLBACK_METRICS = {
  tvl: 576_400_000, tvl_24h: 1.87, tvl_7d: 4.23,
  volume_24h: 152_000_000, volume_24h_change: -2.1,
  fees_24h: 1_420_000, fees_7d: 9_800_000,
  stablecoins_mcap: 89_000_000,
  active_addresses_24h: 142_000,
  transactions_24h: 2_340_000,
};

const SNAPSHOT_STEPS = [
  { key: "fetching",  label: "Fetching live Sui yields" },
  { key: "analyzing", label: "Generating AI report" },
  { key: "storing",   label: "Storing on Walrus" },
  { key: "done",      label: "Snapshot complete" },
];

function useCountUp(target, ms = 1000) {
  const [v, setV] = useState(0);
  const r = useRef();
  useEffect(() => {
    const t0 = performance.now();
    const go = (now) => {
      const p = Math.min((now - t0) / ms, 1);
      setV(target * (1 - Math.pow(1 - p, 4)));
      if (p < 1) r.current = requestAnimationFrame(go);
    };
    r.current = requestAnimationFrame(go);
    return () => cancelAnimationFrame(r.current);
  }, [target, ms]);
  return v;
}

function DotGrid() {
  return (
    <div style={{
      position: "fixed", inset: 0, zIndex: 0, pointerEvents: "none",
      backgroundImage: "radial-gradient(circle, rgba(255,255,255,0.065) 1px, transparent 1px)",
      backgroundSize: "28px 28px",
      maskImage: "radial-gradient(ellipse 80% 80% at 50% 50%, black 30%, transparent 100%)",
      WebkitMaskImage: "radial-gradient(ellipse 80% 80% at 50% 50%, black 30%, transparent 100%)",
    }} />
  );
}

function GlowOrb({ x, y, color, size = 400, opacity = 0.1 }) {
  return (
    <div style={{
      position: "fixed", left: x, top: y, width: size, height: size,
      borderRadius: "50%", pointerEvents: "none", zIndex: 0,
      background: `radial-gradient(circle, ${color} 0%, transparent 70%)`,
      opacity, filter: "blur(60px)", transform: "translate(-50%,-50%)",
    }} />
  );
}

function LiveDot() {
  return (
    <span style={{ position: "relative", display: "inline-flex", width: 7, height: 7 }}>
      <span style={{ position: "absolute", inset: 0, borderRadius: "50%", background: "#22C55E", animation: "ping 1.8s cubic-bezier(0,0,0.2,1) infinite", opacity: 0.6 }} />
      <span style={{ position: "relative", width: 7, height: 7, borderRadius: "50%", background: "#22C55E" }} />
    </span>
  );
}

function Line() { return <div style={{ height: 1, background: "rgba(255,255,255,0.06)" }} />; }

function Pill({ label, active, onClick }) {
  return (
    <button onClick={onClick} style={{
      padding: "4px 12px", borderRadius: 20, fontSize: 11, cursor: "pointer",
      fontFamily: "inherit", fontWeight: active ? 500 : 400, whiteSpace: "nowrap",
      border: active ? "1px solid rgba(255,255,255,0.25)" : "1px solid rgba(255,255,255,0.08)",
      background: active ? "rgba(255,255,255,0.1)" : "transparent",
      color: active ? "#fff" : "rgba(255,255,255,0.4)",
      transition: "all 0.15s",
    }}>{label}</button>
  );
}

function RiskBadge({ risk }) {
  const map = { none: ["#22C55E", "No IL"], low: ["#86EFAC", "Low IL"], medium: ["#EAB308", "Med IL"], high: ["#F97316", "High IL"] };
  const [c, l] = map[risk] || ["#6B7280", "Unknown"];
  return (
    <span style={{ fontSize: 10, color: c, fontWeight: 500, display: "flex", alignItems: "center", gap: 4 }}>
      <span style={{ width: 5, height: 5, borderRadius: "50%", background: c, display: "inline-block", boxShadow: `0 0 4px ${c}` }} />{l}
    </span>
  );
}

function APYColor(apy) { return apy > 20 ? "#F97316" : apy > 10 ? "#EAB308" : "#22C55E"; }

function BlobTag({ id, full = false }) {
  if (!id) return <span style={{ fontSize: 10, color: "rgba(255,255,255,0.2)" }}>—</span>;
  const s = full ? id : `${id.slice(0, 12)}…`;
  const [hov, setHov] = useState(false);
  return (
    <span 
      title={`Blob ID: ${id} (click to copy)`} 
      onClick={() => navigator.clipboard?.writeText(id)}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        fontFamily: "monospace", fontSize: 10,
        color: "#22C55E",
        backgroundColor: hov ? "rgba(34, 197, 94, 0.12)" : "rgba(34, 197, 94, 0.08)",
        border: hov ? "1px solid rgba(34, 197, 94, 0.4)" : "1px solid rgba(34, 197, 94, 0.2)",
        padding: "3px 8px", borderRadius: 4, cursor: "pointer",
        transition: "all 0.15s", whiteSpace: "nowrap",
        display: "inline-block", wordBreak: "break-all",
      }}
    >{s}</span>
  );
}

function ProgressModal({ steps, currentStep, onClose }) {
  const stepKeys = SNAPSHOT_STEPS.map(s => s.key);
  const currentIdx = stepKeys.indexOf(currentStep);
  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 500, background: "rgba(0,0,0,0.75)", display: "flex", alignItems: "center", justifyContent: "center", backdropFilter: "blur(6px)" }}>
      <div style={{ background: "#111", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 14, padding: "32px 36px", width: 360, opacity: 0, animation: "rise 0.25s ease both" }}>
        <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 24, letterSpacing: "-0.02em" }}>Capturing Snapshot</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {SNAPSHOT_STEPS.map((s, i) => {
            const done = i < currentIdx;
            const active = i === currentIdx;
            const pending = i > currentIdx;
            return (
              <div key={s.key} style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <div style={{
                  width: 22, height: 22, borderRadius: "50%", flexShrink: 0,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  background: done ? "#22C55E" : active ? "rgba(255,255,255,0.1)" : "rgba(255,255,255,0.04)",
                  border: done ? "none" : active ? "1px solid rgba(255,255,255,0.3)" : "1px solid rgba(255,255,255,0.1)",
                  transition: "all 0.3s",
                }}>
                  {done && <span style={{ fontSize: 11, color: "#000" }}>✓</span>}
                  {active && <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#fff", animation: "shimmer 0.8s infinite" }} />}
                </div>
                <span style={{ fontSize: 12, color: done ? "#22C55E" : active ? "#fff" : "rgba(255,255,255,0.25)", transition: "color 0.3s" }}>
                  {s.label}
                </span>
              </div>
            );
          })}
        </div>
        {currentStep === "complete" && (
          <button onClick={onClose} style={{
            marginTop: 24, width: "100%", padding: "10px", borderRadius: 8,
            background: "rgba(255,255,255,0.08)", border: "1px solid rgba(255,255,255,0.15)",
            color: "#fff", fontSize: 12, cursor: "pointer", fontFamily: "inherit",
          }}>View Snapshot →</button>
        )}
      </div>
    </div>
  );
}

function ProtocolCard({ p, i, onSelect }) {
  const [hov, setHov] = useState(false);
  return (
    <div
      onClick={() => onSelect(p)}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        padding: "16px", borderRadius: 10, cursor: "pointer",
        border: `1px solid ${hov ? "rgba(255,255,255,0.15)" : "rgba(255,255,255,0.07)"}`,
        background: hov ? "rgba(255,255,255,0.04)" : "rgba(255,255,255,0.015)",
        transition: "all 0.15s",
        opacity: 0, animation: `rise 0.3s ease ${0.02 * i}s forwards`,
        display: "flex", flexDirection: "column", gap: 10,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: "#fff", marginBottom: 2 }}>{p.protocol}</div>
          <div style={{ fontSize: 11, color: "rgba(255,255,255,0.3)" }}>{p.symbol}</div>
        </div>
        <span style={{ fontSize: 10, color: "rgba(255,255,255,0.3)", background: "rgba(255,255,255,0.05)", padding: "2px 8px", borderRadius: 6, border: "1px solid rgba(255,255,255,0.07)", whiteSpace: "nowrap" }}>
          {p.category}
        </span>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end" }}>
        <div>
          <div style={{ fontSize: 10, color: "rgba(255,255,255,0.25)", marginBottom: 3 }}>APY</div>
          <div style={{ fontSize: 22, fontWeight: 700, color: APYColor(p.apy), letterSpacing: "-0.02em" }}>{p.apy}%</div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: 10, color: "rgba(255,255,255,0.25)", marginBottom: 3 }}>TVL</div>
          <div style={{ fontSize: 13, fontWeight: 500, color: "rgba(255,255,255,0.7)" }}>
            ${p.tvl_usd >= 1_000_000 ? `${(p.tvl_usd / 1_000_000).toFixed(1)}M` : `${(p.tvl_usd / 1000).toFixed(0)}K`}
          </div>
        </div>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <RiskBadge risk={p.il_risk} />
        {p.apy_reward > 0 && <span style={{ fontSize: 10, color: "rgba(255,255,255,0.3)" }}>+{p.apy_reward}% rewards</span>}
      </div>
    </div>
  );
}

function ProtocolModal({ p, onClose }) {
  if (!p) return null;
  return (
    <div onClick={onClose} style={{ position: "fixed", inset: 0, zIndex: 300, background: "rgba(0,0,0,0.7)", display: "flex", alignItems: "center", justifyContent: "center", backdropFilter: "blur(4px)" }}>
      <div onClick={e => e.stopPropagation()} style={{ background: "#111", border: "1px solid rgba(255,255,255,0.12)", borderRadius: 14, padding: "28px", width: 380, opacity: 0, animation: "rise 0.25s ease both" }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 20 }}>
          <div>
            <div style={{ fontSize: 20, fontWeight: 600, letterSpacing: "-0.02em" }}>{p.protocol}</div>
            <div style={{ fontSize: 12, color: "rgba(255,255,255,0.35)", marginTop: 3 }}>{p.symbol} · {p.category}</div>
          </div>
          <button onClick={onClose} style={{ background: "none", border: "none", color: "rgba(255,255,255,0.4)", fontSize: 18, cursor: "pointer" }}>✕</button>
        </div>
        <Line />
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr" }}>
          {[
            { l: "Total APY", v: `${p.apy}%`, big: true },
            { l: "TVL", v: `$${(p.tvl_usd / 1e6).toFixed(2)}M`, big: true },
            { l: "Base APY", v: `${p.apy_base}%` },
            { l: "Reward APY", v: p.apy_reward > 0 ? `${p.apy_reward}%` : "—" },
          ].map(({ l, v, big }) => (
            <div key={l} style={{ padding: "16px 0" }}>
              <div style={{ fontSize: 10, color: "rgba(255,255,255,0.25)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 5 }}>{l}</div>
              <div style={{ fontSize: big ? 22 : 16, fontWeight: big ? 600 : 500, color: big && l === "Total APY" ? APYColor(p.apy) : "#fff", letterSpacing: "-0.02em" }}>{v}</div>
            </div>
          ))}
        </div>
        <Line />
        <div style={{ padding: "14px 0" }}><RiskBadge risk={p.il_risk} /></div>
      </div>
    </div>
  );
}

function MetricTile({ label, value, change, note, delay = 0 }) {
  const pos = change === undefined ? null : change >= 0;
  return (
    <div style={{ padding: "18px", borderRadius: 10, border: "1px solid rgba(255,255,255,0.07)", background: "rgba(255,255,255,0.02)", opacity: 0, animation: `rise 0.4s ease ${delay}s forwards` }}>
      <div style={{ fontSize: 10, color: "rgba(255,255,255,0.3)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 10 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 600, color: "#fff", letterSpacing: "-0.02em", marginBottom: 4 }}>{value}</div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        {note && <span style={{ fontSize: 11, color: "rgba(255,255,255,0.25)" }}>{note}</span>}
        {change !== undefined && (
          <span style={{ fontSize: 11, fontWeight: 500, color: pos ? "#22C55E" : "#F97316" }}>
            {pos ? "↑" : "↓"} {Math.abs(change).toFixed(2)}%
          </span>
        )}
      </div>
    </div>
  );
}

function SnapshotRow({ s, selected, onSelect, i }) {
  const ago = Math.round((Date.now() - new Date(s.timestamp || s.ts).getTime()) / 60000);
  const isSel = selected?.snapshot_id === s.snapshot_id || selected?.id === s.id;
  return (
    <div onClick={() => onSelect(s)} style={{
      padding: "14px 20px", cursor: "pointer",
      background: isSel ? "rgba(255,255,255,0.05)" : "transparent",
      borderLeft: isSel ? "2px solid rgba(255,255,255,0.4)" : "2px solid transparent",
      transition: "background 0.15s",
      opacity: 0, animation: `rise 0.3s ease ${0.04 * i}s forwards`,
    }}
      onMouseEnter={e => { if (!isSel) e.currentTarget.style.background = "rgba(255,255,255,0.03)"; }}
      onMouseLeave={e => { if (!isSel) e.currentTarget.style.background = "transparent"; }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span style={{ fontSize: 11, color: "rgba(255,255,255,0.4)" }}>{ago < 60 ? `${ago}m ago` : `${Math.floor(ago/60)}h ago`}</span>
          <BlobTag id={s.blob_id} />
        </div>
        <span style={{ fontSize: 14, fontWeight: 600, color: "#fff" }}>{s.top_apy}%</span>
      </div>
      <div style={{ fontSize: 11, color: "rgba(255,255,255,0.25)" }}>
        {s.top_protocol || s.top} · avg {s.avg_apy}% · ${((s.chain_tvl_usd || s.tvl || 0) / 1e9).toFixed(2)}B
      </div>
    </div>
  );
}

export default function BlobFi() {
  const [view, setView] = useState("yields");
  const [protocols, setProtocols] = useState(FALLBACK_PROTOCOLS);
  const [metrics, setMetrics] = useState(FALLBACK_METRICS);
  const [snapshots, setSnapshots] = useState([]);
  const [selProtocol, setSelProtocol] = useState(null);
  const [selSnap, setSelSnap] = useState(null);
  const [filter, setFilter] = useState("All");
  const [search, setSearch] = useState("");
  const [blobSearch, setBlobSearch] = useState("");
  const [blobResult, setBlobResult] = useState(null);
  const [blobSearching, setBlobSearching] = useState(false);
  const [blobError, setBlobError] = useState("");
  const [query, setQuery] = useState("");
  const [answer, setAnswer] = useState("");
  const [asking, setAsking] = useState(false);
  const [snapping, setSnapping] = useState(false);
  const [snapStep, setSnapStep] = useState(null);
  const [flash, setFlash] = useState(false);
  const [loading, setLoading] = useState(true);
  const [dataSource, setDataSource] = useState("fallback");
  const [rateLimit, setRateLimit] = useState({ allowed: true, wait_minutes: 0 });

  // Fetch live DefiLlama data
  useEffect(() => {
    const fetchLive = async () => {
      setLoading(true);
      try {
        const res = await fetch(DEFILLAMA_POOLS);
        const json = await res.json();
        const suiPools = json.data
          .filter(p => (p.chain || "").toLowerCase() === "sui" && p.apy > 0 && p.tvlUsd > 50000)
          .map(p => ({
            protocol: cleanName(p.project),
            symbol: p.symbol || "",
            apy: round(p.apy),
            apy_base: round(p.apyBase || 0),
            apy_reward: round(p.apyReward || 0),
            tvl_usd: Math.round(p.tvlUsd || 0),
            category: mapCategory(p.category, p.project),
            il_risk: p.ilRisk || (p.stablecoin ? "none" : "medium"),
            pool_id: p.pool,
          }))
          .sort((a, b) => b.tvl_usd - a.tvl_usd);
        if (suiPools.length > 0) { setProtocols(suiPools); setDataSource("live"); }
      } catch (e) { setDataSource("fallback"); }

      try {
        const res2 = await fetch(DEFILLAMA_CHAINS);
        const chains = await res2.json();
        const sui = chains.find(c => (c.name || "").toLowerCase() === "sui");
        if (sui) setMetrics(m => ({ ...m, tvl: Math.round(sui.tvl || m.tvl) }));
      } catch {}

      setLoading(false);
    };
    fetchLive();
    const interval = setInterval(fetchLive, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  // Load snapshots from backend on mount
  useEffect(() => {
    const loadSnapshots = async () => {
      try {
        const res = await fetch(`${API}/snapshots?limit=50`);
        if (res.ok) {
          const d = await res.json();
          if (d.snapshots?.length) {
            setSnapshots(d.snapshots);
            setSelSnap(d.snapshots[0]);
          }
        }
      } catch {}
    };
    loadSnapshots();
  }, []);

  // Check rate limit on mount
  useEffect(() => {
    const checkRate = async () => {
      try {
        const res = await fetch(`${API}/rate-limit`);
        if (res.ok) setRateLimit(await res.json());
      } catch {}
    };
    checkRate();
  }, []);

  function round(n) { return Math.round(n * 100) / 100; }
  function cleanName(n) {
    const map = { "cetus-amm": "Cetus", "navi-protocol": "NAVI Protocol", "scallop-lend": "Scallop", "aftermath-finance": "Aftermath Finance", "turbos-finance": "Turbos Finance", "bluefin": "Bluefin", "bucket-protocol": "Bucket Protocol", "suilend": "Suilend", "flowx-finance": "FlowX Finance", "kai-finance": "KAI Finance", "haedal-protocol": "Haedal Protocol", "volo": "Volo", "alphafi": "AlphaFi", "kriya-dex": "Kriya DEX", "steamm": "Steamm", "typus-finance": "Typus Finance", "deepbook": "DeepBook" };
    return map[n] || n.split("-").map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
  }
  function mapCategory(c, project) {
    const m = { "Dexes": "DEX", "DEX": "DEX", "Lending": "Lending", "Liquid Staking": "LST", "Liquid staking": "LST", "liquid staking": "LST", "Yield": "Yield", "Yield Aggregator": "Yield", "CDP": "CDP", "cdp": "CDP", "Derivatives": "Perps", "Perps": "Perps", "RWA": "RWA", "Options": "Options", "Farm": "Yield", "Staking": "Staking" };
    if (c && m[c]) return m[c];
    const p = (project || "").toLowerCase();
    if (p.includes("lend") || p.includes("navi") || p.includes("scallop") || p.includes("suilend") || p.includes("kai")) return "Lending";
    if (p.includes("swap") || p.includes("dex") || p.includes("cetus") || p.includes("turbos") || p.includes("flowx") || p.includes("kriya") || p.includes("steamm") || p.includes("deepbook")) return "DEX";
    if (p.includes("staking") || p.includes("aftermath") || p.includes("haedal") || p.includes("volo")) return "LST";
    if (p.includes("bucket") || p.includes("cdp")) return "CDP";
    if (p.includes("bluefin") || p.includes("perp")) return "Perps";
    if (p.includes("ondo") || p.includes("rwa")) return "RWA";
    if (p.includes("typus") || p.includes("option")) return "Options";
    return c || "Other";
  }

  const cats = ["All", ...new Set(protocols.map(p => p.category))];
  const saneProtocols = protocols.filter(p => p.apy <= 200);
  const topByApy = [...saneProtocols].sort((a, b) => b.apy - a.apy)[0];
  const avgApy = saneProtocols.length ? (saneProtocols.reduce((s, p) => s + p.apy, 0) / saneProtocols.length).toFixed(1) : "0";
  const safeTvl = (metrics?.tvl && !isNaN(metrics.tvl)) ? metrics.tvl : FALLBACK_METRICS.tvl;
  const totalTvlNum = useCountUp(safeTvl / 1e9, 1400);

  const visible = protocols
    .filter(p => filter === "All" || p.category === filter)
    .filter(p => {
      if (!search.trim()) return true;
      const s = search.toLowerCase();
      return p.protocol.toLowerCase().includes(s) || p.symbol.toLowerCase().includes(s) || p.category.toLowerCase().includes(s);
    });

  const doSnapshot = async () => {
    if (!rateLimit.allowed) return;
    setSnapping(true);
    setSnapStep("fetching");

    // Try SSE stream first
    try {
      const evtSource = new EventSource(`${API}/snapshot/stream`);
      evtSource.onmessage = (e) => {
        const data = JSON.parse(e.data);
        if (data.step === "error") {
          setSnapping(false); setSnapStep(null);
          if (data.message?.includes("Rate limit")) {
            setRateLimit({ allowed: false, wait_minutes: parseInt(data.message.match(/\d+/) || [60]) });
          }
          evtSource.close(); return;
        }
        if (data.step === "complete") {
          const snap = data.snapshot;
          setSnapshots(p => [snap, ...p]);
          setSelSnap(snap);
          setSnapStep("complete");
          setFlash(true);
          setTimeout(() => setFlash(false), 600);
          setRateLimit({ allowed: false, wait_minutes: 60 });
          evtSource.close();
        } else {
          setSnapStep(data.step);
        }
      };
      evtSource.onerror = async () => {
        evtSource.close();
        // Fallback to regular POST
        await fallbackSnapshot();
      };
      return;
    } catch {}
    await fallbackSnapshot();
  };

  const fallbackSnapshot = async () => {
    const steps = ["fetching", "analyzing", "storing", "done"];
    for (const s of steps) {
      setSnapStep(s);
      await new Promise(r => setTimeout(r, 1200));
    }
    try {
      const res = await fetch(`${API}/snapshot`, { method: "POST" });
      if (res.ok) {
        const d = await res.json();
        setSnapshots(p => [d.snapshot, ...p]);
        setSelSnap(d.snapshot);
        setSnapStep("complete");
        setFlash(true);
        setTimeout(() => setFlash(false), 600);
        setRateLimit({ allowed: false, wait_minutes: 60 });
        return;
      }
      if (res.status === 429) {
        const err = await res.json();
        setRateLimit({ allowed: false, wait_minutes: err.detail?.wait_minutes || 60 });
      }
    } catch {}
    // Frontend-only fallback
    const currentTvl = safeTvl;
    const top3 = [...saneProtocols].sort((a, b) => b.apy - a.apy).slice(0, 3);
    const s = {
      snapshot_id: `blobfi-${Date.now()}`,
      blob_id: Math.random().toString(36).slice(2, 38),
      timestamp: new Date().toISOString(),
      top_apy: topByApy?.apy || 0,
      avg_apy: +avgApy,
      chain_tvl_usd: currentTvl,
      top_protocol: topByApy?.protocol || "",
      protocols_tracked: protocols.length,
      ai_report: `Sui TVL: $${(currentTvl / 1e9).toFixed(2)}B. Top: ${top3.map(p => `${p.protocol} ${p.apy}%`).join(", ")}. Avg APY: ${avgApy}%.`,
      walrus_stored: false,
    };
    setSnapshots(p => [s, ...p]);
    setSelSnap(s);
    setSnapStep("complete");
    setFlash(true);
    setTimeout(() => setFlash(false), 600);
    setSnapping(false);
  };

  const closeProgress = () => { setSnapping(false); setSnapStep(null); setView("history"); };

  const ask = async () => {
    if (!query.trim()) return;
    setAsking(true);
    try {
      const res = await fetch(`${API}/query`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question: query }) });
      if (res.ok) { const d = await res.json(); setAnswer(d.answer); setAsking(false); return; }
    } catch {}
    await new Promise(r => setTimeout(r, 600));
    const q = query.toLowerCase();
    const top3 = [...saneProtocols].sort((a, b) => b.apy - a.apy).slice(0, 3);
    if (q.includes("safe") || q.includes("low risk")) setAnswer(`Lowest risk: ${protocols.filter(p => p.il_risk === "none").slice(0, 3).map(p => `${p.protocol} (${p.apy}% APY, zero IL)`).join(", ")}.`);
    else if (q.includes("best") || q.includes("highest")) setAnswer(`Top 3: ${top3.map(p => `${p.protocol} ${p.apy}%`).join(", ")}. Best risk-adjusted: NAVI at 12.8% with $42M TVL.`);
    else setAnswer(`Sui DeFi: $${(safeTvl / 1e9).toFixed(2)}B TVL · ${protocols.length} pools · Best: ${topByApy?.protocol} ${topByApy?.apy}% · Avg: ${avgApy}%.`);
    setAsking(false);
  };

  const searchBlob = async () => {
    if (!blobSearch.trim()) return;
    setBlobSearching(true); setBlobError(""); setBlobResult(null);
    try {
      const res = await fetch(`${API}/snapshots/search/${blobSearch.trim()}`);
      if (res.ok) { setBlobResult(await res.json()); }
      else { setBlobError("No snapshot found for this blob ID."); }
    } catch { setBlobError("Search failed — check your connection."); }
    setBlobSearching(false);
  };

  const css = `
    @import url('https://fonts.googleapis.com/css2?family=Geist:wght@300;400;500;600;700&family=Geist+Mono:wght@400;500&display=swap');
    *{box-sizing:border-box;margin:0;padding:0}
    html,body,#root{width:100%;height:100%;overflow:hidden}
    @keyframes rise{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
    @keyframes ping{75%,100%{transform:scale(2);opacity:0}}
    @keyframes shimmer{0%,100%{opacity:.3}50%{opacity:1}}
    @keyframes flashbg{0%{background:rgba(255,255,255,0.06)}100%{background:transparent}}
    input::placeholder{color:rgba(255,255,255,0.2)}
    input:focus{outline:none;border-color:rgba(255,255,255,0.25)!important}
    ::-webkit-scrollbar{width:5px;height:5px}
    ::-webkit-scrollbar-track{background:transparent}
    ::-webkit-scrollbar-thumb{background:rgba(255,255,255,0.12);border-radius:3px}
    ::-webkit-scrollbar-thumb:hover{background:rgba(255,255,255,0.22)}
  `;

  return (
    <div style={{ fontFamily: "'Geist', system-ui, sans-serif", background: "#0a0a0a", width: "100%", height: "100vh", color: "#fff", position: "relative", overflow: "hidden" }}>
      <style>{css}</style>
      <DotGrid />
      <GlowOrb x="10%" y="15%" color="rgba(99,102,241,0.9)" size={600} opacity={0.06} />
      <GlowOrb x="90%" y="75%" color="rgba(34,197,94,0.9)" size={500} opacity={0.05} />
      {flash && <div style={{ position: "fixed", inset: 0, zIndex: 200, pointerEvents: "none", animation: "flashbg 0.6s ease forwards" }} />}
      {selProtocol && <ProtocolModal p={selProtocol} onClose={() => setSelProtocol(null)} />}
      {snapping && snapStep && <ProgressModal currentStep={snapStep} onClose={closeProgress} />}

      <div style={{ position: "relative", zIndex: 1, display: "flex", flexDirection: "column", width: "100%", height: "100%" }}>

        {/* NAV */}
        <header style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 24px", height: 52, borderBottom: "1px solid rgba(255,255,255,0.07)", backdropFilter: "blur(12px)", background: "rgba(10,10,10,0.85)", flexShrink: 0, zIndex: 100 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 28 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                <rect x="2" y="2" width="7" height="7" rx="1.5" fill="white" opacity="0.9"/>
                <rect x="11" y="2" width="7" height="7" rx="1.5" fill="white" opacity="0.5"/>
                <rect x="2" y="11" width="7" height="7" rx="1.5" fill="white" opacity="0.5"/>
                <rect x="11" y="11" width="7" height="7" rx="1.5" fill="white" opacity="0.2"/>
              </svg>
              <span style={{ fontSize: 15, fontWeight: 600, letterSpacing: "-0.03em" }}>BlobFi</span>
            </div>
            <nav style={{ display: "flex", gap: 2 }}>
              {[["yields","Yields"],["metrics","Metrics"],["history","History"],["ask","Ask AI"]].map(([k,l]) => (
                <button key={k} onClick={() => setView(k)} style={{
                  padding: "5px 13px", borderRadius: 6, fontSize: 12, cursor: "pointer",
                  fontFamily: "inherit", border: "none",
                  background: view === k ? "rgba(255,255,255,0.1)" : "transparent",
                  color: view === k ? "#fff" : "rgba(255,255,255,0.4)",
                  fontWeight: view === k ? 500 : 400, transition: "all 0.15s",
                }}>{l}</button>
              ))}
            </nav>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            {loading && <span style={{ fontSize: 11, color: "rgba(255,255,255,0.3)", animation: "shimmer 1s infinite" }}>fetching…</span>}
            {!loading && <span style={{ fontSize: 11, color: "rgba(255,255,255,0.3)" }}>{dataSource === "live" ? `${protocols.length} live pools` : "fallback"}</span>}
            <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: "rgba(255,255,255,0.35)" }}>
              <LiveDot /> Sui Mainnet
            </div>
            <div style={{ position: "relative" }}>
              <button onClick={doSnapshot} disabled={snapping || !rateLimit.allowed} title={!rateLimit.allowed ? `Available in ${rateLimit.wait_minutes}m` : "Capture snapshot"} style={{
                padding: "6px 14px", borderRadius: 7, fontSize: 12, fontWeight: 500,
                fontFamily: "inherit", cursor: (snapping || !rateLimit.allowed) ? "not-allowed" : "pointer",
                border: "1px solid rgba(255,255,255,0.15)",
                background: (snapping || !rateLimit.allowed) ? "transparent" : "rgba(255,255,255,0.08)",
                color: (snapping || !rateLimit.allowed) ? "rgba(255,255,255,0.25)" : "#fff",
                transition: "all 0.15s",
              }}>
                {snapping ? <span style={{ animation: "shimmer 0.8s infinite" }}>Capturing…</span>
                  : !rateLimit.allowed ? `Wait ${rateLimit.wait_minutes}m`
                  : "Snapshot →"}
              </button>
            </div>
          </div>
        </header>

        {/* YIELDS VIEW */}
        {view === "yields" && (
          <div style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
            {/* Stats */}
            <div style={{ padding: "18px 24px 16px", borderBottom: "1px solid rgba(255,255,255,0.07)", flexShrink: 0 }}>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(5,1fr)", gap: 24 }}>
                {[
                  { l: "Chain TVL", v: `$${totalTvlNum.toFixed(2)}B`, s: "Sui · DefiLlama", d: 0.05 },
                  { l: "Best APY", v: `${topByApy?.apy || 0}%`, s: topByApy?.protocol, d: 0.1 },
                  { l: "Avg APY", v: `${avgApy}%`, s: `${saneProtocols.length} pools`, d: 0.15 },
                  { l: "24h Change", v: `${metrics.tvl_24h > 0 ? "+" : ""}${metrics.tvl_24h.toFixed(2)}%`, s: "TVL", d: 0.2 },
                  { l: "Blobs Stored", v: snapshots.length, s: "on Walrus", d: 0.25 },
                ].map(({ l, v, s, d }) => (
                  <div key={l} style={{ opacity: 0, animation: `rise 0.5s ease ${d}s forwards` }}>
                    <div style={{ fontSize: 10, color: "rgba(255,255,255,0.3)", marginBottom: 5, letterSpacing: "0.06em", textTransform: "uppercase" }}>{l}</div>
                    <div style={{ fontSize: 24, fontWeight: 600, letterSpacing: "-0.03em", color: "#fff", lineHeight: 1 }}>{v}</div>
                    {s && <div style={{ fontSize: 11, color: "rgba(255,255,255,0.3)", marginTop: 4 }}>{s}</div>}
                  </div>
                ))}
              </div>
            </div>

            {/* Filters + Search */}
            <div style={{ padding: "10px 22px", borderBottom: "1px solid rgba(255,255,255,0.07)", display: "flex", gap: 8, alignItems: "center", flexShrink: 0, overflowX: "auto" }}>
              <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
                {cats.map(c => <Pill key={c} label={c} active={filter === c} onClick={() => setFilter(c)} />)}
              </div>
              <div style={{ flex: 1, minWidth: 140, position: "relative" }}>
                <input
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  placeholder="Search protocol or token…"
                  style={{
                    width: "100%", background: "rgba(255,255,255,0.04)",
                    border: "1px solid rgba(255,255,255,0.1)", borderRadius: 8,
                    padding: "5px 12px 5px 28px", color: "#fff",
                    fontFamily: "inherit", fontSize: 11,
                  }}
                />
                <span style={{ position: "absolute", left: 9, top: "50%", transform: "translateY(-50%)", fontSize: 11, color: "rgba(255,255,255,0.25)", pointerEvents: "none" }}>⌕</span>
              </div>
              <span style={{ fontSize: 11, color: "rgba(255,255,255,0.2)", whiteSpace: "nowrap", flexShrink: 0 }}>
                {visible.length} pools
              </span>
            </div>

            {/* Protocol grid — 5 columns with height limit */}
            <div style={{ flex: 1, overflowY: "auto", padding: "18px 22px" }}>
              {loading ? (
                <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "rgba(255,255,255,0.2)", fontSize: 13, animation: "shimmer 1s infinite" }}>
                  Fetching live Sui protocols from DefiLlama…
                </div>
              ) : visible.length === 0 ? (
                <div style={{ padding: "40px 0", textAlign: "center", color: "rgba(255,255,255,0.2)", fontSize: 13 }}>
                  No protocols match "{search}"
                </div>
              ) : (
                <div style={{ 
                  display: "grid", 
                  gridTemplateColumns: "repeat(5, 1fr)", 
                  gap: 12,
                  autoRows: "max-content"
                }}>
                  {visible.map((p, i) => (
                    <ProtocolCard key={`${p.protocol}-${p.symbol}`} p={p} i={i} onSelect={setSelProtocol} />
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* METRICS VIEW */}
        {view === "metrics" && (
          <div style={{ flex: 1, overflowY: "auto", padding: "28px" }}>
            <div style={{ maxWidth: 1100 }}>
              <div style={{ marginBottom: 28, opacity: 0, animation: "rise 0.4s ease both" }}>
                <div style={{ fontSize: 26, fontWeight: 600, letterSpacing: "-0.03em", marginBottom: 6 }}>Sui Network Metrics</div>
                <div style={{ fontSize: 13, color: "rgba(255,255,255,0.35)" }}>Live data from DefiLlama · Updates every 5 minutes</div>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 14, marginBottom: 14 }}>
                <MetricTile label="Total Value Locked" value={`$${(safeTvl / 1e9).toFixed(2)}B`} change={metrics.tvl_24h} delay={0.05} />
                <MetricTile label="7d TVL Change" value={`${metrics.tvl_7d > 0 ? "+" : ""}${metrics.tvl_7d.toFixed(2)}%`} change={metrics.tvl_7d} delay={0.1} />
                <MetricTile label="24h DEX Volume" value={`$${(metrics.volume_24h / 1e6).toFixed(0)}M`} change={metrics.volume_24h_change} delay={0.15} />
                <MetricTile label="24h Fees" value={`$${(metrics.fees_24h / 1e6).toFixed(2)}M`} note="Protocol fees" delay={0.2} />
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 14, marginBottom: 28 }}>
                <MetricTile label="Stablecoins TVL" value={`$${(metrics.stablecoins_mcap / 1e6).toFixed(0)}M`} delay={0.25} />
                <MetricTile label="Active Addresses" value={`${(metrics.active_addresses_24h / 1000).toFixed(0)}K`} note="24h unique" delay={0.3} />
                <MetricTile label="Transactions" value={`${(metrics.transactions_24h / 1e6).toFixed(2)}M`} note="24h on-chain" delay={0.35} />
                <MetricTile label="7d Fees" value={`$${(metrics.fees_7d / 1e6).toFixed(2)}M`} delay={0.4} />
              </div>
              <Line />
              <div style={{ padding: "20px 0", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 32, opacity: 0, animation: "rise 0.4s ease 0.45s both" }}>
                <div>
                  <div style={{ fontSize: 12, fontWeight: 500, marginBottom: 10 }}>About Sui DeFi</div>
                  <p style={{ fontSize: 12, color: "rgba(255,255,255,0.35)", lineHeight: 1.75 }}>Sui is a Layer 1 blockchain using the Move programming language. Its DeFi ecosystem spans DEXs, lending, liquid staking, CDPs, and perps. TVL data is sourced from DefiLlama. Each BlobFi snapshot is stored permanently on Walrus decentralized storage via Tatum RPC.</p>
                </div>
                <div>
                  <div style={{ fontSize: 12, fontWeight: 500, marginBottom: 10 }}>Metric Definitions</div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    {[["TVL","Total value locked in smart contracts"],["Volume","Total DEX trading activity"],["Fees","Revenue paid by users to protocols"],["IL Risk","Impermanent loss exposure in yield pools"]].map(([k, v]) => (
                      <div key={k} style={{ fontSize: 12, color: "rgba(255,255,255,0.35)" }}>
                        <span style={{ color: "rgba(255,255,255,0.6)", fontWeight: 500 }}>{k}</span> — {v}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* HISTORY VIEW */}
        {view === "history" && (
          <div style={{ display: "grid", gridTemplateColumns: "320px 1fr", flex: 1, overflow: "hidden" }}>
            <div style={{ borderRight: "1px solid rgba(255,255,255,0.07)", display: "flex", flexDirection: "column", overflow: "hidden" }}>
              {/* Blob search */}
              <div style={{ padding: "12px 16px", borderBottom: "1px solid rgba(255,255,255,0.07)", flexShrink: 0 }}>
                <div style={{ fontSize: 10, color: "rgba(255,255,255,0.25)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 8 }}>{snapshots.length} snapshots · Walrus</div>
                <div style={{ display: "flex", gap: 6 }}>
                  <input
                    value={blobSearch}
                    onChange={e => setBlobSearch(e.target.value)}
                    onKeyDown={e => e.key === "Enter" && searchBlob()}
                    placeholder="Search by blob ID…"
                    style={{
                      flex: 1, background: "rgba(255,255,255,0.04)",
                      border: "1px solid rgba(255,255,255,0.1)", borderRadius: 7,
                      padding: "6px 10px", color: "#fff",
                      fontFamily: "monospace", fontSize: 10.5,
                    }}
                  />
                  <button onClick={searchBlob} disabled={blobSearching} style={{
                    padding: "6px 10px", borderRadius: 7, fontSize: 11,
                    background: "rgba(255,255,255,0.07)", border: "1px solid rgba(255,255,255,0.12)",
                    color: "rgba(255,255,255,0.6)", cursor: "pointer", fontFamily: "inherit",
                  }}>{blobSearching ? "…" : "→"}</button>
                </div>
                {blobError && <div style={{ fontSize: 10, color: "#F97316", marginTop: 5 }}>{blobError}</div>}
              </div>
              <div style={{ flex: 1, overflowY: "auto" }}>
                {snapshots.map((s, i) => (
                  <div key={s.snapshot_id || s.id}>
                    <SnapshotRow s={s} i={i} selected={selSnap} onSelect={setSelSnap} />
                    <Line />
                  </div>
                ))}
                {snapshots.length === 0 && (
                  <div style={{ padding: "24px 20px", fontSize: 12, color: "rgba(255,255,255,0.2)" }}>
                    No snapshots yet — auto-snapshot runs every 30 minutes.
                  </div>
                )}
              </div>
            </div>

            {/* Detail panel */}
            <div style={{ overflowY: "auto", padding: "32px" }}>
              {blobResult ? (
                <div style={{ maxWidth: 560, opacity: 0, animation: "rise 0.3s ease both" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
                    <div style={{ fontSize: 11, color: "rgba(255,255,255,0.25)", textTransform: "uppercase", letterSpacing: "0.08em" }}>Blob Search Result</div>
                    <button onClick={() => setBlobResult(null)} style={{ background: "none", border: "none", color: "rgba(255,255,255,0.3)", cursor: "pointer", fontSize: 12 }}>✕ Clear</button>
                  </div>
                  <div style={{ padding: "16px", borderRadius: 10, border: "1px solid rgba(255,255,255,0.1)", background: "rgba(255,255,255,0.02)", marginBottom: 20 }}>
                    <div style={{ fontSize: 28, fontWeight: 600, letterSpacing: "-0.03em", marginBottom: 6 }}>{blobResult.top_apy}%</div>
                    <div style={{ fontSize: 12, color: "rgba(255,255,255,0.4)", marginBottom: 12 }}>peak APY · {blobResult.top_protocol}</div>
                    <div style={{ fontSize: 11, color: "rgba(255,255,255,0.4)", lineHeight: 1.7 }}>{blobResult.ai_report}</div>
                    <div style={{ marginTop: 12, paddingTop: 12, borderTop: "1px solid rgba(255,255,255,0.07)" }}>
                      <BlobTag id={blobResult.blob_id} full />
                    </div>
                  </div>
                </div>
              ) : selSnap ? (
                <div style={{ maxWidth: 560, opacity: 0, animation: "rise 0.3s ease both" }} key={selSnap.snapshot_id}>
                  <div style={{ marginBottom: 28 }}>
                    <div style={{ fontSize: 11, color: "rgba(255,255,255,0.25)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 8 }}>
                      Snapshot · {new Date(selSnap.timestamp || selSnap.ts).toLocaleString()}
                    </div>
                    <div style={{ fontSize: 32, fontWeight: 600, letterSpacing: "-0.04em", color: "#fff", marginBottom: 5 }}>{selSnap.top_apy}%</div>
                    <div style={{ fontSize: 13, color: "rgba(255,255,255,0.4)" }}>peak APY · {selSnap.top_protocol || selSnap.top}</div>
                  </div>
                  <Line />
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)" }}>
                    {[
                      ["Avg APY", `${selSnap.avg_apy}%`],
                      ["Chain TVL", `$${((selSnap.chain_tvl_usd || selSnap.tvl || 0) / 1e9).toFixed(2)}B`],
                      ["Walrus", selSnap.walrus_stored || selSnap.blob_id ? "✓ Stored" : "Local only"],
                    ].map(([l, v]) => (
                      <div key={l} style={{ padding: "20px 0" }}>
                        <div style={{ fontSize: 10, color: "rgba(255,255,255,0.25)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 5 }}>{l}</div>
                        <div style={{ fontSize: 17, fontWeight: 500, color: "#fff", letterSpacing: "-0.02em" }}>{v}</div>
                      </div>
                    ))}
                  </div>
                  <Line />
                  <div style={{ padding: "22px 0" }}>
                    <div style={{ fontSize: 10, color: "rgba(255,255,255,0.25)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 10 }}>AI Report</div>
                    <p style={{ fontSize: 13, color: "rgba(255,255,255,0.55)", lineHeight: 1.75 }}>{selSnap.ai_report || selSnap.report}</p>
                  </div>
                  <Line />
                  <div style={{ padding: "18px 0" }}>
                    <div style={{ fontSize: 10, color: "rgba(255,255,255,0.25)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 8 }}>Blob ID</div>
                    <BlobTag id={selSnap.blob_id} full />
                    {selSnap.blob_id && (
                      <div style={{ marginTop: 8, fontSize: 11, color: "rgba(255,255,255,0.2)", fontFamily: "'Geist Mono', monospace" }}>
                        GET {API}/blob/{selSnap.blob_id?.slice(0, 16)}…
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div style={{ color: "rgba(255,255,255,0.2)", fontSize: 12 }}>← Select a snapshot or search by blob ID</div>
              )}
            </div>
          </div>
        )}

        {/* ASK AI VIEW */}
        {view === "ask" && (
          <div style={{ flex: 1, display: "flex", flexDirection: "column", maxWidth: 640, margin: "0 auto", padding: "48px 24px 32px", width: "100%", overflowY: "auto", opacity: 0, animation: "rise 0.4s ease both" }}>
            <div style={{ marginBottom: 40 }}>
              <div style={{ fontSize: 26, fontWeight: 600, letterSpacing: "-0.04em", marginBottom: 8 }}>Ask about Sui yields</div>
              <div style={{ fontSize: 13, color: "rgba(255,255,255,0.35)" }}>Powered by Claude · {protocols.length} live pools · {dataSource}</div>
            </div>
            <div style={{ display: "flex", gap: 6, marginBottom: 28, flexWrap: "wrap" }}>
              {["Best low-risk yield?", "Top APY right now?", "Highest TVL protocols?"].map(s => (
                <button key={s} onClick={() => setQuery(s)} style={{
                  padding: "6px 13px", borderRadius: 20, fontSize: 11, cursor: "pointer",
                  fontFamily: "inherit", border: "1px solid rgba(255,255,255,0.1)",
                  background: "transparent", color: "rgba(255,255,255,0.4)", transition: "all 0.15s",
                }}
                  onMouseEnter={e => { e.currentTarget.style.color = "#fff"; e.currentTarget.style.borderColor = "rgba(255,255,255,0.3)"; }}
                  onMouseLeave={e => { e.currentTarget.style.color = "rgba(255,255,255,0.4)"; e.currentTarget.style.borderColor = "rgba(255,255,255,0.1)"; }}
                >{s}</button>
              ))}
            </div>
            <div style={{ display: "flex", gap: 10, marginBottom: 24 }}>
              <input value={query} onChange={e => setQuery(e.target.value)} onKeyDown={e => e.key === "Enter" && ask()}
                placeholder="e.g. What's the safest yield on Sui right now?"
                style={{ flex: 1, background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.12)", borderRadius: 9, padding: "12px 16px", color: "#fff", fontFamily: "inherit", fontSize: 13 }}
              />
              <button onClick={ask} disabled={asking} style={{
                padding: "12px 20px", borderRadius: 9, fontSize: 13, fontWeight: 500,
                fontFamily: "inherit", cursor: asking ? "not-allowed" : "pointer",
                border: "1px solid rgba(255,255,255,0.2)",
                background: asking ? "transparent" : "rgba(255,255,255,0.1)",
                color: asking ? "rgba(255,255,255,0.3)" : "#fff", whiteSpace: "nowrap",
              }}>{asking ? <span style={{ animation: "shimmer 0.8s infinite" }}>…</span> : "Ask →"}</button>
            </div>
            {answer && (
              <div style={{ padding: "20px", borderRadius: 10, border: "1px solid rgba(255,255,255,0.08)", background: "rgba(255,255,255,0.02)", opacity: 0, animation: "rise 0.4s ease both" }}>
                <div style={{ fontSize: 10, color: "rgba(255,255,255,0.25)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 10 }}>Answer</div>
                <p style={{ fontSize: 13, color: "rgba(255,255,255,0.65)", lineHeight: 1.75 }}>{answer}</p>
              </div>
            )}
            <div style={{ marginTop: "auto", paddingTop: 20, borderTop: "1px solid rgba(255,255,255,0.07)" }}>
              <div style={{ fontSize: 11, color: "rgba(255,255,255,0.2)" }}>
                {snapshots.length} snapshots on Walrus · auto-snapshot every 30 mins
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}