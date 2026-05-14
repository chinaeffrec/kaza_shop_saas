import { useState, useEffect } from 'react'
import { api } from './api.js'
import { useTheme } from './hooks/useTheme.js'
import { useKeyboardShortcuts, buildShortcuts } from './hooks/useKeyboardShortcuts.js'
import LoginPage from './pages/LoginPage.jsx'
import ProductsPage from './pages/ProductsPage.jsx'
import OrdersPage from './pages/OrdersPage.jsx'
import ImportPage from './pages/ImportPage.jsx'
import StatsPage from './pages/StatsPage.jsx'
import SettingsPage from './pages/SettingsPage.jsx'
import ShopsPage from './pages/ShopsPage.jsx'
import MembersPage from './pages/MembersPage.jsx'
import AuditLogPage from './pages/AuditLogPage.jsx'
import CustomersPage from './pages/CustomersPage.jsx'
import PromoCodesPage from './pages/PromoCodesPage.jsx'
import BillingPage from './pages/BillingPage.jsx'
import ReviewsPage from './pages/ReviewsPage.jsx'
import MonitoringPage from './pages/MonitoringPage.jsx'
import ImpersonatePage from './pages/ImpersonatePage.jsx'
import FeatureFlagsPage from './pages/FeatureFlagsPage.jsx'
import BroadcastPage from './pages/BroadcastPage.jsx'
import ProfilePage from './pages/ProfilePage.jsx'
import NotificationCenter from './components/NotificationCenter.jsx'
import OnboardingWizard, { isOnboardingDone } from './components/OnboardingWizard.jsx'
import ShortcutsModal from './components/ShortcutsModal.jsx'
import s from './App.module.css'

// ── Navigation config ─────────────────────────────────────────────────────────
const OWNER_NAV = [
  { id: 'products',  label: '📦 Товары',      perm: 'products:read' },
  { id: 'orders',    label: '🧾 Заказы',       perm: 'orders:read',   orderBadge: true },
  { id: 'customers', label: '👤 Покупатели',   perm: 'orders:read' },
  { id: 'promos',    label: '🏷 Промокоды',    perm: 'promos:read' },
  { id: 'stats',     label: '📊 Статистика',   perm: 'stats:read' },
  { id: 'import',    label: '📥 Импорт',       perm: 'import:write' },
  { id: 'members',   label: '👥 Команда',      perm: 'members:read' },
  { id: 'audit',     label: '📋 Журнал',       perm: 'settings:read' },
  { id: 'reviews',   label: '⭐ Отзывы',        perm: 'reviews:read'  },
  { id: 'billing',   label: '💳 Тариф',        perm: 'settings:read' },
  { id: 'settings',  label: '⚙️ Настройки',    perm: 'settings:read' },
]

const ADMIN_NAV = [
  { id: 'shops',       label: '🏪 Магазины'    },
  { id: 'monitoring',  label: '📡 Мониторинг'  },
  { id: 'impersonate', label: '🔑 Impersonate' },
  { id: 'flags',       label: '🚩 Флаги'       },
  { id: 'broadcast',   label: '📢 Рассылки'    },
  { id: 'audit',       label: '📋 Аудит'       },
  { id: 'settings',    label: '⚙️ Платформа'   },
]

const PAGE_STORAGE_KEY = 'seller_active_page'

function filterNav(nav, permissions) {
  if (!permissions || permissions.includes('*')) return nav
  return nav.filter(n => !n.perm || permissions.includes(n.perm))
}

function getInitialPage(role, permissions) {
  const saved = localStorage.getItem(PAGE_STORAGE_KEY)
  const nav = role === 'super_admin' ? ADMIN_NAV : filterNav(OWNER_NAV, permissions)
  return nav.some(n => n.id === saved) ? saved : nav[0]?.id ?? 'products'
}

// ── App ───────────────────────────────────────────────────────────────────────
export default function App() {
  const { isDark, toggle: toggleTheme } = useTheme()

  const [authed, setAuthed]         = useState(false)
  const [authChecked, setChecked]   = useState(false)
  const [userEmail, setUserEmail]   = useState('')
  const [role, setRole]             = useState('owner')
  const [shopId, setShopId]         = useState(null)
  const [permissions, setPerms]     = useState([])
  const [page, setPage]             = useState('products')
  const [shopName, setShopName]     = useState('Kaza Shop')
  const [statsState, setStatsState] = useState({ dateFrom: '', dateTo: '', stats: [], products: {}, sort: 'ordered' })
  const [newOrders, setNewOrders]   = useState(0)
  const [impersonation, setImpersonation] = useState(() => {
    const backup = localStorage.getItem('impersonation_backup_token')
    const name   = localStorage.getItem('impersonation_shop_name')
    return backup ? { active: true, shopName: name || 'магазин' } : null
  })
  const [broadcasts, setBroadcasts] = useState([])
  const [showOnboarding, setShowOnboarding] = useState(false)
  const [showShortcuts, setShowShortcuts]   = useState(false)

  // ── Auth check on mount ───────────────────────────────────────────────────
  useEffect(() => {
    const token = localStorage.getItem(api.TOKEN_KEY)
    if (!token) { setChecked(true); return }

    api.me()
      .then(me => {
        setAuthed(true)
        setUserEmail(me.email)
        setRole(me.role)
        setShopId(me.shop_id ?? null)
        setPerms(me.permissions ?? [])
        setPage(getInitialPage(me.role, me.permissions ?? []))
        if (me.role !== 'super_admin') {
          return api.getSettings().then(cfg => setShopName(cfg?.shop_name || 'Kaza Shop'))
        }
      })
      .catch(() => localStorage.removeItem(api.TOKEN_KEY))
      .finally(() => setChecked(true))
  }, [])

  // ── Onboarding: show for new shop owners ──────────────────────────────────
  useEffect(() => {
    if (authed && role !== 'super_admin' && shopId && !isOnboardingDone()) {
      // Small delay so the main layout renders first
      const t = setTimeout(() => setShowOnboarding(true), 800)
      return () => clearTimeout(t)
    }
  }, [authed, role, shopId])

  // ── Active broadcasts ─────────────────────────────────────────────────────
  useEffect(() => {
    if (!authed) return
    api.getActiveBroadcasts().then(setBroadcasts).catch(() => {})
  }, [authed])

  // ── New order polling ─────────────────────────────────────────────────────
  useEffect(() => {
    if (!authed || role === 'super_admin') { setNewOrders(0); document.title = 'Kaza Shop'; return }
    let cancelled = false
    const poll = async () => {
      try {
        const res = await api.getOrders('new', 1, 1)
        if (!cancelled) setNewOrders(res.total ?? 0)
      } catch {}
    }
    poll()
    const t = setInterval(poll, 30_000)
    return () => { cancelled = true; clearInterval(t) }
  }, [authed, role])

  useEffect(() => {
    document.title = newOrders > 0 ? `(${newOrders}) Kaza Shop` : 'Kaza Shop'
  }, [newOrders])

  useEffect(() => {
    localStorage.setItem(PAGE_STORAGE_KEY, page)
  }, [page])

  // ── Keyboard shortcuts ────────────────────────────────────────────────────
  const isSuperAdmin = role === 'super_admin'
  const nav = isSuperAdmin ? ADMIN_NAV : filterNav(OWNER_NAV, permissions)

  const shortcuts = [
    ...buildShortcuts(setPage),
    { keys: '?', description: 'Горячие клавиши', action: () => setShowShortcuts(v => !v) },
  ]
  useKeyboardShortcuts(shortcuts, { enabled: authed })

  // Close shortcuts on Escape
  useEffect(() => {
    function onKey(e) {
      if (e.key === 'Escape') setShowShortcuts(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  // ── Event handlers ────────────────────────────────────────────────────────
  function handleLogin({ email, role: r, shopId: sid, permissions: perms }) {
    setAuthed(true)
    setUserEmail(email)
    setRole(r)
    setShopId(sid ?? null)
    setPerms(perms ?? [])
    setPage(getInitialPage(r, perms ?? []))
    if (r !== 'super_admin') {
      api.getSettings().then(cfg => setShopName(cfg?.shop_name || 'Kaza Shop')).catch(() => {})
    }
  }

  function handleLogout() {
    localStorage.removeItem(api.TOKEN_KEY)
    localStorage.removeItem('impersonation_backup_token')
    localStorage.removeItem('impersonation_shop_name')
    setAuthed(false); setUserEmail(''); setRole('owner'); setShopId(null); setPerms([])
    setImpersonation(null)
  }

  function exitImpersonation() {
    const backup = localStorage.getItem('impersonation_backup_token')
    if (backup) {
      localStorage.setItem(api.TOKEN_KEY, backup)
      localStorage.removeItem('impersonation_backup_token')
      localStorage.removeItem('impersonation_shop_name')
    }
    setImpersonation(null)
    window.location.reload()
  }

  function onSettingsSaved(cfg) {
    if (cfg?.shop_name) setShopName(cfg.shop_name)
  }

  // ── Guards ────────────────────────────────────────────────────────────────
  if (!authChecked) return null
  if (!authed) return <LoginPage onLogin={handleLogin} />

  if (!isSuperAdmin && !shopId) {
    return (
      <div style={{
        minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: 'var(--bg-page)',
      }}>
        <div style={{
          background: 'var(--bg-card)', borderRadius: 14, padding: '40px 36px', width: 400,
          boxShadow: 'var(--shadow-md)', textAlign: 'center', border: '1px solid var(--border)',
        }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>🏪</div>
          <h2 style={{ fontSize: 20, fontWeight: 600, marginBottom: 8, color: 'var(--text-primary)' }}>
            Магазин не подключён
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: 14, marginBottom: 24, lineHeight: 1.5 }}>
            Ваш аккаунт зарегистрирован, но магазин ещё не создан.<br />
            Обратитесь к администратору платформы.
          </p>
          <p style={{ color: 'var(--text-muted)', fontSize: 12, marginBottom: 20 }}>{userEmail}</p>
          <button
            onClick={handleLogout}
            style={{
              background: 'var(--accent)', color: 'var(--accent-text)', border: 'none',
              borderRadius: 8, padding: '10px 24px', fontSize: 14, fontWeight: 500, cursor: 'pointer',
            }}
          >
            Выйти
          </button>
        </div>
      </div>
    )
  }

  const title = isSuperAdmin ? 'Kaza Platform' : shopName

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <>
      <div className={s.layout}>
        {/* ── Sidebar ─────────────────────────────────────────────────────── */}
        <aside className={s.sidebar}>
          <div className={s.logo}>
            <span className={s.logoIcon}>🛍</span>
            <span
              className={s.logoText}
              style={{ cursor: 'pointer' }}
              onClick={() => setPage(nav[0]?.id)}
              title={title}
            >
              {title}
            </span>
          </div>

          <nav className={s.nav}>
            {nav.map(n => (
              <button
                key={n.id}
                className={`${s.navBtn} ${page === n.id ? s.active : ''}`}
                onClick={() => setPage(n.id)}
                title={n.label}
              >
                <span className={s.navLabel}>{n.label}</span>
                {n.orderBadge && newOrders > 0 && (
                  <span className={s.navBadge}>{newOrders > 99 ? '99+' : newOrders}</span>
                )}
              </button>
            ))}
          </nav>

          <div className={s.sideFooter}>
            <div className={s.sideFooterRow}>
              {/* Avatar / profile button */}
              <button
                className={s.profileBtn}
                onClick={() => setPage('profile')}
                title={`Профиль: ${userEmail}`}
              >
                <div style={{
                  width: 28, height: 28, borderRadius: '50%',
                  background: 'var(--accent)', color: 'var(--accent-text)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 13, fontWeight: 700,
                }}>
                  {(userEmail[0] || '?').toUpperCase()}
                </div>
              </button>

              <span className={s.adminLabel} title={userEmail}>{userEmail}</span>
            </div>

            <div className={s.footerActions}>
              {/* Notification bell */}
              {!isSuperAdmin && (
                <NotificationCenter
                  newOrders={newOrders}
                  broadcasts={broadcasts}
                  onNavigate={setPage}
                />
              )}

              {/* Theme toggle */}
              <button
                className={s.themeBtn}
                onClick={toggleTheme}
                title={isDark ? 'Светлая тема' : 'Тёмная тема'}
              >
                {isDark ? '☀️' : '🌙'}
              </button>

              {/* Logout */}
              <button className={s.logoutBtn} onClick={handleLogout} title="Выйти">
                Выйти
              </button>
            </div>
          </div>
        </aside>

        {/* ── Main ────────────────────────────────────────────────────────── */}
        <main className={s.main}>
          {/* Impersonation banner */}
          {impersonation?.active && (
            <div className={s.impersonationBanner}>
              <span>🔑 <strong>Режим impersonation:</strong> вы работаете как владелец «{impersonation.shopName}»</span>
              <button className={s.impersonationBannerBtn} onClick={exitImpersonation}>
                Выйти из режима
              </button>
            </div>
          )}

          {/* Platform broadcast banners */}
          {broadcasts.map(b => (
            <div key={b.id} className={s.broadcastBanner}>
              📢 <strong>{b.title}:</strong> {b.body}
            </div>
          ))}

          <div className={s.mainScroll}>
            {/* Profile page (all users) */}
            {page === 'profile' && <ProfilePage userEmail={userEmail} />}

            {/* Owner / shop-user pages */}
            {!isSuperAdmin && page === 'products'  && <ProductsPage />}
            {!isSuperAdmin && page === 'orders'    && <OrdersPage />}
            {!isSuperAdmin && page === 'customers' && <CustomersPage />}
            {!isSuperAdmin && page === 'promos'    && <PromoCodesPage />}
            {!isSuperAdmin && page === 'stats'     && <StatsPage saved={statsState} onSave={setStatsState} />}
            {!isSuperAdmin && page === 'import'    && <ImportPage />}
            {!isSuperAdmin && page === 'members'   && <MembersPage shopId={shopId} />}
            {!isSuperAdmin && page === 'audit'     && <AuditLogPage shopId={shopId} isSuperAdmin={false} />}
            {!isSuperAdmin && page === 'reviews'   && <ReviewsPage />}
            {!isSuperAdmin && page === 'billing'   && <BillingPage />}
            {!isSuperAdmin && page === 'settings'  && <SettingsPage onSaved={onSettingsSaved} userEmail={userEmail} shopId={shopId} />}

            {/* Super-admin pages */}
            {isSuperAdmin && page === 'shops'       && <ShopsPage />}
            {isSuperAdmin && page === 'monitoring'  && <MonitoringPage />}
            {isSuperAdmin && page === 'impersonate' && (
              <ImpersonatePage onImpersonateStart={r => {
                setImpersonation({ active: true, shopName: r.shop_name })
                window.location.reload()
              }} />
            )}
            {isSuperAdmin && page === 'flags'      && <FeatureFlagsPage />}
            {isSuperAdmin && page === 'broadcast'  && <BroadcastPage />}
            {isSuperAdmin && page === 'audit'      && <AuditLogPage isSuperAdmin={true} />}
            {isSuperAdmin && page === 'settings'   && <SettingsPage onSaved={onSettingsSaved} userEmail={userEmail} isSuperAdmin />}
          </div>
        </main>
      </div>

      {/* ── Modals ────────────────────────────────────────────────────────── */}
      {showOnboarding && (
        <OnboardingWizard
          onNavigate={(p) => { setPage(p); setShowOnboarding(false) }}
          onClose={() => setShowOnboarding(false)}
        />
      )}

      {showShortcuts && (
        <ShortcutsModal onClose={() => setShowShortcuts(false)} />
      )}
    </>
  )
}
