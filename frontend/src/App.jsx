import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  analyzeSymbol,
  closeTrade,
  fetchHealth,
  fetchOpportunities,
  fetchPatterns,
  fetchPositions,
  fetchScanPlan,
  fetchSettings,
  fetchTradeSummary,
  openDemoTrade,
  runCycle,
  updateSettings,
} from './api'
import CandleChart from './CandleChart'
import PatternVisual from './PatternVisual'

const NAV_ITEMS = [
  ['scan', 'Scan', 'scan'],
  ['active', 'Active', 'pulse'],
  ['history', 'History', 'history'],
  ['knowledge', 'Knowledge', 'book'],
  ['settings', 'Settings', 'settings'],
]

const SCAN_GROUPS = [
  { id: 'gainers', label: 'Top Gainers', accent: 'emerald', sources: ['gainer', 'ws-price-gainer'] },
  { id: 'losers', label: 'Top Losers', accent: 'rose', sources: ['loser', 'ws-price-loser'] },
  { id: 'movers', label: 'Top Movers', accent: 'violet', sources: ['trending', 'ws-price-trending'] },
  { id: 'volume', label: '24h Volume', accent: 'cyan', sources: ['volume', 'book-liquidity'] },
]

function cx(...items) { return items.filter(Boolean).join(' ') }

function Icon({ name, size = 18 }) {
  const paths = {
    scan: <><circle cx="11" cy="11" r="6"/><path d="m16 16 4 4"/><path d="M8 11h6M11 8v6"/></>,
    pulse: <><path d="M3 12h4l2-5 4 10 2-5h6"/><path d="M4 4h16v16H4z" opacity=".18"/></>,
    history: <><path d="M4 12a8 8 0 1 0 2-5.3"/><path d="M4 4v5h5"/><path d="M12 8v5l3 2"/></>,
    book: <><path d="M4 5.5A3.5 3.5 0 0 1 7.5 2H11v17H7.5A3.5 3.5 0 0 0 4 22z"/><path d="M20 5.5A3.5 3.5 0 0 0 16.5 2H13v17h3.5A3.5 3.5 0 0 1 20 22z"/></>,
    settings: <><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06-2.83 2.83-.06-.06A1.7 1.7 0 0 0 15 19.4a1.7 1.7 0 0 0-1 .6 1.7 1.7 0 0 0-.4 1.1V21h-4v-.1A1.7 1.7 0 0 0 8.6 19.4a1.7 1.7 0 0 0-1.88.34l-.06.06-2.83-2.83.06-.06A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-.6-1 1.7 1.7 0 0 0-1.1-.4H3v-4h.1A1.7 1.7 0 0 0 4.6 8.6a1.7 1.7 0 0 0-.34-1.88l-.06-.06 2.83-2.83.06.06A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-.6 1.7 1.7 0 0 0 .4-1.1V3h4v.1A1.7 1.7 0 0 0 15.4 4.6a1.7 1.7 0 0 0 1.88-.34l.06-.06 2.83 2.83-.06.06A1.7 1.7 0 0 0 19.4 9c.14.36.35.7.6 1 .28.3.66.48 1.1.5h.1v4h-.1A1.7 1.7 0 0 0 19.4 15z"/></>,
    chart: <><path d="M4 19V9M9 15V5M14 19v-7M19 19V3"/><path d="M3 21h18"/></>,
    arrow: <><path d="M5 12h14"/><path d="m14 7 5 5-5 5"/></>,
    back: <><path d="M19 12H5"/><path d="m10 7-5 5 5 5"/></>,
    target: <><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/><path d="M12 2v3M22 12h-3M12 22v-3M2 12h3"/></>,
    shield: <><path d="M12 3 5 6v5c0 5 3 8 7 10 4-2 7-5 7-10V6z"/><path d="m9 12 2 2 4-5"/></>,
    refresh: <><path d="M20 6v5h-5"/><path d="M4 18v-5h5"/><path d="M18 9a7 7 0 0 0-12-2M6 15a7 7 0 0 0 12 2"/></>,
  }
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name] || paths.chart}</svg>
}

function Brand() {
  return (
    <div className="flex items-center gap-3">
      <div className="xora-brand-mark" />
      <div>
        <div className="flex items-baseline gap-2">
          <span className="text-[16px] font-black tracking-[.2em] text-white">XORA</span>
          <span className="text-[10px] font-semibold tracking-[.14em] text-cyan-300">CHART AI</span>
        </div>
        <div className="text-[9px] uppercase tracking-[.16em] text-slate-600">Pattern intelligence</div>
      </div>
    </div>
  )
}

function Badge({ children, tone = 'neutral' }) {
  const tones = {
    neutral: 'border-slate-600/45 bg-slate-700/20 text-slate-300',
    bull: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300',
    bear: 'border-rose-500/30 bg-rose-500/10 text-rose-300',
    info: 'border-cyan-400/25 bg-cyan-400/10 text-cyan-200',
    violet: 'border-violet-400/25 bg-violet-500/10 text-violet-200',
    wait: 'border-amber-500/30 bg-amber-500/10 text-amber-300',
    reject: 'border-rose-500/30 bg-rose-500/10 text-rose-300',
    approve: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300',
  }
  return <span className={cx('inline-flex items-center rounded-full border px-2.5 py-1 text-[9px] font-bold uppercase tracking-[.12em]', tones[tone] || tones.neutral)}>{children}</span>
}

function fmt(n, d = 4) {
  if (n == null || Number.isNaN(Number(n))) return '—'
  const v = Number(n)
  if (Math.abs(v) >= 1000) return v.toLocaleString(undefined, { maximumFractionDigits: 2 })
  if (Math.abs(v) >= 1) return v.toFixed(Math.min(d, 4))
  return v.toFixed(Math.min(d, 6))
}

function fmtPct(n) {
  if (n == null || Number.isNaN(Number(n))) return '—'
  const v = Number(n)
  return `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`
}

function fmtVolume(n) {
  const v = Number(n || 0)
  if (!v) return '—'
  if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`
  if (v >= 1e6) return `$${(v / 1e6).toFixed(1)}M`
  if (v >= 1e3) return `$${(v / 1e3).toFixed(1)}K`
  return `$${v.toFixed(0)}`
}

function decisionTone(action) {
  if (action === 'APPROVE') return 'approve'
  if (action === 'WAIT') return 'wait'
  if (action === 'REJECT') return 'reject'
  return 'neutral'
}

function pnlClass(n) { return Number(n || 0) >= 0 ? 'text-emerald-300' : 'text-rose-300' }

function sourceLabel(source) {
  const labels = {
    gainer: 'Gainer', 'ws-price-gainer': 'Gainer',
    loser: 'Loser', 'ws-price-loser': 'Loser',
    trending: 'Mover', 'ws-price-trending': 'Mover',
    volume: '24h volume', 'book-liquidity': 'Liquidity',
    'ws-price-watchlist': 'Discovery fill',
  }
  return labels[source] || source || 'Discovery'
}

function buildBuckets(coins = []) {
  const unique = []
  const seen = new Set()
  for (const coin of coins) {
    const symbol = String(coin?.symbol || '').toUpperCase()
    if (!symbol || seen.has(symbol)) continue
    seen.add(symbol)
    unique.push({ ...coin, symbol })
  }

  const used = new Set()
  const buckets = {}
  for (const group of SCAN_GROUPS) {
    buckets[group.id] = unique.filter((coin) => group.sources.includes(coin.source)).slice(0, 5)
    buckets[group.id].forEach((coin) => used.add(coin.symbol))
  }

  const pool = unique.filter((coin) => !used.has(coin.symbol))
  for (const group of SCAN_GROUPS) {
    while (buckets[group.id].length < 5 && pool.length) {
      const fill = pool.shift()
      buckets[group.id].push({ ...fill, display_fill: true })
      used.add(fill.symbol)
    }
  }
  return { buckets, total: used.size, sourceTotal: unique.length }
}

function PageHeading({ eyebrow, title, description, actions }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div className="max-w-3xl">
        <div className="text-[10px] font-bold uppercase tracking-[.24em] text-cyan-300">{eyebrow}</div>
        <h1 className="mt-2 text-2xl font-bold tracking-tight text-white sm:text-3xl">{title}</h1>
        {description && <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  )
}

function MetricCard({ label, value, detail, tone = 'blue' }) {
  return (
    <div className={`metric-card metric-${tone}`}>
      <div className="text-[9px] font-semibold uppercase tracking-[.18em] text-slate-500">{label}</div>
      <div className="mt-2 text-2xl font-bold tracking-tight text-white">{value}</div>
      {detail && <div className="mt-1 text-[11px] text-slate-500">{detail}</div>}
    </div>
  )
}

function ScanCoinCard({ coin, opportunity, group, onReview, busy }) {
  const match = opportunity?.best_match
  const positive = Number(coin.price_change_pct || 0) >= 0
  return (
    <button onClick={() => onReview(coin, opportunity)} disabled={busy} className="scan-coin-card group text-left disabled:opacity-60">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full border border-white/10 bg-white/[.04] text-[10px] font-black text-slate-300">{coin.symbol?.slice(0, 2)}</span>
            <div>
              <div className="truncate text-sm font-bold text-white">{coin.symbol}</div>
              <div className="mt-0.5 text-[9px] uppercase tracking-[.12em] text-slate-600">{coin.display_fill ? 'Unique discovery fill' : sourceLabel(coin.source)}</div>
            </div>
          </div>
        </div>
        <div className="text-right">
          <div className={cx('font-mono text-xs font-semibold', positive ? 'text-emerald-300' : 'text-rose-300')}>{fmtPct(coin.price_change_pct)}</div>
          <div className="mt-1 text-[9px] text-slate-600">{fmtVolume(coin.quote_volume)}</div>
        </div>
      </div>
      <div className="mt-3 flex items-center justify-between gap-2 border-t border-white/[.05] pt-2.5">
        {match ? (
          <div className="min-w-0">
            <div className="truncate text-[10px] font-semibold text-slate-300">{match.pattern_name}</div>
            <div className="mt-0.5 text-[9px] text-cyan-300">match {fmt(match.reference_similarity ?? match.similarity, 0)}%</div>
          </div>
        ) : <span className="text-[10px] text-slate-600">Open full analysis</span>}
        <span className={`rounded-lg border px-2 py-1 text-[9px] font-bold uppercase tracking-[.1em] ${group.accent === 'emerald' ? 'border-emerald-500/20 text-emerald-300' : group.accent === 'rose' ? 'border-rose-500/20 text-rose-300' : group.accent === 'violet' ? 'border-violet-500/20 text-violet-300' : 'border-cyan-500/20 text-cyan-300'}`}>
          {busy ? 'Analyzing' : 'Review'}
        </span>
      </div>
    </button>
  )
}

function ScanPage({ health, onReview }) {
  const [plan, setPlan] = useState(null)
  const [opps, setOpps] = useState([])
  const [loading, setLoading] = useState(true)
  const [scanning, setScanning] = useState(false)
  const [busySymbol, setBusySymbol] = useState(null)
  const [manual, setManual] = useState('')
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    try {
      const [nextPlan, nextOpps] = await Promise.all([fetchScanPlan(), fetchOpportunities(60)])
      setPlan(nextPlan)
      setOpps(nextOpps || [])
      setError(null)
    } catch (e) {
      setError(e.message || 'Could not load market scan')
    } finally { setLoading(false) }
  }, [])

  useEffect(() => { load(); const timer = setInterval(load, 12000); return () => clearInterval(timer) }, [load])

  const oppMap = useMemo(() => Object.fromEntries((opps || []).map((o) => [o.symbol, o])), [opps])
  const { buckets, total, sourceTotal } = useMemo(() => buildBuckets(plan?.coins || []), [plan])
  const matched = opps.filter((o) => o.best_match)
  const approved = opps.filter((o) => o.decision?.action === 'APPROVE')
  const avgMatch = matched.length ? matched.reduce((sum, o) => sum + Number(o.best_match?.reference_similarity ?? o.best_match?.similarity ?? 0), 0) / matched.length : 0

  async function handleScan() {
    setScanning(true); setError(null)
    try { await runCycle(); await load() } catch (e) { setError(e.message || 'Market scan failed') } finally { setScanning(false) }
  }

  async function handleReview(coin, cached) {
    setBusySymbol(coin.symbol); setError(null)
    try {
      const opp = cached || await analyzeSymbol(coin.symbol)
      onReview(opp)
    } catch (e) { setError(e.message || `Could not analyze ${coin.symbol}`) } finally { setBusySymbol(null) }
  }

  async function handleManual(e) {
    e.preventDefault()
    if (!manual.trim()) return
    const symbol = manual.trim().toUpperCase()
    setBusySymbol(symbol); setError(null)
    try { onReview(await analyzeSymbol(symbol)); setManual('') } catch (e) { setError(e.message || 'Symbol analysis failed') } finally { setBusySymbol(null) }
  }

  return (
    <div className="page-scroll">
      <div className="mx-auto max-w-[1540px] space-y-5 p-4 sm:p-6 lg:p-8">
        <PageHeading eyebrow="Market discovery" title="20-Coin Intelligence Scan" description="Four discovery cohorts, one unique universe. XORA keeps pattern matching, analysis, decision and execution logic on the backend and gives you a focused review workflow here." actions={<button onClick={handleScan} disabled={scanning} className="btn-primary"><Icon name="refresh" size={15}/>{scanning ? 'Scanning…' : 'Run new scan'}</button>} />

        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <MetricCard label="Unique universe" value={loading ? '—' : `${total || sourceTotal}/20`} detail="No duplicate symbols" tone="cyan" />
          <MetricCard label="Matched patterns" value={matched.length} detail="Current opportunity cache" tone="violet" />
          <MetricCard label="Approved setups" value={approved.length} detail="Decision engine APPROVE" tone="green" />
          <MetricCard label="Avg. chart match" value={avgMatch ? `${avgMatch.toFixed(0)}%` : '—'} detail="Reference similarity" tone="blue" />
          <MetricCard label="Feed readiness" value={health?.market_live ? 'LIVE' : health?.ws_connected ? 'WARMING' : 'OFFLINE'} detail={`${health?.ws_ready_symbols || 0} symbols ready`} tone={health?.market_live ? 'green' : 'amber'} />
        </div>

        <section className="xora-panel overflow-hidden rounded-2xl">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/[.06] px-4 py-4 sm:px-5">
            <div>
              <div className="text-sm font-bold text-white">Discovery cohorts</div>
              <div className="mt-1 text-[11px] text-slate-500">5 gainers · 5 losers · 5 movers · 5 volume candidates · globally unique</div>
            </div>
            <form onSubmit={handleManual} className="flex w-full gap-2 sm:w-auto">
              <input value={manual} onChange={(e) => setManual(e.target.value)} placeholder="Analyze BTCUSDT" className="input-field min-w-0 flex-1 sm:w-48" />
              <button className="btn-secondary" disabled={!manual.trim() || !!busySymbol}>Analyze</button>
            </form>
          </div>
          {error && <div className="mx-4 mt-4 rounded-xl border border-rose-500/20 bg-rose-500/10 px-3 py-2 text-xs text-rose-200 sm:mx-5">{error}</div>}
          <div className="grid gap-3 p-4 md:grid-cols-2 2xl:grid-cols-4 sm:p-5">
            {SCAN_GROUPS.map((group) => (
              <div key={group.id} className={`scan-group scan-group-${group.accent}`}>
                <div className="mb-3 flex items-center justify-between">
                  <div>
                    <div className="text-xs font-bold text-white">{group.label}</div>
                    <div className="mt-0.5 text-[9px] uppercase tracking-[.14em] text-slate-600">{buckets[group.id]?.length || 0}/5 unique</div>
                  </div>
                  <span className={`h-2 w-2 rounded-full ${group.accent === 'emerald' ? 'bg-emerald-400' : group.accent === 'rose' ? 'bg-rose-400' : group.accent === 'violet' ? 'bg-violet-400' : 'bg-cyan-400'}`} />
                </div>
                <div className="space-y-2">
                  {(buckets[group.id] || []).map((coin) => <ScanCoinCard key={coin.symbol} coin={coin} opportunity={oppMap[coin.symbol]} group={group} onReview={handleReview} busy={busySymbol === coin.symbol} />)}
                  {!loading && !(buckets[group.id] || []).length && <div className="rounded-xl border border-dashed border-white/10 p-5 text-center text-xs text-slate-600">Waiting for this discovery source.</div>}
                </div>
              </div>
            ))}
          </div>
          <div className="border-t border-white/[.06] px-4 py-3 text-[10px] leading-5 text-slate-500 sm:px-5">
            Source overlap is never duplicated. If the backend returns a unique fallback symbol to complete the 20-coin universe, XORA marks it as <span className="text-slate-300">Discovery fill</span> instead of mislabeling its ranking source.
          </div>
        </section>

        <section className="xora-panel rounded-2xl p-4 sm:p-5">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div><div className="text-sm font-bold text-white">Matched coins ready for review</div><div className="mt-1 text-[11px] text-slate-500">Click a result to inspect the chart overlay, market evidence, decision and trade plan.</div></div>
            <Badge tone="info">{matched.length} matches</Badge>
          </div>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {matched.slice(0, 6).map((opp) => (
              <button key={opp.id || opp.symbol} onClick={() => onReview(opp)} className="matched-card text-left">
                <div className="flex items-start justify-between gap-3">
                  <div><div className="text-sm font-bold text-white">{opp.symbol}</div><div className="mt-1 text-[11px] text-slate-400">{opp.best_match?.pattern_name}</div></div>
                  <Badge tone={opp.decision?.action === 'APPROVE' ? 'approve' : opp.decision?.action === 'REJECT' ? 'reject' : 'wait'}>{opp.decision?.action || opp.status}</Badge>
                </div>
                <div className="mt-3 flex items-center justify-between border-t border-white/[.05] pt-3 text-[10px]"><span className="text-slate-500">Reference match</span><span className="font-mono font-semibold text-cyan-300">{fmt(opp.best_match?.reference_similarity ?? opp.best_match?.similarity, 0)}%</span></div>
              </button>
            ))}
            {!matched.length && <div className="col-span-full rounded-xl border border-dashed border-white/10 p-7 text-center text-sm text-slate-600">No pattern matches cached yet. Run a market scan to populate this review queue.</div>}
          </div>
        </section>
      </div>
    </div>
  )
}

function CoinReviewPage({ opp, health, onBack, onKnowledge, onTraded }) {
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState(null)
  if (!opp) return <div className="page-scroll grid place-items-center p-8 text-slate-500">Select a coin from Scan to review it.</div>
  const match = opp.best_match || {}
  const market = opp.market_analysis
  const decision = opp.decision
  const trade = opp.trade || {}
  const analysis = opp.analysis || {}
  const canTrade = !!trade.entry && decision?.action === 'APPROVE' && !!match.reference_verified && !!match.matched_example && opp.status !== 'traded'

  async function openPosition() {
    setBusy(true); setMessage(null)
    try { const pos = await openDemoTrade(opp.id); setMessage(`Demo position opened for ${pos.symbol}`); onTraded?.() } catch (e) { setMessage(e.message || 'Could not open position') } finally { setBusy(false) }
  }

  return (
    <div className="page-scroll">
      <div className="mx-auto max-w-[1500px] space-y-4 p-4 sm:p-6 lg:p-8">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <button onClick={onBack} className="icon-btn mt-1"><Icon name="back"/></button>
            <div>
              <div className="flex flex-wrap items-center gap-2"><h1 className="text-2xl font-bold text-white sm:text-3xl">{opp.symbol}</h1>{trade.side && <Badge tone={trade.side === 'BUY' ? 'bull' : 'bear'}>{trade.side}</Badge>}{decision?.action && <Badge tone={decisionTone(decision.action)}>{decision.action}</Badge>}</div>
              <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500"><span>Live {fmt(opp.last_price)}</span><span>{match.pattern_name || 'No catalog match'}</span><span>Reference {fmt(match.reference_similarity ?? match.similarity, 0)}%</span></div>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {match.pattern_key && <button onClick={() => onKnowledge(match.pattern_key)} className="btn-secondary"><Icon name="book" size={15}/>View in Knowledge</button>}
            {canTrade && <button onClick={openPosition} disabled={busy} className="btn-primary"><Icon name="target" size={15}/>{busy ? 'Opening…' : 'Open demo trade'}</button>}
          </div>
        </div>

        {message && <div className="rounded-xl border border-cyan-500/20 bg-cyan-500/10 px-4 py-3 text-xs text-cyan-100">{message}</div>}

        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.7fr)_minmax(330px,.7fr)]">
          <div className="space-y-4">
            <section className="xora-panel overflow-hidden rounded-2xl">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/[.06] px-4 py-3"><div><div className="text-xs font-bold text-white">Live chart + matched structure</div><div className="mt-1 text-[10px] text-slate-500">Dashed pattern geometry is rendered over the same candle window used by XORA analysis.</div></div><Badge tone="violet">{match.pattern_name || 'Structure review'}</Badge></div>
              <CandleChart candles={opp.candles || []} trade={opp.trade} overlays={analysis.chart_overlays} height={430} />
            </section>

            {market && <section className="xora-panel rounded-2xl p-4 sm:p-5">
              <div className="mb-4 flex flex-wrap items-center justify-between gap-3"><div><div className="text-[9px] font-bold uppercase tracking-[.2em] text-slate-600">Market analytics</div><div className="mt-2 flex gap-2"><Badge tone={market.bias === 'bullish' ? 'bull' : market.bias === 'bearish' ? 'bear' : 'neutral'}>{market.bias}</Badge><Badge tone="info">{market.regime}</Badge></div></div><div className="text-right"><div className="font-mono text-2xl font-bold text-cyan-200">{fmt(market.score, 0)}<span className="text-xs text-slate-600">/100</span></div><div className="text-[9px] uppercase tracking-[.14em] text-slate-600">evidence score</div></div></div>
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{(market.signals || []).map((signal) => <div key={signal.name} className="analytics-card"><div className="flex justify-between gap-3 text-[10px]"><span className="text-slate-400">{signal.name}</span><span className="font-mono text-slate-300">{fmt(signal.score, 0)} · {signal.status}</span></div><div className="mt-2 h-1 overflow-hidden rounded-full bg-white/[.05]"><div className="h-full rounded-full bg-cyan-400" style={{ width: `${Math.max(2, Math.min(100, Number(signal.score || 0)))}%` }} /></div></div>)}</div>
            </section>}

            {analysis.summary && <section className="xora-panel rounded-2xl p-5"><div className="text-[9px] font-bold uppercase tracking-[.2em] text-slate-600">AI chart explanation</div><p className="mt-3 whitespace-pre-line text-sm leading-7 text-slate-300">{analysis.summary}</p></section>}
          </div>

          <aside className="space-y-4">
            <section className="xora-panel rounded-2xl p-4 sm:p-5">
              <div className="flex items-center justify-between"><div><div className="text-[9px] font-bold uppercase tracking-[.2em] text-slate-600">Matched pattern</div><h2 className="mt-2 text-lg font-bold text-white">{match.pattern_name || 'No catalog match'}</h2></div><div className="font-mono text-xl font-bold text-violet-300">{fmt(match.reference_similarity ?? match.similarity, 0)}%</div></div>
              {match.pattern_key && <div className="mt-4 overflow-hidden rounded-xl border border-violet-400/15 bg-violet-500/[.04]"><PatternVisual patternKey={match.pattern_key} direction={match.direction} compact /></div>}
              {(opp.all_matches || []).length > 1 && <div className="mt-4"><div className="mb-2 text-[9px] uppercase tracking-[.14em] text-slate-600">Other candidate matches</div><div className="flex flex-wrap gap-2">{opp.all_matches.slice(1, 5).map((m) => <span key={`${m.pattern_key}-${m.similarity}`} className="rounded-lg border border-white/[.07] px-2 py-1 text-[10px] text-slate-400">{m.pattern_name} · {fmt(m.reference_similarity ?? m.similarity, 0)}%</span>)}</div></div>}
              {match.pattern_key && <button onClick={() => onKnowledge(match.pattern_key)} className="mt-4 flex w-full items-center justify-between rounded-xl border border-violet-400/20 bg-violet-500/10 px-3 py-2.5 text-xs font-semibold text-violet-200 hover:bg-violet-500/15"><span>Open pattern guide</span><Icon name="arrow" size={15}/></button>}
            </section>

            <section className="xora-panel rounded-2xl p-4 sm:p-5">
              <div className="text-[9px] font-bold uppercase tracking-[.2em] text-slate-600">Decision engine</div>
              <div className="mt-3 flex items-center gap-2">{decision?.action ? <Badge tone={decisionTone(decision.action)}>{decision.action}</Badge> : <Badge>No decision</Badge>}<span className="text-[10px] text-slate-600">{health?.trade_mode || 'demo'} mode</span></div>
              <p className="mt-3 text-sm leading-6 text-slate-300">{decision?.reason || opp.ai_rationale || 'No trade decision on this structure.'}</p>
            </section>

            <section className="xora-panel rounded-2xl p-4 sm:p-5">
              <div className="text-[9px] font-bold uppercase tracking-[.2em] text-slate-600">Trade plan</div>
              <div className="mt-3 grid grid-cols-2 gap-2">{[
                ['Entry', trade.entry, 'text-blue-200'], ['Stop loss', trade.stop_loss, 'text-rose-300'], ['Target 1', trade.take_profit_1, 'text-emerald-300'], ['Target 2', trade.take_profit_2, 'text-emerald-300'], ['Target 3', trade.take_profit_3, 'text-emerald-300'], ['Risk : reward', trade.risk_reward, 'text-cyan-200'],
              ].map(([label, value, cls]) => <div key={label} className="rounded-xl border border-white/[.06] bg-black/10 p-3"><div className="text-[8px] uppercase tracking-[.12em] text-slate-600">{label}</div><div className={cx('mt-1 font-mono text-xs font-semibold', cls)}>{fmt(value)}</div></div>)}</div>
            </section>
          </aside>
        </div>
      </div>
    </div>
  )
}

function PositionsPage({ mode = 'open' }) {
  const [positions, setPositions] = useState([])
  const [summary, setSummary] = useState(null)
  const [picked, setPicked] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(null)

  const load = useCallback(async () => {
    try {
      const [items, stats] = await Promise.all([fetchPositions(mode), fetchTradeSummary()])
      setPositions(items || []); setSummary(stats); setPicked((prev) => (items || []).find((p) => p.id === prev?.id) || items?.[0] || null); setError(null)
    } catch (e) { setError(e.message || 'Could not load positions') }
  }, [mode])

  useEffect(() => { load(); const timer = setInterval(load, mode === 'open' ? 5000 : 12000); return () => clearInterval(timer) }, [load, mode])

  async function handleClose(id) {
    setBusy(id)
    try { await closeTrade(id); await load() } catch (e) { setError(e.message || 'Could not close position') } finally { setBusy(null) }
  }

  const active = mode === 'open'
  return (
    <div className="page-scroll">
      <div className="mx-auto max-w-[1500px] space-y-5 p-4 sm:p-6 lg:p-8">
        <PageHeading eyebrow={active ? 'Position guardian' : 'Execution journal'} title={active ? 'Active Trades' : 'Trade History'} description={active ? 'Live demo positions with guardian health, current price, risk levels and manual close controls.' : 'Closed positions separated from live risk so performance review stays clean and auditable.'} />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {active ? <><MetricCard label="Open positions" value={summary?.open_count ?? positions.length} detail="Currently managed" tone="cyan"/><MetricCard label="Unrealized PnL" value={fmt(summary?.open_unrealized_pnl, 2)} detail="USDT" tone={Number(summary?.open_unrealized_pnl || 0) >= 0 ? 'green' : 'red'}/><MetricCard label="Max capacity" value={`${summary?.open_count || 0}/5`} detail="Engine risk cap" tone="violet"/><MetricCard label="Total trades" value={summary?.total_trades ?? '—'} detail="Open + closed" tone="blue"/></> : <><MetricCard label="Closed trades" value={summary?.closed_count ?? positions.length} detail="Journal records" tone="blue"/><MetricCard label="Realized PnL" value={fmt(summary?.total_realized_pnl, 2)} detail="USDT" tone={Number(summary?.total_realized_pnl || 0) >= 0 ? 'green' : 'red'}/><MetricCard label="Win rate" value={`${fmt(summary?.win_rate, 1)}%`} detail={`${summary?.wins || 0} wins · ${summary?.losses || 0} losses`} tone="cyan"/><MetricCard label="Average PnL" value={fmt(summary?.avg_pnl, 2)} detail="Per closed trade" tone="violet"/></>}
        </div>
        {error && <div className="rounded-xl border border-rose-500/20 bg-rose-500/10 px-4 py-3 text-xs text-rose-200">{error}</div>}
        <div className="grid min-h-[560px] gap-4 lg:grid-cols-[360px_minmax(0,1fr)]">
          <section className="xora-panel rounded-2xl p-3">
            <div className="mb-3 flex items-center justify-between px-1"><div className="text-xs font-bold text-white">{active ? 'Open positions' : 'Closed positions'}</div><Badge tone={active ? 'info' : 'neutral'}>{positions.length}</Badge></div>
            <div className="space-y-2">{positions.map((p) => <button key={p.id} onClick={() => setPicked(p)} className={cx('position-row w-full text-left', picked?.id === p.id && 'position-row-active')}><div className="flex items-start justify-between gap-3"><div><div className="text-sm font-bold text-white">{p.symbol}</div><div className="mt-1 text-[10px] text-slate-600">{p.side} · {p.leverage}x · {p.status}</div></div><div className="text-right"><div className={cx('font-mono text-xs font-semibold', pnlClass(active ? p.live_pnl : p.realized_pnl))}>{fmt(active ? p.live_pnl : p.realized_pnl, 2)}</div><div className="mt-1 text-[9px] text-slate-600">{active ? fmt(p.live_price) : p.exit_reason || 'closed'}</div></div></div></button>)}{!positions.length && <div className="rounded-xl border border-dashed border-white/10 p-7 text-center text-xs text-slate-600">{active ? 'No active trades.' : 'No closed trades yet.'}</div>}</div>
          </section>
          <section className="xora-panel rounded-2xl p-4 sm:p-5">
            {!picked ? <div className="grid h-full min-h-[420px] place-items-center text-sm text-slate-600">Select a position to inspect it.</div> : <div className="space-y-4">
              <div className="flex flex-wrap items-start justify-between gap-4"><div><div className="text-[9px] uppercase tracking-[.18em] text-slate-600">{active ? 'Managed position' : 'Closed trade'}</div><div className="mt-1 flex items-center gap-2"><h2 className="text-2xl font-bold text-white">{picked.symbol}</h2><Badge tone={picked.side === 'BUY' ? 'bull' : 'bear'}>{picked.side}</Badge></div><div className="mt-2 text-xs text-slate-500">Entry {fmt(picked.entry)} · {active ? `Live ${fmt(picked.live_price)}` : `Exit ${fmt(picked.exit_price)}`}</div></div><div className="text-right"><div className={cx('font-mono text-2xl font-bold', pnlClass(active ? picked.live_pnl : picked.realized_pnl))}>{fmt(active ? picked.live_pnl : picked.realized_pnl, 2)}</div><div className="text-[9px] uppercase tracking-[.14em] text-slate-600">{active ? 'Unrealized' : 'Realized'} PnL USDT</div></div></div>
              {picked.health && active && <div className="rounded-xl border border-cyan-500/15 bg-cyan-500/[.05] p-4"><div className="flex flex-wrap items-center gap-2"><Badge tone={picked.health.status === 'strong' ? 'approve' : picked.health.status === 'critical' ? 'reject' : 'wait'}>{picked.health.action}</Badge><span className="text-xs text-slate-500">health {picked.health.score}/100 · progress {picked.health.progress_to_tp}</span></div><p className="mt-2 text-sm leading-6 text-slate-300">{picked.health.reason}</p></div>}
              <CandleChart candles={picked.candles || []} trade={{ entry: picked.entry, stop_loss: picked.stop_loss, take_profit_1: picked.take_profit_1, take_profit_2: picked.take_profit_2, take_profit_3: picked.take_profit_3 }} height={330} />
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">{[['Entry', picked.entry], ['Stop', picked.stop_loss], ['TP1', picked.take_profit_1], ['TP2', picked.take_profit_2], ['TP3', picked.take_profit_3], [active ? 'Live' : 'Exit', active ? picked.live_price : picked.exit_price]].map(([label, value]) => <div key={label} className="rounded-xl border border-white/[.06] p-3"><div className="text-[8px] uppercase tracking-[.14em] text-slate-600">{label}</div><div className="mt-1 font-mono text-xs font-semibold text-slate-200">{fmt(value)}</div></div>)}</div>
              {active && <button onClick={() => handleClose(picked.id)} disabled={busy === picked.id} className="btn-danger">{busy === picked.id ? 'Closing…' : 'Close position manually'}</button>}
            </div>}
          </section>
        </div>
      </div>
    </div>
  )
}

function KnowledgePage({ focusKey, onFocusHandled }) {
  const [patterns, setPatterns] = useState([])
  const [selectedKey, setSelectedKey] = useState(focusKey || null)
  const [filter, setFilter] = useState('all')
  const [query, setQuery] = useState('')

  useEffect(() => { fetchPatterns().then((list) => { setPatterns(list || []); setSelectedKey((prev) => prev || list?.[0]?.key || null) }).catch(() => {}) }, [])
  useEffect(() => { if (focusKey) { setSelectedKey(focusKey); onFocusHandled?.() } }, [focusKey, onFocusHandled])
  const selected = patterns.find((p) => p.key === selectedKey) || patterns[0]
  const visible = patterns.filter((p) => (filter === 'all' || p.direction === filter || p.type === filter) && (!query || p.name.toLowerCase().includes(query.toLowerCase())))

  return (
    <div className="page-scroll">
      <div className="mx-auto max-w-[1500px] space-y-5 p-4 sm:p-6 lg:p-8">
        <PageHeading eyebrow="Pattern knowledge" title="10 Visual Pattern Guides" description="The catalog is the educational mirror of XORA’s matcher. Each guide shows structure, confirmation logic, setup rules, volume behaviour and the same pattern key used by detected opportunities." />
        <div className="flex flex-wrap gap-2"><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search pattern" className="input-field w-full sm:w-56" />{['all', 'bullish', 'bearish', 'continuation', 'reversal'].map((id) => <button key={id} onClick={() => setFilter(id)} className={cx('filter-chip', filter === id && 'filter-chip-active')}>{id}</button>)}</div>
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_420px]">
          <section className="grid gap-3 sm:grid-cols-2 2xl:grid-cols-3">{visible.map((pattern) => <button key={pattern.key} onClick={() => setSelectedKey(pattern.key)} className={cx('knowledge-card text-left', selected?.key === pattern.key && 'knowledge-card-active')}><div className="flex items-start justify-between gap-2"><div><div className="text-sm font-bold text-white">{pattern.name}</div><div className="mt-1 flex gap-2"><Badge tone={pattern.direction === 'bullish' ? 'bull' : 'bear'}>{pattern.direction}</Badge><Badge tone="violet">{pattern.type}</Badge></div></div></div><div className="mt-3 overflow-hidden rounded-xl border border-white/[.05] bg-black/10"><PatternVisual patternKey={pattern.key} direction={pattern.direction} compact /></div><p className="mt-3 line-clamp-2 text-[11px] leading-5 text-slate-500">{pattern.overview}</p></button>)}</section>
          <aside className="xora-panel rounded-2xl p-5 xl:sticky xl:top-5 xl:self-start">{selected ? <div><div className="flex flex-wrap items-start justify-between gap-3"><div><div className="text-[9px] uppercase tracking-[.18em] text-cyan-300">Pattern detail</div><h2 className="mt-2 text-2xl font-bold text-white">{selected.name}</h2><div className="mt-2 flex gap-2"><Badge tone={selected.direction === 'bullish' ? 'bull' : 'bear'}>{selected.direction}</Badge><Badge tone="violet">{selected.type}</Badge></div></div><span className="font-mono text-[10px] text-slate-600">{selected.key}</span></div><div className="mt-4 overflow-hidden rounded-xl border border-cyan-400/10 bg-cyan-500/[.025]"><PatternVisual patternKey={selected.key} direction={selected.direction}/></div><p className="mt-4 text-sm leading-6 text-slate-300">{selected.overview}</p><div className="mt-5 grid gap-4">
            <div><div className="section-mini-title">Trading setup</div><div className="mt-2 grid gap-2">{Object.entries(selected.trading_setup || {}).map(([k, v]) => <div key={k} className="flex gap-3 rounded-lg border border-white/[.05] px-3 py-2"><span className="w-20 shrink-0 text-[9px] font-bold uppercase tracking-[.1em] text-slate-600">{k.replace('_', ' ')}</span><span className="text-xs text-slate-300">{v}</span></div>)}</div></div>
            <div><div className="section-mini-title">Key points</div><ul className="mt-2 space-y-2">{(selected.key_points || []).map((item) => <li key={item} className="flex gap-2 text-xs leading-5 text-slate-400"><span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-cyan-400"/>{item}</li>)}</ul></div>
            <div><div className="section-mini-title">Volume behaviour</div><div className="mt-2 flex flex-wrap gap-2">{Object.entries(selected.volume_behaviour || {}).map(([k, v]) => <span key={k} className="rounded-lg border border-white/[.06] bg-white/[.02] px-2.5 py-2 text-[10px] text-slate-400"><strong className="text-slate-300">{k.replaceAll('_', ' ')}</strong> · {v}</span>)}</div></div>
          </div></div> : <div className="text-sm text-slate-600">Loading knowledge…</div>}</aside>
        </div>
      </div>
    </div>
  )
}

function SettingsPage({ health, autoTrade, onAutoTradeChange }) {
  const [settings, setSettings] = useState(null)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState(null)
  const [refreshRate, setRefreshRate] = useState(() => localStorage.getItem('xora_refresh_rate') || 'standard')

  useEffect(() => { fetchSettings().then(setSettings).catch(() => {}) }, [])

  async function patch(next) {
    setSaving(true); setMessage(null)
    try { const updated = await updateSettings(next); setSettings(updated); if ('auto_trade' in next) onAutoTradeChange?.(!!next.auto_trade, false); setMessage('Settings saved') } catch (e) { setMessage(e.message || 'Settings could not be saved') } finally { setSaving(false) }
  }

  function updateRefresh(value) { setRefreshRate(value); localStorage.setItem('xora_refresh_rate', value); setMessage('Interface preference saved on this device') }

  return (
    <div className="page-scroll">
      <div className="mx-auto max-w-5xl space-y-5 p-4 sm:p-6 lg:p-8">
        <PageHeading eyebrow="Configuration" title="Settings" description="Only existing XORA settings are sent to the backend. Interface-only preferences stay local to this browser; no trading logic is duplicated in the frontend." />
        {message && <div className="rounded-xl border border-cyan-500/20 bg-cyan-500/10 px-4 py-3 text-xs text-cyan-100">{message}</div>}
        <div className="grid gap-4 lg:grid-cols-2">
          <section className="xora-panel rounded-2xl p-5"><div className="flex items-center gap-3"><div className="settings-icon"><Icon name="shield"/></div><div><div className="text-sm font-bold text-white">Execution safeguards</div><div className="mt-1 text-[11px] text-slate-500">Backend-owned settings</div></div></div><div className="mt-5 space-y-3">
            <label className="setting-row"><div><div className="text-xs font-semibold text-slate-200">Auto demo execution</div><div className="mt-1 text-[10px] leading-4 text-slate-600">Still requires APPROVE + verified reference match.</div></div><input type="checkbox" checked={!!(settings?.auto_trade ?? autoTrade)} disabled={saving} onChange={(e) => patch({ auto_trade: e.target.checked })} className="h-4 w-4 accent-cyan-400"/></label>
            <div className="setting-row"><div><div className="text-xs font-semibold text-slate-200">Trade mode</div><div className="mt-1 text-[10px] leading-4 text-slate-600">The current engine is demo-first; live adapter remains backend-controlled.</div></div><select value={settings?.trade_mode || health?.trade_mode || 'demo'} disabled={saving} onChange={(e) => patch({ trade_mode: e.target.value })} className="select-field"><option value="demo">Demo</option><option value="live">Live</option></select></div>
          </div></section>
          <section className="xora-panel rounded-2xl p-5"><div className="flex items-center gap-3"><div className="settings-icon"><Icon name="settings"/></div><div><div className="text-sm font-bold text-white">Interface</div><div className="mt-1 text-[11px] text-slate-500">This device only</div></div></div><div className="mt-5"><div className="text-xs font-semibold text-slate-200">Refresh density</div><div className="mt-3 grid grid-cols-3 gap-2">{[['calm', 'Calm'], ['standard', 'Standard'], ['fast', 'Fast']].map(([id, label]) => <button key={id} onClick={() => updateRefresh(id)} className={cx('filter-chip', refreshRate === id && 'filter-chip-active')}>{label}</button>)}</div><p className="mt-3 text-[10px] leading-5 text-slate-600">This preference is reserved for UI polling cadence and does not alter market discovery or trading decisions.</p></div></section>
          <section className="xora-panel rounded-2xl p-5 lg:col-span-2"><div className="text-sm font-bold text-white">System status</div><div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{[['Market feed', health?.market_live ? 'Live' : health?.ws_connected ? 'Warming' : 'Offline'], ['Tickers', health?.ws_tickers ?? '—'], ['Ready symbols', health?.ws_ready_symbols ?? '—'], ['Reference library', `${health?.reference_images ?? '—'} images`]].map(([label, value]) => <div key={label} className="rounded-xl border border-white/[.06] bg-black/10 p-3"><div className="text-[9px] uppercase tracking-[.14em] text-slate-600">{label}</div><div className="mt-1 text-sm font-semibold text-slate-200">{value}</div></div>)}</div></section>
        </div>
      </div>
    </div>
  )
}

export default function App() {
  const [page, setPage] = useState('scan')
  const [reviewOpp, setReviewOpp] = useState(null)
  const [knowledgeKey, setKnowledgeKey] = useState(null)
  const [health, setHealth] = useState(null)
  const [autoTrade, setAutoTrade] = useState(false)

  useEffect(() => {
    const load = () => fetchHealth().then(setHealth).catch(() => setHealth(null))
    load(); fetchSettings().then((s) => setAutoTrade(!!s.auto_trade)).catch(() => {})
    const timer = setInterval(load, 8000)
    return () => clearInterval(timer)
  }, [])

  function openReview(opp) { setReviewOpp(opp); setPage('review') }
  function openKnowledge(key) { setKnowledgeKey(key); setPage('knowledge') }
  async function changeAuto(on, persist = true) { const before = autoTrade; setAutoTrade(on); if (persist) { try { await updateSettings({ auto_trade: on }) } catch { setAutoTrade(before) } } }

  const marketLive = health?.market_live === true
  return (
    <div className="app-shell xora-grid">
      <aside className="desktop-sidebar">
        <div className="px-4 py-5"><Brand /></div>
        <nav className="mt-3 space-y-1 px-3">{NAV_ITEMS.map(([id, label, icon]) => <button key={id} onClick={() => setPage(id)} className={cx('nav-item', (page === id || (page === 'review' && id === 'scan')) && 'nav-item-active')}><Icon name={icon}/><span>{label}</span></button>)}</nav>
        <div className="mt-auto p-3"><div className="rounded-2xl border border-white/[.06] bg-white/[.025] p-3"><div className="flex items-center gap-2"><span className={cx('h-2 w-2 rounded-full', marketLive ? 'bg-emerald-400' : 'bg-amber-400')} /><span className="text-[10px] font-bold uppercase tracking-[.12em] text-slate-400">{marketLive ? 'Market live' : health?.ws_connected ? 'Feed warming' : 'Connecting'}</span></div><div className="mt-2 text-[10px] leading-4 text-slate-600">{health?.ws_tickers || 0} tickers · {health?.ws_ready_symbols || 0} ready</div></div></div>
      </aside>

      <div className="min-w-0 flex flex-1 flex-col">
        <header className="topbar"><div className="mobile-brand"><Brand/></div><div className="hidden md:block"><div className="text-[9px] uppercase tracking-[0.16em] font-display text-xtinex-gold border-b-2 border-xtinex-gold/20 pb-1">XORA BY XTINEX</div><div className="mt-1 text-xs font-semibold text-slate-300">Reference-gated pattern analysis · {health?.trade_mode || 'demo'} execution</div></div><div className="ml-auto flex items-center gap-2"><div className={cx('status-pill', marketLive ? 'status-live' : 'status-warn')}><span className="h-1.5 w-1.5 rounded-full bg-current"/>{marketLive ? 'Market live' : health?.ws_connected ? 'Warming' : 'Offline'}</div><div className="hidden rounded-xl border border-white/[.06] bg-white/[.02] px-3 py-2 text-[10px] text-slate-500 sm:block">Refs <span className="font-mono text-slate-300">{health?.reference_images ?? '—'}</span></div></div></header>

        <main className="min-h-0 flex-1">
          {page === 'scan' && <ScanPage health={health} onReview={openReview}/>} 
          {page === 'review' && <CoinReviewPage opp={reviewOpp} health={health} onBack={() => setPage('scan')} onKnowledge={openKnowledge} onTraded={() => setPage('active')}/>} 
          {page === 'active' && <PositionsPage mode="open"/>}
          {page === 'history' && <PositionsPage mode="closed"/>}
          {page === 'knowledge' && <KnowledgePage focusKey={knowledgeKey} onFocusHandled={() => setKnowledgeKey(null)}/>} 
          {page === 'settings' && <SettingsPage health={health} autoTrade={autoTrade} onAutoTradeChange={changeAuto}/>} 
        </main>
      </div>

      <nav className="mobile-nav">{NAV_ITEMS.map(([id, label, icon]) => <button key={id} onClick={() => setPage(id)} className={cx('mobile-nav-item', (page === id || (page === 'review' && id === 'scan')) && 'mobile-nav-item-active')}><Icon name={icon} size={18}/><span>{label}</span></button>)}</nav>
    </div>
  )
}
