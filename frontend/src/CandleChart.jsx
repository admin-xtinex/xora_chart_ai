import { useEffect, useRef } from 'react'
import { createChart, ColorType } from 'lightweight-charts'

/**
 * Renders live OHLCV from Binance with trade levels as horizontal lines.
 * No static reference images — only real 1m candles from the scan.
 */
export default function CandleChart({ candles = [], trade = null, height = 360 }) {
  const containerRef = useRef(null)
  const chartRef = useRef(null)

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
      rightPriceScale: {
        borderColor: '#1c2538',
      },
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

    const series = chart.addCandlestickSeries({
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

    // dedupe timestamps
    const seen = new Set()
    const unique = []
    for (const bar of data) {
      if (seen.has(bar.time)) continue
      seen.add(bar.time)
      unique.push(bar)
    }

    if (unique.length) {
      series.setData(unique)
      chart.timeScale().fitContent()
    }

    // Trade levels
    if (trade) {
      const lines = [
        { price: trade.entry, color: '#3b82f6', title: 'Entry' },
        { price: trade.stop_loss, color: '#ef4444', title: 'SL' },
        { price: trade.take_profit_1, color: '#22c55e', title: 'TP1' },
        { price: trade.take_profit_2, color: '#4ade80', title: 'TP2' },
        { price: trade.take_profit_3, color: '#86efac', title: 'TP3' },
      ]
      for (const ln of lines) {
        if (ln.price == null || Number.isNaN(ln.price)) continue
        series.createPriceLine({
          price: ln.price,
          color: ln.color,
          lineWidth: 1,
          lineStyle: 2, // dashed
          axisLabelVisible: true,
          title: ln.title,
        })
      }
    }

    chartRef.current = chart

    const ro = new ResizeObserver(() => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth })
      }
    })
    ro.observe(containerRef.current)

    return () => {
      ro.disconnect()
      chart.remove()
      chartRef.current = null
    }
  }, [candles, trade, height])

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
        <span className="flex gap-3">
          <span className="text-blue-400">Entry</span>
          <span className="text-rose-400">SL</span>
          <span className="text-emerald-400">TP</span>
        </span>
      </div>
      <div ref={containerRef} />
    </div>
  )
}
