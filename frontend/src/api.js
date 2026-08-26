const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8030'

export async function fetchPatterns({ direction, type } = {}) {
  const params = new URLSearchParams()
  if (direction) params.set('direction', direction)
  if (type) params.set('type', type)
  const qs = params.toString()
  const url = `${API_BASE}/api/v1/patterns${qs ? `?${qs}` : ''}`
  const res = await fetch(url)
  if (!res.ok) throw new Error(`Failed to load patterns: ${res.status}`)
  return res.json()
}

export async function fetchPattern(key) {
  const res = await fetch(`${API_BASE}/api/v1/patterns/${key}`)
  if (!res.ok) throw new Error(`Pattern not found`)
  return res.json()
}

export async function fetchHealth() {
  const res = await fetch(`${API_BASE}/api/v1/health`)
  if (!res.ok) throw new Error('Backend offline')
  return res.json()
}

/** Map pattern key → reference image filename (best effort from the uploaded set) */
const IMAGE_MAP = {
  breakout_retest: 'ChatGPT Image Aug 26, 2026, 03_17_17 AM.png',
  double_bottom: 'ChatGPT Image Aug 26, 2026, 03_17_21 AM.png',
  bull_pennant: 'ChatGPT Image Aug 26, 2026, 03_17_26 AM.png',
  cup_and_handle: 'ChatGPT Image Aug 26, 2026, 03_17_32 AM.png',
  bull_flag: 'ChatGPT Image Aug 26, 2026, 03_17_38 AM.png',
  bear_flag: 'ChatGPT Image Aug 26, 2026, 05_35_49 AM.png',
  double_top: 'ChatGPT Image Aug 26, 2026, 05_44_42 AM.png',
  bear_pennant: 'ChatGPT Image Aug 26, 2026, 05_44_45 AM.png',
  breakdown_retest: 'ChatGPT Image Aug 26, 2026, 05_47_03 AM.png',
  head_and_shoulders: 'ChatGPT Image Aug 26, 2026, 05_52_40 AM.png',
}

export function referenceImageUrl(key) {
  const file = IMAGE_MAP[key]
  if (!file) return null
  return `${API_BASE}/references/${encodeURIComponent(file)}`
}

export { API_BASE }
