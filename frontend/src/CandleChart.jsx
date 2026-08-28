import { useEffect, useRef } from 'react'
import { createChart, ColorType, LineStyle } from 'lightweight-charts'

function overlayStyle(style) {
  const key = String(style || '').toLowerCase()
  if (key === 'solid') return LineStyle.Solid
  if (key === 'dashed') return LineStyle.Dashed
  return LineStyle.Dotted
}

/** Live Binance candles + trade levels + pattern geometry. */
export default function CandleChart({ candles = [], trade = null, overlays = null, height = 380 }) {
  const containerRef = useRef(null)

  useEffect(() => {
    if (!containerRef.current) return

    const chart = createChart(containerRef.current, {
      height,
      layout: { background: { type: ColorType.Solid, color: '#070c14' }, textColor: '#8190a8' },
      grid: { vertLines: { color: '#111a29' }, horzLines: { color: '#111a29' } },
      rightPriceScale: { borderColor: '#1a2639', scaleMargins: { top: 0.08, bottom: 0.08 } },
      timeScale: { borderColor: '#1a2639', timeVisible: true, secondsVisible: false, rightOffset: 6 },
      crosshair: {
        vertLine: { color: '#34445d', labelBackgroundColor: '#172235' },
        horzLine: { color: '#34445d', labelBackgroundColor: '#172235' },
      },
    })

    const candleSeries = chart.addCandlestickSeries({
      upColor: '#22c55e', downColor: '#ef4444',
      borderUpColor: '#22c55e', borderDownColor: '#ef4444',
      wickUpColor: '#22c55e', wickDownColor: '#ef4444',
    })

    const data = (candles || [])
      .map((c) => ({ time: Math.floor((c.open_time || c.close_time || 0) / 1000), open: c.open, high: c.high, low: c.low, close: c.close }))
      .filter((c) => c.time > 0)
      .sort((a, b) => a.time - b.time)

    const seen = new Set()
    const unique = []
    for (const bar of data) {
      if (seen.has(bar.time)) continue
      seen.add(bar.time)
      unique.push(bar)
    }
    if (unique.length) { candleSeries.setData(unique); chart.timeScale().fitContent() }

    const ov = overlays || {}
    for (const ln of ov.lines || []) {
      if (!ln.points?.length) continue
      const lineSeries = chart.addLineSeries({
        color: ln.color || 'rgba(103,232,249,0.78)',
        lineWidth: Number(ln.line_width || 2),
        lineStyle: overlayStyle(ln.style),
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
        title: ln.title || '',
      })
      const pts = ln.points.map((p) => ({ time: p.time, value: p.value })).filter((p) => p.time > 0).sort((a, b) => a.time - b.time)
      const usedTimes = new Set()
      const clean = pts.filter((p) => !usedTimes.has(p.time) && usedTimes.add(p.time))
      if (clean.length >= 2) lineSeries.setData(clean)
    }

    for (const lv of ov.levels || []) {
      if (lv.price == null) continue
      candleSeries.createPriceLine({
        price: lv.price,
        color: lv.color || 'rgba(167,139,250,0.78)',
        lineWidth: 1,
        lineStyle: overlayStyle(lv.style || 'dashed'),
        axisLabelVisible: true,
        title: lv.title || '',
      })
    }

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
      const markerTimes = new Set()
      const uniqueMarkers = markers.filter((m) => !markerTimes.has(m.time) && markerTimes.add(m.time))
      if (uniqueMarkers.length) candleSeries.setMarkers(uniqueMarkers)
    }

    if (trade) {
      const tradeLines = [
        { price: trade.entry, color: '#4f8cff', title: 'Entry' },
        { price: trade.stop_loss, color: '#fb7185', title: 'SL' },
        { price: trade.take_profit_1, color: '#22c55e', title: 'TP1' },
        { price: trade.take_profit_2, color: '#4ade80', title: 'TP2' },
        { price: trade.take_profit_3, color: '#86efac', title: 'TP3' },
      ]
      for (const ln of tradeLines) {
        if (ln.price == null || Number.isNaN(Number(ln.price))) continue
        candleSeries.createPriceLine({ price: ln.price, color: ln.color, lineWidth: 1, lineStyle: LineStyle.Dotted, axisLabelVisible: true, title: ln.title })
      }
    }

    const ro = new ResizeObserver(() => {
      if (containerRef.current) chart.applyOptions({ width: containerRef.current.clientWidth })
    })
    ro.observe(containerRef.current)
    return () => { ro.disconnect(); chart.remove() }
  }, [candles, trade, overlays, height])

  if (!candles?.length) {
    return <div className="flex items-center justify-center bg-[#070c14] text-sm text-slate-600" style={{ height }}>No candle data available for this position.</div>
  }

  return (
    <div className="overflow-hidden bg-[#070c14]">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/[.05] px-3 py-2 text-[9px] text-slate-600">
        <span>Binance Futures · 1m · {candles.length} candles</span>
        <span className="flex flex-wrap gap-3"><span className="text-cyan-300/80">- - matched structure</span><span className="text-blue-400">Entry</span><span className="text-rose-400">SL</span><span className="text-emerald-400">TP</span></span>
      </div>
      <div ref={containerRef} />
    </div>
  )
}
