import { useCallback, useEffect, useState } from 'react'
import {
  API_BASE,
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
    rev: 'bg-amber-500/15 text-amber-300 ring-1 ring-amber-500/30',
    buy: 'bg-emerald-500/20 text-emerald-300 ring-1 ring-emerald-500/40',
    sell: 'bg-rose-500/20 text-rose-300 ring-1 ring-rose-500/40',
    phase: 'bg-violet-500/15 text-violet-300 ring-1 ring-violet-500/30',
    approve: 'bg-emerald-500/20 text-emerald-300 ring-1 ring-emerald-500/40',
    wait: 'bg-amber-500/20 text-amber-300 ring-1 ring-amber-500/40',
    reject: 'bg-rose-500/20 text-rose-300 ring-1 ring-rose-500/40',
    traded: 'bg-blue-500/20 text-blue-300 ring-1 ring-blue-500/40',
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

function Section({ title, children, accent }) {
  return (
    <section className={`rounded-xl border p-4 ${
      accent ? 'bg-violet-500/10 border-violet-500/30' : 'bg-xora-800/60 border-xora-600/40'
    }`}>
      <h3 className={`text-xs font-semibold uppercase tracking-wider mb-2 ${
        accent ? 'text-violet-300' : 'text-slate-400'
      }`}>{title}</h3>
      <div className="text-sm text-slate-300 leading-relaxed whitespace-pre-line">{children}</div>
    </section>
  )
}

function decisionTone(action) {
  if (action === 'APPROVE') return 'approve'
  if (action === 'WAIT') return 'wait'
  if (action === 'REJECT') return 'reject'
  return 'neutral'
}

/* ═══════════════════ Opportunities ═══════════════════ */

function OppCard({ opp, selected, onClick }) {
  const side = opp.trade?.side || '—'
  const isBuy = side === 'BUY'
  const sim = opp.best_match?.similarity
  const action = opp.decision?.action
  const anScore = opp.market_analysis?.score
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
        <div className="flex flex-col items-end gap-1">
          <Badge tone={isBuy ? 'buy' : 'sell'}>{side}</Badge>
          {action && <Badge tone={decisionTone(action)}>{action}</Badge>}
        </div>
      </div>
      <div className="flex items-center gap-2 flex-wrap text-[11px]">
        <span className="text-blue-300 font-mono">{sim != null ? `${sim.toFixed(0)}%` : '—'}</span>
        <span className="text-slate-600">·</span>
        <span className="text-violet-300">A {anScore != null ? anScore.toFixed(0) : '—'}</span>
        <span className="text-slate-600">·</span>
        <span className="text-slate-400">RR {opp.trade?.risk_reward ?? '—'}</span>
      </div>
    </button>
  )
}

function OppDetail({ opp, onTraded }) {
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState(null)

  if (!opp) {
    return (
      <div className="h-full flex items-center justify-center text-slate-500">
        <div className="text-center px-6">
          <div className="text-4xl mb-3 opacity-40">🎯</div>
          <p className="text-sm">Select an opportunity or run a scan</p>
        </div>
      </div>
    )
  }

  const t = opp.trade || {}
  const m = opp.best_match || {}
  const a = opp.analysis || {}
  const ma = opp.market_analysis
  const d = opp.decision
  const isBuy = t.side === 'BUY'
  const canTrade = d?.action === 'APPROVE' && opp.status !== 'traded'

  async function handleOpen() {
    setBusy(true)
    setMsg(null)
    try {
      const pos = await openDemoTrade(opp.id)
      setMsg(`Demo opened · ${pos.symbol} · qty ${pos.quantity}`)
      onTraded?.()
    } catch (e) {
      setMsg(e.message || 'Failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="sticky top-0 z-10 bg-xora-900/95 backdrop-blur border-b border-xora-600/40 px-6 py-4">
        <div className="flex items-center gap-3 flex-wrap">
          <h2 className="text-xl font-bold tracking-tight">{opp.symbol}</h2>
          <Badge tone={isBuy ? 'buy' : 'sell'}>{t.side || '—'}</Badge>
          {d?.action && <Badge tone={decisionTone(d.action)}>{d.action}</Badge>}
          {opp.status === 'traded' && <Badge tone="traded">TRADED</Badge>}
          {a.pattern_phase && <Badge tone="phase">{a.pattern_phase}</Badge>}
        </div>
        <p className="text-xs text-slate-500 mt-1">
          {m.pattern_name} · sim {m.similarity?.toFixed?.(1)}% · analysis {ma?.score?.toFixed?.(0) ?? '—'} · rank {opp.rank_score}
        </p>
      </div>

      <div className="p-6 space-y-5">
        {/* Decision + trade action */}
        {d && (
          <section className="rounded-xl border border-xora-600/40 bg-xora-800/60 p-4 space-y-3">
            <div className="flex items-center justify-between gap-3 flex-wrap">
              <div>
                <div className="text-xs uppercase tracking-wider text-slate-400 mb-1">Decision</div>
                <div className="text-sm text-slate-200">{d.reason}</div>
              </div>
              {canTrade && (
                <button
                  onClick={handleOpen}
                  disabled={busy}
                  className="px-4 py-2 rounded-lg text-sm font-semibold bg-emerald-600 hover:bg-emerald-500 text-white disabled:opacity-50"
                >
                  {busy ? 'Opening…' : 'Open demo trade'}
                </button>
              )}
            </div>
            {msg && <div className="text-xs text-sky-300">{msg}</div>}
            {d.confirmations?.length > 0 && (
              <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {d.confirmations.map((c) => (
                  <li key={c.name} className="flex items-start gap-2 text-xs">
                    <span className={c.met ? 'text-emerald-400' : 'text-rose-400'}>{c.met ? '✓' : '✗'}</span>
                    <span className="text-slate-300">
                      <span className="font-medium">{c.name}</span>
                      {c.required ? ' · required' : ''}
                      {c.note ? ` — ${c.note}` : ''}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        )}

        {/* Analysis engine scores */}
        {ma && (
          <section className="rounded-xl border border-xora-600/40 bg-xora-800/60 p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">Analysis Engine</h3>
              <span className="text-sm font-mono text-violet-300">{ma.score?.toFixed?.(0)} / 100</span>
            </div>
            <div className="flex gap-2 flex-wrap text-[11px] mb-3">
              <Badge tone={ma.bias === 'bullish' ? 'bull' : ma.bias === 'bearish' ? 'bear' : 'neutral'}>{ma.bias}</Badge>
              <Badge tone="cont">{ma.regime}</Badge>
            </div>
            <div className="space-y-2">
              {(ma.signals || []).map((s) => (
                <div key={s.name}>
                  <div className="flex justify-between text-[11px] mb-0.5">
                    <span className="text-slate-400">{s.name}</span>
                    <span className={`font-mono ${
                      s.status === 'pass' ? 'text-emerald-400' : s.status === 'fail' ? 'text-rose-400' : 'text-amber-300'
                    }`}>{s.score?.toFixed?.(0)} · {s.status}</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-xora-900 overflow-hidden">
                    <div
                      className={`h-full rounded-full ${
                        s.status === 'pass' ? 'bg-emerald-500' : s.status === 'fail' ? 'bg-rose-500' : 'bg-amber-500'
                      }`}
                      style={{ width: `${Math.min(100, s.score || 0)}%` }}
                    />
                  </div>
                  {s.note && <div className="text-[10px] text-slate-500 mt-0.5">{s.note}</div>}
                </div>
              ))}
            </div>
          </section>
        )}

        <section>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
            Live structure · pattern overlay
          </h3>
          <CandleChart candles={opp.candles || []} trade={opp.trade} overlays={a.chart_overlays} height={380} />
        </section>

        {(a.pattern_phase || a.pattern_phase_detail) && (
          <Section title="Where price is now" accent>
            {a.pattern_phase && <div className="text-base font-semibold text-violet-200 mb-2">{a.pattern_phase}</div>}
            {a.pattern_phase_detail || a.current_area}
          </Section>
        )}

        <section className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          {[
            ['Entry', t.entry, 'text-blue-300'],
            ['SL', t.stop_loss, 'text-rose-300'],
            ['TP1', t.take_profit_1, 'text-emerald-300'],
            ['TP2', t.take_profit_2, 'text-emerald-300'],
            ['TP3', t.take_profit_3, 'text-emerald-300'],
            ['R:R', t.risk_reward, 'text-sky-300'],
          ].map(([label, val, cls]) => (
            <div key={label} className="rounded-lg bg-xora-800 border border-xora-600/50 p-3">
              <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">{label}</div>
              <div className={`text-sm font-mono font-medium ${cls}`}>{fmt(val)}</div>
            </div>
          ))}
        </section>

        {a.summary && <Section title="Pattern analysis">{a.summary}</Section>}
      </div>
    </div>
  )
}

function OpportunityBoard({ autoTrade, onToggleAuto }) {
  const [opps, setOpps] = useState([])
  const [selected, setSelected] = useState(null)
  const [loading, setLoading] = useState(true)
  const [scanning, setScanning] = useState(false)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    setError(null)
    try {
      const list = await fetchOpportunities(40)
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
    const t = setInterval(load, 12000)
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

  return (
    <div className="flex-1 min-h-0 flex">
      <aside className="w-80 shrink-0 border-r border-xora-600/40 bg-xora-900 flex flex-col">
        <div className="p-3 border-b border-xora-600/40 space-y-2">
          <button
            onClick={handleScan}
            disabled={scanning}
            className={`w-full py-2.5 rounded-lg text-sm font-semibold transition
              ${scanning ? 'bg-blue-900/50 text-blue-300 cursor-wait' : 'bg-blue-600 hover:bg-blue-500 text-white'}`}
          >
            {scanning ? 'Scanning…' : 'Run scan now'}
          </button>

          <label className={`flex items-center justify-between gap-2 px-3 py-2 rounded-lg border cursor-pointer
            ${autoTrade ? 'border-emerald-500/40 bg-emerald-500/10' : 'border-xora-600/50 bg-xora-800/50'}`}>
            <div>
              <div className="text-xs font-semibold text-slate-200">Auto demo trades</div>
              <div className="text-[10px] text-slate-500">APPROVE → open automatically</div>
            </div>
            <input
              type="checkbox"
              checked={!!autoTrade}
              onChange={(e) => onToggleAuto(e.target.checked)}
              className="w-4 h-4 accent-emerald-500"
            />
          </label>

          <div className="text-[11px] text-slate-500 text-center">{opps.length} opportunities</div>
        </div>

        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          {loading && <div className="text-center text-slate-500 text-sm py-8">Loading…</div>}
          {error && <div className="text-center text-rose-400 text-sm py-6 px-2">{error}</div>}
          {!loading && !error && opps.length === 0 && (
            <div className="text-center text-slate-500 text-sm py-10">No opportunities yet. Run a scan.</div>
          )}
          {opps.map((o) => (
            <OppCard key={o.id} opp={o} selected={selected?.id === o.id} onClick={setSelected} />
          ))}
        </div>
      </aside>

      <main className="flex-1 min-w-0 bg-xora-950">
        <OppDetail opp={selected} onTraded={load} />
      </main>
    </div>
  )
}

/* ═══════════════════ Trade history ═══════════════════ */

function TradesPanel() {
  const [positions, setPositions] = useState([])
  const [summary, setSummary] = useState(null)
  const [filter, setFilter] = useState('')
  const [error, setError] = useState(null)
  const [busyId, setBusyId] = useState(null)

  const load = useCallback(async () => {
    try {
      setError(null)
      const [pos, sum] = await Promise.all([
        fetchPositions(filter || undefined),
        fetchTradeSummary(),
      ])
      setPositions(pos)
      setSummary(sum)
    } catch (e) {
      setError(e.message)
    }
  }, [filter])

  useEffect(() => {
    load()
    const t = setInterval(load, 10000)
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
    <div className="flex-1 min-h-0 overflow-y-auto p-6 space-y-5">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <h2 className="text-lg font-semibold">Trade history</h2>
        <div className="flex gap-1">
          {['', 'open', 'closed'].map((f) => (
            <button
              key={f || 'all'}
              onClick={() => setFilter(f)}
              className={`px-3 py-1 rounded-md text-xs font-medium ${
                filter === f ? 'bg-blue-600 text-white' : 'bg-xora-800 text-slate-400'
              }`}
            >
              {f || 'all'}
            </button>
          ))}
        </div>
      </div>

      {summary && (
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3">
          {[
            ['Open', summary.open_count],
            ['Closed', summary.closed_count],
            ['Win rate', `${summary.win_rate}%`],
            ['Total PnL', summary.total_realized_pnl],
            ['Avg PnL', summary.avg_pnl],
            ['W / L', `${summary.wins} / ${summary.losses}`],
          ].map(([label, val]) => (
            <div key={label} className="rounded-xl bg-xora-800/80 border border-xora-600/40 p-3">
              <div className="text-[10px] uppercase text-slate-500 mb-1">{label}</div>
              <div className={`text-sm font-mono font-semibold ${
                label.includes('PnL') && Number(val) < 0 ? 'text-rose-300' : label.includes('PnL') ? 'text-emerald-300' : 'text-slate-100'
              }`}>{val}</div>
            </div>
          ))}
        </div>
      )}

      {error && <div className="text-sm text-rose-400">{error}</div>}

      <div className="rounded-xl border border-xora-600/40 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-xora-900 text-[11px] uppercase tracking-wider text-slate-500">
            <tr>
              <th className="text-left px-4 py-2">Symbol</th>
              <th className="text-left px-4 py-2">Side</th>
              <th className="text-left px-4 py-2">Entry</th>
              <th className="text-left px-4 py-2">SL / TP1</th>
              <th className="text-left px-4 py-2">Qty · Lev</th>
              <th className="text-left px-4 py-2">Status</th>
              <th className="text-left px-4 py-2">PnL</th>
              <th className="text-right px-4 py-2">Action</th>
            </tr>
          </thead>
          <tbody>
            {positions.length === 0 && (
              <tr>
                <td colSpan={8} className="px-4 py-10 text-center text-slate-500">
                  No trades yet. Enable auto demo or open from an APPROVE opportunity.
                </td>
              </tr>
            )}
            {positions.map((p) => (
              <tr key={p.id} className="border-t border-xora-600/30 hover:bg-xora-800/40">
                <td className="px-4 py-2.5 font-medium">{p.symbol}</td>
                <td className="px-4 py-2.5">
                  <Badge tone={p.side === 'BUY' ? 'buy' : 'sell'}>{p.side}</Badge>
                </td>
                <td className="px-4 py-2.5 font-mono text-xs">{fmt(p.entry)}</td>
                <td className="px-4 py-2.5 font-mono text-xs text-slate-400">
                  {fmt(p.stop_loss)} / {fmt(p.take_profit_1)}
                </td>
                <td className="px-4 py-2.5 font-mono text-xs">{p.quantity} · {p.leverage}x</td>
                <td className="px-4 py-2.5">
                  <Badge tone={p.status === 'open' ? 'approve' : 'neutral'}>{p.status}</Badge>
                  <span className="ml-1 text-[10px] text-slate-500">{p.mode}</span>
                </td>
                <td className={`px-4 py-2.5 font-mono text-xs ${
                  p.realized_pnl > 0 ? 'text-emerald-400' : p.realized_pnl < 0 ? 'text-rose-400' : 'text-slate-400'
                }`}>
                  {p.realized_pnl != null ? fmt(p.realized_pnl, 2) : '—'}
                </td>
                <td className="px-4 py-2.5 text-right">
                  {p.status === 'open' && (
                    <button
                      onClick={() => handleClose(p.id)}
                      disabled={busyId === p.id}
                      className="text-xs px-2 py-1 rounded bg-rose-500/20 text-rose-300 hover:bg-rose-500/30 disabled:opacity-50"
                    >
                      {busyId === p.id ? '…' : 'Close'}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

/* ═══════════════════ Pattern library ═══════════════════ */

function PatternLibrary() {
  const [patterns, setPatterns] = useState([])
  const [selected, setSelected] = useState(null)
  const [filterDir, setFilterDir] = useState('')

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      const list = await fetchPatterns({ direction: filterDir || undefined })
      if (!cancelled) {
        setPatterns(list)
        setSelected((prev) => list.find((p) => p.key === prev?.key) || list[0] || null)
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
          {patterns.map((p) => (
            <button
              key={p.key}
              onClick={() => setSelected(p)}
              className={`w-full text-left p-3 rounded-xl border text-sm
                ${selected?.key === p.key ? 'bg-xora-700 border-blue-500/60' : 'bg-xora-800/80 border-xora-600/50'}`}
            >
              {p.name}
            </button>
          ))}
        </div>
      </aside>
      <main className="flex-1 min-w-0 bg-xora-950 p-6 overflow-y-auto">
        {selected ? (
          <div className="space-y-4">
            <h2 className="text-xl font-bold">{selected.name}</h2>
            <p className="text-sm text-slate-300">{selected.overview}</p>
          </div>
        ) : (
          <p className="text-slate-500 text-sm">Select a pattern</p>
        )}
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
    fetchSettings()
      .then((s) => setAutoTrade(!!s.auto_trade))
      .catch(() => {})
    const t = setInterval(() => {
      fetchHealth().then(setHealth).catch(() => setHealth(null))
    }, 15000)
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
    <div className="h-full flex flex-col">
      <header className="shrink-0 border-b border-xora-600/40 bg-xora-900/90 backdrop-blur px-5 py-3 flex items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-sm font-bold">X</div>
            <div>
              <div className="font-semibold text-sm tracking-tight">XORA Chart AI</div>
              <div className="text-[11px] text-slate-500">Analysis · Decision · Trade</div>
            </div>
          </div>
          <nav className="flex gap-1 ml-2">
            {[
              ['opportunities', 'Opportunities'],
              ['trades', 'Trades'],
              ['library', 'Patterns'],
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

        <div className="flex items-center gap-3">
          {autoTrade && (
            <span className="text-[11px] px-2 py-1 rounded-full bg-emerald-500/15 text-emerald-400 ring-1 ring-emerald-500/30">
              Auto demo ON
            </span>
          )}
          <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium
            ${health ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${health ? 'bg-emerald-400' : 'bg-rose-400'}`} />
            {health
              ? `API · ${health.opportunities_cached ?? 0} opp · ${health.positions_open ?? 0} open`
              : 'API offline'}
          </div>
        </div>
      </header>

      {tab === 'opportunities' && (
        <OpportunityBoard autoTrade={autoTrade} onToggleAuto={handleToggleAuto} />
      )}
      {tab === 'trades' && <TradesPanel />}
      {tab === 'library' && <PatternLibrary />}
    </div>
  )
}
