const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8030'

async function json(res, label) {
  if (!res.ok) {
    let detail = `${label}: ${res.status}`
    try {
      const body = await res.json()
      if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      /* ignore */
    }
    throw new Error(detail)
  }
  return res.json()
}

export async function fetchPatterns({ direction, type } = {}) {
  const params = new URLSearchParams()
  if (direction) params.set('direction', direction)
  if (type) params.set('type', type)
  const qs = params.toString()
  const res = await fetch(`${API_BASE}/api/v1/patterns${qs ? `?${qs}` : ''}`)
  return json(res, 'patterns')
}

export async function fetchHealth() {
  const res = await fetch(`${API_BASE}/api/v1/health`)
  return json(res, 'health')
}

export async function fetchOpportunities(limit = 30) {
  const res = await fetch(`${API_BASE}/api/v1/opportunities?limit=${limit}`)
  return json(res, 'opportunities')
}

export async function runCycle() {
  const res = await fetch(`${API_BASE}/api/v1/cycles/run`, { method: 'POST' })
  return json(res, 'scan')
}

export async function fetchSettings() {
  const res = await fetch(`${API_BASE}/api/v1/settings`)
  return json(res, 'settings')
}

export async function updateSettings(patch) {
  const res = await fetch(`${API_BASE}/api/v1/settings`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  })
  return json(res, 'settings')
}

export async function fetchPositions(status) {
  const qs = status ? `?status=${status}` : ''
  const res = await fetch(`${API_BASE}/api/v1/positions${qs}`)
  return json(res, 'positions')
}

export async function fetchTradeSummary() {
  const res = await fetch(`${API_BASE}/api/v1/positions/history/summary`)
  return json(res, 'summary')
}

export async function managePositions() {
  const res = await fetch(`${API_BASE}/api/v1/positions/manage`, { method: 'POST' })
  return json(res, 'manage')
}

export async function openDemoTrade(opportunityId) {
  const res = await fetch(`${API_BASE}/api/v1/positions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ opportunity_id: opportunityId }),
  })
  return json(res, 'open trade')
}

export async function closeTrade(posId, exitPrice) {
  const res = await fetch(`${API_BASE}/api/v1/positions/${posId}/close`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(exitPrice != null ? { exit_price: exitPrice, reason: 'manual' } : { reason: 'manual' }),
  })
  return json(res, 'close trade')
}

export { API_BASE }
