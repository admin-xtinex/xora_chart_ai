import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  API_BASE,
  fetchHealth,
  fetchOpportunities,
  fetchPatterns,
  referenceImageUrl,
  runCycle,
} from './api'

function Badge({ children, tone = 'neutral' }) {
  const tones = {
    neutral: 'bg-slate-700/60 text-slate-200',
    bull: 'bg-emerald-500/15 text-emerald-400 ring-1 ring-emerald-500/30',
    bear: 'bg-rose-500/15 text-rose-400 ring-1 ring-rose-500/30',
    cont: 'bg-sky-500/15 text-sky-300 ring-1 ring-sky-500/30',
    rev: 'bg-amber-500/15 text-amber-300 ring-1 ring-amber-500/30',
    buy: 'bg-emerald-500/20 text-emerald-300 ring-1 ring-emerald-500/40',
    sell: 'bg-rose-500/20 text-rose-300 ring-1 ring-rose-500/40',
  }
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium ${tones[tone] || tones.neutral}`}>
      {children}
    </span>
  )
}

function fmt(n, d = 4) {
  if (n == null || Number.isNaN(n)) return '—'
  const abs = Math.abs(n)
  if (abs >= 1000) return n.toLocaleString(undefined, { maximumFractionDigits: 2 })
  if (abs >= 1) return n.toFixed(Math.min(d, 4))
  return n.toFixed(Math.min(d, 6))
}

/* ═══════════════════ Opportunity Board ═══════════════════ */

function OppCard({ opp, selected, onClick }) {
  const side = opp.trade?.side || '—'
  const isBuy = side === 'BUY'
  const sim = opp.best_match?.similarity
  return (
    <button
      onClick={() => onClick(opp)}
      className={`w-full text-left p-4 rounded-xl border transition-all duration-150
        ${selected
          ? 'bg-xora-700 border-blue-500/60 shadow-lg shadow-blue-500/10'
          : 'bg-xora-800/80 border-xora-600/50 hover:border-slate-500 hover:bg-xora-700/80'}`}
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <div>
          <div className="font-semibold text-sm text-slate-100">{opp.symbol}</div>
          <div className="text-[11px] text-slate-500 mt-0.5">{opp.best_match?.pattern_name || '—'}</div>
        </div>
        <Badge tone={isBuy ? 'buy' : 'sell'}>{side}</Badge>
      </div>
      <div className="flex items-center gap-2 flex-wrap text-[11px]">
        <span className="text-blue-300 font-mono">{sim != null ? `${sim.toFixed(0)}%` : '—'}</span>
        <span className="text-slate-600">·</span>
        <span className="text-slate-400">RR {opp.trade?.risk_reward ?? '—'}</span>
        <span className="text-slate-600">·</span>
        <span className="text-amber-300/90">{opp.trade?.confidence != null ? `${opp.trade.confidence.toFixed(0)}% conf` : '—'}</span>
      </div>
      <div className="mt-2 text-[10px] text-slate-500 font-mono">rank {opp.rank_score?.toFixed?.(1) ?? opp.rank_score}</div>
    </button>
  )
}

function OppDetail({ opp }) {
  if (!opp) {
    return (
      <div className="h-full flex items-center justify-center text-slate-500">
        <div className="text-center px-6">
          <div className="text-4xl mb-3 opacity-40">🎯</div>
          <p className="text-sm">Select an opportunity or run a scan</p>
          <p className="text-xs text-slate-600 mt-2">Live matches from Binance Futures appear here</p>
        </div>
      </div>
    )
  }

  const t = opp.trade || {}
  const m = opp.best_match || {}
  const isBuy = t.side === 'BUY'
  const img = referenceImageUrl(m.pattern_key)

  return (
    <div className="h-full overflow-y-auto">
      <div className="sticky top-0 z-10 bg-xora-900/95 backdrop-blur border-b border-xora-600/40 px-6 py-4">
        <div className="flex items-center gap-3 flex-wrap">
          <h2 className="text-xl font-bold tracking-tight">{opp.symbol}</h2>
          <Badge tone={isBuy ? 'buy' : 'sell'}>{t.side || '—'}</Badge>
          <Badge tone={m.direction === 'bullish' ? 'bull' : 'bear'}>{m.direction || '—'}</Badge>
          {opp.ai_validated && <Badge tone="cont">AI validated</Badge>}
        </div>
        <p className="text-xs text-slate-500 mt-1">
          {m.pattern_name} · similarity {m.similarity?.toFixed?.(1)}% · rank {opp.rank_score}
        </p>
      </div>

      <div className="p-6 space-y-6">
        {/* Trade levels */}
        <section className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          <div className="rounded-lg bg-xora-800 border border-xora-600/50 p-3">
            <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">Entry</div>
            <div className="text-sm font-mono font-medium text-slate-100">{fmt(t.entry)}</div>
          </div>
          <div className="rounded-lg bg-rose-500/10 border border-rose-500/20 p-3">
            <div className="text-[10px] uppercase tracking-wider text-rose-400/80 mb-1">Stop Loss</div>
            <div className="text-sm font-mono font-medium text-rose-300">{fmt(t.stop_loss)}</div>
          </div>
          <div className="rounded-lg bg-emerald-500/10 border border-emerald-500/20 p-3">
            <div className="text-[10px] uppercase tracking-wider text-emerald-400/80 mb-1">TP1</div>
            <div className="text-sm font-mono font-medium text-emerald-300">{fmt(t.take_profit_1)}</div>
          </div>
          <div className="rounded-lg bg-emerald-500/10 border border-emerald-500/20 p-3">
            <div className="text-[10px] uppercase tracking-wider text-emerald-400/80 mb-1">TP2</div>
            <div className="text-sm font-mono font-medium text-emerald-300">{fmt(t.take_profit_2)}</div>
          </div>
          <div className="rounded-lg bg-emerald-500/10 border border-emerald-500/20 p-3">
            <div className="text-[10px] uppercase tracking-wider text-emerald-400/80 mb-1">TP3</div>
            <div className="text-sm font-mono font-medium text-emerald-300">{fmt(t.take_profit_3)}</div>
          </div>
          <div className="rounded-lg bg-sky-500/10 border border-sky-500/20 p-3">
            <div className="text-[10px] uppercase tracking-wider text-sky-400/80 mb-1">R:R</div>
            <div className="text-sm font-mono font-medium text-sky-300">{t.risk_reward ?? '—'}</div>
          </div>
        </section>

        {/* Confidence + AI */}
        <section className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="rounded-xl bg-xora-800/80 border border-xora-600/50 p-4">
            <div className="text-xs text-slate-500 mb-2">Confidence</div>
            <div className="flex items-end gap-2">
              <span className="text-3xl font-bold text-amber-300">{t.confidence != null ? t.confidence.toFixed(0) : '—'}%</span>
              <span className="text-xs text-slate-500 mb-1">pattern {m.similarity?.toFixed?.(0)}% match</span>
            </div>
          </div>
          <div className="rounded-xl bg-xora-800/80 border border-xora-600/50 p-4">
            <div className="text-xs text-slate-500 mb-2">AI / validation</div>
            <p className="text-sm text-slate-300 leading-relaxed">{opp.ai_rationale || '—'}</p>
          </div>
        </section>

        {/* All matches */}
        {opp.all_matches?.length > 0 && (
          <section>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">Pattern matches</h3>
            <div className="space-y-2">
              {opp.all_matches.map((pm) => (
                <div key={pm.pattern_key} className="flex items-center justify-between rounded-lg bg-xora-800/60 border border-xora-600/40 px-3 py-2 text-sm">
                  <span className="text-slate-200">{pm.pattern_name}</span>
                  <span className="font-mono text-blue-300">{pm.similarity?.toFixed?.(1)}%</span>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Score breakdown */}
        {m.score_breakdown && Object.keys(m.score_breakdown).length > 0 && (
          <section>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">Similarity features</h3>
            <div className="flex flex-wrap gap-2">
              {Object.entries(m.score_breakdown).map(([k, v]) => (
                <div key={k} className="rounded-md bg-xora-800 border border-xora-600/50 px-3 py-1.5 text-xs">
                  <span className="text-slate-500">{k.replace(/_/g, ' ')}:</span>{' '}
                  <span className="text-slate-200 font-mono">{typeof v === 'number' ? v.toFixed(2) : v}</span>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Reference pattern image */}
        {img && (
          <section>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">Reference pattern</h3>
            <div className="rounded-xl overflow-hidden border border-xora-600/50 bg-xora-950">
              <img src={img} alt={m.pattern_name} className="w-full h-auto object-contain max-h-[380px]" loading="lazy" />
            </div>
          </section>
        )}

        <div className="text-[11px] text-slate-600 font-mono">
          id={opp.id?.slice?.(0, 8)} · cycle={opp.cycle_id?.slice?.(0, 8)} · candles={opp.candle_count} · last={fmt(opp.last_price)}
        </div>
      </div>
    </div>
  )
}

function OpportunityBoard() {
  const [opps, setOpps] = useState([])
  const [selected, setSelected] = useState(null)
  const [loading, setLoading] = useState(true)
  const [scanning, setScanning] = useState(false)
  const [error, setError] = useState(null)
  const [lastScan, setLastScan] = useState(null)

  const load = useCallback(async () => {
    setError(null)
    try {
      const list = await fetchOpportunities(30)
      setOpps(list)
      setSelected((prev) => {
        if (prev) {
          const still = list.find((o) => o.id === prev.id)
          if (still) return still
        }
        return list[0] || null
      })
    } catch (e) {
      setError(e.message || 'Failed to load')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    const t = setInterval(load, 15000)
    return () => clearInterval(t)
  }, [load])

  async function handleScan() {
    setScanning(true)
    setError(null)
    try {
      const cycle = await runCycle()
      setLastScan(cycle)
      await load()
    } catch (e) {
      setError(e.message || 'Scan failed')
    } finally {
      setScanning(false)
    }
  }

  return (
    <div className="flex-1 min-h-0 flex">
      <aside className="w-80 shrink-0 border-r border-xora-600/40 bg-xora-900 flex flex-col">
        <div className="p-3 border-b border-xora-600/40 space-y-2">
          <button
            onClick={handleScan}
            disabled={scanning}
            className={`w-full py-2.5 rounded-lg text-sm font-semibold transition
              ${scanning
                ? 'bg-blue-900/50 text-blue-300 cursor-wait'
                : 'bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-600/20'}`}
          >
            {scanning ? 'Scanning Binance…' : 'Run scan now'}
          </button>
          <div className="text-[11px] text-slate-500 text-center">
            {opps.length} opportunities
            {lastScan?.finished_at && (
              <span> · last scan {new Date(lastScan.finished_at).toLocaleTimeString()}</span>
            )}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          {loading && <div className="text-center text-slate-500 text-sm py-8">Loading…</div>}
          {error && (
            <div className="text-center text-rose-400 text-sm py-6 px-2">
              {error}
              <div className="text-[11px] text-slate-500 mt-2">API: {API_BASE}</div>
            </div>
          )}
          {!loading && !error && opps.length === 0 && (
            <div className="text-center text-slate-500 text-sm py-10 px-3">
              No opportunities yet.
              <div className="mt-2 text-xs text-slate-600">Click “Run scan now” or wait for the worker.</div>
            </div>
          )}
          {opps.map((o) => (
            <OppCard key={o.id} opp={o} selected={selected?.id === o.id} onClick={setSelected} />
          ))}
        </div>
      </aside>

      <main className="flex-1 min-w-0 bg-xora-950">
        <OppDetail opp={selected} />
      </main>
    </div>
  )
}

/* ═══════════════════ Pattern Library (Phase 1) ═══════════════════ */

function PatternCard({ pattern, selected, onClick }) {
  const isBull = pattern.direction === 'bullish'
  return (
    <button
      onClick={() => onClick(pattern)}
      className={`w-full text-left p-4 rounded-xl border transition-all duration-150
        ${selected
          ? 'bg-xora-700 border-blue-500/60 shadow-lg shadow-blue-500/10'
          : 'bg-xora-800/80 border-xora-600/50 hover:border-slate-500 hover:bg-xora-700/80'}`}
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <h3 className="font-semibold text-sm leading-snug text-slate-100">{pattern.name}</h3>
        <Badge tone={isBull ? 'bull' : 'bear'}>{isBull ? 'Bull' : 'Bear'}</Badge>
      </div>
      <Badge tone={pattern.type === 'continuation' ? 'cont' : 'rev'}>{pattern.type}</Badge>
    </button>
  )
}

function PatternDetail({ pattern }) {
  if (!pattern) {
    return (
      <div className="h-full flex items-center justify-center text-slate-500">
        <p className="text-sm">Select a pattern</p>
      </div>
    )
  }
  const img = referenceImageUrl(pattern.key)
  const isBull = pattern.direction === 'bullish'
  return (
    <div className="h-full overflow-y-auto">
      <div className="sticky top-0 z-10 bg-xora-900/95 backdrop-blur border-b border-xora-600/40 px-6 py-4">
        <div className="flex items-center gap-3 flex-wrap">
          <h2 className="text-xl font-bold">{pattern.name}</h2>
          <Badge tone={isBull ? 'bull' : 'bear'}>{isBull ? 'Bullish' : 'Bearish'}</Badge>
          <Badge tone={pattern.type === 'continuation' ? 'cont' : 'rev'}>{pattern.type}</Badge>
        </div>
      </div>
      <div className="p-6 space-y-6">
        {img && (
          <div className="rounded-xl overflow-hidden border border-xora-600/50 bg-xora-950">
            <img src={img} alt={pattern.name} className="w-full h-auto object-contain max-h-[420px]" loading="lazy" />
          </div>
        )}
        <p className="text-sm text-slate-300 leading-relaxed">{pattern.overview}</p>
        <section className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="rounded-lg bg-emerald-500/10 border border-emerald-500/20 p-3">
            <div className="text-[10px] uppercase text-emerald-400/80 mb-1">Entry</div>
            <div className="text-sm text-emerald-300">{pattern.trading_setup.entry}</div>
          </div>
          <div className="rounded-lg bg-rose-500/10 border border-rose-500/20 p-3">
            <div className="text-[10px] uppercase text-rose-400/80 mb-1">Stop Loss</div>
            <div className="text-sm text-rose-300">{pattern.trading_setup.stop_loss}</div>
          </div>
          <div className="rounded-lg bg-sky-500/10 border border-sky-500/20 p-3">
            <div className="text-[10px] uppercase text-sky-400/80 mb-1">Target</div>
            <div className="text-sm text-sky-300">{pattern.trading_setup.target}</div>
          </div>
        </section>
        <ul className="space-y-1.5">
          {pattern.key_points.map((k, i) => (
            <li key={i} className="flex gap-2 text-sm text-slate-300">
              <span className="text-emerald-400">✓</span>{k}
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}

function PatternLibrary() {
  const [patterns, setPatterns] = useState([])
  const [selected, setSelected] = useState(null)
  const [filterDir, setFilterDir] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setLoading(true)
      try {
        const list = await fetchPatterns({ direction: filterDir || undefined })
        if (!cancelled) {
          setPatterns(list)
          setSelected((prev) => list.find((p) => p.key === prev?.key) || list[0] || null)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [filterDir])

  return (
    <div className="flex-1 min-h-0 flex">
      <aside className="w-72 shrink-0 border-r border-xora-600/40 bg-xora-900 flex flex-col">
        <div className="p-3 border-b border-xora-600/40 flex gap-1.5">
          {[('', 'All'), ('bullish', 'Bull'), ('bearish', 'Bear')].map(([v, label]) => (
            <button
              key={v}
              onClick={() => setFilterDir(v)}
              className={`flex-1 text-xs py-1.5 rounded-md font-medium
                ${filterDir === v ? 'bg-blue-600 text-white' : 'bg-xora-800 text-slate-400'}`}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          {loading && <div className="text-center text-slate-500 text-sm py-8">Loading…</div>}
          {patterns.map((p) => (
            <PatternCard key={p.key} pattern={p} selected={selected?.key === p.key} onClick={setSelected} />
          ))}
        </div>
      </aside>
      <main className="flex-1 min-w-0 bg-xora-950">
        <PatternDetail pattern={selected} />
      </main>
    </div>
  )
}

/* ═══════════════════ Shell ═══════════════════ */

export default function App() {
  const [tab, setTab] = useState('opportunities')
  const [health, setHealth] = useState(null)

  useEffect(() => {
    fetchHealth().then(setHealth).catch(() => setHealth(null))
    const t = setInterval(() => {
      fetchHealth().then(setHealth).catch(() => setHealth(null))
    }, 20000)
    return () => clearInterval(t)
  }, [])

  return (
    <div className="h-full flex flex-col">
      <header className="shrink-0 border-b border-xora-600/40 bg-xora-900/90 backdrop-blur px-5 py-3 flex items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-sm font-bold shadow-lg shadow-blue-500/20">
              X
            </div>
            <div>
              <div className="font-semibold text-sm tracking-tight">XORA Chart AI</div>
              <div className="text-[11px] text-slate-500">Live scanner · Phase 2</div>
            </div>
          </div>

          <nav className="flex gap-1 ml-2">
            {[
              ['opportunities', 'Opportunities'],
              ['library', 'Pattern Library'],
            ].map(([id, label]) => (
              <button
                key={id}
                onClick={() => setTab(id)}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition
                  ${tab === id ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-slate-200 hover:bg-xora-800'}`}
              >
                {label}
              </button>
            ))}
          </nav>
        </div>

        <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium
          ${health ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'}`}>
          <span className={`w-1.5 h-1.5 rounded-full ${health ? 'bg-emerald-400' : 'bg-rose-400'}`} />
          {health ? `API · ${health.opportunities_cached ?? 0} cached` : 'API offline'}
        </div>
      </header>

      {tab === 'opportunities' ? <OpportunityBoard /> : <PatternLibrary />}
    </div>
  )
}
