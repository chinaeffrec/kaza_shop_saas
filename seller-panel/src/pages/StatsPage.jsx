import { useState, useEffect, useCallback } from 'react'
import { api } from '../api.js'
import { useToast } from '../components/Toast.jsx'
import s from './StatsPage.module.css'

export default function StatsPage({ saved, onSave }) {
  const toast = useToast()
  const [dashboard, setDashboard] = useState(saved?.dashboard || null)
  const [stats, setStats]         = useState(saved?.stats || [])
  const [productsSummary, setProductsSummary] = useState(saved?.productsSummary || null)
  const [dateFrom, setDateFrom]   = useState(saved?.dateFrom || '')
  const [dateTo, setDateTo]       = useState(saved?.dateTo || '')
  const [loading, setLoading]     = useState(false)
  const [sort, setSort]           = useState(saved?.sort || 'ordered')
  const [sortDir, setSortDir]     = useState(saved?.sortDir || 'desc')
  const [tab, setTab]             = useState('dashboard')

  const load = useCallback(async (nextFilters = {}) => {
    const from = nextFilters.dateFrom ?? dateFrom
    const to = nextFilters.dateTo ?? dateTo

    if (from && to && from > to) {
      toast('Дата "По" не может быть раньше даты "С"', 'error')
      return
    }

    setLoading(true)
    try {
      const [dash, statsRes] = await Promise.all([
        api.getDashboard(from || null, to || null),
        api.getStats(from || null, to || null),
      ])
      setDashboard(dash)
      setStats(statsRes.items || [])
      setProductsSummary(statsRes.summary || null)
      onSave?.({
        dashboard: dash,
        stats: statsRes.items || [],
        productsSummary: statsRes.summary || null,
        dateFrom: from,
        dateTo: to,
        sort,
        sortDir,
      })
    } catch(e) { toast(e.message, 'error') }
    finally { setLoading(false) }
  }, [dateFrom, dateTo, onSave, sort, sortDir])

  useEffect(() => { load() }, [])

  const sorted = [...stats].sort((a, b) => {
    const av = Number(a[sort] ?? 0)
    const bv = Number(b[sort] ?? 0)
    if (av === bv) return a.product_id - b.product_id
    return sortDir === 'asc' ? av - bv : bv - av
  })

  function handleSort(col) {
    const nextDir = sort === col ? (sortDir === 'desc' ? 'asc' : 'desc') : 'desc'
    setSort(col)
    setSortDir(nextDir)
    onSave?.({
      dashboard,
      stats,
      productsSummary,
      products,
      dateFrom,
      dateTo,
      sort: col,
      sortDir: nextDir,
    })
  }

  const th = (col, label) => (
      <th
        className={s.sortable}
        style={{cursor:'pointer'}}
        onClick={() => handleSort(col)}
      >
        {label}{sort === col ? (sortDir === 'desc' ? ' ▼' : ' ▲') : ' ↕'}
      </th>
  )

  const fmt = (n) => (n||0).toLocaleString('ru-RU')

  return (
    <div>
      <div className={s.toolbar}>
        <h1 className={s.title}>Статистика</h1>
        <button className={s.btnRefresh} onClick={load} disabled={loading}>
          {loading ? '...' : '↻ Обновить'}
        </button>
      </div>

      <div className={s.filters}>
        <label className={s.dateLabel}>С <input type="date" className={s.dateInput} value={dateFrom} onChange={e=>setDateFrom(e.target.value)} /></label>
        <label className={s.dateLabel}>По <input type="date" className={s.dateInput} value={dateTo} onChange={e=>setDateTo(e.target.value)} /></label>
        <button className={s.btnApply} onClick={load}>Применить</button>
        <button className={s.btnReset} onClick={()=>{
          setDateFrom('')
          setDateTo('')
          load({ dateFrom: '', dateTo: '' })
        }}>Сбросить</button>
      </div>

      <div className={s.tabs}>
        <button className={`${s.tab} ${tab==='dashboard'?s.activeTab:''}`} onClick={()=>setTab('dashboard')}>📊 Заказы</button>
        <button className={`${s.tab} ${tab==='products'?s.activeTab:''}`} onClick={()=>setTab('products')}>📦 Товары</button>
      </div>

      {tab === 'dashboard' && dashboard && (
        <div>
          <div className={s.summary}>
            <div className={s.card}>
              <div className={s.cardVal}>{fmt(dashboard.total_revenue)} ₽</div>
              <div className={s.cardLabel}>Выручка</div>
            </div>
            <div className={s.card}>
              <div className={s.cardVal}>{dashboard.total_orders}</div>
              <div className={s.cardLabel}>Заказов всего</div>
            </div>
            <div className={s.card}>
              <div className={s.cardVal}>{fmt(dashboard.average_order_value)} ₽</div>
              <div className={s.cardLabel}>Средний чек</div>
            </div>
            <div className={s.card}>
              <div className={s.cardVal}>{dashboard.billable_orders}</div>
              <div className={s.cardLabel}>Без отмен и возвратов</div>
            </div>
            {dashboard.orders_by_status.map(st => (
              <div key={st.status} className={s.card}>
                <div className={s.cardVal}>{st.count}</div>
                <div className={s.cardLabel}>{st.label}</div>
              </div>
            ))}
          </div>

          <div style={{marginBottom: 12}}>
            <button className={s.btnApply} style={{background:'#43a047'}}
              onClick={() => api.exportDashboard(dateFrom, dateTo).catch(e => toast('Ошибка экспорта: ' + e.message, 'error'))}
            >
              📥 Экспорт в Excel
            </button>
          </div>

          {dashboard.recent_orders?.length > 0 && (
            <div className={s.topSection}>
              <h2 className={s.sectionTitle}>🧾 Последние заказы</h2>
              <table className={s.table}>
                <thead><tr><th>Заказ</th><th>Покупатель</th><th>Статус</th><th>Сумма</th><th>Дата</th></tr></thead>
                <tbody>
                  {dashboard.recent_orders.map(order => (
                    <tr key={order.id}>
                      <td>#{order.id}</td>
                      <td>{order.user_name || `ID ${order.user_id}`}</td>
                      <td>{order.status_label}</td>
                      <td className={s.num}>{fmt(order.total)} ₽</td>
                      <td>{order.created_at ? new Date(order.created_at).toLocaleString('ru-RU') : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {dashboard.total_orders === 0 && (
            <p className={s.msg}>Нет данных за выбранный период</p>
          )}
        </div>
      )}

      {tab === 'products' && (
        loading ? <p className={s.msg}>Загрузка...</p> : (
          <>
            {productsSummary && (
              <div className={s.summary} style={{marginBottom: 16}}>
                <div className={s.card}>
                  <div className={s.cardVal}>{fmt(productsSummary.total_sold_sum)} ₽</div>
                  <div className={s.cardLabel}>Выручка за период</div>
                </div>
                <div className={s.card}>
                  <div className={s.cardVal}>{productsSummary.total_sold_qty}</div>
                  <div className={s.cardLabel}>Продано товаров</div>
                </div>
                <div className={s.card}>
                  <div className={s.cardVal}>{productsSummary.avg_items_per_order}</div>
                  <div className={s.cardLabel}>В среднем в заказе</div>
                </div>
                <div className={s.card}>
                  <div className={s.cardVal}>{fmt(productsSummary.avg_price)} ₽</div>
                  <div className={s.cardLabel}>Средняя цена</div>
                </div>
                <div className={s.card}>
                  <div className={s.cardVal}>{productsSummary.total_returned}</div>
                  <div className={s.cardLabel}>Возвратов</div>
                </div>
              </div>
            )}

            <div style={{marginBottom: 12}}>
              <button className={s.btnApply} style={{background:'#43a047'}}
                onClick={() => api.exportStats(dateFrom, dateTo).catch(e => toast('Ошибка экспорта: ' + e.message, 'error'))}
              >
                📥 Экспорт в Excel
              </button>
            </div>

            <table className={s.table}>
              <thead><tr>
                <th>Товар</th>
                {th('added_to_cart','В корзину')}
                {th('ordered','Заказано')}
                {th('returned','Возвраты')}
                {th('period_sold_qty','Продано (период)')}
                {th('period_sold_sum','Выручка (период)')}
                <th></th>
              </tr></thead>
              <tbody>
                {sorted.map(st => {
                  return (
                    <tr key={st.product_id}>
                      <td>{st.name || `ID ${st.product_id}`}</td>
                      <td className={s.num}>{st.added_to_cart}</td>
                      <td className={s.num}>{st.ordered}</td>
                      <td className={`${s.num} ${st.returned>0?s.warn:''}`}>{st.returned}</td>
                      <td className={s.num}>{st.period_sold_qty||0}</td>
                      <td className={s.num}>{fmt(st.period_sold_sum||0)} ₽</td>
                      <td>
                        <button className={s.btnReturn}
                          onClick={() => api.trackReturn(st.product_id).then(load)}
                          title="Зарегистрировать возврат">↩️</button>
                      </td>
                    </tr>
                  )
                })}
                {sorted.length === 0 && (
                  <tr><td colSpan={7} style={{textAlign:'center',color:'#aaa',padding:20}}>Нет данных</td></tr>
                )}
              </tbody>
            </table>
          </>
        )
      )}
    </div>
  )
}
