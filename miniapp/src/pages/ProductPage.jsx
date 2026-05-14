import { useState, useEffect } from 'react'
import { catalog as catalogApi, reviews as reviewsApi, cart as cartApi, getShopId } from '../api.js'
import { showMainButton, hideMainButton, setMainButtonLoading, showBackButton, hideBackButton, haptic } from '../tg.js'
import Spinner from '../components/Spinner.jsx'

function fmtPrice(kopecks) {
  return (kopecks / 100).toLocaleString('ru-RU', { style: 'currency', currency: 'RUB', maximumFractionDigits: 0 })
}

function Stars({ value, size = 16 }) {
  const full  = Math.round(value)
  return (
    <span style={{ fontSize: size, lineHeight: 1 }}>
      {[1,2,3,4,5].map(i => (
        <span key={i} style={{ color: i <= full ? '#f59e0b' : 'var(--tg-theme-hint-color)' }}>★</span>
      ))}
    </span>
  )
}

function ReviewCard({ review }) {
  const date = new Date(review.created_at).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' })
  return (
    <div style={{ padding: '12px 0', borderBottom: '1px solid var(--tg-theme-secondary-bg-color, #f3f4f6)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
        <Stars value={review.rating} size={14} />
        <span style={{ fontSize: 12, color: 'var(--tg-theme-hint-color)' }}>{date}</span>
      </div>
      {review.text && (
        <p style={{ margin: 0, fontSize: 14, color: 'var(--tg-theme-text-color)', lineHeight: 1.4 }}>
          {review.text}
        </p>
      )}
    </div>
  )
}

export default function ProductPage({ navigate, setCartCount, productId }) {
  const [product, setProduct]     = useState(null)
  const [loading, setLoading]     = useState(true)
  const [qty, setQty]             = useState(1)
  const [adding, setAdding]       = useState(false)

  // Reviews state
  const [stats, setStats]           = useState(null)
  const [reviewItems, setReviewItems] = useState([])
  const [revPage, setRevPage]         = useState(1)
  const [revTotal, setRevTotal]       = useState(0)
  const [revLoading, setRevLoading]   = useState(false)
  const shopId = getShopId()

  useEffect(() => {
    catalogApi.getProduct(productId, shopId)
      .then(setProduct)
      .catch(console.error)
      .finally(() => setLoading(false))

    // Load review stats (non-blocking)
    reviewsApi.getStats(productId, shopId)
      .then(setStats)
      .catch(() => {})
  }, [productId, shopId])

  // Load reviews
  useEffect(() => {
    if (!shopId) return
    setRevLoading(true)
    reviewsApi.getByProduct(productId, shopId, revPage)
      .then(data => {
        setReviewItems(prev => revPage === 1 ? data.items : [...prev, ...data.items])
        setRevTotal(data.total)
      })
      .catch(() => {})
      .finally(() => setRevLoading(false))
  }, [productId, shopId, revPage])

  // Telegram BackButton
  useEffect(() => {
    showBackButton(() => navigate('catalog'))
    return () => hideBackButton()
  }, [navigate])

  // Telegram MainButton — «Добавить в корзину»
  useEffect(() => {
    if (!product || !product.in_stock) return
    const handler = async () => {
      setMainButtonLoading(true)
      setAdding(true)
      haptic('medium')
      try {
        const updated = await cartApi.add(product.id, qty)
        const count = updated.items?.reduce((s, i) => s + i.quantity, 0) ?? 0
        setCartCount(count)
        haptic('success')
        navigate('cart')
      } catch (e) {
        console.error(e)
        haptic('error')
      } finally {
        setMainButtonLoading(false)
        setAdding(false)
      }
    }
    showMainButton(`Добавить ${qty > 1 ? `(${qty}) ` : ''}— ${fmtPrice(product.price * qty)}`, handler)
    return () => hideMainButton()
  }, [product, qty, navigate, setCartCount])

  if (loading) return <Spinner />
  if (!product) return (
    <div className="empty-state">
      <div className="es-icon">🔍</div>
      <div className="es-text">Товар не найден</div>
    </div>
  )

  const hasMore = reviewItems.length < revTotal

  return (
    <div className="page product-detail">
      {product.image_url
        ? <img className="pd-image" src={product.image_url} alt={product.name} />
        : <div className="pd-image-placeholder">📦</div>
      }
      <div className="pd-body">
        <div className="pd-name">{product.name}</div>

        {/* Rating summary */}
        {stats && stats.count > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, margin: '4px 0 8px' }}>
            <Stars value={stats.average} size={15} />
            <span style={{ fontSize: 13, color: 'var(--tg-theme-hint-color)' }}>
              {stats.average.toFixed(1)} · {stats.count} отзыв{stats.count === 1 ? '' : stats.count < 5 ? 'а' : 'ов'}
            </span>
          </div>
        )}

        <div className="pd-price">{fmtPrice(product.price)}</div>
        {product.description && <div className="pd-desc">{product.description}</div>}

        {!product.in_stock ? (
          <div style={{ marginTop: 16, color: 'var(--tg-theme-hint-color)', fontSize: 14 }}>
            Нет в наличии
          </div>
        ) : (
          <div className="qty-row">
            <button className="qty-btn"
              onClick={() => { haptic('light'); setQty(q => Math.max(1, q - 1)) }}
              disabled={qty <= 1}>−</button>
            <span className="qty-val">{qty}</span>
            <button className="qty-btn"
              onClick={() => { haptic('light'); setQty(q => q + 1) }}>+</button>
            <span style={{ marginLeft: 8, color: 'var(--tg-theme-hint-color)', fontSize: 13 }}>шт.</span>
          </div>
        )}

        {/* Reviews section */}
        {revTotal > 0 && (
          <div style={{ marginTop: 24 }}>
            <h3 style={{ margin: '0 0 12px', fontSize: 15, fontWeight: 600, color: 'var(--tg-theme-text-color)' }}>
              Отзывы ({revTotal})
            </h3>
            {reviewItems.map(r => <ReviewCard key={r.id} review={r} />)}
            {hasMore && (
              <button
                onClick={() => setRevPage(p => p + 1)}
                disabled={revLoading}
                style={{
                  marginTop: 12, width: '100%', padding: '10px',
                  background: 'none', border: '1px solid var(--tg-theme-button-color, #3b82f6)',
                  color: 'var(--tg-theme-button-color, #3b82f6)',
                  borderRadius: 8, fontSize: 14, cursor: 'pointer',
                }}
              >
                {revLoading ? '…' : 'Показать ещё'}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
