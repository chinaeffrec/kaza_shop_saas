/**
 * API-клиент Mini App.
 * Хранит JWT в памяти (не localStorage — он сбрасывается при каждом открытии TMA).
 */

const BASE = import.meta.env.VITE_API_URL ?? ''
const V1 = `${BASE}/api/v1`

let _token = null
let _shopId = null

export function setToken(token) { _token = token }
export function setShopId(id) { _shopId = id }
export function getShopId() { return _shopId }

function authHeaders() {
  const h = { 'Content-Type': 'application/json' }
  if (_token) h['Authorization'] = `Bearer ${_token}`
  return h
}

async function req(method, path, body) {
  const opts = { method, headers: authHeaders() }
  if (body !== undefined) opts.body = JSON.stringify(body)
  const res = await fetch(`${V1}${path}`, opts)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    const msg = Array.isArray(err.detail)
      ? err.detail.map(d => d.msg || JSON.stringify(d)).join('; ')
      : (err.detail || 'Ошибка запроса')
    throw new Error(String(msg))
  }
  if (res.status === 204) return null
  return res.json()
}

// ── Auth ──────────────────────────────────────────────────────────────────────
export const auth = {
  login: (initData, shopId) =>
    req('POST', '/miniapp/auth', { init_data: initData, shop_id: shopId }),
}

// ── Settings ──────────────────────────────────────────────────────────────────
export const settings = {
  get: (shopId) => req('GET', `/miniapp/settings?shop_id=${shopId}`),
}

// ── Catalog ───────────────────────────────────────────────────────────────────
export const catalog = {
  getAll: (shopId) => req('GET', `/miniapp/catalog?shop_id=${shopId}`),
  getProduct: (id, shopId) => req('GET', `/miniapp/products/${id}?shop_id=${shopId}`),
}

// ── Cart ──────────────────────────────────────────────────────────────────────
export const cart = {
  get: () => req('GET', '/miniapp/cart'),
  add: (productId, quantity = 1) =>
    req('POST', '/miniapp/cart', { product_id: productId, quantity }),
  update: (productId, quantity) =>
    req('PATCH', '/miniapp/cart', { product_id: productId, quantity }),
  remove: (productId) => req('DELETE', `/miniapp/cart/${productId}`),
  clear: () => req('DELETE', '/miniapp/cart'),
}

// ── Orders ────────────────────────────────────────────────────────────────────
export const orders = {
  create: (data) => req('POST', '/miniapp/orders', data),
  list: () => req('GET', '/miniapp/orders'),
}

// ── Reviews ───────────────────────────────────────────────────────────────────
export const reviews = {
  getByProduct: (productId, shopId, page = 1) =>
    req('GET', `/reviews/product/${productId}?shop_id=${shopId}&page=${page}&per_page=10`),
  getStats: (productId, shopId) =>
    req('GET', `/reviews/product/${productId}/stats?shop_id=${shopId}`),
}

export default { auth, settings, catalog, cart, orders, reviews }
