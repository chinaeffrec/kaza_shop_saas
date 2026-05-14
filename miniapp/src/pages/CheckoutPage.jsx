import { useState, useEffect } from 'react'
import { cart as cartApi, orders as ordersApi } from '../api.js'
import { showMainButton, hideMainButton, setMainButtonLoading, showBackButton, hideBackButton, haptic } from '../tg.js'
import Spinner from '../components/Spinner.jsx'

function fmtPrice(kopecks) {
  return (kopecks / 100).toLocaleString('ru-RU', { style: 'currency', currency: 'RUB', maximumFractionDigits: 0 })
}

export default function CheckoutPage({ navigate, setCartCount }) {
  const [cartData, setCartData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [placing, setPlacing] = useState(false)
  const [form, setForm] = useState({ delivery_address: '', comment: '', promo_code: '' })
  const [done, setDone] = useState(null)   // { id, total } after success

  useEffect(() => {
    cartApi.get()
      .then(setCartData)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  // BackButton
  useEffect(() => {
    if (done) return
    showBackButton(() => navigate('cart'))
    return () => hideBackButton()
  }, [navigate, done])

  // MainButton
  useEffect(() => {
    if (done || !cartData || cartData.items?.length === 0) {
      hideMainButton()
      return
    }
    showMainButton('Оформить заказ', handlePlace)
    return () => hideMainButton()
  }, [cartData, done, form])

  async function handlePlace() {
    setPlacing(true)
    setMainButtonLoading(true)
    haptic('medium')
    try {
      const order = await ordersApi.create({
        comment: form.comment || null,
        delivery_address: form.delivery_address || null,
        promo_code: form.promo_code || null,
      })
      setCartCount(0)
      setDone({ id: order.id, total: order.total })
      haptic('success')
      hideMainButton()
      hideBackButton()
    } catch (e) {
      haptic('error')
      alert('Ошибка: ' + e.message)
    } finally {
      setPlacing(false)
      setMainButtonLoading(false)
    }
  }

  if (loading) return <Spinner />

  // Success screen
  if (done) {
    return (
      <div className="page">
        <div style={{ padding: 32, textAlign: 'center' }}>
          <div style={{ fontSize: 56, marginBottom: 16 }}>✅</div>
          <div style={{ fontSize: 20, fontWeight: 700, marginBottom: 8 }}>
            Заказ #{done.id} оформлен!
          </div>
          <div style={{ fontSize: 15, color: 'var(--tg-theme-hint-color)', marginBottom: 28 }}>
            Сумма: {fmtPrice(done.total)}
          </div>
          <button className="tg-btn" onClick={() => navigate('orders')}>
            Мои заказы
          </button>
          <button className="tg-btn"
            style={{ marginTop: 10, background: 'var(--tg-theme-secondary-bg-color)', color: 'var(--tg-theme-text-color)' }}
            onClick={() => navigate('catalog')}>
            Продолжить покупки
          </button>
        </div>
      </div>
    )
  }

  const items = cartData?.items ?? []

  return (
    <div className="page">
      <div className="page-header">
        <span className="page-title">Оформление заказа</span>
      </div>

      <div className="checkout-form">
        {/* Summary */}
        <div className="checkout-summary">
          {items.map(it => (
            <div key={it.product_id} className="cs-row">
              <span>{it.name} × {it.quantity}</span>
              <span>{fmtPrice(it.sum)}</span>
            </div>
          ))}
          <div className="cs-total">
            <span>Итого</span>
            <span>{fmtPrice(cartData?.total ?? 0)}</span>
          </div>
        </div>

        {/* Address */}
        <div className="form-field">
          <label>Адрес доставки (необязательно)</label>
          <input
            value={form.delivery_address}
            onChange={e => setForm(f => ({ ...f, delivery_address: e.target.value }))}
            placeholder="ул. Примерная, д. 1, кв. 5"
          />
        </div>

        {/* Comment */}
        <div className="form-field">
          <label>Комментарий к заказу (необязательно)</label>
          <textarea
            value={form.comment}
            onChange={e => setForm(f => ({ ...f, comment: e.target.value }))}
            placeholder="Особые пожелания, время доставки…"
          />
        </div>

        {/* Promo */}
        <div className="form-field">
          <label>Промокод</label>
          <input
            value={form.promo_code}
            onChange={e => setForm(f => ({ ...f, promo_code: e.target.value.toUpperCase() }))}
            placeholder="СКИДКА10"
          />
        </div>
      </div>
    </div>
  )
}
