import { useState, useEffect, useCallback } from 'react'
import { api } from '../api.js'
import s from './ReviewsPage.module.css'

const STATUS_TABS = [
  { id: 'pending',  label: '⏳ На модерации' },
  { id: 'approved', label: '✅ Одобренные'   },
  { id: 'all',      label: '📋 Все'           },
]

const STARS = ['★', '★★', '★★★', '★★★★', '★★★★★']

function Stars({ value, size = 15 }) {
  return (
    <span className={s.stars} style={{ fontSize: size }}>
      {[1, 2, 3, 4, 5].map(i => (
        <span key={i} style={{ color: i <= value ? '#f59e0b' : '#d1d5db' }}>★</span>
      ))}
    </span>
  )
}

function ReviewCard({ review, onApprove, onReject, onDelete, loading }) {
  const date = new Date(review.created_at).toLocaleDateString('ru-RU', {
    day: 'numeric', month: 'short', year: 'numeric',
  })
  const isPending = !review.is_approved

  return (
    <div className={`${s.card} ${isPending ? s.cardPending : ''}`}>
      <div className={s.cardHeader}>
        <div className={s.cardMeta}>
          <Stars value={review.rating} />
          <span className={s.cardDate}>{date}</span>
          {isPending
            ? <span className={s.badgePending}>На модерации</span>
            : <span className={s.badgeApproved}>Одобрен</span>
          }
        </div>
        <div className={s.cardActions}>
          {isPending && (
            <button
              className={s.btnApprove}
              onClick={() => onApprove(review.id)}
              disabled={loading}
              title="Одобрить"
            >
              ✓ Одобрить
            </button>
          )}
          {!isPending && (
            <button
              className={s.btnReject}
              onClick={() => onReject(review.id)}
              disabled={loading}
              title="Скрыть"
            >
              ✕ Скрыть
            </button>
          )}
          <button
            className={s.btnDelete}
            onClick={() => onDelete(review.id)}
            disabled={loading}
            title="Удалить"
          >
            🗑
          </button>
        </div>
      </div>

      <div className={s.cardProduct}>
        📦 {review.product?.name ?? `Товар #${review.product_id}`}
      </div>

      {review.text && (
        <p className={s.cardText}>{review.text}</p>
      )}

      <div className={s.cardFooter}>
        <span className={s.cardUser}>Пользователь: {review.user_id}</span>
        {review.order_id && (
          <span className={s.cardOrder}>Заказ #{review.order_id}</span>
        )}
      </div>
    </div>
  )
}

export default function ReviewsPage() {
  const [tab, setTab]               = useState('pending')
  const [reviews, setReviews]       = useState([])
  const [total, setTotal]           = useState(0)
  const [page, setPage]             = useState(1)
  const [loading, setLoading]       = useState(false)
  const [actionLoading, setAction]  = useState(false)
  const [error, setError]           = useState('')
  const [success, setSuccess]       = useState('')

  const PER_PAGE = 30

  const load = useCallback(async (status, pg) => {
    setLoading(true)
    setError('')
    try {
      const data = await api.getReviews(status, null, pg, PER_PAGE)
      setReviews(prev => pg === 1 ? data.items : [...prev, ...data.items])
      setTotal(data.total)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    setReviews([])
    setPage(1)
    load(tab, 1)
  }, [tab, load])

  function loadMore() {
    const next = page + 1
    setPage(next)
    load(tab, next)
  }

  function flash(msg, isError = false) {
    if (isError) { setError(msg); setTimeout(() => setError(''), 4000) }
    else         { setSuccess(msg); setTimeout(() => setSuccess(''), 3000) }
  }

  async function handleApprove(id) {
    setAction(true)
    try {
      await api.moderateReview(id, { is_approved: true })
      setReviews(prev => prev.map(r => r.id === id ? { ...r, is_approved: true } : r))
      // if we're on the pending tab, remove it from the list
      if (tab === 'pending') setReviews(prev => prev.filter(r => r.id !== id))
      flash('Отзыв одобрен')
    } catch (e) {
      flash(e.message, true)
    } finally {
      setAction(false)
    }
  }

  async function handleReject(id) {
    setAction(true)
    try {
      await api.moderateReview(id, { is_approved: false })
      setReviews(prev => prev.map(r => r.id === id ? { ...r, is_approved: false } : r))
      if (tab === 'approved') setReviews(prev => prev.filter(r => r.id !== id))
      flash('Отзыв скрыт')
    } catch (e) {
      flash(e.message, true)
    } finally {
      setAction(false)
    }
  }

  async function handleDelete(id) {
    if (!window.confirm('Удалить отзыв безвозвратно?')) return
    setAction(true)
    try {
      await api.deleteReview(id)
      setReviews(prev => prev.filter(r => r.id !== id))
      setTotal(t => Math.max(0, t - 1))
      flash('Отзыв удалён')
    } catch (e) {
      flash(e.message, true)
    } finally {
      setAction(false)
    }
  }

  const hasMore = reviews.length < total

  return (
    <div className={s.page}>
      <div className={s.header}>
        <h1 className={s.title}>⭐ Отзывы</h1>
        <span className={s.counter}>{total > 0 ? `${total} отзыв${total === 1 ? '' : total < 5 ? 'а' : 'ов'}` : ''}</span>
      </div>

      {/* Tabs */}
      <div className={s.tabs}>
        {STATUS_TABS.map(t => (
          <button
            key={t.id}
            className={`${s.tab} ${tab === t.id ? s.tabActive : ''}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Toast messages */}
      {error   && <div className={s.toastError}>{error}</div>}
      {success && <div className={s.toastSuccess}>{success}</div>}

      {/* Content */}
      {loading && reviews.length === 0 ? (
        <div className={s.spinner}>Загрузка…</div>
      ) : reviews.length === 0 ? (
        <div className={s.empty}>
          <div className={s.emptyIcon}>⭐</div>
          <div className={s.emptyText}>
            {tab === 'pending'  && 'Нет отзывов на модерации'}
            {tab === 'approved' && 'Нет одобренных отзывов'}
            {tab === 'all'      && 'Отзывов пока нет'}
          </div>
        </div>
      ) : (
        <div className={s.list}>
          {reviews.map(r => (
            <ReviewCard
              key={r.id}
              review={r}
              onApprove={handleApprove}
              onReject={handleReject}
              onDelete={handleDelete}
              loading={actionLoading}
            />
          ))}
          {hasMore && (
            <button
              className={s.loadMore}
              onClick={loadMore}
              disabled={loading}
            >
              {loading ? 'Загрузка…' : 'Показать ещё'}
            </button>
          )}
        </div>
      )}
    </div>
  )
}
