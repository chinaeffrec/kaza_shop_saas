import { useState, useEffect, useCallback } from 'react'
import { api } from '../api.js'
import s from './AuditLogPage.module.css'

const PER_PAGE = 50

export default function AuditLogPage({ shopId, isSuperAdmin }) {
  const [items, setItems]   = useState([])
  const [total, setTotal]   = useState(0)
  const [page, setPage]     = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError]   = useState('')

  // filters
  const [action,    setAction]   = useState('')
  const [dateFrom,  setDateFrom] = useState('')
  const [dateTo,    setDateTo]   = useState('')
  const [actorId,   setActorId]  = useState('')   // super_admin only

  // expanded row
  const [expanded, setExpanded] = useState(null)

  const load = useCallback(async () => {
    setLoading(true); setError('')
    const filters = {
      page,
      per_page: PER_PAGE,
      ...(action   ? { action }    : {}),
      ...(dateFrom ? { date_from: dateFrom } : {}),
      ...(dateTo   ? { date_to: dateTo }     : {}),
      ...(actorId  ? { actor_id: actorId }   : {}),
    }
    try {
      let data
      if (isSuperAdmin && !shopId) {
        data = await api.getAuditLogs(filters)
      } else {
        data = await api.getShopAuditLogs(shopId, filters)
      }
      setItems(data.items)
      setTotal(data.total)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [page, action, dateFrom, dateTo, actorId, shopId, isSuperAdmin])

  useEffect(() => { load() }, [load])

  function handleFilter(e) {
    e.preventDefault()
    if (page !== 1) setPage(1); else load()
  }

  const totalPages = Math.max(1, Math.ceil(total / PER_PAGE))

  return (
    <div className={s.page}>
      <h1 className={s.title}>
        {isSuperAdmin && !shopId ? 'Аудит платформы' : 'Журнал событий магазина'}
      </h1>

      {/* Filters */}
      <div className={s.card}>
        <form className={s.filters} onSubmit={handleFilter}>
          <input
            className={s.input}
            placeholder="Событие (напр. product.created)"
            value={action}
            onChange={e => setAction(e.target.value)}
          />
          <input
            className={s.input}
            type="date"
            title="Дата с"
            value={dateFrom}
            onChange={e => setDateFrom(e.target.value)}
          />
          <input
            className={s.input}
            type="date"
            title="Дата по"
            value={dateTo}
            onChange={e => setDateTo(e.target.value)}
          />
          {isSuperAdmin && (
            <input
              className={s.input}
              placeholder="ID актора"
              value={actorId}
              onChange={e => setActorId(e.target.value)}
            />
          )}
          <button className={s.btnPrimary} type="submit">Найти</button>
          <button
            className={s.btnGhost}
            type="button"
            onClick={() => {
              setAction(''); setDateFrom(''); setDateTo(''); setActorId('')
              setPage(1)
            }}
          >
            Сбросить
          </button>
        </form>
      </div>

      {/* Table */}
      <div className={s.card}>
        {loading && <p className={s.muted}>Загрузка…</p>}
        {error   && <p className={s.error}>{error}</p>}

        {!loading && !error && items.length === 0 && (
          <p className={s.muted}>Событий не найдено</p>
        )}

        {!loading && !error && items.length > 0 && (
          <>
            <table className={s.table}>
              <thead>
                <tr>
                  <th>Дата</th>
                  <th>Событие</th>
                  <th>Актор</th>
                  {isSuperAdmin && <th>Магазин</th>}
                  <th>Сущность</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {items.map(item => (
                  <>
                    <tr
                      key={item.id}
                      className={s.row}
                      onClick={() => setExpanded(expanded === item.id ? null : item.id)}
                    >
                      <td className={s.date}>
                        {new Date(item.created_at).toLocaleString('ru-RU', {
                          day: '2-digit', month: '2-digit', year: '2-digit',
                          hour: '2-digit', minute: '2-digit',
                        })}
                      </td>
                      <td>
                        <span className={s.actionTag}>{item.action}</span>
                      </td>
                      <td className={s.actor}>
                        {item.actor_email
                          ? <span title={`ID ${item.actor_id} · ${item.actor_role}`}>{item.actor_email}</span>
                          : <span className={s.muted}>—</span>
                        }
                      </td>
                      {isSuperAdmin && <td>{item.shop_id ?? <span className={s.muted}>—</span>}</td>}
                      <td className={s.muted}>
                        {item.entity_type
                          ? `${item.entity_type}${item.entity_id ? ` #${item.entity_id}` : ''}`
                          : '—'
                        }
                      </td>
                      <td className={s.chevron}>
                        {expanded === item.id ? '▲' : '▼'}
                      </td>
                    </tr>
                    {expanded === item.id && (
                      <tr key={`${item.id}-detail`} className={s.detail}>
                        <td colSpan={isSuperAdmin ? 6 : 5}>
                          <div className={s.detailGrid}>
                            {item.before_data && (
                              <div>
                                <p className={s.detailLabel}>До</p>
                                <pre className={s.json}>
                                  {JSON.stringify(item.before_data, null, 2)}
                                </pre>
                              </div>
                            )}
                            {item.after_data && (
                              <div>
                                <p className={s.detailLabel}>После</p>
                                <pre className={s.json}>
                                  {JSON.stringify(item.after_data, null, 2)}
                                </pre>
                              </div>
                            )}
                            {item.extra && (
                              <div>
                                <p className={s.detailLabel}>Детали</p>
                                <pre className={s.json}>
                                  {JSON.stringify(item.extra, null, 2)}
                                </pre>
                              </div>
                            )}
                            {item.ip_address && (
                              <div>
                                <p className={s.detailLabel}>IP</p>
                                <code className={s.code}>{item.ip_address}</code>
                              </div>
                            )}
                            {!item.before_data && !item.after_data && !item.extra && !item.ip_address && (
                              <p className={s.muted}>Дополнительных данных нет</p>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </>
                ))}
              </tbody>
            </table>

            {/* Pagination */}
            <div className={s.pagination}>
              <span className={s.muted}>Всего: {total}</span>
              <div className={s.pgBtns}>
                <button
                  className={s.pgBtn}
                  disabled={page <= 1}
                  onClick={() => setPage(p => p - 1)}
                >
                  ← Назад
                </button>
                <span className={s.pgInfo}>{page} / {totalPages}</span>
                <button
                  className={s.pgBtn}
                  disabled={page >= totalPages}
                  onClick={() => setPage(p => p + 1)}
                >
                  Вперёд →
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
