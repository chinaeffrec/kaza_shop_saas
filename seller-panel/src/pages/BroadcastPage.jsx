import { useState, useEffect } from 'react'
import { api } from '../api.js'
import s from './BroadcastPage.module.css'

function BroadcastCard({ msg, onDelete, onDeactivate, loading }) {
  const date = new Date(msg.created_at).toLocaleString('ru-RU', {
    day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  })
  return (
    <div className={`${s.card} ${!msg.is_active ? s.cardInactive : ''}`}>
      <div className={s.cardHeader}>
        <span className={`${s.badge} ${msg.is_active ? s.badgeActive : s.badgeOff}`}>
          {msg.is_active ? '● Активно' : '○ Скрыто'}
        </span>
        <span className={s.cardDate}>{date}</span>
        {msg.created_by_email && (
          <span className={s.cardAuthor}>{msg.created_by_email}</span>
        )}
      </div>
      <div className={s.cardTitle}>{msg.title}</div>
      <div className={s.cardBody}>{msg.body}</div>
      {msg.expires_at && (
        <div className={s.cardExpiry}>
          Истекает: {new Date(msg.expires_at).toLocaleDateString('ru-RU')}
        </div>
      )}
      <div className={s.cardActions}>
        {msg.is_active && (
          <button
            className={s.btnDeactivate}
            onClick={() => onDeactivate(msg.id)}
            disabled={loading}
          >
            Скрыть
          </button>
        )}
        <button
          className={s.btnDelete}
          onClick={() => onDelete(msg.id)}
          disabled={loading}
        >
          🗑 Удалить
        </button>
      </div>
    </div>
  )
}

function PreviewBanner({ title, body }) {
  if (!title && !body) return null
  return (
    <div className={s.preview}>
      <div className={s.previewLabel}>Preview — так видят владельцы</div>
      <div className={s.banner}>
        <div className={s.bannerTitle}>{title || 'Заголовок'}</div>
        {body && <div className={s.bannerBody}>{body}</div>}
      </div>
    </div>
  )
}

export default function BroadcastPage() {
  const [messages, setMessages] = useState([])
  const [loading, setLoading]   = useState(false)
  const [saving, setSaving]     = useState(false)
  const [error, setError]       = useState('')
  const [success, setSuccess]   = useState('')
  const [showForm, setShowForm] = useState(false)
  const [form, setForm]         = useState({
    title: '',
    body: '',
    expires_at: '',
  })

  useEffect(() => { load() }, [])

  async function load() {
    setLoading(true)
    try {
      const data = await api.getBroadcasts()
      setMessages(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  function flash(msg, isErr = false) {
    if (isErr) { setError(msg); setTimeout(() => setError(''), 4000) }
    else       { setSuccess(msg); setTimeout(() => setSuccess(''), 3000) }
  }

  async function handleCreate(e) {
    e.preventDefault()
    if (!form.title.trim() || !form.body.trim()) return
    setSaving(true)
    try {
      const payload = {
        title: form.title.trim(),
        body: form.body.trim(),
        expires_at: form.expires_at ? new Date(form.expires_at).toISOString() : null,
      }
      const created = await api.createBroadcast(payload)
      setMessages(prev => [created, ...prev])
      setForm({ title: '', body: '', expires_at: '' })
      setShowForm(false)
      flash('Сообщение опубликовано')
    } catch (e) {
      flash(e.message, true)
    } finally {
      setSaving(false)
    }
  }

  async function handleDeactivate(id) {
    setSaving(true)
    try {
      await api.deactivateBroadcast(id)
      setMessages(prev => prev.map(m => m.id === id ? { ...m, is_active: false } : m))
      flash('Сообщение скрыто')
    } catch (e) {
      flash(e.message, true)
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete(id) {
    if (!window.confirm('Удалить сообщение безвозвратно?')) return
    setSaving(true)
    try {
      await api.deleteBroadcast(id)
      setMessages(prev => prev.filter(m => m.id !== id))
      flash('Сообщение удалено')
    } catch (e) {
      flash(e.message, true)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className={s.page}>
      <div className={s.header}>
        <div>
          <h1 className={s.title}>📢 Рассылки</h1>
          <p className={s.desc}>
            Системные сообщения отображаются в seller panel у всех владельцев магазинов.
          </p>
        </div>
        <button className={s.addBtn} onClick={() => setShowForm(v => !v)}>
          {showForm ? '✕ Закрыть' : '+ Новое сообщение'}
        </button>
      </div>

      {error   && <div className={s.toastError}>{error}</div>}
      {success && <div className={s.toastSuccess}>{success}</div>}

      {/* Create form */}
      {showForm && (
        <form className={s.form} onSubmit={handleCreate}>
          <input
            className={s.input}
            placeholder="Заголовок *"
            value={form.title}
            onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
            required
            maxLength={256}
          />
          <textarea
            className={s.textarea}
            placeholder="Текст сообщения *"
            value={form.body}
            onChange={e => setForm(f => ({ ...f, body: e.target.value }))}
            required
            rows={4}
          />
          <div className={s.formRow}>
            <label className={s.expiryLabel}>
              Истекает:
              <input
                type="datetime-local"
                className={s.dateInput}
                value={form.expires_at}
                onChange={e => setForm(f => ({ ...f, expires_at: e.target.value }))}
              />
            </label>
            <button className={s.sendBtn} disabled={saving}>
              {saving ? 'Публикация…' : '📢 Опубликовать'}
            </button>
          </div>
          <PreviewBanner title={form.title} body={form.body} />
        </form>
      )}

      {/* Messages list */}
      {loading && messages.length === 0 ? (
        <div className={s.spinner}>Загрузка…</div>
      ) : messages.length === 0 ? (
        <div className={s.empty}>
          <div>📢</div>
          <div>Рассылок пока нет</div>
        </div>
      ) : (
        <div className={s.list}>
          {messages.map(msg => (
            <BroadcastCard
              key={msg.id}
              msg={msg}
              onDelete={handleDelete}
              onDeactivate={handleDeactivate}
              loading={saving}
            />
          ))}
        </div>
      )}
    </div>
  )
}
