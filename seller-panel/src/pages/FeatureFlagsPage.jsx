import { useState, useEffect } from 'react'
import { api } from '../api.js'
import s from './FeatureFlagsPage.module.css'

function FlagRow({ flag, onToggle, onDelete, loading }) {
  return (
    <div className={`${s.row} ${flag.is_enabled ? s.rowOn : s.rowOff}`}>
      <div className={s.rowLeft}>
        <button
          className={`${s.toggle} ${flag.is_enabled ? s.toggleOn : s.toggleOff}`}
          onClick={() => onToggle(flag, !flag.is_enabled)}
          disabled={loading}
          title={flag.is_enabled ? 'Выключить' : 'Включить'}
        >
          <span className={s.toggleKnob} />
        </button>
        <div className={s.rowBody}>
          <span className={s.rowKey}>{flag.key}</span>
          {flag.description && (
            <span className={s.rowDesc}>{flag.description}</span>
          )}
        </div>
      </div>
      <div className={s.rowRight}>
        <span className={`${s.badge} ${flag.is_enabled ? s.badgeOn : s.badgeOff}`}>
          {flag.is_enabled ? 'ON' : 'OFF'}
        </span>
        <span className={s.rowDate}>
          {new Date(flag.updated_at).toLocaleDateString('ru-RU')}
        </span>
        <button
          className={s.deleteBtn}
          onClick={() => onDelete(flag)}
          disabled={loading}
          title="Удалить флаг"
        >
          🗑
        </button>
      </div>
    </div>
  )
}

export default function FeatureFlagsPage() {
  const [flags, setFlags]       = useState([])
  const [loading, setLoading]   = useState(false)
  const [saving, setSaving]     = useState(false)
  const [error, setError]       = useState('')
  const [success, setSuccess]   = useState('')
  const [showForm, setShowForm] = useState(false)
  const [form, setForm]         = useState({ key: '', is_enabled: true, description: '' })

  useEffect(() => { load() }, [])

  async function load() {
    setLoading(true)
    try {
      const data = await api.getFeatureFlags()
      setFlags(data)
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

  async function handleToggle(flag, newVal) {
    setSaving(true)
    try {
      const updated = await api.upsertFeatureFlag({ key: flag.key, is_enabled: newVal, description: flag.description })
      setFlags(prev => prev.map(f => f.key === flag.key ? updated : f))
      flash(`${flag.key}: ${newVal ? 'включён' : 'выключен'}`)
    } catch (e) {
      flash(e.message, true)
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete(flag) {
    if (!window.confirm(`Удалить флаг «${flag.key}»?`)) return
    setSaving(true)
    try {
      await api.deleteFeatureFlag(flag.key)
      setFlags(prev => prev.filter(f => f.key !== flag.key))
      flash('Флаг удалён')
    } catch (e) {
      flash(e.message, true)
    } finally {
      setSaving(false)
    }
  }

  async function handleCreate(e) {
    e.preventDefault()
    if (!form.key.trim()) return
    setSaving(true)
    try {
      const created = await api.upsertFeatureFlag({
        key: form.key.trim(),
        is_enabled: form.is_enabled,
        description: form.description.trim() || null,
      })
      setFlags(prev => {
        const idx = prev.findIndex(f => f.key === created.key)
        return idx >= 0
          ? prev.map(f => f.key === created.key ? created : f)
          : [...prev, created].sort((a, b) => a.key.localeCompare(b.key))
      })
      setShowForm(false)
      setForm({ key: '', is_enabled: true, description: '' })
      flash('Флаг сохранён')
    } catch (e) {
      flash(e.message, true)
    } finally {
      setSaving(false)
    }
  }

  const onCount  = flags.filter(f => f.is_enabled).length
  const offCount = flags.length - onCount

  return (
    <div className={s.page}>
      <div className={s.header}>
        <div>
          <h1 className={s.title}>🚩 Feature Flags</h1>
          <span className={s.counts}>
            <span className={s.countOn}>{onCount} включено</span>
            <span className={s.countOff}>{offCount} выключено</span>
          </span>
        </div>
        <button className={s.addBtn} onClick={() => setShowForm(v => !v)}>
          {showForm ? '✕ Закрыть' : '+ Добавить флаг'}
        </button>
      </div>

      {error   && <div className={s.toastError}>{error}</div>}
      {success && <div className={s.toastSuccess}>{success}</div>}

      {/* New flag form */}
      {showForm && (
        <form className={s.form} onSubmit={handleCreate}>
          <input
            className={s.input}
            placeholder="Ключ флага (напр. cdek_enabled)"
            value={form.key}
            onChange={e => setForm(f => ({ ...f, key: e.target.value }))}
            pattern="[a-z0-9_.:\-]+"
            title="Только строчные буквы, цифры, _ . : -"
            required
          />
          <input
            className={s.input}
            placeholder="Описание (необязательно)"
            value={form.description}
            onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
          />
          <div className={s.formRow}>
            <label className={s.checkLabel}>
              <input
                type="checkbox"
                checked={form.is_enabled}
                onChange={e => setForm(f => ({ ...f, is_enabled: e.target.checked }))}
              />
              Включить сразу
            </label>
            <button className={s.saveBtn} disabled={saving}>
              {saving ? 'Сохранение…' : 'Создать'}
            </button>
          </div>
        </form>
      )}

      {/* Flags list */}
      {loading && flags.length === 0 ? (
        <div className={s.spinner}>Загрузка…</div>
      ) : flags.length === 0 ? (
        <div className={s.empty}>
          <div>🚩</div>
          <div>Флагов пока нет. Создайте первый!</div>
        </div>
      ) : (
        <div className={s.list}>
          {flags.map(flag => (
            <FlagRow
              key={flag.key}
              flag={flag}
              onToggle={handleToggle}
              onDelete={handleDelete}
              loading={saving}
            />
          ))}
        </div>
      )}
    </div>
  )
}
