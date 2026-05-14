// Пустая строка = относительные URL → работает через nginx на любом сервере
// Для локальной разработки задай VITE_API_URL=http://localhost:8000 в .env
const BASE = import.meta.env.VITE_API_URL ?? ''
const TOKEN_KEY = 'platform_token'

function buildQuery(params) {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      query.set(key, value)
    }
  })
  const qs = query.toString()
  return qs ? `?${qs}` : ''
}

async function req(method, path, body, isFormData = false, extraHeaders = {}) {
  const opts = { method, headers: { ...extraHeaders } }
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) opts.headers['Authorization'] = `Bearer ${token}`

  if (body) {
    if (isFormData) { opts.body = body }
    else { opts.headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(body) }
  }
  const res = await fetch(`${BASE}${path}`, opts)
  if (res.status === 401) {
    localStorage.removeItem(TOKEN_KEY)
    window.location.reload()
    throw new Error('Unauthorized')
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    const detail = Array.isArray(err.detail)
      ? err.detail.map(d => d.msg || JSON.stringify(d)).join('; ')
      : (err.detail || 'Request failed')
    throw new Error(String(detail))
  }
  if (res.status === 204) return null
  return res.json()
}

async function downloadFile(path, fallbackName) {
  const token = localStorage.getItem(TOKEN_KEY)
  const res = await fetch(`${BASE}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (res.status === 401) {
    localStorage.removeItem(TOKEN_KEY)
    window.location.reload()
    throw new Error('Unauthorized')
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Download failed')
  }

  const blob = await res.blob()
  const contentDisposition = res.headers.get('content-disposition') || ''
  const matchedName = contentDisposition.match(/filename="?([^"]+)"?/)
  const filename = matchedName?.[1] || fallbackName

  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}

function uploadFile(path, file) {
  const fd = new FormData()
  fd.append('file', file)
  return req('POST', path, fd, true)
}

export const api = {
  BASE,
  TOKEN_KEY,

  // ── Platform Auth ────────────────────────────────────────────────────────────
  login: (email, password) =>
    req('POST', '/platform/auth/login', { email, password }),
  me: () => req('GET', '/platform/auth/me'),
  logout: (refreshToken) =>
    req('POST', '/platform/auth/logout', { refresh_token: refreshToken }),
  changePassword: (currentPassword, newPassword) =>
    req('PATCH', '/platform/auth/password', {
      current_password: currentPassword,
      new_password: newPassword,
    }),

  // ── Platform Users (super_admin) ─────────────────────────────────────────────
  getPlatformUsers: () => req('GET', '/platform/auth/users'),
  createPlatformUser: (email, password, isSuperAdmin = false) =>
    req('POST', '/platform/auth/users', { email, password, is_super_admin: isSuperAdmin }),
  deactivatePlatformUser: (id) =>
    req('PATCH', `/platform/auth/users/${id}/deactivate`),

  // ── Platform Shops (super_admin) ─────────────────────────────────────────────
  getShops: (page = 1, perPage = 20, filters = {}) =>
    req('GET', `/platform/shops/${buildQuery({ page, per_page: perPage, ...filters })}`),
  createShop: (data) => req('POST', '/platform/shops/', data),
  getShop: (id) => req('GET', `/platform/shops/${id}`),
  updateShop: (id, data) => req('PATCH', `/platform/shops/${id}`, data),
  deleteShop: (id) => req('DELETE', `/platform/shops/${id}`),
  setShopBotToken: (id, botToken) =>
    req('PUT', `/platform/shops/${id}/bot-token`, { bot_token: botToken }),
  deleteShopBotToken: (id) => req('DELETE', `/platform/shops/${id}/bot-token`),
  setShopStatus: (id, status) =>
    req('PATCH', `/platform/shops/${id}/status`, { status }),
  setShopPlan: (id, plan, planExpiresAt = null) =>
    req('PATCH', `/platform/shops/${id}/plan`, { plan, plan_expires_at: planExpiresAt }),
  assignShopOwner: (id, ownerId) =>
    req('POST', `/platform/shops/${id}/assign`, { owner_id: ownerId }),
  getShopStats: (id) => req('GET', `/platform/shops/${id}/stats`),

  // ── Catalog ──────────────────────────────────────────────────────────────────
  getCategories:       () => req('GET', '/api/v1/catalog/categories'),
  getAllSubcategories:  () => req('GET', '/api/v1/catalog/subcategories'),
  getSubcategories:    (id) => req('GET', `/api/v1/catalog/categories/${id}/subcategories`),
  reloadCache:         () => req('POST', '/api/v1/catalog/cache/reload'),

  // ── Products ─────────────────────────────────────────────────────────────────
  getProducts: (page = 1, perPage = 20, filters = {}) =>
    req('GET', `/api/v1/products/${buildQuery({ page, per_page: perPage, ...filters })}`),
  createProduct:    (d) => req('POST', '/api/v1/products/', d),
  updateProduct:    (id, d) => req('PATCH', `/api/v1/products/${id}`, d),
  deleteProduct:    (id) => req('DELETE', `/api/v1/products/${id}`),
  bulkDeleteProducts: (ids) => req('POST', '/api/v1/products/bulk-delete', { ids }),
  uploadPhotoSlot:  (id, slot, file) => uploadFile(`/api/v1/products/${id}/photo/${slot}`, file),
  deletePhotoSlot:  (id, slot) => req('DELETE', `/api/v1/products/${id}/photo/${slot}`),
  toggleActive:     (id, is_active) => req('PATCH', `/api/v1/products/${id}`, { is_active }),

  // ── Import ───────────────────────────────────────────────────────────────────
  importXlsx: (file) => uploadFile('/api/v1/import/products', file),

  // ── Orders ───────────────────────────────────────────────────────────────────
  getOrders:        (status, page = 1, perPage = 20) => req('GET', `/api/v1/orders/${buildQuery({ status, page, per_page: perPage })}`),
  getOrder:         (id) => req('GET', `/api/v1/orders/${id}`),
  getOrderStatuses: () => req('GET', '/api/v1/orders/statuses'),
  updateOrderStatus:(id, status, comment) => req('PATCH', `/api/v1/orders/${id}/status`, { status, comment }),
  generateReceipt:  (id) => req('POST', `/api/v1/orders/${id}/receipt`),

  // ── Stats ────────────────────────────────────────────────────────────────────
  getDashboard: (from, to) => req('GET', `/api/v1/stats/dashboard${buildQuery({ date_from: from, date_to: to })}`),
  getAnalytics: (from, to, period = 'day') =>
    req('GET', `/api/v1/stats/analytics${buildQuery({ date_from: from, date_to: to, period })}`),
  getStats:     (from, to) => req('GET', `/api/v1/stats/products${buildQuery({ date_from: from, date_to: to })}`),
  trackReturn:  (pid) => req('POST', `/api/v1/stats/products/${pid}/return`),
  exportCustomers: () => downloadFile('/api/v1/stats/customers/export', `customers_${new Date().toISOString().slice(0,10)}.xlsx`),

  exportDashboard: (from, to) => {
    const token = localStorage.getItem(TOKEN_KEY)
    const qs = buildQuery({ date_from: from || null, date_to: to || null })
    const url = `${BASE}/api/v1/stats/export${qs}`
    return fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      .then(r => {
        if (!r.ok) throw new Error('Export failed')
        return r.blob()
      })
      .then(blob => {
        const a = document.createElement('a')
        a.href = URL.createObjectURL(blob)
        a.download = `stats_orders.xlsx`
        a.click()
        URL.revokeObjectURL(a.href)
      })
  },

  exportStats: (from, to) => {
    const token = localStorage.getItem(TOKEN_KEY)
    const qs = buildQuery({ date_from: from || null, date_to: to || null })
    const url = `${BASE}/api/v1/stats/products/export${qs}`
    return fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      .then(r => {
        if (!r.ok) throw new Error('Export failed')
        return r.blob()
      })
      .then(blob => {
        const a = document.createElement('a')
        a.href = URL.createObjectURL(blob)
        a.download = `stats_products.xlsx`
        a.click()
        URL.revokeObjectURL(a.href)
      })
  },

  // ── Settings ─────────────────────────────────────────────────────────────────
  getSettings:    () => req('GET', '/api/v1/settings/'),
  updateSettings: (d) => req('PATCH', '/api/v1/settings/', d),
  downloadLogs:   () => downloadFile('/api/v1/settings/logs/download', 'kaza-shop-logs.zip'),
  exportDb:    () => downloadFile(`/api/v1/settings/db-export`,    `kaza_db_${new Date().toISOString().slice(0,10)}.json`),
  importDb: (file) => {
    // A5: разрушительная операция требует явного заголовка подтверждения
    const fd = new FormData()
    fd.append('file', file)
    return req('POST', '/api/v1/settings/db-import', fd, true, { 'X-Confirm-Destructive': 'yes' })
  },
  exportMedia: () => downloadFile(`/api/v1/settings/media-export`, `kaza_media_${new Date().toISOString().slice(0,10)}.zip`),
  importMedia: (file) => {
    const fd = new FormData()
    fd.append('file', file)
    return req('POST', '/api/v1/settings/media-import', fd, true, { 'X-Confirm-Destructive': 'yes' })
  },

  // ── FAQ ──────────────────────────────────────────────────────────────────────
  getFaq:    () => req('GET', '/api/v1/faq/'),
  createFaq: (d) => req('POST', '/api/v1/faq/', d),
  updateFaq: (id, d) => req('PATCH', `/api/v1/faq/${id}`, d),
  deleteFaq: (id) => req('DELETE', `/api/v1/faq/${id}`),

  // ── CDEK ─────────────────────────────────────────────────────────────────────
  searchCdekCities: (q) => req('GET', `/api/v1/cdek/cities?q=${encodeURIComponent(q)}`),
  getCdekPvz: (cityCode) => req('GET', `/api/v1/cdek/pvz?city_code=${cityCode}`),
  calcCdekTariff: (toCityCode, weightGrams = 500) =>
    req('POST', '/api/v1/cdek/calculate', { to_city_code: toCityCode, weight_grams: weightGrams }),
  createCdekShipment: (orderId, data) =>
    req('POST', `/api/v1/cdek/orders/${orderId}/ship`, data),
  getCdekStatus: (orderId) =>
    req('GET', `/api/v1/cdek/orders/${orderId}/status`),

  // ── Promo Codes ──────────────────────────────────────────────────────────────
  getPromos: () => req('GET', '/api/v1/promos/'),
  createPromo: (data) => req('POST', '/api/v1/promos/', data),
  updatePromo: (id, data) => req('PATCH', `/api/v1/promos/${id}`, data),
  deletePromo: (id) => req('DELETE', `/api/v1/promos/${id}`),
  validatePromo: (code, cartTotal) =>
    req('POST', '/api/v1/promos/validate', { code, cart_total: cartTotal }),

  // ── YooKassa ─────────────────────────────────────────────────────────────────
  createPayment: (orderId) => req('POST', `/api/v1/yookassa/payments/${orderId}`),
  getPaymentStatus: (orderId) => req('GET', `/api/v1/yookassa/payments/${orderId}`),
  createRefund: (orderId) => req('POST', `/api/v1/yookassa/payments/${orderId}/refund`),

  // ── Customers (CRM) ──────────────────────────────────────────────────────────
  getCustomers: (page = 1, perPage = 30, search = '') =>
    req('GET', `/api/v1/customers/${buildQuery({ page, per_page: perPage, search: search || undefined })}`),
  getCustomer: (id) => req('GET', `/api/v1/customers/${id}`),
  updateCustomer: (id, data) => req('PATCH', `/api/v1/customers/${id}`, data),
  getCustomerOrders: (id, page = 1, perPage = 20) =>
    req('GET', `/api/v1/customers/${id}/orders${buildQuery({ page, per_page: perPage })}`),

  // ── Product Variants ──────────────────────────────────────────────────────────
  getVariants: (productId) => req('GET', `/api/v1/products/${productId}/variants`),
  createVariant: (productId, data) => req('POST', `/api/v1/products/${productId}/variants`, data),
  updateVariant: (productId, variantId, data) =>
    req('PATCH', `/api/v1/products/${productId}/variants/${variantId}`, data),
  deleteVariant: (productId, variantId) =>
    req('DELETE', `/api/v1/products/${productId}/variants/${variantId}`),
  setProductStock: (productId, stock) =>
    req('PATCH', `/api/v1/products/${productId}/stock`, { stock }),

  // ── Shop Members ─────────────────────────────────────────────────────────────
  getMembers:    (shopId) => req('GET', `/platform/shops/${shopId}/members`),
  inviteMember:  (shopId, email, role) =>
    req('POST', `/platform/shops/${shopId}/members`, { email, role }),
  updateMemberRole: (shopId, userId, role) =>
    req('PATCH', `/platform/shops/${shopId}/members/${userId}`, { role }),
  removeMember:  (shopId, userId) =>
    req('DELETE', `/platform/shops/${shopId}/members/${userId}`),

  // ── Audit Logs ───────────────────────────────────────────────────────────────
  // Platform-wide audit (super_admin only)
  getAuditLogs: (filters = {}) =>
    req('GET', `/platform/audit-logs${buildQuery(filters)}`),
  // Shop-scoped audit (owner+ of that shop)
  getShopAuditLogs: (shopId, filters = {}) =>
    req('GET', `/platform/shops/${shopId}/audit-logs${buildQuery(filters)}`),

  // ── Billing ──────────────────────────────────────────────────────────────────
  getBillingPlans:       () => req('GET', '/api/v1/billing/plans'),
  getBillingSubscription:() => req('GET', '/api/v1/billing/subscription'),
  getBillingUsage:       () => req('GET', '/api/v1/billing/usage'),
  assignPlan: (shopId, planSlug, expiresAt = null) =>
    req('PATCH', '/api/v1/billing/subscription', { shop_id: shopId, plan_slug: planSlug, expires_at: expiresAt }),

  // ── Reviews ──────────────────────────────────────────────────────────────────
  getReviews: (status = 'all', productId = null, page = 1, perPage = 30) =>
    req('GET', `/api/v1/reviews/${buildQuery({ status, product_id: productId, page, per_page: perPage })}`),
  moderateReview: (id, data) => req('PATCH', `/api/v1/reviews/${id}`, data),
  deleteReview: (id) => req('DELETE', `/api/v1/reviews/${id}`),

  // ── Platform Control (super_admin) ───────────────────────────────────────────
  getMonitoring:     () => req('GET', '/platform/monitoring'),
  getHealthDetailed: () => req('GET', '/platform/health/detailed'),
  impersonateShop:   (shopId) => req('POST', `/platform/shops/${shopId}/impersonate`),

  getBroadcasts:        ()   => req('GET', '/platform/broadcast'),
  getActiveBroadcasts:  ()   => req('GET', '/platform/broadcast/active'),
  createBroadcast:      (data) => req('POST', '/platform/broadcast', data),
  deactivateBroadcast:  (id) => req('PATCH', `/platform/broadcast/${id}/deactivate`),
  deleteBroadcast:      (id) => req('DELETE', `/platform/broadcast/${id}`),

  getMaintenance:  ()     => req('GET', '/platform/maintenance'),
  setMaintenance:  (data) => req('POST', '/platform/maintenance', data),

  getFeatureFlags:    ()      => req('GET', '/platform/feature-flags'),
  upsertFeatureFlag:  (data)  => req('POST', '/platform/feature-flags', data),
  deleteFeatureFlag:  (key)   => req('DELETE', `/platform/feature-flags/${encodeURIComponent(key)}`),

  // ── Profile & 2FA ────────────────────────────────────────────────────────────
  getProfile:     ()      => req('GET', '/api/v1/profile'),
  updateProfile:  (data)  => req('PATCH', '/api/v1/profile', data),
  setup2FA:       ()      => req('POST', '/api/v1/profile/2fa/setup'),
  verify2FA:      (code)  => req('POST', '/api/v1/profile/2fa/verify', { code }),
  disable2FA:     ()      => req('DELETE', '/api/v1/profile/2fa'),

  // ── 2FA login challenge ──────────────────────────────────────────────────────
  verify2FALogin: (challengeToken, totpCode) =>
    req('POST', '/platform/auth/2fa/verify', { challenge_token: challengeToken, totp_code: totpCode }),
}
