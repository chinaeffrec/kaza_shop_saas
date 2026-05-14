import { useState, useEffect, useCallback } from 'react'
import { api } from '../api.js'
import s from './OrdersPage.module.css'
import { useToast } from '../components/Toast.jsx'

export default function OrdersPage() {
  const toast = useToast()
  const [orders, setOrders]         = useState([])
  const [ordersPage, setOrdersPage] = useState(1)
  const [ordersTotal, setOrdersTotal] = useState(0)
  const [ordersPages, setOrdersPages] = useState(1)
  const [statuses, setStatuses]     = useState([])
  const [filter, setFilter]         = useState('')
  const [loading, setLoading]       = useState(true)
  const [expanded, setExpanded]     = useState(null)
  const [detail, setDetail]         = useState(null)
  const [updating, setUpdating]     = useState(null)

  const load = useCallback(async (pageOverride) => {
    const page = pageOverride || ordersPage
    setLoading(true)
    try {
      const [ordRes, st] = await Promise.all([api.getOrders(filter, page, 20), api.getOrderStatuses()])
      setOrders(ordRes.items)
      setOrdersTotal(ordRes.total)
      setOrdersPages(ordRes.pages)
      setOrdersPage(ordRes.page)
      setStatuses(st)
    } catch(e) { toast(e.message) }
    finally { setLoading(false) }
  }, [filter, ordersPage])

  useEffect(() => { setOrdersPage(1); load(1) }, [filter])
  useEffect(() => {
    const t = setInterval(() => {
      load(ordersPage)
    }, 30000)
    return () => clearInterval(t)
  }, [load, ordersPage])

  async function expand(order) {
    if (expanded === order.id) { setExpanded(null); setDetail(null); return }
    setExpanded(order.id); setDetail(null)
    const d = await api.getOrder(order.id).catch(() => null)
    setDetail(d)
  }

  async function changeStatus(orderId, newStatus) {
    setUpdating(orderId)
    try { await api.updateOrderStatus(orderId, newStatus); await load() }
    catch(e) { toast(e.message) }
    finally { setUpdating(null) }
  }

  async function generateReceipt(orderId) {
    if (!confirm('Сформировать чек и отправить покупателю?')) return
    try {
      const res = await api.generateReceipt(orderId)
      toast(res.sent_to_buyer
        ? '✅ Чек сформирован и отправлен покупателю'
        : '⚠️ Чек сформирован, но не отправлен. Проверьте связь с ботом.')
    } catch(e) {
      toast('Ошибка: ' + e.message)
    }
  }

  async function createPaymentLink(orderId) {
    try {
      const res = await api.createPayment(orderId)
      if (res.confirmation_url) {
        window.open(res.confirmation_url, '_blank')
        toast('💳 Ссылка на оплату создана', 'success')
      }
      await load(ordersPage)
    } catch(e) { toast('Ошибка: ' + e.message, 'error') }
  }

  async function doRefund(orderId) {
    if (!confirm('Инициировать возврат по заказу #' + orderId + '? Это действие необратимо.')) return
    try {
      const res = await api.createRefund(orderId)
      toast(`↩️ Возврат создан: ${res.refund_id}`, 'success')
      await load(ordersPage)
    } catch(e) { toast('Ошибка возврата: ' + e.message, 'error') }
  }

  const _PAY_STATUS_LABELS = {
    pending: '⏳ Ожидает оплаты',
    waiting_for_capture: '🔄 Подтверждение',
    succeeded: '✅ Оплачен',
    canceled: '❌ Отменён',
    refunded: '↩️ Возврат',
  }

  return (
    <div>
      <div className={s.toolbar}>
        <h1 className={s.title}>Заказы <span className={s.count}>{ordersTotal}</span></h1>
        <button className={s.refresh} onClick={() => load(ordersPage)}>↻ Обновить</button>
      </div>

      <div className={s.tabs}>
        <button className={`${s.tab} ${filter===''?s.activeTab:''}`} onClick={()=>setFilter('')}>
          Все ({ordersTotal})
        </button>
        {statuses.map(st => (
          <button key={st.value}
            className={`${s.tab} ${filter===st.value?s.activeTab:''}`}
            onClick={()=>setFilter(st.value)}>
            {st.label}
          </button>
        ))}
      </div>

      {ordersPages > 1 && (
        <div style={{display:'flex', gap:8, alignItems:'center', marginBottom:12, fontSize:13, color:'#555'}}>
          <button onClick={() => load(ordersPage - 1)} disabled={ordersPage <= 1}
            style={{padding:'4px 12px', borderRadius:6, border:'1px solid #ddd', background:'#fff', cursor:ordersPage<=1?'default':'pointer'}}>
            ←
          </button>
          <span>Стр. {ordersPage} из {ordersPages} (всего {ordersTotal})</span>
          <button onClick={() => load(ordersPage + 1)} disabled={ordersPage >= ordersPages}
            style={{padding:'4px 12px', borderRadius:6, border:'1px solid #ddd', background:'#fff', cursor:ordersPage>=ordersPages?'default':'pointer'}}>
            →
          </button>
        </div>
      )}

      {loading ? <p className={s.msg}>Загрузка...</p> : orders.length===0 ? <p className={s.msg}>Заказов нет</p> : (
        <div className={s.list}>
          {orders.map(o => (
            <div key={o.id} className={s.card}>
              <div className={s.cardHead} onClick={()=>expand(o)}>
                <span className={s.orderId}>#{o.id}</span>
                <span className={s.userName}>{o.user_name || `ID ${o.user_id}`}</span>
                {o.user_contact && <span className={s.userContact}>{o.user_contact}</span>}
                <span className={s.total}>{(o.total||0).toLocaleString()} ₽</span>
                <span className={s.statusBadge}>{o.status_label || o.status}</span>
                <span className={s.date}>{o.created_at?.slice(0,10)}</span>
                <span className={s.chevron}>{expanded===o.id?'▲':'▼'}</span>
              </div>

              {expanded===o.id && (
                <div className={s.cardBody}>
                  <div className={s.infoGrid}>
                    <div><span className={s.infoLabel}>Покупатель:</span> {o.user_name || `ID ${o.user_id}`}</div>
                    {o.user_contact && <div><span className={s.infoLabel}>Контакт:</span> {o.user_contact}</div>}
                    {o.pvz_address
                      ? <div><span className={s.infoLabel}>📦 СДЭК ПВЗ:</span> {o.pvz_address}</div>
                      : o.delivery_address && <div><span className={s.infoLabel}>Адрес:</span> {o.delivery_address}</div>
                    }
                    {o.delivery_cost > 0 && <div><span className={s.infoLabel}>Доставка:</span> {o.delivery_cost} ₽</div>}
                    {o.discount > 0 && <div><span className={s.infoLabel}>Скидка:</span> −{o.discount} ₽ {o.promo_code && `(${o.promo_code})`}</div>}
                    {o.comment && <div><span className={s.infoLabel}>Комментарий:</span> {o.comment}</div>}
                    {/* CDEK tracking block */}
                    {o.cdek_order_uuid && (
                      <div className={s.cdekBlock}>
                        <div className={s.cdekTitle}>📦 СДЭК</div>
                        {o.cdek_track_number
                          ? <a className={s.trackLink}
                              href={`https://www.cdek.ru/ru/tracking?order_id=${o.cdek_track_number}`}
                              target="_blank" rel="noreferrer">
                              🔗 Отследить: {o.cdek_track_number}
                            </a>
                          : <span className={s.trackPending}>Трек-номер ещё не присвоен</span>
                        }
                        {o.cdek_status && <div className={s.cdekStatus}>{o.cdek_status}</div>}
                      </div>
                    )}
                    {/* YooKassa payment block */}
                    {o.payment_id && (
                      <div className={s.cdekBlock}>
                        <div className={s.cdekTitle}>💳 ЮКасса</div>
                        <div>
                          <span className={s.infoLabel}>Статус оплаты: </span>
                          <span className={s.cdekStatus}>
                            {_PAY_STATUS_LABELS[o.payment_status] || o.payment_status || '—'}
                          </span>
                        </div>
                        {o.payment_status === 'succeeded' && !o.refund_id && (
                          <button onClick={() => doRefund(o.id)}
                            style={{marginTop:6, background:'#e53935', color:'#fff',
                              padding:'5px 14px', borderRadius:7, fontSize:12,
                              border:'none', cursor:'pointer'}}>
                            ↩️ Инициировать возврат
                          </button>
                        )}
                        {o.refund_id && (
                          <div style={{fontSize:12, color:'#888', marginTop:4}}>
                            Возврат: {o.refund_id}
                          </div>
                        )}
                      </div>
                    )}
                    {!o.payment_id && (
                      <div style={{marginTop: 8}}>
                        <button onClick={() => createPaymentLink(o.id)}
                          style={{background:'#1976d2', color:'#fff', padding:'6px 14px',
                            borderRadius:7, fontSize:12, border:'none', cursor:'pointer'}}>
                          💳 Создать ссылку оплаты
                        </button>
                      </div>
                    )}
                    <div style={{marginTop: 14}}>
                      <button
                          onClick={() => generateReceipt(o.id)}
                          style={{
                            background: '#43a047', color: '#fff', padding: '7px 16px',
                            borderRadius: 8, fontSize: 13, border: 'none', cursor: 'pointer'
                      }}
                      >
                        🧾 Сформировать чек
                      </button>
                    </div>
                  </div>

                  <h4 className={s.subTitle}>Товары</h4>
                  {!detail ? <p className={s.loadingTxt}>Загрузка...</p> : (
                    <table className={s.itemsTable}>
                      <thead><tr><th>Фото</th><th>Товар</th><th>Цена</th><th>Кол-во</th><th>Сумма</th></tr></thead>
                      <tbody>
                        {detail.items?.map((it,i) => (
                          <tr key={i}>
                            <td className={s.photoCell}>
                              {it.image_url ? (
                                <img
                                  src={`${api.BASE}${it.image_url}`}
                                  alt={it.name}
                                  className={s.thumb}
                                  onError={e => { e.currentTarget.style.display = 'none' }}
                                />
                              ) : (
                                <span className={s.thumbFallback}>нет</span>
                              )}
                            </td>
                            <td>{it.name}</td>
                            <td>{(it.price||0).toLocaleString()} ₽</td>
                            <td>{it.quantity}</td>
                            <td>{(it.sum||0).toLocaleString()} ₽</td>
                          </tr>
                        ))}
                        <tr className={s.totalRow}>
                          <td colSpan={4}><b>Итого</b></td>
                          <td><b>{(o.total||0).toLocaleString()} ₽</b></td>
                        </tr>
                      </tbody>
                    </table>
                  )}

                  <h4 className={s.subTitle}>Изменить статус</h4>
                  <div className={s.statusRow}>
                    {statuses.map(st => (
                      <button key={st.value}
                        className={`${s.statusBtn} ${o.status===st.value?s.activeSt:''}`}
                        disabled={updating===o.id || o.status===st.value}
                        onClick={()=>changeStatus(o.id, st.value)}>{st.label}</button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
