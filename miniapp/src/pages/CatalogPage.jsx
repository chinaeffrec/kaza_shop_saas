import { useState, useEffect } from 'react'
import { catalog as catalogApi, getShopId } from '../api.js'
import { haptic } from '../tg.js'
import Spinner from '../components/Spinner.jsx'

function fmtPrice(kopecks) {
  return (kopecks / 100).toLocaleString('ru-RU', { style: 'currency', currency: 'RUB', maximumFractionDigits: 0 })
}

export default function CatalogPage({ navigate, shopSettings }) {
  const [categories, setCategories] = useState([])
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(true)
  const [activeCat, setActiveCat] = useState(null)   // null = все

  useEffect(() => {
    catalogApi.getAll(getShopId())
      .then(data => {
        setCategories(data.categories || [])
        setProducts(data.products || [])
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const filtered = activeCat === null
    ? products
    : products.filter(p => p.category_id === activeCat)

  function openProduct(id) {
    haptic('light')
    navigate('product', { productId: id })
  }

  if (loading) return <Spinner />

  return (
    <div className="page">
      <div className="page-header">
        <span className="page-title">{shopSettings?.shop_name || 'Магазин'}</span>
      </div>

      {/* Category chips */}
      {categories.length > 0 && (
        <div className="chips">
          <button
            className={`chip ${activeCat === null ? 'active' : ''}`}
            onClick={() => { haptic('light'); setActiveCat(null) }}>
            Все
          </button>
          {categories.map(c => (
            <button
              key={c.id}
              className={`chip ${activeCat === c.id ? 'active' : ''}`}
              onClick={() => { haptic('light'); setActiveCat(c.id) }}>
              {c.name}
            </button>
          ))}
        </div>
      )}

      {filtered.length === 0 ? (
        <div className="empty-state">
          <div className="es-icon">📭</div>
          <div className="es-text">Товаров нет</div>
        </div>
      ) : (
        <div className="product-grid">
          {filtered.map(p => (
            <div key={p.id} className="product-card" onClick={() => openProduct(p.id)}>
              {p.image_url
                ? <img src={p.image_url} alt={p.name} loading="lazy" />
                : <div className="img-placeholder">📦</div>
              }
              <div className="card-body">
                <div className="card-name">{p.name}</div>
                <div className="card-price">{fmtPrice(p.price)}</div>
                {!p.in_stock && <div className="card-oos">Нет в наличии</div>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
