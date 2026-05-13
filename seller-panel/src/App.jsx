import { useState, useEffect } from 'react'
import { api } from './api.js'
import LoginPage from './pages/LoginPage.jsx'
import ProductsPage from './pages/ProductsPage.jsx'
import OrdersPage from './pages/OrdersPage.jsx'
import ImportPage from './pages/ImportPage.jsx'
import StatsPage from './pages/StatsPage.jsx'
import SettingsPage from './pages/SettingsPage.jsx'
import s from './App.module.css'

const NAV = [
  { id: 'products', label: '📦 Товары' },
  { id: 'orders', label: '🧾 Заказы', orderBadge: true },
  { id: 'stats',    label: '📊 Статистика' },
  { id: 'import',   label: '📥 Импорт' },
  { id: 'settings', label: '⚙️ Настройки' },
]

const PAGE_STORAGE_KEY = 'seller_active_page'

function getInitialPage() {
  const savedPage = localStorage.getItem(PAGE_STORAGE_KEY)
  return NAV.some(item => item.id === savedPage) ? savedPage : 'products'
}

export default function App() {
  const [authed, setAuthed]         = useState(false)
  const [authChecked, setChecked]   = useState(false)
  const [adminLogin, setAdminLogin] = useState('')
  const [page, setPage]             = useState(getInitialPage)
  const [shopName, setShopName]     = useState('Kaza Shop')
  const [statsState, setStatsState] = useState({ dateFrom:'', dateTo:'', stats:[], products:{}, sort:'ordered' })
  const [newOrders, setNewOrders] = useState(0)

  useEffect(() => {
    const token = localStorage.getItem('admin_token')
    if (!token) {
      setChecked(true)
      return
    }

    api.me()
      .then(d => {
        setAuthed(true)
        setAdminLogin(d.login)
        return api.getSettings()
      })
      .then(cfg => {
        setShopName(cfg?.shop_name || 'Kaza Shop')
      })
      .catch(() => {
        localStorage.removeItem('admin_token')
      })
      .finally(() => setChecked(true))
  }, [])

  useEffect(() => {
    if (!authed) {
      setNewOrders(0)
      document.title = 'Kaza Shop'
      return
    }

    let cancelled = false
    const pollOrders = async () => {
      try {
        const res = await api.getOrders('new', 1, 1)
        if (!cancelled) setNewOrders(res.total)
      } catch {}
    }

    pollOrders()
    const t = setInterval(pollOrders, 30000)
    return () => {
      cancelled = true
      clearInterval(t)
    }
  }, [authed])

  useEffect(() => {
    document.title = newOrders > 0 ? `(${newOrders}) Kaza Shop` : 'Kaza Shop'
  }, [newOrders])

  useEffect(() => {
    localStorage.setItem(PAGE_STORAGE_KEY, page)
  }, [page])

  function handleLogin(login) {
    setAuthed(true); setAdminLogin(login)
    api.getSettings().then(cfg => setShopName(cfg?.shop_name || 'Kaza Shop')).catch(() => {})
  }

  function handleLogout() {
    localStorage.removeItem('admin_token')
    setAuthed(false); setAdminLogin('')
  }

  function onSettingsSaved(cfg) {
    setShopName(cfg.shop_name || 'Kaza Shop')
  }

  if (!authChecked) return null
  if (!authed) return <LoginPage onLogin={handleLogin} />

  return (
    <div className={s.layout}>
      <aside className={s.sidebar}>
        <div className={s.logo}>
          <span className={s.logoText} style={{cursor:'pointer'}} onClick={()=>setPage('products')}>
            {shopName}
          </span>
        </div>
        <nav>
          {NAV.map(n => (
            <button key={n.id}
              className={`${s.navBtn} ${page===n.id ? s.active : ''}`}
              onClick={() => setPage(n.id)}
            >
              <span className={s.navLabel}>{n.label}</span>
              {n.orderBadge && newOrders > 0 && (
                <span className={s.navBadge}>{newOrders}</span>
              )}
            </button>
          ))}
        </nav>
        <div className={s.sideFooter}>
          <span className={s.adminLabel}>{adminLogin}</span>
          <button className={s.logoutBtn} onClick={handleLogout}>Выйти</button>
        </div>
      </aside>
      <main className={s.main}>
        {page === 'products' && <ProductsPage />}
        {page === 'orders'   && <OrdersPage />}
        {page === 'stats'    && <StatsPage saved={statsState} onSave={setStatsState} />}
        {page === 'import'   && <ImportPage />}
        {page === 'settings' && <SettingsPage onSaved={onSettingsSaved} adminLogin={adminLogin} />}
      </main>
    </div>
  )
}
