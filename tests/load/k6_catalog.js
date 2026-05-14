/**
 * Kaza Shop — k6 load test: Catalog & Order API
 *
 * Tests the most critical API paths under high concurrency:
 *   1. Product catalog listing
 *   2. Single product detail
 *   3. Add to cart
 *   4. Order creation
 *   5. Seller panel login + order list
 *
 * Usage:
 *   k6 run tests/load/k6_catalog.js
 *   k6 run --vus 100 --duration 60s tests/load/k6_catalog.js
 *   k6 run --vus 500 --duration 120s tests/load/k6_catalog.js
 *   k6 run --vus 1000 --duration 60s tests/load/k6_catalog.js
 *
 * Environment variables (pass via -e flag):
 *   BASE_URL       — default: http://localhost:8000
 *   BOT_TOKEN      — X-Bot-Token header value
 *   SHOP_ID        — shop ID (default: 1)
 *   SELLER_EMAIL   — seller panel email
 *   SELLER_PASS    — seller panel password
 */

import http from 'k6/http'
import { check, group, sleep } from 'k6'
import { Counter, Rate, Trend } from 'k6/metrics'
import { randomIntBetween, randomItem } from 'https://jslib.k6.io/k6-utils/1.4.0/index.js'

// ── Config ────────────────────────────────────────────────────────────────────
const BASE     = __ENV.BASE_URL      || 'http://localhost:8000'
const BOT_TOK  = __ENV.BOT_TOKEN     || 'test-bot-token'
const SHOP_ID  = __ENV.SHOP_ID       || '1'
const EMAIL    = __ENV.SELLER_EMAIL  || 'admin@example.com'
const PASS     = __ENV.SELLER_PASS   || 'changeme'

// ── Test options ──────────────────────────────────────────────────────────────
export const options = {
  scenarios: {
    // Ramp up to 100 VUs over 30s, hold for 60s, ramp down
    catalog_ramp: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '30s', target: 100  },
        { duration: '60s', target: 100  },
        { duration: '15s', target: 0    },
      ],
      tags: { scenario: 'catalog_ramp' },
    },
    // Constant spike of 50 VUs doing order creation
    order_spike: {
      executor: 'constant-vus',
      vus: 50,
      duration: '90s',
      startTime: '15s',
      tags: { scenario: 'order_spike' },
    },
    // Seller panel constant load
    seller_panel: {
      executor: 'constant-vus',
      vus: 20,
      duration: '90s',
      startTime: '15s',
      tags: { scenario: 'seller_panel' },
    },
  },
  thresholds: {
    // P95 of catalog requests must be below 500ms
    'http_req_duration{endpoint:catalog}': ['p(95)<500'],
    // P95 of order creation below 1000ms
    'http_req_duration{endpoint:order}': ['p(95)<1000'],
    // Error rate must stay below 1%
    'http_req_failed': ['rate<0.01'],
    // Seller login must always succeed
    'seller_login_ok': ['rate>0.99'],
  },
}

// ── Custom metrics ────────────────────────────────────────────────────────────
const sellerLoginOk  = new Rate('seller_login_ok')
const orderCreated   = new Counter('orders_created')
const catalogLatency = new Trend('catalog_latency_ms')

// ── Shared state ──────────────────────────────────────────────────────────────
let productIds = []

// ── Helper: bot headers ───────────────────────────────────────────────────────
function botHeaders(tgId) {
  return {
    'Content-Type':  'application/json',
    'X-Bot-Token':   BOT_TOK,
    'X-Bot-Shop-Id': SHOP_ID,
    'X-Bot-User-Id': String(tgId),
  }
}

// ── Setup: fetch product IDs ──────────────────────────────────────────────────
export function setup() {
  const headers = {
    'Content-Type': 'application/json',
    'X-Bot-Token':  BOT_TOK,
    'X-Bot-Shop-Id': SHOP_ID,
  }
  const res = http.get(`${BASE}/api/v1/products/?page=1&per_page=50`, { headers })
  if (res.status === 200) {
    const body = JSON.parse(res.body)
    const items = Array.isArray(body) ? body : (body.items || [])
    return { productIds: items.map(p => p.id).filter(Boolean) }
  }
  console.warn('Setup: could not fetch products, using empty list')
  return { productIds: [] }
}

// ── Default function — dispatches based on scenario tag ──────────────────────
export default function (data) {
  const scenario = __ENV.K6_SCENARIO_NAME || 'catalog_ramp'

  if (scenario === 'seller_panel') {
    sellerPanelFlow()
  } else if (scenario === 'order_spike') {
    orderFlow(data.productIds)
  } else {
    catalogFlow(data.productIds)
  }
}

// ── Scenario: Catalog browsing ────────────────────────────────────────────────
function catalogFlow(ids) {
  const tgId   = randomIntBetween(100000, 999999999)
  const headers = botHeaders(tgId)

  group('catalog', () => {
    // 1. List products
    const t0 = Date.now()
    const listRes = http.get(`${BASE}/api/v1/products/?page=1&per_page=20`, {
      headers,
      tags: { endpoint: 'catalog' },
    })
    catalogLatency.add(Date.now() - t0)
    check(listRes, {
      'product list 200': r => r.status === 200,
      'product list has items': r => {
        try {
          const b = JSON.parse(r.body)
          return (Array.isArray(b) ? b : b.items || []).length > 0
        } catch { return false }
      },
    })

    sleep(randomIntBetween(1, 2))

    // 2. View a random product detail
    if (ids && ids.length > 0) {
      const pid = randomItem(ids)
      const detailRes = http.get(`${BASE}/api/v1/products/${pid}`, {
        headers,
        tags: { endpoint: 'catalog' },
      })
      check(detailRes, { 'product detail 200': r => r.status === 200 })
    }

    sleep(randomIntBetween(1, 3))

    // 3. Public settings
    http.get(`${BASE}/api/v1/settings/public`, {
      headers,
      tags: { endpoint: 'catalog' },
    })
  })
}

// ── Scenario: Order flow ──────────────────────────────────────────────────────
function orderFlow(ids) {
  const tgId   = randomIntBetween(100000, 999999999)
  const headers = botHeaders(tgId)
  const jsonHeaders = { ...headers, 'Content-Type': 'application/json' }

  group('order', () => {
    // Register user
    http.post(`${BASE}/api/v1/users/register`, JSON.stringify({
      id: tgId,
      username: `k6_${tgId}`,
      first_name: 'K6',
      last_name: 'Test',
    }), { headers: jsonHeaders })

    sleep(0.5)

    // Clear cart
    http.del(`${BASE}/api/v1/cart/`, null, { headers })

    // Add a product
    if (ids && ids.length > 0) {
      const pid = randomItem(ids)
      http.post(`${BASE}/api/v1/cart/`, JSON.stringify({
        product_id: pid, quantity: 1,
      }), { headers: jsonHeaders })
    }

    sleep(0.5)

    // Create order
    const cities = ['Москва', 'Казань', 'Новосибирск', 'Екатеринбург']
    const orderRes = http.post(`${BASE}/api/v1/orders/`, JSON.stringify({
      comment: 'k6 load test order',
      delivery_address: `г. ${randomItem(cities)}, ул. Нагрузочная, д. ${randomIntBetween(1, 100)}`,
    }), {
      headers: jsonHeaders,
      tags: { endpoint: 'order' },
    })

    const orderOk = check(orderRes, {
      'order created 200/201': r => r.status === 200 || r.status === 201,
      'order has id': r => {
        try { return JSON.parse(r.body).id > 0 } catch { return false }
      },
    })
    if (orderOk) orderCreated.add(1)
  })

  sleep(randomIntBetween(2, 4))
}

// ── Scenario: Seller panel ────────────────────────────────────────────────────
function sellerPanelFlow() {
  let accessToken = null

  group('seller_login', () => {
    const loginRes = http.post(
      `${BASE}/platform/auth/login`,
      JSON.stringify({ email: EMAIL, password: PASS }),
      { headers: { 'Content-Type': 'application/json' } },
    )
    const ok = check(loginRes, {
      'seller login 200': r => r.status === 200,
      'seller has access_token': r => {
        try { return !!JSON.parse(r.body).access_token } catch { return false }
      },
    })
    sellerLoginOk.add(ok ? 1 : 0)
    if (ok) {
      try { accessToken = JSON.parse(loginRes.body).access_token } catch {}
    }
  })

  if (!accessToken) return

  const authHeaders = {
    'Authorization': `Bearer ${accessToken}`,
    'Content-Type': 'application/json',
  }

  sleep(1)

  group('seller_dashboard', () => {
    check(
      http.get(`${BASE}/api/v1/orders/?status=new&page=1&per_page=20`, { headers: authHeaders }),
      { 'orders 200': r => r.status === 200 },
    )
    sleep(0.5)
    check(
      http.get(`${BASE}/api/v1/stats/dashboard`, { headers: authHeaders }),
      { 'dashboard 200': r => r.status === 200 },
    )
    sleep(0.5)
    check(
      http.get(`${BASE}/api/v1/products/?page=1&per_page=20`, { headers: authHeaders }),
      { 'products 200': r => r.status === 200 },
    )
  })

  sleep(randomIntBetween(3, 6))
}
