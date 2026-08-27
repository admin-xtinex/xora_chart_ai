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
    neutral: 'border-slate-600/50 bg-slate-700/30 text-slate-300',
    bull: 'border-emerald-500/25 bg-emerald-500/10 text-emerald-300',
    bear: 'border-rose-500/25 bg-rose-500/10 text-rose-300',
    cont: 'border-cyan-400/20 bg-cyan-400/10 text-cyan-200',
    buy: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300',
    sell: 'border-rose-500/30 bg-rose-500/10 text-rose-300',
    approve: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300',
    wait: 'border-amber-500/30 bg-amber-500/10 text-amber-300',
    reject: 'border-rose-500/30 bg-rose-500/10 text-rose-300',
    traded: 'border-blue-500/30 bg-blue-500/10 text-blue-300',
    strong: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300',
    ok: 'border-cyan-400/25 bg-cyan-400/10 text-cyan-200',
    watch: 'border-amber-500/30 bg-amber-500/10 text-amber-300',
    weak: 'border-orange-500/30 bg-orange-500/10 text-orange-300',
    critical: 'border-rose-500/30 bg-rose-500/10 text-rose-300',
    unknown: 'border-slate-600/40 bg-slate-700/20 text-slate-400',
  }
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[.12em] ${tones[tone] || tones.neutral}`}>
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
  return Number(n) >= 0 ? 'text-emerald-300' : 'text-rose-300'
}

function decisionTone(action) {
  if (action === 'APPROVE') return 'approve'
  if (action === 'WAIT') return 'wait'
  if (action === 'REJECT') return 'reject'
  return 'neutral'
}

function uniqueBySymbol(list) {
  const seen = new Set()
  return (list || []).filter((item) => {
    const key = (item.symbol || '').toUpperCase()
    if (!key || seen.has(key)) return false
    seen.add(key)
    return true
  })
}

function Brand() {
  return (
    <div className="flex min-w-0 items-center gap-3">
      <div className="xora-brand-mark shrink-0" aria-hidden="true" />
      <div className="min-w-0">
        <div className="flex items-baseline gap-2">
          <span className="text-[15px] font-extrabold tracking-[.22em] text-white">XORA</span>
          <span className="hidden text-[9px] font-semibold uppercase tracking-[.22em] text-slate-500 sm:inline">by XTINEX</span>
        </div>
        <div className="truncate text-[10px] text-slate-500">AI Futures Co-Pilot · Risk gated</div>
      </div>
    </div>
  )
}

function EmptyState({ health }) {
  const connected = !!health?.ws_connected
  const tickers = Number(health?.ws_tickers || 0)
  const ready = Number(health?.ws_ready_symbols || 0)
  return (
    <div className="flex h-full min-h-[360px] items-center justify-center p-8">
      <div className="max-w-md text-center">
        <div className="mx-auto mb-5 grid h-16 w-16 place-items-center rounded-2xl border border-blue-400/20 bg-blue-500/10 shadow-glow">
          <div className="xora-brand-mark scale-75" />
        </div>
        <div className="text-[10px] font-semibold uppercase tracking-[.28em] text-blue-300">Market intelligence</div>
        <h2 className="mt-2 text-2xl font-semibold tracking-tight text-white">Waiting for a qualified setup</h2>
        <p className="mt-3 text-sm leading-6 text-slate-400">
          XORA filters market noise through live WebSocket data, reference-chart matching and risk gates before surfacing an opportunity.
        </p>
        <div className="mt-6 grid grid-cols-3 gap-2 text-left">
          {[
            ['Feed', connected ? 'Online' : 'Offline'],
            ['Tickers', tickers],
            ['Ready', ready],
          ].map(([label, value]) => (
            <div key={label} className="rounded-xl border border-xora-600/40 bg-xora-900/70 p-3">
              <div className="text-[9px] uppercase tracking-[.18em] text-slate-600">{label}</div>
              <div className="mt-1 text-sm font-semibold text-slate-200">{value}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function OpportunityDetail({ opp, onTraded, health }) {
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState(null)
  if (!opp) return <EmptyState health={health} />

  const t = opp.trade || {}
  const m = opp.best_match || {}
  const a = opp.analysis || {}
  const ma = opp.market_analysis
  const d = opp.decision
  const canTrade = !!t.entry && opp.status !== 'traded' && d?.action === 'APPROVE' && !!m.reference_verified && !!m.matched_example

  async function handleOpen() {
    setBusy(true)
    setMsg(null)
    try {
      const pos = await openDemoTrade(opp.id)
      setMsg(`Demo position opened · ${pos.symbol}`)
      onTraded?.()
    } catch (e) {
      setMsg(e.message || 'Trade could not be opened')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="sticky top-0 z-10 border-b border-xora-600/30 bg-xora-950/85 px-4 py-4 backdrop-blur-xl sm:px-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-2xl font-bold tracking-tight text-white">{opp.symbol}</h2>
              {t.side && <Badge tone={t.side === 'BUY' ? 'buy' : 'sell'}>{t.side}</Badge>}
              {d?.action && <Badge tone={decisionTone(d.action)}>{d.action}</Badge>}
              {opp.status === 'traded' && <Badge tone="traded">Traded</Badge>}
            </div>
            <p className="mt-1 text-xs text-slate-500">
              {m.pattern_name || 'Structure review'} · live {fmt(opp.last_price)} · reference {m.reference_similarity?.toFixed?.(0) ?? m.similarity?.toFixed?.(0) ?? '—'}%
            </p>
          </div>
          <div className="text-right">
            <div className="text-[9px] uppercase tracking-[.2em] text-slate-600">Decision engine</div>
            <div className="mt-1 font-mono text-sm text-blue-200">{ma?.score?.toFixed?.(0) ?? '—'} / 100</div>
          </div>
        </div>
      </div>

      <div className="space-y-4 p-4 sm:p-6">
        {d && (
          <section className="xora-glass rounded-2xl p-4 sm:p-5">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="max-w-3xl">
                <div className="mb-1 text-[9px] font-semibold uppercase tracking-[.2em] text-slate-600">XORA decision</div>
                <p className="text-sm leading-6 text-slate-200">{d.reason}</p>
              </div>
              {canTrade && (
                <button onClick={handleOpen} disabled={busy} className="rounded-xl bg-white px-4 py-2.5 text-xs font-bold text-slate-950 hover:bg-blue-100 disabled:opacity-50">
                  {busy ? 'Opening…' : 'Open demo position'}
                </button>
              )}
            </div>
            {msg && <div className="mt-3 text-xs text-cyan-200">{msg}</div>}
          </section>
        )}

        <section className="grid grid-cols-2 gap-2 md:grid-cols-3 xl:grid-cols-6">
          {[
            ['Entry', t.entry, 'text-blue-200'],
            ['Invalidation', t.stop_loss, 'text-rose-300'],
            ['Target 1', t.take_profit_1, 'text-emerald-300'],
            ['Target 2', t.take_profit_2, 'text-emerald-300'],
            ['Target 3', t.take_profit_3, 'text-emerald-300'],
            ['Risk : reward', t.risk_reward, 'text-cyan-200'],
          ].map(([label, val, cls]) => (
            <div key={label} className="rounded-xl border border-xora-600/35 bg-xora-900/65 p-3">
              <div className="text-[9px] uppercase tracking-[.16em] text-slate-600">{label}</div>
              <div className={`mt-1 font-mono text-sm font-semibold ${cls}`}>{fmt(val)}</div>
            </div>
          ))}
        </section>

        <div className="overflow-hidden rounded-2xl border border-xora-600/35 bg-xora-900/55">
          <CandleChart candles={opp.candles || []} trade={opp.trade} overlays={a.chart_overlays} height={360} />
        </div>

        {ma && (
          <section className="xora-glass rounded-2xl p-4 sm:p-5">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="text-[9px] font-semibold uppercase tracking-[.2em] text-slate-600">Market evidence</div>
                <div className="mt-2 flex gap-2">
                  <Badge tone={ma.bias === 'bullish' ? 'bull' : ma.bias === 'bearish' ? 'bear' : 'neutral'}>{ma.bias}</Badge>
                  <Badge tone="cont">{ma.regime}</Badge>
                </div>
              </div>
              <div className="font-mono text-xl font-semibold text-blue-200">{ma.score?.toFixed?.(0)}<span className="text-xs text-slate-600">/100</span></div>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              {(ma.signals || []).map((s) => (
                <div key={s.name} className="rounded-xl border border-xora-600/30 bg-xora-950/50 p-3">
                  <div className="flex justify-between text-[11px]">
                    <span className="text-slate-400">{s.name}</span>
                    <span className="font-mono text-slate-300">{s.score?.toFixed?.(0)} · {s.status}</span>
                  </div>
                  <div className="mt-2 h-1 overflow-hidden rounded-full bg-xora-800">
                    <div className="h-full rounded-full bg-blue-500" style={{ width: `${Math.min(100, s.score || 0)}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {a.summary && <p className="whitespace-pre-line rounded-2xl border border-xora-600/30 bg-xora-900/45 p-4 text-sm leading-6 text-slate-300">{a.summary}</p>}
      </div>
    </div>
  )
}

function OpportunityBoard({ autoTrade, onToggleAuto, health }) {
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
      setSelected((prev) => list.find((o) => prev && (o.symbol === prev.symbol || o.id === prev.id)) || list[0] || null)
      setError(null)
    } catch (e) {
      setError(e.message || 'Could not load opportunities')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    const timer = setInterval(load, 8000)
    return () => clearInterval(timer)
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
    } catch (e) {
      setError(e.message || 'Symbol analysis failed')
    } finally {
      setAnalyzing(false)
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
      <aside className="flex shrink-0 flex-col border-b border-xora-600/30 bg-xora-900/55 lg:w-[350px] lg:border-b-0 lg:border-r">
        <div className="space-y-3 border-b border-xora-600/30 p-4">
          <div>
            <div className="text-[9px] font-semibold uppercase tracking-[.22em] text-blue-300">Signal desk</div>
            <h1 className="mt-1 text-lg font-semibold tracking-tight text-white">Qualified opportunities</h1>
            <p className="mt-1 text-xs leading-5 text-slate-500">Only setups that survive XORA’s reference and risk gates reach this desk.</p>
          </div>
          <button onClick={handleScan} disabled={scanning} className="w-full rounded-xl bg-blue-600 px-4 py-2.5 text-xs font-bold text-white shadow-glow hover:bg-blue-500 disabled:opacity-50">
            {scanning ? 'Scanning market…' : 'Run market scan'}
          </button>
          <form onSubmit={handleAnalyze} className="flex gap-2">
            <input value={coin} onChange={(e) => setCoin(e.target.value)} placeholder="Analyze BTC or ETHUSDT" className="min-w-0 flex-1 rounded-xl border border-xora-600/40 bg-xora-950/80 px-3 py-2.5 text-xs text-slate-100 outline-none placeholder:text-slate-600 focus:border-blue-500/60" />
            <button type="submit" disabled={analyzing || !coin.trim()} className="rounded-xl border border-blue-400/25 bg-blue-500/10 px-3 text-xs font-semibold text-blue-200 hover:bg-blue-500/20 disabled:opacity-40">
              {analyzing ? '…' : 'Analyze'}
            </button>
          </form>
          <label className={`flex items-center justify-between gap-3 rounded-xl border p-3 ${autoTrade ? 'border-emerald-500/30 bg-emerald-500/8' : 'border-xora-600/35 bg-xora-950/50'}`}>
            <div>
              <div className="text-xs font-semibold text-slate-200">Auto demo execution</div>
              <div className="mt-0.5 text-[10px] text-slate-600">APPROVE + verified chart match only</div>
            </div>
            <input type="checkbox" checked={!!autoTrade} onChange={(e) => onToggleAuto(e.target.checked)} className="accent-blue-500" />
          </label>
        </div>

        <div className="max-h-[280px] flex-1 overflow-y-auto p-3 lg:max-h-none">
          <div className="mb-2 flex items-center justify-between px-1">
            <span className="text-[9px] uppercase tracking-[.18em] text-slate-600">Current desk</span>
            <span className="font-mono text-[10px] text-slate-500">{opps.length} symbols</span>
          </div>
          {loading && <div className="py-8 text-center text-xs text-slate-600">Loading market desk…</div>}
          {error && <div className="mb-2 rounded-xl border border-rose-500/20 bg-rose-500/10 p-3 text-xs text-rose-300">{error}</div>}
          {!loading && opps.length === 0 && <div className="rounded-xl border border-dashed border-xora-600/35 p-5 text-center text-xs leading-5 text-slate-600">No qualified setups yet. XORA will surface them here when market structure is ready.</div>}
          <div className="space-y-2">
            {opps.map((o) => (
              <button key={o.symbol} onClick={() => setSelected(o)} className={`w-full rounded-xl border p-3 text-left ${selected?.symbol === o.symbol ? 'border-blue-500/45 bg-blue-500/10 shadow-glow' : 'border-xora-600/30 bg-xora-950/45 hover:border-xora-600/60 hover:bg-xora-800/60'}`}>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-sm font-bold text-white">{o.symbol}</div>
                    <div className="mt-1 text-[10px] text-slate-600">{o.best_match?.pattern_name || 'Structure review'} · ref {o.best_match?.reference_similarity?.toFixed?.(0) ?? o.best_match?.similarity?.toFixed?.(0) ?? '—'}%</div>
                  </div>
                  <div className="flex flex-wrap justify-end gap-1">
                    {o.trade?.side && <Badge tone={o.trade.side === 'BUY' ? 'buy' : 'sell'}>{o.trade.side}</Badge>}
                    {o.decision?.action && <Badge tone={decisionTone(o.decision.action)}>{o.decision.action}</Badge>}
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>
      </aside>
      <main className="min-w-0 flex-1 bg-xora-950/40">
        <OpportunityDetail opp={selected} onTraded={load} health={health} />
      </main>
    </div>
  )
}

function TradesPanel() {
  const [positions, setPositions] = useState([])
  const [summary, setSummary] = useState(null)
  const [filter, setFilter] = useState('open')
  const [picked, setPicked] = useState(null)
  const [error, setError] = useState(null)
  const [busyId, setBusyId] = useState(null)

  const load = useCallback(async () => {
    try {
      const [pos, sum] = await Promise.all([fetchPositions(filter || undefined), fetchTradeSummary()])
      setPositions(pos)
      setSummary(sum)
      setPicked((prev) => pos.find((p) => prev && p.id === prev.id) || pos[0] || null)
      setError(null)
    } catch (e) {
      setError(e.message)
    }
  }, [filter])

  useEffect(() => {
    load()
    const timer = setInterval(load, 4000)
    return () => clearInterval(timer)
  }, [load])

  async function handleClose(id) {
    setBusyId(id)
    try { await closeTrade(id); await load() } catch (e) { setError(e.message) } finally { setBusyId(null) }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
      <aside className="shrink-0 border-b border-xora-600/30 bg-xora-900/55 lg:w-[420px] lg:border-b-0 lg:border-r">
        <div className="space-y-3 border-b border-xora-600/30 p-4">
          <div className="text-[9px] font-semibold uppercase tracking-[.22em] text-blue-300">Position guardian</div>
          <div className="grid grid-cols-3 gap-2">
            {[
              ['Open PnL', summary?.open_unrealized_pnl, pnlClass(summary?.open_unrealized_pnl)],
              ['Realized', summary?.total_realized_pnl, pnlClass(summary?.total_realized_pnl)],
              ['Win rate', summary?.win_rate, 'text-slate-100'],
            ].map(([label, value, cls]) => <div key={label} className="rounded-xl border border-xora-600/30 bg-xora-950/45 p-3"><div className="text-[9px] uppercase tracking-[.12em] text-slate-600">{label}</div><div className={`mt-1 font-mono text-sm font-semibold ${cls}`}>{fmt(value, 2)}</div></div>)}
          </div>
          <div className="flex gap-1 rounded-xl border border-xora-600/30 bg-xora-950/50 p-1">
            {['open', 'closed', ''].map((f) => <button key={f || 'all'} onClick={() => setFilter(f)} className={`flex-1 rounded-lg py-2 text-[10px] font-semibold uppercase tracking-[.12em] ${filter === f ? 'bg-blue-600 text-white' : 'text-slate-500 hover:bg-xora-800'}`}>{f || 'all'}</button>)}
          </div>
        </div>
        <div className="max-h-[280px] overflow-y-auto p-3 lg:max-h-none lg:h-[calc(100%-180px)]">
          {error && <div className="mb-2 text-xs text-rose-300">{error}</div>}
          {positions.length === 0 && <div className="py-10 text-center text-xs text-slate-600">No positions in this view.</div>}
          <div className="space-y-2">
            {positions.map((p) => <button key={p.id} onClick={() => setPicked(p)} className={`w-full rounded-xl border p-3 text-left ${picked?.id === p.id ? 'border-blue-500/45 bg-blue-500/10' : 'border-xora-600/30 bg-xora-950/45 hover:bg-xora-800/60'}`}><div className="flex justify-between"><div><div className="text-sm font-bold text-white">{p.symbol}</div><div className="mt-1 text-[10px] text-slate-600">{p.side} · {p.leverage}x · {p.status}</div></div><div className="text-right"><div className={`font-mono text-sm ${pnlClass(p.live_pnl)}`}>{fmt(p.live_pnl, 2)}</div><div className="text-[10px] text-slate-600">{fmt(p.live_price)}</div></div></div></button>)}
          </div>
        </div>
      </aside>
      <main className="min-w-0 flex-1 overflow-y-auto p-4 sm:p-6">
        {!picked && <div className="grid h-full min-h-[300px] place-items-center text-sm text-slate-600">Select a position to inspect its guardian state.</div>}
        {picked && <div className="space-y-4"><div className="flex flex-wrap items-start justify-between gap-3"><div><div className="text-[9px] uppercase tracking-[.2em] text-slate-600">Managed position</div><h2 className="mt-1 text-2xl font-bold text-white">{picked.symbol}</h2><p className="mt-1 text-xs text-slate-500">{picked.side} · entry {fmt(picked.entry)} · live {fmt(picked.live_price)}</p></div><div className="text-right"><div className={`font-mono text-2xl font-semibold ${pnlClass(picked.live_pnl)}`}>{fmt(picked.live_pnl, 2)}</div><div className="text-[10px] uppercase tracking-[.16em] text-slate-600">Live PnL USDT</div></div></div>{picked.health && <section className="xora-glass flex flex-wrap items-center justify-between gap-3 rounded-2xl p-4"><div><div className="mb-2 flex gap-2"><Badge tone={picked.health.status}>{picked.health.action}</Badge><span className="text-xs text-slate-500">health {picked.health.score}/100 · R {picked.health.progress_to_tp}</span></div><p className="text-sm text-slate-200">{picked.health.reason}</p></div>{picked.status === 'open' && <button onClick={() => handleClose(picked.id)} disabled={busyId === picked.id} className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-2.5 text-xs font-semibold text-rose-200 hover:bg-rose-500/20 disabled:opacity-50">{busyId === picked.id ? 'Closing…' : 'Close position'}</button>}</section>}<div className="overflow-hidden rounded-2xl border border-xora-600/35 bg-xora-900/55"><CandleChart candles={picked.candles || []} trade={{ entry: picked.entry, stop_loss: picked.stop_loss, take_profit_1: picked.take_profit_1, take_profit_2: picked.take_profit_2, take_profit_3: picked.take_profit_3 }} height={360} /></div></div>}
      </main>
    </div>
  )
}

function PatternLibrary() {
  const [patterns, setPatterns] = useState([])
  const [selected, setSelected] = useState(null)
  useEffect(() => { fetchPatterns().then((list) => { setPatterns(list); setSelected(list[0] || null) }).catch(() => {}) }, [])
  return (
    <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
      <aside className="max-h-[260px] shrink-0 overflow-y-auto border-b border-xora-600/30 bg-xora-900/55 p-3 lg:max-h-none lg:w-80 lg:border-b-0 lg:border-r">
        <div className="px-2 pb-3"><div className="text-[9px] font-semibold uppercase tracking-[.22em] text-blue-300">Reference knowledge</div><p className="mt-1 text-xs leading-5 text-slate-500">Pattern context supports the strategy; it never overrides structure, reference verification or risk gates.</p></div>
        <div className="space-y-2">{patterns.map((p) => <button key={p.key} onClick={() => setSelected(p)} className={`w-full rounded-xl border p-3 text-left text-sm ${selected?.key === p.key ? 'border-blue-500/45 bg-blue-500/10 text-white' : 'border-xora-600/30 bg-xora-950/45 text-slate-400 hover:bg-xora-800/60'}`}>{p.name}</button>)}</div>
      </aside>
      <main className="flex-1 overflow-y-auto p-5 sm:p-8">{selected ? <div className="mx-auto max-w-3xl"><div className="text-[9px] uppercase tracking-[.2em] text-slate-600">Pattern intelligence</div><h2 className="mt-2 text-3xl font-bold tracking-tight text-white">{selected.name}</h2><p className="mt-5 text-sm leading-7 text-slate-300">{selected.overview}</p></div> : null}</main>
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
    const timer = setInterval(() => fetchHealth().then(setHealth).catch(() => setHealth(null)), 8000)
    return () => clearInterval(timer)
  }, [])

  async function handleToggleAuto(on) {
    setAutoTrade(on)
    try { await updateSettings({ auto_trade: on }) } catch { setAutoTrade(!on) }
  }

  const wsHealthy = !!health?.ws_connected && Number(health?.ws_last_message_age_seconds ?? 999) < 30
  const ready = Number(health?.ws_ready_symbols || 0)
  const tickers = Number(health?.ws_tickers || 0)

  return (
    <div className="xora-grid flex h-full flex-col bg-xora-950 text-slate-100">
      <header className="xora-glass z-20 shrink-0 border-x-0 border-t-0 px-3 py-3 sm:px-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-4 sm:gap-6">
            <Brand />
            <nav className="flex rounded-xl border border-xora-600/30 bg-xora-950/55 p-1">
              {[
                ['opportunities', 'Signals'],
                ['trades', 'Positions'],
                ['library', 'Knowledge'],
              ].map(([id, label]) => <button key={id} onClick={() => setTab(id)} className={`rounded-lg px-2.5 py-2 text-[10px] font-semibold uppercase tracking-[.11em] sm:px-3 ${tab === id ? 'bg-blue-600 text-white shadow-glow' : 'text-slate-500 hover:bg-xora-800 hover:text-slate-200'}`}>{label}</button>)}
            </nav>
          </div>

          <div className="flex items-center gap-2">
            <div className="hidden items-center gap-3 rounded-xl border border-xora-600/30 bg-xora-950/50 px-3 py-2 md:flex">
              <div><div className="text-[8px] uppercase tracking-[.16em] text-slate-600">Tickers</div><div className="font-mono text-[11px] text-slate-300">{tickers}</div></div>
              <div className="h-6 w-px bg-xora-600/30" />
              <div><div className="text-[8px] uppercase tracking-[.16em] text-slate-600">Ready</div><div className="font-mono text-[11px] text-slate-300">{ready}</div></div>
              <div className="h-6 w-px bg-xora-600/30" />
              <div><div className="text-[8px] uppercase tracking-[.16em] text-slate-600">Mode</div><div className="text-[11px] font-semibold uppercase text-slate-300">{health?.trade_mode || 'demo'}</div></div>
            </div>
            <div className={`flex items-center gap-2 rounded-full border px-3 py-2 text-[10px] font-semibold uppercase tracking-[.12em] ${wsHealthy ? 'border-emerald-500/25 bg-emerald-500/10 text-emerald-300' : 'border-amber-500/25 bg-amber-500/10 text-amber-300'}`}>
              <span className={`h-1.5 w-1.5 rounded-full ${wsHealthy ? 'bg-emerald-400' : 'bg-amber-400'}`} />
              {wsHealthy ? 'Market live' : health ? 'Warming up' : 'Connecting'}
            </div>
          </div>
        </div>
      </header>

      {tab === 'opportunities' && <OpportunityBoard autoTrade={autoTrade} onToggleAuto={handleToggleAuto} health={health} />}
      {tab === 'trades' && <TradesPanel />}
      {tab === 'library' && <PatternLibrary />}
    </div>
  )
}
