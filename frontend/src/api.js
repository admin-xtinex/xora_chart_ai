const explicit = (import.meta.env.VITE_WS_BASE || '').replace(/\/+$/, '')
const WS_URL = explicit || `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws`

let socket = null
let connectPromise = null
let seq = 0
const pending = new Map()

function failPending(message) {
  for (const [, item] of pending) item.reject(new Error(message))
  pending.clear()
}

function connect() {
  if (socket?.readyState === WebSocket.OPEN) return Promise.resolve(socket)
  if (connectPromise) return connectPromise

  connectPromise = new Promise((resolve, reject) => {
    const ws = new WebSocket(WS_URL)
    socket = ws

    const timer = setTimeout(() => {
      try { ws.close() } catch { /* ignore */ }
      reject(new Error('WebSocket connection timeout'))
    }, 10000)

    ws.onopen = () => {
      clearTimeout(timer)
      connectPromise = null
      resolve(ws)
    }

    ws.onmessage = (event) => {
      let msg
      try {
        msg = JSON.parse(event.data)
      } catch {
        return
      }
      if (msg.type !== 'response' || !msg.id) return
      const item = pending.get(msg.id)
      if (!item) return
      pending.delete(msg.id)
      clearTimeout(item.timer)
      if (msg.ok) item.resolve(msg.data)
      else item.reject(new Error(msg.error || 'WebSocket request failed'))
    }

    ws.onerror = () => {
      // close handler performs the actual rejection so callers receive one error
    }

    ws.onclose = () => {
      clearTimeout(timer)
      if (socket === ws) socket = null
      connectPromise = null
      failPending('Backend WebSocket disconnected')
    }
  })

  return connectPromise
}

async function rpc(action, payload = {}, timeoutMs = 190000) {
  const ws = await connect()
  const id = `${Date.now()}-${++seq}`
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      pending.delete(id)
      reject(new Error(`${action}: WebSocket timeout`))
    }, timeoutMs)
    pending.set(id, { resolve, reject, timer })
    try {
      ws.send(JSON.stringify({ id, action, payload }))
    } catch (err) {
      clearTimeout(timer)
      pending.delete(id)
      reject(err)
    }
  })
}

export function fetchPatterns({ direction, type } = {}) {
  return rpc('patterns.list', { direction, type })
}

export function fetchHealth() {
  return rpc('health')
}

export function fetchOpportunities(limit = 30) {
  return rpc('opportunities.list', { limit })
}

export async function runCycle() {
  const result = await rpc('cycle.run')
  const errors = Array.isArray(result?.errors) ? result.errors.filter(Boolean) : []
  if (errors.length) {
    throw new Error(errors.join(' · '))
  }
  return result
}

export function analyzeSymbol(symbol) {
  return rpc('analyze', { symbol })
}

export function fetchSettings() {
  return rpc('settings.get')
}

export function updateSettings(patch) {
  return rpc('settings.update', patch)
}

export function fetchPositions(status) {
  return rpc('positions.list', { status })
}

export function fetchTradeSummary() {
  return rpc('positions.summary')
}

export function managePositions() {
  return rpc('positions.manage')
}

export function openDemoTrade(opportunityId) {
  return rpc('position.open', { opportunity_id: opportunityId })
}

export function closeTrade(posId, exitPrice) {
  return rpc('position.close', {
    position_id: posId,
    ...(exitPrice != null ? { exit_price: exitPrice } : {}),
    reason: 'manual',
  })
}

export { WS_URL as API_BASE }
