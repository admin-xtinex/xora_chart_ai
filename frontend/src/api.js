const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8030'

export async function fetchPatterns({ direction, type } = {}) {
  const params = new URLSearchParams()
  if (direction) params.set('direction', direction)
  if (type) params.set('type', type)
  const qs = params.toString()
  const res = await fetch(`${API_BASE}/api/v1/patterns${qs ? `?${qs}` : ''}`)
  if (!res.ok) throw new Error(`Failed to load patterns: ${res.status}`)
  return res.json()
}

export async function fetchHealth() {
  const res = await fetch(`${API_BASE}/api/v1/health`)
  if (!res.ok) throw new Error('Backend offline')
  return res.json()
}

export async function fetchOpportunities(limit = 20) {
  const res = await fetch(`${API_BASE}/api/v1/opportunities?limit=${limit}`)
  if (!res.ok) throw new Error(`Failed to load opportunities: ${res.status}`)
  return res.json()
}

export async function fetchLatestCycle() {
  const res = await fetch(`${API_BASE}/api/v1/cycles/latest`)
  if (!res.ok) throw new Error('Failed to load cycle')
  if (res.status === 204) return null
  return res.json()
}

export async function runCycle() {
  const res = await fetch(`${API_BASE}/api/v1/cycles/run`, { method: 'POST' })
  if (!res.ok) throw new Error(`Scan failed: ${res.status}`)
  return res.json()
}

export { API_BASE }
