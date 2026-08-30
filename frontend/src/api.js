const explicit = (import.meta.env.VITE_WS_BASE || '').replace(/\/+$/, '')
const WS_URL = explicit || `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws`
const BINANCE_FUTURES_REST_BASE = (
  import.meta.env.VITE_BINANCE_FUTURES_REST_BASE || 'https://fapi.binance.com/fapi/v1'
).replace(/\/+$/, '')

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
      try { msg = JSON.parse(event.data) } catch { return }
      if (msg.type !== 'response' || !msg.id) return
      const item = pending.get(msg.id)
      if (!item) return
      pending.delete(msg.id)
      clearTimeout(item.timer)
      if (msg.ok) item.resolve(msg.data)
      else item.reject(new Error(msg.error || 'WebSocket request failed'))
    }

    ws.onerror = () => { /* close handler rejects active requests */ }
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
    try { ws.send(JSON.stringify({ id, action, payload })) }
    catch (err) { clearTimeout(timer); pending.delete(id); reject(err) }
  })
}

function normalizeSymbol(raw) {
  const compact = String(raw || '').trim().toUpperCase().replace(/[\/\-\s]/g, '')
  if (!compact) throw new Error('Enter a coin symbol')
  return compact.endsWith('USDT') ? compact : `${compact}USDT`
}

async function fetchFuturesHistory(rawSymbol, limit = 100) {
  const symbol = normalizeSymbol(rawSymbol)
  const params = new URLSearchParams({ symbol, interval: '1m', limit: String(Math.min(1000, Math.max(21, Number(limit) + 1))) })
  const response = await fetch(`${BINANCE_FUTURES_REST_BASE}/klines?${params.toString()}`, {
    method: 'GET', cache: 'no-store', headers: { Accept: 'application/json' },
  })
  if (!response.ok) {
    const body = (await response.text()).slice(0, 180)
    throw new Error(`Binance history HTTP ${response.status}${body ? ` · ${body}` : ''}`)
  }
  const rows = await response.json()
  if (!Array.isArray(rows) || rows.length < 20) throw new Error(`Binance returned only ${Array.isArray(rows) ? rows.length : 0} history rows for ${symbol}`)
  return rows
}

async function mapLimit(items, limit, worker) {
  const queue = [...items]
  const count = Math.max(1, Math.min(limit, queue.length || 1))
  const runners = Array.from({ length: count }, async () => {
    while (queue.length) await worker(queue.shift())
  })
  await Promise.all(runners)
}

export function fetchPatterns({ direction, type } = {}) { return rpc('patterns.list', { direction, type }) }
export function fetchHealth() { return rpc('health') }
export function fetchOpportunities(limit = 30) { return rpc('opportunities.list', { limit }) }
export function fetchScanPlan() { return rpc('cycle.plan') }

export async function runCycle(coinsOverride = null) {
  const plan = Array.isArray(coinsOverride) ? { coins: coinsOverride } : await fetchScanPlan()
  const coins = Array.isArray(plan?.coins) ? plan.coins.slice(0, 20) : []
  if (!coins.length) throw new Error('No live WebSocket coins are available for scanning yet')

  const histories = {}
  const clientHistoryErrors = []
  await mapLimit(coins, 4, async (coin) => {
    const symbol = normalizeSymbol(coin?.symbol)
    try { histories[symbol] = await fetchFuturesHistory(symbol, 100) }
    catch (err) { clientHistoryErrors.push(`${symbol}: ${err.message || err}`) }
  })

  const result = await rpc('cycle.run', { coins, histories })
  const errors = Array.isArray(result?.errors) ? result.errors.filter(Boolean) : []
  if (errors.length) throw new Error([...errors, ...clientHistoryErrors].join(' · '))
  return result
}

export async function analyzeSymbol(symbol) {
  const normalized = normalizeSymbol(symbol)
  try {
    const history = await fetchFuturesHistory(normalized, 100)
    return await rpc('analyze', { symbol: normalized, history })
  } catch (clientErr) {
    try { return await rpc('analyze', { symbol: normalized }) }
    catch (backendErr) { throw new Error(`Historical data unavailable for ${normalized}: ${clientErr.message || clientErr} · ${backendErr.message || backendErr}`) }
  }
}

export function fetchSettings() { return rpc('settings.get') }
export function updateSettings(patch) { return rpc('settings.update', patch) }
export function fetchPositions(status) { return rpc('positions.list', { status }) }
export function fetchTradeSummary() { return rpc('positions.summary') }
export function managePositions() { return rpc('positions.manage') }
export function openDemoTrade(opportunityId) { return rpc('position.open', { opportunity_id: opportunityId }) }
export function closeTrade(posId, exitPrice) {
  return rpc('position.close', { position_id: posId, ...(exitPrice != null ? { exit_price: exitPrice } : {}), reason: 'manual' })
}

export { WS_URL as API_BASE, BINANCE_FUTURES_REST_BASE }
