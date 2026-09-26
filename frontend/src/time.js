// All timestamps render in the viewer's local time zone (IST for India).
// Backend datetimes are naive UTC ("2026-09-26T01:45:14"), so pin them to UTC
// before letting the browser convert.

export function parseUtc(value) {
  if (value == null || value === '') return null
  if (typeof value === 'number') return new Date(value < 1e12 ? value * 1000 : value)
  const s = String(value)
  const hasZone = /(Z|[+-]\d{2}:?\d{2})$/.test(s)
  const d = new Date(hasZone ? s : `${s}Z`)
  return Number.isNaN(d.getTime()) ? null : d
}

function zoneLabel(d) {
  // Browsers print India as "GMT+5:30"; show the familiar abbreviation.
  if (d.getTimezoneOffset() === -330) return 'IST'
  const part = new Intl.DateTimeFormat(undefined, { timeZoneName: 'short' }).formatToParts(d).find((p) => p.type === 'timeZoneName')
  return part ? part.value : ''
}

export function fmtDateTime(value) {
  const d = parseUtc(value)
  if (!d) return '—'
  const text = d.toLocaleString(undefined, { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
  return `${text} ${zoneLabel(d)}`.trim()
}

export function fmtDuration(seconds) {
  const s = Number(seconds)
  if (!Number.isFinite(s) || s < 0) return '—'
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60)
  return h ? `${h}h ${m}m` : m ? `${m}m ${Math.floor(s % 60)}s` : `${Math.floor(s)}s`
}

// lightweight-charts works in UTC seconds; these format axis/crosshair locally.
export function chartTimeFormatter(time) {
  return new Date(time * 1000).toLocaleString(undefined, { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false })
}

export function chartTickFormatter(time, tickType) {
  const d = new Date(time * 1000)
  // TickMarkType: 0 Year, 1 Month, 2 DayOfMonth, 3 Time, 4 TimeWithSeconds
  if (tickType === 0) return String(d.getFullYear())
  if (tickType === 1) return d.toLocaleString(undefined, { month: 'short' })
  if (tickType === 2) return d.toLocaleString(undefined, { day: '2-digit', month: 'short' })
  return d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', hour12: false })
}
