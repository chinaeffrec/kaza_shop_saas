import { useState, useEffect } from 'react'
import { orders as ordersApi } from '../api.js'
import Spinner from '../components/Spinner.jsx'

function fmtPrice(kopecks) {
  return (kopecks / 100).toLocaleString('ru-RU', { style: 'currency', currency: 'RUB', maximumFractionDigits: 0 })
}

const STATUS_COLORS = {
  new:       '#2481cc',
  paid:      '#1976d2',
  confirmed: '#43a047',
  assembled: '#f57c00',
  shipped:   '#6d4c41',
  delivered: '#388e3c',
  cancelled: '#e53935',
  returned:  '#757575',
}

export default function OrdersPage() {
  const [orderList, setOrderList] = useState([])
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState(null)

  useEffect(() => {
    ordersApi.list()
      .then(setOrderList)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <Spinner />

  if (orderList.length === 0) {
    return (
      <div className="page">
        <div className="page-header">
          <span className="page-title">Мои заказы</span>
        </div>
        <div className="empty-state">
          <div className="es-icon">📦</div>
          <div className="es-text">Заказов пока нет</div>
        </div>
      </div>
    )
  }

  return (
    <div className="page">
      <div className="page-header">
        <span className="page-title">Мои заказы</span>
      </div>

      {orderList.map(o => (
        <div key={o.id} className="order-card" onClick={() => setExpanded(expanded === o.id ? null : o.id)}>
          <div className="oc-head">
            <span className="oc-id">Заказ #{o.id}</span>
            <span className="oc-status"
              style={{ background: STATUS_COLORS[o.status] || '#2481cc' }}>
              {o.status_label}
            </span>
          </div>

          <div className="oc-total">{fmtPrice(o.total)}</div>
          <div className="oc-date">{o.created_at?.slice(0, 10)}</div>

          {expanded === o.id && o.items?.length > 0 && (
            <div style={{ marginTop: 10, borderTop: '1px solid var(--tg-theme-bg-color)', paddingTop: 10 }}>
              {o.items.map((it, i) => (
                <div key={i} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, marginBottom: 4 }}>
                  <span>{it.name} × {it.quantity}</span>
                  <span>{fmtPrice(it.sum)}</span>
                </div>
              ))}
              {o.delivery_address && (
                <div style={{ fontSize: 12, marginTop: 6, color: 'var(--tg-theme-hint-color)' }}>
                  📍 {o.delivery_address}
                </div>
              )}
              {o.payment_status && (
                <div style={{ fontSize: 12, marginTop: 4, color: 'var(--tg-theme-hint-color)' }}>
                  💳 {o.payment_status}
                </div>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
