import { useEffect, useState, useMemo } from 'react'
import { fetchPatterns, fetchHealth, referenceImageUrl, API_BASE } from './api'

function Badge({ children, tone = 'neutral' }) {
  const tones = {
    neutral: 'bg-slate-700/60 text-slate-200',
    bull: 'bg-emerald-500/15 text-emerald-400 ring-1 ring-emerald-500/30',
    bear: 'bg-rose-500/15 text-rose-400 ring-1 ring-rose-500/30',
    cont: 'bg-sky-500/15 text-sky-300 ring-1 ring-sky-500/30',
    rev: 'bg-amber-500/15 text-amber-300 ring-1 ring-amber-500/30',
  }
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium ${tones[tone] || tones.neutral}`}>
      {children}
    </span>
  )
}

function PatternCard({ pattern, selected, onClick }) {
  const isBull = pattern.direction === 'bullish'
  return (
    <button
      onClick={() => onClick(pattern)}
      className={`w-full text-left p-4 rounded-xl border transition-all duration-150
        ${selected
          ? 'bg-xora-700 border-blue-500/60 shadow-lg shadow-blue-500/10'
          : 'bg-xora-800/80 border-xora-600/50 hover:border-slate-500 hover:bg-xora-700/80'
        }`}
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <h3 className="font-semibold text-sm leading-snug text-slate-100">{pattern.name}</h3>
        <Badge tone={isBull ? 'bull' : 'bear'}>{isBull ? 'Bull' : 'Bear'}</Badge>
      </div>
      <div className="flex gap-1.5 flex-wrap">
        <Badge tone={pattern.type === 'continuation' ? 'cont' : 'rev'}>
          {pattern.type}
        </Badge>
      </div>
    </button>
  )
}

function DetailPanel({ pattern }) {
  if (!pattern) {
    return (
      <div className="h-full flex items-center justify-center text-slate-500">
        <div className="text-center">
          <div className="text-4xl mb-3 opacity-40">📈</div>
          <p className="text-sm">Select a pattern to view details</p>
        </div>
      </div>
    )
  }

  const img = referenceImageUrl(pattern.key)
  const isBull = pattern.direction === 'bullish'

  return (
    <div className="h-full overflow-y-auto">
      <div className="sticky top-0 z-10 bg-xora-900/95 backdrop-blur border-b border-xora-600/40 px-6 py-4">
        <div className="flex items-center gap-3 flex-wrap">
          <h2 className="text-xl font-bold tracking-tight">{pattern.name}</h2>
          <Badge tone={isBull ? 'bull' : 'bear'}>
            {isBull ? 'Bullish' : 'Bearish'}
          </Badge>
          <Badge tone={pattern.type === 'continuation' ? 'cont' : 'rev'}>
            {pattern.type}
          </Badge>
        </div>
        <p className="text-xs text-slate-500 mt-1 font-mono">{pattern.key}</p>
      </div>

      <div className="p-6 space-y-6">
        {/* Reference image */}
        {img && (
          <div className="rounded-xl overflow-hidden border border-xora-600/50 bg-xora-950">
            <img
              src={img}
              alt={pattern.name}
              className="w-full h-auto object-contain max-h-[420px]"
              loading="lazy"
            />
          </div>
        )}

        {/* Overview */}
        <section>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">Overview</h3>
          <p className="text-sm text-slate-300 leading-relaxed">{pattern.overview}</p>
        </section>

        {/* Trading Setup */}
        <section className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="rounded-lg bg-emerald-500/10 border border-emerald-500/20 p-3">
            <div className="text-[10px] uppercase tracking-wider text-emerald-400/80 mb-1">Entry</div>
            <div className="text-sm font-medium text-emerald-300">{pattern.trading_setup.entry}</div>
          </div>
          <div className="rounded-lg bg-rose-500/10 border border-rose-500/20 p-3">
            <div className="text-[10px] uppercase tracking-wider text-rose-400/80 mb-1">Stop Loss</div>
            <div className="text-sm font-medium text-rose-300">{pattern.trading_setup.stop_loss}</div>
          </div>
          <div className="rounded-lg bg-sky-500/10 border border-sky-500/20 p-3">
            <div className="text-[10px] uppercase tracking-wider text-sky-400/80 mb-1">Target</div>
            <div className="text-sm font-medium text-sky-300">{pattern.trading_setup.target}</div>
          </div>
        </section>

        {/* Characteristics */}
        <section>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">Characteristics</h3>
          <ul className="space-y-1.5">
            {pattern.characteristics.map((c, i) => (
              <li key={i} className="flex gap-2 text-sm text-slate-300">
                <span className="text-blue-400 mt-0.5">•</span>
                <span>{c}</span>
              </li>
            ))}
          </ul>
        </section>

        {/* Key Points */}
        <section>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">Key Points</h3>
          <ul className="space-y-1.5">
            {pattern.key_points.map((k, i) => (
              <li key={i} className="flex gap-2 text-sm text-slate-300">
                <span className="text-emerald-400">✓</span>
                <span>{k}</span>
              </li>
            ))}
          </ul>
        </section>

        {/* Volume */}
        {pattern.volume_behaviour && Object.keys(pattern.volume_behaviour).length > 0 && (
          <section>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">Volume Behaviour</h3>
            <div className="flex flex-wrap gap-2">
              {Object.entries(pattern.volume_behaviour).map(([k, v]) => (
                <div key={k} className="rounded-md bg-xora-800 border border-xora-600/50 px-3 py-1.5 text-xs">
                  <span className="text-slate-500 capitalize">{k.replace(/_/g, ' ')}:</span>{' '}
                  <span className="text-slate-200 font-medium">{v}</span>
                </div>
              ))}
            </div>
          </section>
        )}
      </div>
    </div>
  )
}

export default function App() {
  const [patterns, setPatterns] = useState([])
  const [selected, setSelected] = useState(null)
  const [filterDir, setFilterDir] = useState('')
  const [filterType, setFilterType] = useState('')
  const [health, setHealth] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      setError(null)
      try {
        const [list, h] = await Promise.all([
          fetchPatterns({ direction: filterDir || undefined, type: filterType || undefined }),
          fetchHealth().catch(() => null),
        ])
        if (!cancelled) {
          setPatterns(list)
          setHealth(h)
          // keep selection if still present
          if (selected) {
            const still = list.find((p) => p.key === selected.key)
            setSelected(still || list[0] || null)
          } else if (list.length) {
            setSelected(list[0])
          }
        }
      } catch (e) {
        if (!cancelled) setError(e.message || 'Failed to load')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [filterDir, filterType])

  const counts = useMemo(() => {
    const bull = patterns.filter((p) => p.direction === 'bullish').length
    const bear = patterns.filter((p) => p.direction === 'bearish').length
    return { total: patterns.length, bull, bear }
  }, [patterns])

  return (
    <div className="h-full flex flex-col">
      {/* Top bar */}
      <header className="shrink-0 border-b border-xora-600/40 bg-xora-900/90 backdrop-blur px-5 py-3 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-sm font-bold shadow-lg shadow-blue-500/20">
            X
          </div>
          <div>
            <div className="font-semibold text-sm tracking-tight">XORA Chart AI</div>
            <div className="text-[11px] text-slate-500">Pattern Library · Phase 1</div>
          </div>
        </div>

        <div className="flex items-center gap-4 text-xs">
          <div className="hidden sm:flex items-center gap-3 text-slate-400">
            <span>{counts.total} patterns</span>
            <span className="text-emerald-400">{counts.bull} bull</span>
            <span className="text-rose-400">{counts.bear} bear</span>
          </div>
          <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium
            ${health ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${health ? 'bg-emerald-400' : 'bg-rose-400'}`} />
            {health ? 'API online' : 'API offline'}
          </div>
        </div>
      </header>

      {/* Body */}
      <div className="flex-1 min-h-0 flex">
        {/* Sidebar */}
        <aside className="w-72 shrink-0 border-r border-xora-600/40 bg-xora-900 flex flex-col">
          {/* Filters */}
          <div className="p-3 border-b border-xora-600/40 space-y-2">
            <div className="flex gap-1.5">
              {[('', 'All'), ('bullish', 'Bull'), ('bearish', 'Bear')].map(([v, label]) => (
                <button
                  key={v}
                  onClick={() => setFilterDir(v)}
                  className={`flex-1 text-xs py-1.5 rounded-md font-medium transition
                    ${filterDir === v
                      ? 'bg-blue-600 text-white'
                      : 'bg-xora-800 text-slate-400 hover:text-slate-200'}`}
                >
                  {label}
                </button>
              ))}
            </div>
            <div className="flex gap-1.5">
              {[('', 'All types'), ('continuation', 'Cont.'), ('reversal', 'Rev.')].map(([v, label]) => (
                <button
                  key={v}
                  onClick={() => setFilterType(v)}
                  className={`flex-1 text-xs py-1.5 rounded-md font-medium transition
                    ${filterType === v
                      ? 'bg-blue-600 text-white'
                      : 'bg-xora-800 text-slate-400 hover:text-slate-200'}`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {/* List */}
          <div className="flex-1 overflow-y-auto p-3 space-y-2">
            {loading && (
              <div className="text-center text-slate-500 text-sm py-8">Loading…</div>
            )}
            {error && (
              <div className="text-center text-rose-400 text-sm py-8 px-2">
                {error}
                <div className="text-[11px] text-slate-500 mt-2">API: {API_BASE}</div>
              </div>
            )}
            {!loading && !error && patterns.map((p) => (
              <PatternCard
                key={p.key}
                pattern={p}
                selected={selected?.key === p.key}
                onClick={setSelected}
              />
            ))}
          </div>
        </aside>

        {/* Detail */}
        <main className="flex-1 min-w-0 bg-xora-950">
          <DetailPanel pattern={selected} />
        </main>
      </div>
    </div>
  )
}
