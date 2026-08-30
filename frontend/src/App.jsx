import { useCallback, useEffect, useState } from 'react'
import {
  analyzeSymbol,
  closeTrade,
  fetchHealth,
  fetchOpportunities,
  fetchPatterns,
  fetchPositions,
  fetchSettings,
  fetchTradeSummary,
  openDemoTrade,
  runCycle,
  updateSettings,
} from './api'
import CandleChart from './CandleChart'

function Badge({ children, tone = 'neutral' }) {
  const tones = {
    neutral: 'bg-slate-700/60 text-slate-200',
    bull: 'bg-emerald-500/15 text-emerald-400 ring-1 ring-emerald-500/30',
    bear: 'bg-rose-500/15 text-rose-400 ring-1 ring-rose-500/30',
    cont: 'bg-sky-500/15 text-sky-300 ring-1 ring-sky-500/30',
    buy: 'bg-emerald-500/20 text-emerald-300 ring-1 ring-emerald-500/40',
    sell: 'bg-rose-500/20 text-rose-300 ring-1 ring-rose-500/40',
    approve: 'bg-emerald-500/20 text-emerald-300 ring-1 ring-emerald-500/40',
    wait: 'bg-amber-500/20 text-amber-300 ring-1 ring-amber-500/40',
    reject: 'bg-rose-500/20 text-rose-300 ring-1 ring-rose-500/40',
    traded: 'bg-blue-500/20 text-blue-300 ring-1 ring-blue-500/40',
    strong: 'bg-emerald-500/20 text-emerald-300',
    ok: 'bg-sky-500/20 text-sky-300',
    watch: 'bg-amber-500/20 text-amber-300',
    weak: 'bg-orange-500/20 text-orange-300',
    critical: 'bg-rose-500/20 text-rose-300',
    unknown: 'bg-slate-700/40 text-slate-300',
  }
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium ${tones[tone] || tones.neutral}`}>
      {children}
    </span>
  )
}

function fmt(n, d = 4) {
  if (n == null || Number.isNaN(Number(n))) return '—'
  const v = Number(n)
  const abs = Math.abs(v)
  if (abs >= 1000) return v.toLocaleString(undefined, { maximumFractionDigits: 2 })
  if (abs >= 1) return v.toFixed(Math.min(d, 4))
  return v.toFixed(Math.min(d, 6))
}

function pnlClass(n) {
  if (n == null) return 'text-slate-400'
  return n >= 0 ? 'text-emerald-400' : 'text-rose-400'
}

function decisionTone(action) {
  if (action === 'APPROVE') return 'approve'
  if (action === 'WAIT') return 'wait'
  if (action === 'REJECT') return 'reject'
  return 'neutral'
}

function uniqueBySymbol(list) {
  const seen = new Set()
  const out = []
  for (const o of list || []) {
    const k = (o.symbol || '').toUpperCase()
    if (!k || seen.has(k)) continue
    seen.add(k)
    out.push(o)
  }
  return out
}

/* ═══════════════ Opportunity detail ═══════════════ */

function OppDetail({ opp, onTraded }) {
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState(null)
  if (!opp) {
    return (
      <div className="h-full flex items-center justify-center text-slate-500">
        <p className="text-sm">Select an opportunity, run a scan, or analyze a coin</p>
      </div>
    )
  }
  const t = opp.trade || {}
  const m = opp.best_match || {}
  const a = opp.analysis || {}
  const ma = opp.market_analysis
  const d = opp.decision
  const canTrade = !!t.entry && opp.status !== 'traded' && d?.action !== 'REJECT'

  async function handleOpen() {
    setBusy(true)
    setMsg(null)
    try {
      const pos = await openDemoTrade(opp.id)
      setMsg(`Demo opened · ${pos.symbol}`)
      onTraded?.()
    } catch (e) {
      setMsg(e.message || 'Failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="sticky top-0 z-10 bg-xtinex-void/95 backdrop-blur border-b border-xtinex-line px-4 sm:px-6 py-4">
        <div className="flex items-center gap-3 flex-wrap">
          <h2 className="text-xl font-display font-semibold tracking-wide">{opp.symbol}</h2>
          {t.side && <Badge tone={t.side === 'BUY' ? 'buy' : 'sell'}>{t.side}</Badge>}
          {d?.action && <Badge tone={decisionTone(d.action)}>{d.action}</Badge>}
          {opp.status === 'traded' && <Badge tone="traded">TRADED</Badge>}
        </div>
        <p className="text-xs text-slate-500 mt-1">
          {m.pattern_name || 'No pattern'} · live {fmt(opp.last_price)} · sim {m.similarity?.toFixed?.(0) ?? '—'}%
        </p>
      </div>
      <div className="p-4 sm:p-6 space-y-5">
        {d && (
          <section className="rounded-xl border border-xtinex-line bg-xtinex-ink/80 p-4 space-y-3">
            <div className="flex items-center justify-between gap-3 flex-wrap">
              <div className="text-sm text-slate-200">{d.reason}</div>
              {canTrade && (
                <button
                  onClick={handleOpen}
                  disabled={busy}
                  className="px-4 py-2 rounded-lg text-sm font-semibold bg-emerald-600 hover:bg-emerald-500 text-white disabled:opacity-50"
                >
                  {busy ? 'Opening…' : 'Enter demo trade'}
                </button>
              )}
            </div>
            {msg && <div className="text-xs text-sky-300">{msg}</div>}
          </section>
        )}
        {ma && (
          <section className="rounded-xl border border-xtinex-line bg-xtinex-ink/80 p-4">
            <div className="flex justify-between mb-2 text-xs uppercase text-slate-400">
              <span>Analysis</span>
              <span className="text-violet-300 font-mono">{ma.score?.toFixed?.(0)} / 100</span>
            </div>
            <div className="flex gap-2 mb-3">
              <Badge tone={ma.bias === 'bullish' ? 'bull' : ma.bias === 'bearish' ? 'bear' : 'neutral'}>{ma.bias}</Badge>
              <Badge tone="cont">{ma.regime}</Badge>
            </div>
            {(ma.signals || []).map((s) => (
              <div key={s.name} className="mb-2">
                <div className="flex justify-between text-[11px]">
                  <span className="text-slate-400">{s.name}</span>
                  <span className="text-slate-300">{s.score?.toFixed?.(0)} · {s.status}</span>
                </div>
                <div className="h-1.5 rounded-full bg-xora-900 overflow-hidden">
                  <div className="h-full bg-violet-500" style={{ width: `${Math.min(100, s.score || 0)}%` }} />
                </div>
              </div>
            ))}
          </section>
        )}
        <CandleChart candles={opp.candles || []} trade={opp.trade} overlays={a.chart_overlays} height={360} />
        <section className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          {[
            ['Entry', t.entry, 'text-blue-300'],
            ['SL', t.stop_loss, 'text-rose-300'],
            ['TP1', t.take_profit_1, 'text-emerald-300'],
            ['TP2', t.take_profit_2, 'text-emerald-300'],
            ['TP3', t.take_profit_3, 'text-emerald-300'],
            ['R:R', t.risk_reward, 'text-sky-300'],
          ].map(([label, val, cls]) => (
            <div key={label} className="rounded-lg bg-xtinex-ink border border-xtinex-line p-3">
              <div className="text-[10px] uppercase text-slate-500 mb-1">{label}</div>
              <div className={`text-sm font-mono ${cls}`}>{fmt(val)}</div>
            </div>
          ))}
        </section>
        {a.summary && <p className="text-sm text-slate-300 whitespace-pre-line">{a.summary}</p>}
      </div>
    </div>
  )
}

function OpportunityBoard({ autoTrade, onToggleAuto }) {
  const [opps, setOpps] = useState([])
  const [selected, setSelected] = useState(null)
  const [loading, setLoading] = useState(true)
  const [scanning, setScanning] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [coin, setCoin] = useState('')
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    try {
      const list = uniqueBySymbol(await fetchOpportunities(40))
      setOpps(list)
      setSelected((prev) => {
        if (prev) {
          const still = list.find((o) => o.symbol === prev.symbol || o.id === prev.id)
          if (still) return still
        }
        return list[0] || null
      })
      setError(null)
    } catch (e) {
      setError(e.message || 'Failed to load')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    const t = setInterval(load, 8000)
    return () => clearInterval(t)
  }, [load])

  async function handleScan() {
    setScanning(true)
    setError(null)
    try {
      await runCycle()
      await load()
    } catch (e) {
      setError(e.message || 'Scan failed')
    } finally {
      setScanning(false)
    }
  }

  async function handleAnalyze(e) {
    e?.preventDefault()
    if (!coin.trim()) return
    setAnalyzing(true)
    setError(null)
    try {
      const opp = await analyzeSymbol(coin.trim())
      await load()
      setSelected(opp)
    } catch (err) {
      setError(err.message || 'Analyze failed')
    } finally {
      setAnalyzing(false)
    }
  }

  return (
    <div className="flex-1 min-h-0 flex flex-col md:flex-row">
      <aside className="w-full md:w-80 max-h-[45vh] md:max-h-none shrink-0 border-b md:border-b-0 md:border-r border-xtinex-line bg-xtinex-void flex flex-col">
        <div className="p-3 border-b border-xtinex-line space-y-2">
          <button
            onClick={handleScan}
            disabled={scanning}
            className={`w-full py-2.5 rounded-lg text-sm font-semibold ${
              scanning ? 'bg-blue-900/50 text-blue-300' : 'bg-blue-600 hover:bg-blue-500 text-white'
            }`}
          >
            {scanning ? 'Scanning…' : 'Run scan now'}
          </button>

          <form onSubmit={handleAnalyze} className="flex gap-1.5">
            <input
              value={coin}
              onChange={(e) => setCoin(e.target.value)}
              placeholder="BTC or ETHUSDT"
              className="flex-1 min-w-0 bg-xtinex-ink border border-xtinex-line rounded-lg px-2 py-2 text-xs text-xtinex-fg placeholder:text-xtinex-faint"
            />
            <button
              type="submit"
              disabled={analyzing || !coin.trim()}
              className="px-3 rounded-lg text-xs font-semibold bg-violet-600 hover:bg-violet-500 text-white disabled:opacity-40"
            >
              {analyzing ? '…' : 'Analyze'}
            </button>
          </form>

          <label className={`flex items-center justify-between gap-2 px-3 py-2 rounded-lg border cursor-pointer
            ${autoTrade ? 'border-emerald-500/40 bg-emerald-500/10' : 'border-xtinex-line bg-xtinex-ink/70'}`}>
            <div>
              <div className="text-xs font-semibold text-slate-200">Auto demo trades</div>
              <div className="text-[10px] text-slate-500">APPROVE → open automatically</div>
            </div>
            <input type="checkbox" checked={!!autoTrade} onChange={(e) => onToggleAuto(e.target.checked)} className="accent-emerald-500" />
          </label>
          <div className="text-[11px] text-slate-500 text-center">{opps.length} unique symbols</div>
        </div>

        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          {loading && <div className="text-center text-slate-500 text-sm py-8">Loading…</div>}
          {error && <div className="text-center text-rose-400 text-xs py-3 px-2">{error}</div>}
          {!loading && opps.length === 0 && (
            <div className="text-center text-slate-500 text-sm py-8">No opportunities. Scan or analyze a coin.</div>
          )}
          {opps.map((o) => (
            <button
              key={o.symbol}
              onClick={() => setSelected(o)}
              className={`w-full text-left p-3 rounded-xl border ${
                selected?.symbol === o.symbol ? 'bg-xora-700 border-xtinex-gold/70' : 'bg-xtinex-ink/80 border-xtinex-line'
              }`}
            >
              <div className="flex justify-between">
                <span className="font-semibold text-sm">{o.symbol}</span>
                <div className="flex gap-1">
                  {o.trade?.side && <Badge tone={o.trade.side === 'BUY' ? 'buy' : 'sell'}>{o.trade.side}</Badge>}
                  {o.decision?.action && <Badge tone={decisionTone(o.decision.action)}>{o.decision.action}</Badge>}
                </div>
              </div>
              <div className="text-[11px] text-slate-500 mt-1">
                {o.best_match?.pattern_name || '—'} · {o.best_match?.similarity?.toFixed?.(0) ?? '—'}% · {fmt(o.last_price)}
              </div>
            </button>
          ))}
        </div>
      </aside>
      <main className="flex-1 min-w-0 bg-xtinex-black">
        <OppDetail opp={selected} onTraded={load} />
      </main>
    </div>
  )
}

/* ═══════════════ Trades ═══════════════ */

function TradesPanel() {
  const [positions, setPositions] = useState([])
  const [summary, setSummary] = useState(null)
  const [filter, setFilter] = useState('open')
  const [picked, setPicked] = useState(null)
  const [error, setError] = useState(null)
  const [busyId, setBusyId] = useState(null)

  const load = useCallback(async () => {
    try {
      const [pos, sum] = await Promise.all([
        fetchPositions(filter || undefined),
        fetchTradeSummary(),
      ])
      setPositions(pos)
      setSummary(sum)
      setPicked((prev) => {
        if (prev) {
          const still = pos.find((p) => p.id === prev.id)
          if (still) return still
        }
        return pos[0] || null
      })
      setError(null)
    } catch (e) {
      setError(e.message)
    }
  }, [filter])

  useEffect(() => {
    load()
    const t = setInterval(load, 4000)
    return () => clearInterval(t)
  }, [load])

  async function handleClose(id) {
    setBusyId(id)
    try {
      await closeTrade(id)
      await load()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="flex-1 min-h-0 flex flex-col md:flex-row">
      <aside className="w-full md:w-[28rem] max-h-[45vh] md:max-h-none shrink-0 border-b md:border-b-0 md:border-r border-xtinex-line bg-xtinex-void flex flex-col">
        <div className="p-3 border-b border-xtinex-line space-y-3">
          <div className="flex gap-1">
            {['open', 'closed', ''].map((f) => (
              <button
                key={f || 'all'}
                onClick={() => setFilter(f)}
                className={`flex-1 py-1.5 rounded-md text-xs font-medium ${
                  filter === f ? 'bg-blue-600 text-white' : 'bg-xora-800 text-slate-400'
                }`}
              >
                {f || 'all'}
              </button>
            ))}
          </div>
          {summary && (
            <div className="grid grid-cols-3 gap-2 text-center">
              <div className="rounded-lg bg-xora-800/80 p-2">
                <div className="text-[10px] text-slate-500">Open PnL</div>
                <div className={`text-sm font-mono ${pnlClass(summary.open_unrealized_pnl)}`}>{fmt(summary.open_unrealized_pnl, 2)}</div>
              </div>
              <div className="rounded-lg bg-xora-800/80 p-2">
                <div className="text-[10px] text-slate-500">Realized</div>
                <div className={`text-sm font-mono ${pnlClass(summary.total_realized_pnl)}`}>{fmt(summary.total_realized_pnl, 2)}</div>
              </div>
              <div className="rounded-lg bg-xora-800/80 p-2">
                <div className="text-[10px] text-slate-500">Win %</div>
                <div className="text-sm font-mono text-xtinex-fg">{summary.win_rate}</div>
              </div>
            </div>
          )}
        </div>
        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          {error && <div className="text-xs text-rose-400">{error}</div>}
          {positions.length === 0 && <div className="text-sm text-slate-500 text-center py-8">No trades in this filter</div>}
          {positions.map((p) => {
            const h = p.health || {}
            return (
              <button
                key={p.id}
                onClick={() => setPicked(p)}
                className={`w-full text-left p-3 rounded-xl border ${
                  picked?.id === p.id ? 'bg-xora-700 border-xtinex-gold/70' : 'bg-xtinex-ink/80 border-xtinex-line'
                }`}
              >
                <div className="flex justify-between items-start">
                  <div>
                    <div className="font-semibold text-sm">{p.symbol}</div>
                    <div className="text-[11px] text-slate-500">{p.side} · {p.leverage}x · {p.status}</div>
                  </div>
                  <div className="text-right">
                    <div className={`font-mono text-sm ${pnlClass(p.live_pnl)}`}>{fmt(p.live_pnl, 2)}</div>
                    <div className="text-[11px] text-slate-400">{fmt(p.live_price)}</div>
                  </div>
                </div>
                {p.status === 'open' && (
                  <div className="mt-2 flex items-center justify-between">
                    <Badge tone={h.status || 'unknown'}>{h.action || 'HOLD'}</Badge>
                    <span className="text-[10px] text-slate-500">{h.reason}</span>
                  </div>
                )}
                {p.exit_reason && <div className="text-[10px] text-slate-500 mt-1">exit {p.exit_reason}</div>}
              </button>
            )
          })}
        </div>
      </aside>

      <main className="flex-1 min-w-0 bg-xtinex-black overflow-y-auto p-4 sm:p-6 space-y-4">
        {!picked && <p className="text-slate-500 text-sm">Select a trade</p>}
        {picked && (
          <>
            <div className="flex items-start justify-between gap-3 flex-wrap">
              <div>
                <h2 className="text-xl font-display font-semibold tracking-wide">{picked.symbol}</h2>
                <p className="text-xs text-slate-500">
                  {picked.side} · entry {fmt(picked.entry)} · live {fmt(picked.live_price)}
                </p>
              </div>
              <div className="text-right">
                <div className={`text-2xl font-mono font-semibold ${pnlClass(picked.live_pnl)}`}>{fmt(picked.live_pnl, 2)}</div>
                <div className="text-[11px] text-slate-500">live PnL (USDT)</div>
              </div>
            </div>

            {picked.health && (
              <section className="rounded-xl border border-xtinex-line bg-xtinex-ink/80 p-4 flex items-center justify-between gap-3 flex-wrap">
                <div>
                  <div className="flex gap-2 mb-1">
                    <Badge tone={picked.health.status}>{picked.health.action}</Badge>
                    <span className="text-xs text-slate-400">health {picked.health.score}/100 · R {picked.health.progress_to_tp}</span>
                  </div>
                  <p className="text-sm text-slate-200">{picked.health.reason}</p>
                </div>
                {picked.status === 'open' && (
                  <button
                    onClick={() => handleClose(picked.id)}
                    disabled={busyId === picked.id}
                    className="px-4 py-2 rounded-lg text-sm font-semibold bg-rose-600 hover:bg-rose-500 text-white disabled:opacity-50"
                  >
                    {busyId === picked.id ? 'Closing…' : 'Close now'}
                  </button>
                )}
              </section>
            )}

            <CandleChart
              candles={picked.candles || []}
              trade={{
                entry: picked.entry,
                stop_loss: picked.stop_loss,
                take_profit_1: picked.take_profit_1,
                take_profit_2: picked.take_profit_2,
                take_profit_3: picked.take_profit_3,
              }}
              height={340}
            />
          </>
        )}
      </main>
    </div>
  )
}

function PatternLibrary() {
  const [patterns, setPatterns] = useState([])
  const [selected, setSelected] = useState(null)
  useEffect(() => {
    fetchPatterns().then((list) => {
      setPatterns(list)
      setSelected(list[0] || null)
    }).catch(() => {})
  }, [])
  return (
    <div className="flex-1 min-h-0 flex flex-col md:flex-row">
      <aside className="w-full md:w-72 max-h-[40vh] md:max-h-none shrink-0 border-b md:border-b-0 md:border-r border-xtinex-line bg-xtinex-void overflow-y-auto p-3 space-y-2">
        {patterns.map((p) => (
          <button key={p.key} onClick={() => setSelected(p)} className={`w-full text-left p-3 rounded-xl border text-sm ${
            selected?.key === p.key ? 'bg-xora-700 border-xtinex-gold/70' : 'bg-xtinex-ink/80 border-xtinex-line'
          }`}>{p.name}</button>
        ))}
      </aside>
      <main className="flex-1 bg-xtinex-black p-4 sm:p-6 overflow-y-auto">
        {selected ? <><h2 className="text-xl font-display font-semibold tracking-wide text-xtinex-gold mb-2">{selected.name}</h2><p className="text-sm text-xtinex-muted">{selected.overview}</p></> : null}
      </main>
    </div>
  )
}

export default function App() {
  const [tab, setTab] = useState('opportunities')
  const [health, setHealth] = useState(null)
  const [autoTrade, setAutoTrade] = useState(false)

  useEffect(() => {
    fetchHealth().then(setHealth).catch(() => setHealth(null))
    fetchSettings().then((s) => setAutoTrade(!!s.auto_trade)).catch(() => {})
    const t = setInterval(() => {
      fetchHealth().then(setHealth).catch(() => setHealth(null))
    }, 8000)
    return () => clearInterval(t)
  }, [])

  async function handleToggleAuto(on) {
    setAutoTrade(on)
    try {
      await updateSettings({ auto_trade: on })
    } catch {
      setAutoTrade(!on)
    }
  }

  return (
    <div className="h-full flex flex-col bg-xtinex-black text-xtinex-fg font-body">
      <header className="shrink-0 border-b border-xtinex-line bg-xtinex-void/95 backdrop-blur px-3 sm:px-5 py-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 flex-wrap items-center gap-3 sm:gap-4">
          <div>
            <div className="font-display font-semibold text-sm tracking-wide">XORA Chart AI</div>
            <div className="text-[10px] text-xtinex-gold font-display tracking-[0.18em] border-b-2 border-xtinex-gold/20 pb-1">XORA BY XTINEX</div>
            <div className="text-[11px] text-slate-500">Live scan · demo trades</div>
          </div>
          <nav className="flex gap-1 overflow-x-auto" aria-label="Primary navigation">
            {[
              ['opportunities', 'Opportunities'],
              ['trades', 'Trades'],
              ['library', 'Patterns'],
            ].map(([id, label]) => (
              <button
                key={id}
                onClick={() => setTab(id)}
                className={`px-3 py-1.5 rounded-md text-xs font-medium ${
                  tab === id ? 'bg-blue-600 text-white' : 'text-slate-400 hover:bg-xora-800'
                }`}
              >{label}</button>
            ))}
          </nav>
        </div>
        <div className={`text-[11px] px-2.5 py-1 rounded-full ${health ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'}`}>
          {health ? `API · ${health.opportunities_cached ?? 0} coins · ${health.positions_open ?? 0} open` : 'API offline'}
        </div>
      </header>
      {tab === 'opportunities' && <OpportunityBoard autoTrade={autoTrade} onToggleAuto={handleToggleAuto} />}
      {tab === 'trades' && <TradesPanel />}
      {tab === 'library' && <PatternLibrary />}
    </div>
  )
}
