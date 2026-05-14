import { useState, useEffect, useCallback } from 'react'
import { api } from '../api.js'
import { useToast } from '../components/Toast.jsx'
import s from './StatsPage.module.css'

const fmt = (n) => (n || 0).toLocaleString('ru-RU')

// ── Mini SVG bar chart ────────────────────────────────────────────────────────
function BarChart({ points, valueKey = 'revenue', colorHex = '#6c63ff' }) {
  if (!points?.length) return <p className={s.msg}>Нет данных за период</p>

  const values = points.map(p => p[valueKey] || 0)
  const maxVal = Math.max(...values, 1)
  const W = 720, H = 160, PAD = 32, BAR_PAD = 2
  const barW = Math.max(4, Math.floor((W - PAD * 2) / points.length) - BAR_PAD)

  return (
    <div className={s.chartWrap}>
      <svg viewBox={`0 0 ${W} ${H + 24}`} className={s.chart}>
        {points.map((p, i) => {
          const x = PAD + i * ((W - PAD * 2) / points.length)
          const barH = Math.max(2, Math.floor((p[valueKey] || 0) / maxVal * H))
          const y = H - barH
          return (
            <g key={p.date}>
              <rect
                x={x} y={y} width={barW} height={barH}
                fill={colorHex} rx={2} opacity={0.85}
              >
                <title>{p.date}: {fmt(p[valueKey])} {valueKey === 'revenue' ? '₽' : ''}</title>
              </rect>
              {/* x-axis label — every nth point to avoid overlap */}
              {(i % Math.ceil(points.length / 10) === 0) && (
                <text x={x + barW / 2} y={H + 18} textAnchor="middle"
                  fontSize={9} fill="#aaa">
                  {p.date.slice(5)}  {/* MM-DD or W## */}
                </text>
              )}
            </g>
          )
        })}
        {/* y-axis max label */}
        <text x={4} y={12} fontSize={9} fill="#aaa">{fmt(maxVal)}</text>
        <text x={4} y={H + 2} fontSize={9} fill="#aaa">0</text>
        <line x1={PAD - 4} y1={0} x2={PAD - 4} y2={H} stroke="#f0f0f0" strokeWidth={1} />
        <line x1={PAD - 4} y1={H} x2={W} y2={H} stroke="#f0f0f0" strokeWidth={1} />
      </svg>
    </div>
  )
}

// ── Conversion ring (CSS-only) ─────────────────────────────────────────────
function Ring({ pct, label, color = '#6c63ff' }) {
  const r = 36, circ = 2 * Math.PI * r
  const dash = circ * Math.min(pct / 100, 1)
  return (
    <div className={s.ringWrap}>
      <svg width={88} height={88}>
        <circle cx={44} cy={44} r={r} fill="none" stroke="#f0f0f0" strokeWidth={8} />
        <circle cx={44} cy={44} r={r} fill="none" stroke={color}
          strokeWidth={8} strokeDasharray={`${dash} ${circ}`}
          strokeLinecap="round" transform="rotate(-90 44 44)" />
        <text x={44} y={48} textAnchor="middle" fontSize={14} fontWeight={700} fill="#1a1a2e">
          {pct}%
        </text>
      </svg>
      <span className={s.ringLabel}>{label}</span>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────
export default function StatsPage({ saved, onSave }) {
  const toast = useToast()

  const [dashboard, setDashboard]           = useState(saved?.dashboard || null)
  const [analytics, setAnalytics]           = useState(saved?.analytics || null)
  const [stats, setStats]                   = useState(saved?.stats || [])
  const [productsSummary, setProductsSummary] = useState(saved?.productsSummary || null)

  const [dateFrom, setDateFrom] = useState(saved?.dateFrom || '')
  const [dateTo, setDateTo]     = useState(saved?.dateTo || '')
  const [loading, setLoading]   = useState(false)
  const [sort, setSort]         = useState(saved?.sort || 'ordered')
  const [sortDir, setSortDir]   = useState(saved?.sortDir || 'desc')
  const [tab, setTab]           = useState('dashboard')
  const [chartPeriod, setChartPeriod] = useState('day')   // day | week
  const [chartMetric, setChartMetric] = useState('revenue') // revenue | orders_count

  const load = useCallback(async (overrides = {}) => {
    const from = overrides.dateFrom ?? dateFrom
    const to   = overrides.dateTo   ?? dateTo
    const period = overrides.period ?? chartPeriod

    if (from && to && from > to) {
      toast('Дата «По» не может быть раньше «С»', 'error')
      return
    }

    setLoading(true)
    try {
      const [dash, statsRes, analyticsRes] = await Promise.all([
        api.getDashboard(from || null, to || null),
        api.getStats(from || null, to || null),
        api.getAnalytics(from || null, to || null, period),
      ])
      setDashboard(dash)
      setStats(statsRes.items || [])
      setProductsSummary(statsRes.summary || null)
      setAnalytics(analyticsRes)
      onSave?.({
        dashboard: dash, analytics: analyticsRes,
        stats: statsRes.items || [], productsSummary: statsRes.summary || null,
        dateFrom: from, dateTo: to, sort, sortDir,
      })
    } catch (e) { toast(e.message, 'error') }
    finally { setLoading(false) }
  }, [dateFrom, dateTo, onSave, sort, sortDir, chartPeriod])

  useEffect(() => { load() }, [])

  const sorted = [...stats].sort((a, b) => {
    const av = Number(a[sort] ?? 0), bv = Number(b[sort] ?? 0)
    if (av === bv) return a.product_id - b.product_id
    return sortDir === 'asc' ? av - bv : bv - av
  })

  function handleSort(col) {
    const nextDir = sort === col ? (sortDir === 'desc' ? 'asc' : 'desc') : 'desc'
    setSort(col); setSortDir(nextDir)
  }

  function changePeriod(p) {
    setChartPeriod(p)
    load({ period: p })
  }

  const th = (col, label) => (
    <th className={s.sortable} onClick={() => handleSort(col)} style={{ cursor: 'pointer' }}>
      {label}{sort === col ? (sortDir === 'desc' ? ' ▼' : ' ▲') : ' ↕'}
    </th>
  )

  return (
    <div>
      {/* Toolbar */}
      <div className={s.toolbar}>
        <h1 className={s.title}>Статистика</h1>
        <button className={s.btnRefresh} onClick={() => load()} disabled={loading}>
          {loading ? '…' : '↻ Обновить'}
        </button>
      </div>

      {/* Date filters */}
      <div className={s.filters}>
        <label className={s.dateLabel}>С
          <input type="date" className={s.dateInput} value={dateFrom}
            onChange={e => setDateFrom(e.target.value)} />
        </label>
        <label className={s.dateLabel}>По
          <input type="date" className={s.dateInput} value={dateTo}
            onChange={e => setDateTo(e.target.value)} />
        </label>
        <button className={s.btnApply} onClick={() => load()}>Применить</button>
        <button className={s.btnReset} onClick={() => {
          setDateFrom(''); setDateTo('')
          load({ dateFrom: '', dateTo: '' })
        }}>Сбросить</button>
      </div>

      {/* Tabs */}
      <div className={s.tabs}>
        <button className={`${s.tab} ${tab === 'dashboard' ? s.activeTab : ''}`}
          onClick={() => setTab('dashboard')}>📊 Заказы</button>
        <button className={`${s.tab} ${tab === 'analytics' ? s.activeTab : ''}`}
          onClick={() => setTab('analytics')}>📈 Динамика</button>
        <button className={`${s.tab} ${tab === 'cohorts' ? s.activeTab : ''}`}
          onClick={() => setTab('cohorts')}>👥 Покупатели</button>
        <button className={`${s.tab} ${tab === 'products' ? s.activeTab : ''}`}
          onClick={() => setTab('products')}>📦 Товары</button>
      </div>

      {loading && <p className={s.msg}>Загрузка…</p>}

      {/* ── Tab: Заказы ─────────────────────────────────────────────────── */}
      {!loading && tab === 'dashboard' && dashboard && (
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
              <div className={s.cardLabel}>Оплачено / в работе</div>
            </div>
            <div className={s.card}>
              <div className={s.cardVal}>{dashboard.conversion_rate ?? 0}%</div>
              <div className={s.cardLabel}>Конверсия в оплату</div>
            </div>
          </div>

          <div className={s.actionRow}>
            <button className={`${s.btnApply} ${s.btnGreen}`}
              onClick={() => api.exportDashboard(dateFrom, dateTo)
                .catch(e => toast('Ошибка: ' + e.message, 'error'))}>
              📥 Экспорт заказов (Excel)
            </button>
          </div>

          {/* Top products */}
          {dashboard.top_products?.length > 0 && (
            <div className={s.topSection}>
              <h2 className={s.sectionTitle}>🏆 Топ товаров</h2>
              <table className={s.table}>
                <thead><tr>
                  <th>Товар</th>
                  <th className={s.num}>Заказано</th>
                  <th className={s.num}>Выручка</th>
                </tr></thead>
                <tbody>
                  {dashboard.top_products.map((p, i) => (
                    <tr key={p.product_id}>
                      <td>
                        <span className={s.rank}>#{i + 1}</span> {p.name}
                      </td>
                      <td className={s.num}>{p.ordered}</td>
                      <td className={s.num}>{fmt(p.revenue)} ₽</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Status breakdown */}
          {dashboard.orders_by_status?.length > 0 && (
            <div className={s.topSection}>
              <h2 className={s.sectionTitle}>📋 По статусам</h2>
              <div className={s.statusGrid}>
                {dashboard.orders_by_status.map(st => (
                  <div key={st.status} className={s.statusCard}>
                    <span className={s.statusLabel}>{st.label}</span>
                    <span className={s.statusCount}>{st.count}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Recent orders */}
          {dashboard.recent_orders?.length > 0 && (
            <div className={s.topSection}>
              <h2 className={s.sectionTitle}>🧾 Последние заказы</h2>
              <table className={s.table}>
                <thead><tr>
                  <th>Заказ</th><th>Покупатель</th><th>Статус</th>
                  <th className={s.num}>Сумма</th><th>Дата</th>
                </tr></thead>
                <tbody>
                  {dashboard.recent_orders.map(o => (
                    <tr key={o.id}>
                      <td>#{o.id}</td>
                      <td>{o.user_name || `ID ${o.user_id}`}</td>
                      <td>{o.status_label}</td>
                      <td className={s.num}>{fmt(o.total)} ₽</td>
                      <td className={s.muted}>
                        {new Date(o.created_at).toLocaleDateString('ru-RU')}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ── Tab: Динамика ───────────────────────────────────────────────── */}
      {!loading && tab === 'analytics' && (
        <div>
          <div className={s.chartControls}>
            <div className={s.segmented}>
              <button className={`${s.seg} ${chartPeriod === 'day' ? s.segActive : ''}`}
                onClick={() => changePeriod('day')}>По дням</button>
              <button className={`${s.seg} ${chartPeriod === 'week' ? s.segActive : ''}`}
                onClick={() => changePeriod('week')}>По неделям</button>
            </div>
            <div className={s.segmented}>
              <button className={`${s.seg} ${chartMetric === 'revenue' ? s.segActive : ''}`}
                onClick={() => setChartMetric('revenue')}>Выручка</button>
              <button className={`${s.seg} ${chartMetric === 'orders_count' ? s.segActive : ''}`}
                onClick={() => setChartMetric('orders_count')}>Заказы</button>
              <button className={`${s.seg} ${chartMetric === 'new_customers' ? s.segActive : ''}`}
                onClick={() => setChartMetric('new_customers')}>Новые клиенты</button>
            </div>
          </div>

          {analytics?.revenue_chart?.length > 0 ? (
            <>
              <BarChart
                points={analytics.revenue_chart}
                valueKey={chartMetric}
                colorHex={chartMetric === 'revenue' ? '#6c63ff'
                  : chartMetric === 'orders_count' ? '#43a047' : '#f57c00'}
              />

              {/* Totals under chart */}
              <div className={s.summary} style={{ marginTop: 16 }}>
                <div className={s.card}>
                  <div className={s.cardVal}>
                    {fmt(analytics.revenue_chart.reduce((a, p) => a + p.revenue, 0))} ₽
                  </div>
                  <div className={s.cardLabel}>Выручка за период</div>
                </div>
                <div className={s.card}>
                  <div className={s.cardVal}>
                    {analytics.revenue_chart.reduce((a, p) => a + p.orders_count, 0)}
                  </div>
                  <div className={s.cardLabel}>Заказов за период</div>
                </div>
                <div className={s.card}>
                  <div className={s.cardVal}>
                    {analytics.revenue_chart.reduce((a, p) => a + p.new_customers, 0)}
                  </div>
                  <div className={s.cardLabel}>Новых клиентов</div>
                </div>
                <div className={s.card}>
                  <div className={s.cardVal}>{analytics.revenue_chart.length}</div>
                  <div className={s.cardLabel}>
                    {chartPeriod === 'day' ? 'Дней с продажами' : 'Недель с продажами'}
                  </div>
                </div>
              </div>

              {/* Data table */}
              <div className={s.topSection} style={{ marginTop: 16 }}>
                <table className={s.table}>
                  <thead><tr>
                    <th>{chartPeriod === 'day' ? 'Дата' : 'Неделя'}</th>
                    <th className={s.num}>Выручка</th>
                    <th className={s.num}>Заказов</th>
                    <th className={s.num}>Новых клиентов</th>
                  </tr></thead>
                  <tbody>
                    {[...analytics.revenue_chart].reverse().map(p => (
                      <tr key={p.date}>
                        <td>{p.date}</td>
                        <td className={s.num}>{fmt(p.revenue)} ₽</td>
                        <td className={s.num}>{p.orders_count}</td>
                        <td className={s.num}>{p.new_customers}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <p className={s.msg}>Нет данных за выбранный период</p>
          )}
        </div>
      )}

      {/* ── Tab: Покупатели / Когорты ────────────────────────────────────── */}
      {!loading && tab === 'cohorts' && analytics && (
        <div>
          <div className={s.cohortGrid}>
            {/* Rings */}
            <div className={s.cohortCard}>
              <h3 className={s.cohortTitle}>Новые vs. Повторные</h3>
              <div className={s.ringRow}>
                <Ring pct={analytics.cohorts.repeat_rate} label="Повторных" color="#6c63ff" />
                <Ring
                  pct={Math.round(100 - analytics.cohorts.repeat_rate)}
                  label="Новых" color="#43a047"
                />
              </div>
              <div className={s.cohortStats}>
                <div className={s.cohortStat}>
                  <span className={s.cohortStatVal}>{analytics.cohorts.period_buyers}</span>
                  <span className={s.cohortStatLabel}>Всего покупателей</span>
                </div>
                <div className={s.cohortStat}>
                  <span className={s.cohortStatVal} style={{ color: '#43a047' }}>
                    {analytics.cohorts.new_buyers}
                  </span>
                  <span className={s.cohortStatLabel}>Новых (первый заказ)</span>
                </div>
                <div className={s.cohortStat}>
                  <span className={s.cohortStatVal} style={{ color: '#6c63ff' }}>
                    {analytics.cohorts.returning_buyers}
                  </span>
                  <span className={s.cohortStatLabel}>Повторных</span>
                </div>
              </div>
            </div>

            {/* Average orders */}
            <div className={s.cohortCard}>
              <h3 className={s.cohortTitle}>Активность в периоде</h3>
              <div className={s.avgGrid}>
                <div className={s.avgBlock}>
                  <div className={s.avgVal} style={{ color: '#43a047' }}>
                    {analytics.cohorts.avg_orders_new}
                  </div>
                  <div className={s.avgLabel}>Заказов в среднем<br />у новых</div>
                </div>
                <div className={s.avgDivider} />
                <div className={s.avgBlock}>
                  <div className={s.avgVal} style={{ color: '#6c63ff' }}>
                    {analytics.cohorts.avg_orders_returning}
                  </div>
                  <div className={s.avgLabel}>Заказов в среднем<br />у повторных</div>
                </div>
              </div>
              <p className={s.cohortHint}>
                Повторный покупатель в среднем делает в{' '}
                <b>{analytics.cohorts.avg_orders_new > 0
                  ? (analytics.cohorts.avg_orders_returning / analytics.cohorts.avg_orders_new).toFixed(1)
                  : '—'}×</b>{' '}
                больше заказов, чем новый.
              </p>
            </div>
          </div>

          {/* Export */}
          <div className={s.actionRow}>
            <button className={`${s.btnApply} ${s.btnGreen}`}
              onClick={() => api.exportCustomers()
                .catch(e => toast('Ошибка: ' + e.message, 'error'))}>
              📥 Экспорт покупателей (Excel)
            </button>
          </div>
        </div>
      )}

      {/* ── Tab: Товары ──────────────────────────────────────────────────── */}
      {!loading && tab === 'products' && (
        <>
          {productsSummary && (
            <div className={s.summary} style={{ marginBottom: 16 }}>
              <div className={s.card}>
                <div className={s.cardVal}>{fmt(productsSummary.total_sold_sum)} ₽</div>
                <div className={s.cardLabel}>Выручка</div>
              </div>
              <div className={s.card}>
                <div className={s.cardVal}>{productsSummary.total_sold_qty}</div>
                <div className={s.cardLabel}>Продано шт.</div>
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

          <div className={s.actionRow}>
            <button className={`${s.btnApply} ${s.btnGreen}`}
              onClick={() => api.exportStats(dateFrom, dateTo)
                .catch(e => toast('Ошибка: ' + e.message, 'error'))}>
              📥 Экспорт товаров (Excel)
            </button>
          </div>

          <table className={s.table}>
            <thead><tr>
              <th>Товар</th>
              {th('added_to_cart', 'В корзину')}
              {th('ordered', 'Заказано')}
              {th('returned', 'Возвраты')}
              {th('period_sold_qty', 'Продано (период)')}
              {th('period_sold_sum', 'Выручка (период)')}
              <th></th>
            </tr></thead>
            <tbody>
              {sorted.map(st => (
                <tr key={st.product_id}>
                  <td>{st.name || `ID ${st.product_id}`}</td>
                  <td className={s.num}>{st.added_to_cart}</td>
                  <td className={s.num}>{st.ordered}</td>
                  <td className={`${s.num} ${st.returned > 0 ? s.warn : ''}`}>{st.returned}</td>
                  <td className={s.num}>{st.period_sold_qty || 0}</td>
                  <td className={s.num}>{fmt(st.period_sold_sum || 0)} ₽</td>
                  <td>
                    <button className={s.btnReturn}
                      onClick={() => api.trackReturn(st.product_id).then(() => load())}
                      title="Зарегистрировать возврат">↩️</button>
                  </td>
                </tr>
              ))}
              {sorted.length === 0 && (
                <tr><td colSpan={7} className={s.msg}>Нет данных</td></tr>
              )}
            </tbody>
          </table>
        </>
      )}
    </div>
  )
}
