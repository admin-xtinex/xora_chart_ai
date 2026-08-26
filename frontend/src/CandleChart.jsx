import { useEffect, useRef } from 'react'
import { createChart, ColorType, LineStyle } from 'lightweight-charts'

/**
 * Live Binance candles + trade levels + transparent pattern geometry.
 */
export default function CandleChart({
  candles = [],
  trade = null,
  overlays = null,
  height = 380,
}) {
  const containerRef = useRef(null)

  useEffect(() => {
    if (!containerRef.current) return

    const chart = createChart(containerRef.current, {
      height,
      layout: {
        background: { type: ColorType.Solid, color: '#0a0e17' },
        textColor: '#94a3b8',
      },
      grid: {
        vertLines: { color: '#151c2c' },
        horzLines: { color: '#151c2c' },
      },
      rightPriceScale: { borderColor: '#1c2538' },
      timeScale: {
        borderColor: '#1c2538',
        timeVisible: true,
        secondsVisible: false,
      },
      crosshair: {
        vertLine: { color: '#334155', labelBackgroundColor: '#1c2538' },
        horzLine: { color: '#334155', labelBackgroundColor: '#1c2538' },
      },
    })

    const candleSeries = chart.addCandlestickSeries({
      upColor: '#22c55e',
      downColor: '#ef4444',
      borderUpColor: '#22c55e',
      borderDownColor: '#ef4444',
      wickUpColor: '#22c55e',
      wickDownColor: '#ef4444',
    })

    const data = (candles || [])
      .map((c) => ({
        time: Math.floor((c.open_time || c.close_time || 0) / 1000),
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      }))
      .filter((c) => c.time > 0)
      .sort((a, b) => a.time - b.time)

    const seen = new Set()
    const unique = []
    for (const bar of data) {
      if (seen.has(bar.time)) continue
      seen.add(bar.time)
      unique.push(bar)
    }

    if (unique.length) {
      candleSeries.setData(unique)
      chart.timeScale().fitContent()
    }

    // ── Pattern structure overlays (transparent) ──────────────────────────
    const ov = overlays || {}

    // Structure lines (peak connections, neckline segments, flag channel)
    for (const ln of ov.lines || []) {
      if (!ln.points?.length) continue
      const lineSeries = chart.addLineSeries({
        color: ln.color || 'rgba(167,139,250,0.45)',
        lineWidth: 2,
        lineStyle: LineStyle.Solid,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
        title: ln.title || '',
      })
      const pts = ln.points
        .map((p) => ({ time: p.time, value: p.value }))
        .filter((p) => p.time > 0)
        .sort((a, b) => a.time - b.time)
      // dedupe times
      const s = new Set()
      const clean = []
      for (const p of pts) {
        if (s.has(p.time)) continue
        s.add(p.time)
        clean.push(p)
      }
      if (clean.length >= 2) lineSeries.setData(clean)
    }

    // Horizontal structure levels (neckline, flag high/low, rim…)
    for (const lv of ov.levels || []) {
      if (lv.price == null) continue
      candleSeries.createPriceLine({
        price: lv.price,
        color: lv.color || 'rgba(167,139,250,0.7)',
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: lv.title || '',
      })
    }

    // Point markers (LS / Head / RS / T1 / T2 …)
    if (ov.markers?.length) {
      const markers = ov.markers
        .filter((m) => m.time > 0)
        .map((m) => ({
          time: m.time,
          position: m.position === 'belowBar' ? 'belowBar' : 'aboveBar',
          color: m.color || '#c4b5fd',
          shape: m.position === 'belowBar' ? 'arrowUp' : 'arrowDown',
          text: m.label || '',
        }))
        .sort((a, b) => a.time - b.time)
      // unique times for markers
      const ms = new Set()
      const um = []
      for (const m of markers) {
        if (ms.has(m.time)) continue
        ms.add(m.time)
        um.push(m)
      }
      if (um.length) candleSeries.setMarkers(um)
    }

    // ── Trade levels (Entry / SL / TP) ─────────────────────────────────────
    if (trade) {
      const tradeLines = [
        { price: trade.entry, color: '#3b82f6', title: 'Entry' },
        { price: trade.stop_loss, color: '#ef4444', title: 'SL' },
        { price: trade.take_profit_1, color: '#22c55e', title: 'TP1' },
        { price: trade.take_profit_2, color: '#4ade80', title: 'TP2' },
        { price: trade.take_profit_3, color: '#86efac', title: 'TP3' },
      ]
      for (const ln of tradeLines) {
        if (ln.price == null || Number.isNaN(ln.price)) continue
        candleSeries.createPriceLine({
          price: ln.price,
          color: ln.color,
          lineWidth: 1,
          lineStyle: LineStyle.Dotted,
          axisLabelVisible: true,
          title: ln.title,
        })
      }
    }

    const ro = new ResizeObserver(() => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth })
      }
    })
    ro.observe(containerRef.current)

    return () => {
      ro.disconnect()
      chart.remove()
    }
  }, [candles, trade, overlays, height])

  if (!candles?.length) {
    return (
      <div
        className="rounded-xl border border-xora-600/50 bg-xora-950 flex items-center justify-center text-slate-500 text-sm"
        style={{ height }}
      >
        No live candle data — run a new scan
      </div>
    )
  }

  return (
    <div className="rounded-xl overflow-hidden border border-xora-600/50 bg-xora-950">
      <div className="px-3 py-1.5 border-b border-xora-600/40 flex items-center justify-between text-[10px] text-slate-500">
        <span>Binance Futures · 1m · {candles.length} candles</span>
        <span className="flex gap-3 flex-wrap justify-end">
          <span className="text-violet-300/80">Pattern structure</span>
          <span className="text-blue-400">Entry</span>
          <span className="text-rose-400">SL</span>
          <span className="text-emerald-400">TP</span>
        </span>
      </div>
      <div ref={containerRef} />
    </div>
  )
}
