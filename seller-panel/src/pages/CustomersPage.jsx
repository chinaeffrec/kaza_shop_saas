import { useState, useEffect, useCallback } from 'react'
import { api } from '../api.js'
import s from './CustomersPage.module.css'

function fmt(n) { return n?.toLocaleString('ru-RU') ?? '0' }
function fmtDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: '2-digit' })
}

export default function CustomersPage() {
  const [items, setItems]     = useState([])
  const [total, setTotal]     = useState(0)
  const [page, setPage]       = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState('')
  const [search, setSearch]   = useState('')
  const [searchInput, setSearchInput] = useState('')

  // drawer
  const [selected, setSelected]   = useState(null)   // CustomerResponse
  const [orders, setOrders]        = useState([])
  const [ordersLoading, setOL]     = useState(false)
  const [editPhone, setEditPhone]  = useState('')
  const [editNotes, setEditNotes]  = useState('')
  const [saving, setSaving]        = useState(false)
  const [drawerTab, setDrawerTab]  = useState('info') // 'info' | 'orders'

  const PER_PAGE = 30

  const load = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const data = await api.getCustomers(page, PER_PAGE, search)
      setItems(data.items)
      setTotal(data.total)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [page, search])

  useEffect(() => { load() }, [load])

  function handleSearch(e) {
    e.preventDefault()
    setSearch(searchInput)
    setPage(1)
  }

  async function openCustomer(c) {
    setSelected(c)
    setEditPhone(c.phone ?? '')
    setEditNotes(c.notes ?? '')
    setDrawerTab('info')
    setOrders([])
  }

  async function loadOrders() {
    if (!selected) return
    setOL(true)
    try {
      const data = await api.getCustomerOrders(selected.id)
      setOrders(data.items)
    } catch (e) {
      alert(e.message)
    } finally {
      setOL(false)
    }
  }

  useEffect(() => {
    if (selected && drawerTab === 'orders') loadOrders()
  }, [selected?.id, drawerTab])

  async function handleSave() {
    if (!selected) return
    setSaving(true)
    try {
      const updated = await api.updateCustomer(selected.id, {
        phone: editPhone || null,
        notes: editNotes || null,
      })
      setSelected(updated)
      setItems(prev => prev.map(c => c.id === updated.id ? updated : c))
    } catch (e) {
      alert(e.message)
    } finally {
      setSaving(false)
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / PER_PAGE))

  const displayName = (c) => {
    const name = [c.first_name, c.last_name].filter(Boolean).join(' ')
    return name || c.username || `ID ${c.telegram_id}`
  }

  return (
    <div className={s.page}>
      <h1 className={s.title}>Покупатели</h1>

      {/* Search */}
      <div className={s.toolbar}>
        <form className={s.searchForm} onSubmit={handleSearch}>
          <input
            className={s.searchInput}
            placeholder="Поиск по имени, @username, телефону…"
            value={searchInput}
            onChange={e => setSearchInput(e.target.value)}
          />
          <button className={s.btnPrimary} type="submit">Найти</button>
          {search && (
            <button className={s.btnGhost} type="button"
              onClick={() => { setSearchInput(''); setSearch(''); setPage(1) }}>
              Сбросить
            </button>
          )}
        </form>
        <span className={s.muted}>Всего: {total}</span>
      </div>

      {/* Table */}
      {loading && <p className={s.muted}>Загрузка…</p>}
      {error   && <p className={s.error}>{error}</p>}

      {!loading && !error && (
        <div className={s.tableWrap}>
          <table className={s.table}>
            <thead>
              <tr>
                <th>Покупатель</th>
                <th>Телефон</th>
                <th>Заказов</th>
                <th>Потрачено</th>
                <th>Последний заказ</th>
                <th>Регистрация</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 && (
                <tr><td colSpan={6} className={s.muted} style={{textAlign:'center',padding:32}}>
                  Покупателей не найдено
                </td></tr>
              )}
              {items.map(c => (
                <tr key={c.id} className={s.row} onClick={() => openCustomer(c)}>
                  <td>
                    <div className={s.nameBlock}>
                      <span className={s.name}>{displayName(c)}</span>
                      {c.username && <span className={s.uname}>@{c.username}</span>}
                    </div>
                  </td>
                  <td className={s.phone}>{c.phone || <span className={s.muted}>—</span>}</td>
                  <td>{c.total_orders}</td>
                  <td>{fmt(c.total_spent)} ₽</td>
                  <td className={s.muted}>{fmtDate(c.last_order_at)}</td>
                  <td className={s.muted}>{fmtDate(c.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {!loading && totalPages > 1 && (
        <div className={s.pagination}>
          <button className={s.pgBtn} disabled={page <= 1} onClick={() => setPage(p => p - 1)}>← Назад</button>
          <span className={s.muted}>{page} / {totalPages}</span>
          <button className={s.pgBtn} disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>Вперёд →</button>
        </div>
      )}

      {/* Drawer */}
      {selected && (
        <div className={s.overlay} onClick={() => setSelected(null)}>
          <div className={s.drawer} onClick={e => e.stopPropagation()}>
            <button className={s.closeBtn} onClick={() => setSelected(null)}>✕</button>

            <div className={s.drawerHeader}>
              <div className={s.drawerName}>{displayName(selected)}</div>
              {selected.username && <div className={s.drawerUname}>@{selected.username}</div>}
              <div className={s.drawerStats}>
                <span>{selected.total_orders} заказов</span>
                <span>·</span>
                <span>{fmt(selected.total_spent)} ₽</span>
              </div>
            </div>

            {/* Tabs */}
            <div className={s.tabs}>
              <button className={`${s.tab} ${drawerTab === 'info' ? s.tabActive : ''}`}
                onClick={() => setDrawerTab('info')}>Карточка</button>
              <button className={`${s.tab} ${drawerTab === 'orders' ? s.tabActive : ''}`}
                onClick={() => setDrawerTab('orders')}>Заказы</button>
            </div>

            {drawerTab === 'info' && (
              <div className={s.drawerBody}>
                <div className={s.infoRow}>
                  <span className={s.infoLabel}>Telegram ID</span>
                  <span>{selected.telegram_id}</span>
                </div>
                <div className={s.infoRow}>
                  <span className={s.infoLabel}>Первый заказ</span>
                  <span>{fmtDate(selected.first_order_at)}</span>
                </div>
                <div className={s.infoRow}>
                  <span className={s.infoLabel}>Последний заказ</span>
                  <span>{fmtDate(selected.last_order_at)}</span>
                </div>

                <label className={s.fieldLabel}>Телефон</label>
                <input className={s.fieldInput} value={editPhone}
                  onChange={e => setEditPhone(e.target.value)}
                  placeholder="+7 999 000 00 00" />

                <label className={s.fieldLabel}>Заметки</label>
                <textarea className={s.fieldTextarea} rows={4} value={editNotes}
                  onChange={e => setEditNotes(e.target.value)}
                  placeholder="Внутренние заметки о покупателе…" />

                <button className={s.btnPrimary} onClick={handleSave} disabled={saving}>
                  {saving ? 'Сохранение…' : 'Сохранить'}
                </button>
              </div>
            )}

            {drawerTab === 'orders' && (
              <div className={s.drawerBody}>
                {ordersLoading && <p className={s.muted}>Загрузка…</p>}
                {!ordersLoading && orders.length === 0 && (
                  <p className={s.muted}>Заказов нет</p>
                )}
                {orders.map(o => (
                  <div key={o.id} className={s.orderCard}>
                    <div className={s.orderTop}>
                      <span className={s.orderId}>#{o.id}</span>
                      <span className={s.orderStatus}>{o.status_label}</span>
                      <span className={s.orderTotal}>{fmt(o.total)} ₽</span>
                    </div>
                    <div className={s.orderDate}>{fmtDate(o.created_at)}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
