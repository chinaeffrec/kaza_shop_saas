import { useState, useEffect, useCallback } from 'react'
import { initTelegramApp, getInitData } from './tg.js'
import { auth as authApi, settings as settingsApi, setToken, setShopId, getShopId } from './api.js'
import Spinner from './components/Spinner.jsx'
import CatalogPage from './pages/CatalogPage.jsx'
import ProductPage from './pages/ProductPage.jsx'
import CartPage from './pages/CartPage.jsx'
import CheckoutPage from './pages/CheckoutPage.jsx'
import OrdersPage from './pages/OrdersPage.jsx'

// shop_id читается из query-параметров URL (передаётся ботом в WebApp button URL)
function getShopIdFromUrl() {
  const params = new URLSearchParams(window.location.search)
  return parseInt(params.get('shop_id') || '1', 10)
}

export default function App() {
  const [page, setPage] = useState('catalog')   // catalog | product | cart | checkout | orders
  const [pageParams, setPageParams] = useState({})
  const [ready, setReady] = useState(false)
  const [error, setError] = useState(null)
  const [shopSettings, setShopSettings] = useState({})
  const [cartCount, setCartCount] = useState(0)

  const navigate = useCallback((to, params = {}) => {
    setPage(to)
    setPageParams(params)
  }, [])

  useEffect(() => {
    initTelegramApp()
    const shopId = getShopIdFromUrl()
    setShopId(shopId)

    async function init() {
      try {
        // Загружаем публичные настройки магазина
        const cfg = await settingsApi.get(shopId)
        setShopSettings(cfg)

        // Аутентификация через Telegram initData
        const initData = getInitData()

        if (!initData) {
          // В браузере без Telegram — показываем без авторизации (для разработки)
          console.warn('No initData — running in browser mode without auth')
          setReady(true)
          return
        }

        const result = await authApi.login(initData, shopId)
        setToken(result.token)
        setReady(true)
      } catch (e) {
        console.error('Init failed:', e)
        setError(e.message)
      }
    }

    init()
  }, [])

  if (error) {
    return (
      <div style={{ padding: 24, textAlign: 'center' }}>
        <div style={{ fontSize: 32, marginBottom: 12 }}>⚠️</div>
        <div style={{ fontSize: 15, marginBottom: 8 }}>Ошибка запуска</div>
        <div style={{ fontSize: 13, color: 'var(--tg-theme-hint-color)' }}>{error}</div>
      </div>
    )
  }

  if (!ready) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh' }}>
        <Spinner />
      </div>
    )
  }

  const commonProps = { navigate, shopSettings, setCartCount }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      {/* Page content */}
      <div style={{ flex: 1 }}>
        {page === 'catalog' && <CatalogPage {...commonProps} />}
        {page === 'product' && <ProductPage {...commonProps} productId={pageParams.productId} />}
        {page === 'cart' && <CartPage {...commonProps} />}
        {page === 'checkout' && <CheckoutPage {...commonProps} />}
        {page === 'orders' && <OrdersPage {...commonProps} />}
      </div>

      {/* Bottom navigation */}
      <nav className="bottom-nav">
        <button className={`nav-btn ${page === 'catalog' ? 'active' : ''}`}
          onClick={() => navigate('catalog')}>
          <span className="icon">🗂</span>
          Каталог
        </button>
        <button className={`nav-btn ${page === 'cart' ? 'active' : ''}`}
          onClick={() => navigate('cart')}>
          <span className="icon">🛒{cartCount > 0 ? ` ${cartCount}` : ''}</span>
          Корзина
        </button>
        <button className={`nav-btn ${page === 'orders' ? 'active' : ''}`}
          onClick={() => navigate('orders')}>
          <span className="icon">📦</span>
          Заказы
        </button>
      </nav>
    </div>
  )
}
