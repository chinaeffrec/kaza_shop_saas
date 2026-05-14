import { useState, useEffect, useRef } from 'react'
import { api } from '../api.js'
import s from './NotificationCenter.module.css'

const POLL_INTERVAL = 30_000

function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const now = new Date()
  const diff = Math.floor((now - d) / 1000)
  if (diff < 60) return 'только что'
  if (diff < 3600) return `${Math.floor(diff / 60)} мин. назад`
  if (diff < 86400) return `${Math.floor(diff / 3600)} ч. назад`
  return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
}

/**
 * Notification center — bell icon that aggregates:
 *  - New/unconfirmed orders (from orders API)
 *  - Active platform broadcasts
 *
 * Props:
 *  newOrders  — count from parent polling (to avoid duplicate requests)
 *  broadcasts — active broadcasts array from parent
 *  onNavigate — (page: string) => void
 */
export default function NotificationCenter({ newOrders = 0, broadcasts = [], onNavigate }) {
  const [open, setOpen] = useState(false)
  const [recentOrders, setRecentOrders] = useState([])
  const [loadingOrders, setLoadingOrders] = useState(false)
  const ref = useRef(null)

  // Close on outside click
  useEffect(() => {
    function onOutside(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    if (open) document.addEventListener('mousedown', onOutside)
    return () => document.removeEventListener('mousedown', onOutside)
  }, [open])

  // Load recent new orders when panel opens
  useEffect(() => {
    if (!open) return
    setLoadingOrders(true)
    api.getOrders('new', 1, 5)
      .then(res => setRecentOrders(res.items || []))
      .catch(() => setRecentOrders([]))
      .finally(() => setLoadingOrders(false))
  }, [open])

  const totalBadge = newOrders + broadcasts.length
  const hasItems = newOrders > 0 || broadcasts.length > 0

  return (
    <div className={s.wrap} ref={ref}>
      <button
        className={s.bell}
        onClick={() => setOpen(v => !v)}
        aria-label="Уведомления"
        title="Уведомления"
      >
        🔔
        {totalBadge > 0 && (
          <span className={s.badge}>{totalBadge > 99 ? '99+' : totalBadge}</span>
        )}
      </button>

      {open && (
        <div className={s.panel}>
          <div className={s.header}>
            <span className={s.headerTitle}>Уведомления</span>
            {hasItems && (
              <span className={s.count}>{totalBadge}</span>
            )}
          </div>

          {/* Platform broadcasts */}
          {broadcasts.map(b => (
            <div key={b.id} className={`${s.item} ${s.itemBroadcast}`}>
              <span className={s.itemIcon}>📢</span>
              <div className={s.itemBody}>
                <div className={s.itemTitle}>{b.title}</div>
                <div className={s.itemText}>{b.body}</div>
              </div>
            </div>
          ))}

          {/* New orders */}
          {newOrders > 0 && (
            <div className={`${s.item} ${s.itemOrder}`}>
              <span className={s.itemIcon}>🧾</span>
              <div className={s.itemBody}>
                <div className={s.itemTitle}>Новые заказы</div>
                {loadingOrders ? (
                  <div className={s.itemText}>Загрузка…</div>
                ) : (
                  <>
                    <div className={s.itemText}>
                      {newOrders > 0
                        ? `${newOrders} заказ${newOrders === 1 ? '' : newOrders < 5 ? 'а' : 'ов'} ожидают обработки`
                        : 'Нет новых заказов'
                      }
                    </div>
                    {recentOrders.slice(0, 3).map(o => (
                      <div key={o.id} className={s.orderRow}>
                        <span>#{o.id}</span>
                        <span className={s.orderAmount}>{o.total?.toLocaleString('ru-RU')} ₽</span>
                        <span className={s.orderTime}>{formatTime(o.created_at)}</span>
                      </div>
                    ))}
                  </>
                )}
              </div>
            </div>
          )}

          {!hasItems && (
            <div className={s.empty}>Нет новых уведомлений</div>
          )}

          {newOrders > 0 && (
            <button
              className={s.viewAll}
              onClick={() => { onNavigate?.('orders'); setOpen(false) }}
            >
              Открыть все заказы →
            </button>
          )}
        </div>
      )}
    </div>
  )
}
