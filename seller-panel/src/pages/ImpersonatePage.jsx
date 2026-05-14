import { useState, useEffect } from 'react'
import { api } from '../api.js'
import s from './ImpersonatePage.module.css'

// Decode JWT payload (no signature check — client side only)
function decodeJwt(token) {
  try {
    const b64 = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')
    return JSON.parse(atob(b64))
  } catch {
    return null
  }
}

function ShopCard({ shop, onImpersonate, loading }) {
  return (
    <div className={s.shopCard}>
      <div className={s.shopInfo}>
        <span className={s.shopName}>{shop.name}</span>
        <span className={s.shopMeta}>
          ID {shop.id}
          <span className={`${s.badge} ${shop.status === 'active' ? s.badgeActive : s.badgeOther}`}>
            {shop.status}
          </span>
        </span>
      </div>
      <button
        className={s.impersonateBtn}
        onClick={() => onImpersonate(shop)}
        disabled={loading}
      >
        🔑 Войти как владелец
      </button>
    </div>
  )
}

export default function ImpersonatePage({ onImpersonateStart }) {
  const [shops, setShops]       = useState([])
  const [search, setSearch]     = useState('')
  const [loading, setLoading]   = useState(false)
  const [acting, setActing]     = useState(false)
  const [error, setError]       = useState('')
  const [confirm, setConfirm]   = useState(null)   // shop being confirmed
  const [total, setTotal]       = useState(0)
  const [page, setPage]         = useState(1)

  const PER_PAGE = 20

  useEffect(() => {
    fetchShops(1, search)
  }, [])

  async function fetchShops(pg, q) {
    setLoading(true)
    setError('')
    try {
      const data = await api.getShops(pg, PER_PAGE, q ? { search: q } : {})
      setShops(pg === 1 ? data.items : prev => [...prev, ...data.items])
      setTotal(data.total)
      setPage(pg)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  function handleSearch(e) {
    const q = e.target.value
    setSearch(q)
    if (e.key === 'Enter' || q === '') fetchShops(1, q)
  }

  async function handleImpersonate(shop) {
    setActing(true)
    setError('')
    setConfirm(null)
    try {
      const result = await api.impersonateShop(shop.id)
      // Decode token to verify claims
      const payload = decodeJwt(result.access_token)
      if (!payload) throw new Error('Получен невалидный токен')

      // Backup current admin token and switch to impersonation token
      const currentToken = localStorage.getItem(api.TOKEN_KEY)
      localStorage.setItem('impersonation_backup_token', currentToken || '')
      localStorage.setItem('impersonation_shop_name', result.shop_name)
      localStorage.setItem(api.TOKEN_KEY, result.access_token)

      // Notify parent — will trigger re-render / redirect
      if (onImpersonateStart) onImpersonateStart(result)
      else window.location.reload()
    } catch (e) {
      setError(e.message)
    } finally {
      setActing(false)
    }
  }

  const filtered = search
    ? shops.filter(sh =>
        sh.name.toLowerCase().includes(search.toLowerCase()) ||
        String(sh.id).includes(search)
      )
    : shops
  const hasMore = shops.length < total

  return (
    <div className={s.page}>
      <h1 className={s.title}>🔑 Войти как владелец</h1>
      <p className={s.desc}>
        Создаёт временный токен (1 ч) с правами owner выбранного магазина.
        Действие записывается в аудит-лог.
      </p>

      {/* Warning box */}
      <div className={s.warning}>
        ⚠️ <strong>Использовать только в целях поддержки и диагностики.</strong>{' '}
        Все действия от имени владельца фиксируются в системе.
        Токен действует 1 час.
      </div>

      {/* Search */}
      <div className={s.searchRow}>
        <input
          className={s.searchInput}
          placeholder="Поиск по названию или ID…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          onKeyDown={handleSearch}
        />
        <button
          className={s.searchBtn}
          onClick={() => fetchShops(1, search)}
          disabled={loading}
        >
          {loading ? '…' : '🔍 Найти'}
        </button>
      </div>

      {error && <div className={s.error}>{error}</div>}

      {/* Confirm dialog */}
      {confirm && (
        <div className={s.overlay}>
          <div className={s.dialog}>
            <div className={s.dialogTitle}>Подтвердить импersonation</div>
            <p className={s.dialogText}>
              Вы собираетесь войти как владелец магазина{' '}
              <strong>«{confirm.name}»</strong> (ID {confirm.id}).
              <br /><br />
              Это действие будет записано в аудит-лог.
            </p>
            <div className={s.dialogBtns}>
              <button
                className={s.dialogConfirm}
                onClick={() => handleImpersonate(confirm)}
                disabled={acting}
              >
                {acting ? 'Получение токена…' : '✓ Войти'}
              </button>
              <button
                className={s.dialogCancel}
                onClick={() => setConfirm(null)}
                disabled={acting}
              >
                Отмена
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Shop list */}
      <div className={s.list}>
        {filtered.map(shop => (
          <ShopCard
            key={shop.id}
            shop={shop}
            onImpersonate={sh => setConfirm(sh)}
            loading={acting}
          />
        ))}
        {filtered.length === 0 && !loading && (
          <div className={s.empty}>Магазины не найдены</div>
        )}
      </div>

      {hasMore && (
        <button
          className={s.loadMore}
          onClick={() => fetchShops(page + 1, search)}
          disabled={loading}
        >
          {loading ? 'Загрузка…' : 'Показать ещё'}
        </button>
      )}
    </div>
  )
}
