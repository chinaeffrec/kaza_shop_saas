import { useState, useEffect } from 'react'
import { cart as cartApi } from '../api.js'
import { showMainButton, hideMainButton, haptic } from '../tg.js'
import Spinner from '../components/Spinner.jsx'

function fmtPrice(kopecks) {
  return (kopecks / 100).toLocaleString('ru-RU', { style: 'currency', currency: 'RUB', maximumFractionDigits: 0 })
}

export default function CartPage({ navigate, setCartCount }) {
  const [cartData, setCartData] = useState(null)
  const [loading, setLoading] = useState(true)

  async function loadCart() {
    try {
      const data = await cartApi.get()
      setCartData(data)
      setCartCount(data.items?.reduce((s, i) => s + i.quantity, 0) ?? 0)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadCart() }, [])

  // MainButton — перейти к оформлению
  useEffect(() => {
    if (!cartData || cartData.items?.length === 0) {
      hideMainButton()
      return
    }
    showMainButton(`Оформить заказ — ${fmtPrice(cartData.total)}`, () => {
      haptic('medium')
      navigate('checkout')
    })
    return () => hideMainButton()
  }, [cartData, navigate])

  async function updateQty(productId, delta, currentQty) {
    const newQty = currentQty + delta
    haptic('light')
    try {
      let updated
      if (newQty <= 0) {
        updated = await cartApi.remove(productId)
      } else {
        updated = await cartApi.update(productId, newQty)
      }
      setCartData(updated)
      setCartCount(updated.items?.reduce((s, i) => s + i.quantity, 0) ?? 0)
    } catch (e) { console.error(e) }
  }

  if (loading) return <Spinner />

  const items = cartData?.items ?? []

  if (items.length === 0) {
    return (
      <div className="page">
        <div className="page-header">
          <span className="page-title">Корзина</span>
        </div>
        <div className="empty-state">
          <div className="es-icon">🛒</div>
          <div className="es-text">Корзина пуста</div>
        </div>
      </div>
    )
  }

  return (
    <div className="page">
      <div className="page-header">
        <span className="page-title">Корзина</span>
      </div>

      <div className="cart-list">
        {items.map(item => (
          <div key={item.product_id} className="cart-item">
            {item.image_url
              ? <img src={item.image_url} alt={item.name} />
              : <div className="ci-img-ph">📦</div>
            }
            <div className="ci-info">
              <div className="ci-name">{item.name}</div>
              <div className="ci-price">{fmtPrice(item.price)} × {item.quantity} = {fmtPrice(item.sum)}</div>
            </div>
            <div className="ci-qty">
              <button className="ci-qty-btn"
                onClick={() => updateQty(item.product_id, -1, item.quantity)}>−</button>
              <span style={{ minWidth: 20, textAlign: 'center', fontWeight: 600 }}>{item.quantity}</span>
              <button className="ci-qty-btn"
                onClick={() => updateQty(item.product_id, +1, item.quantity)}>+</button>
            </div>
          </div>
        ))}
      </div>

      <div className="cart-total">
        <span>Итого</span>
        <span>{fmtPrice(cartData.total)}</span>
      </div>
    </div>
  )
}
