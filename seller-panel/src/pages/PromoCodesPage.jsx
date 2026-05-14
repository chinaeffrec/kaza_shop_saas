import { useEffect, useState } from 'react'
import { api } from '../api'
import s from './PromoCodesPage.module.css'

const EMPTY_FORM = {
  code: '',
  discount_type: 'percent',
  value: '',
  min_order_amount: '',
  max_uses: '',
  expires_at: '',
  is_active: true,
}

function fmtDate(iso) {
  if (!iso) return '—'
  return iso.slice(0, 10)
}

function fmtValue(promo) {
  return promo.discount_type === 'percent'
    ? `${promo.value}%`
    : `${promo.value} ₽`
}

export default function PromoCodesPage() {
  const [promos, setPromos] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState(null)   // promo id or null
  const [form, setForm] = useState(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const [formErr, setFormErr] = useState('')
  const [deleting, setDeleting] = useState(null)

  async function load() {
    setLoading(true)
    setErr('')
    try {
      const data = await api.getPromos()
      setPromos(data.items || [])
      setTotal(data.total || 0)
    } catch (e) {
      setErr(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  function openCreate() {
    setForm(EMPTY_FORM)
    setEditing(null)
    setFormErr('')
    setShowForm(true)
  }

  function openEdit(promo) {
    setForm({
      code: promo.code,
      discount_type: promo.discount_type,
      value: String(promo.value),
      min_order_amount: promo.min_order_amount != null ? String(promo.min_order_amount) : '',
      max_uses: promo.max_uses != null ? String(promo.max_uses) : '',
      expires_at: promo.expires_at ? promo.expires_at.slice(0, 10) : '',
      is_active: promo.is_active,
    })
    setEditing(promo.id)
    setFormErr('')
    setShowForm(true)
  }

  function closeForm() {
    setShowForm(false)
    setEditing(null)
    setFormErr('')
  }

  function set(key, val) {
    setForm(f => ({ ...f, [key]: val }))
  }

  async function save() {
    setFormErr('')
    if (!form.code.trim()) return setFormErr('Введите код')
    const value = parseInt(form.value)
    if (!value || value <= 0) return setFormErr('Введите корректное значение скидки')
    if (form.discount_type === 'percent' && value > 100) return setFormErr('Процент не может превышать 100')

    const payload = {
      code: form.code.trim().toUpperCase(),
      discount_type: form.discount_type,
      value,
      min_order_amount: form.min_order_amount ? parseInt(form.min_order_amount) : null,
      max_uses: form.max_uses ? parseInt(form.max_uses) : null,
      expires_at: form.expires_at ? form.expires_at + 'T23:59:59Z' : null,
      is_active: form.is_active,
    }

    setSaving(true)
    try {
      if (editing) {
        await api.updatePromo(editing, payload)
      } else {
        await api.createPromo(payload)
      }
      closeForm()
      await load()
    } catch (e) {
      setFormErr(e.message)
    } finally {
      setSaving(false)
    }
  }

  async function toggleActive(promo) {
    try {
      await api.updatePromo(promo.id, { is_active: !promo.is_active })
      await load()
    } catch (e) {
      setErr(e.message)
    }
  }

  async function deletePromo(id) {
    if (!window.confirm('Удалить промокод?')) return
    setDeleting(id)
    try {
      await api.deletePromo(id)
      await load()
    } catch (e) {
      setErr(e.message)
    } finally {
      setDeleting(null)
    }
  }

  return (
    <div>
      <div className={s.toolbar}>
        <span className={s.title}>Промокоды <span className={s.badge}>{total}</span></span>
        <button className={s.btnCreate} onClick={openCreate}>+ Создать</button>
      </div>

      {err && <div className={s.error}>{err}</div>}

      {loading ? (
        <div className={s.msg}>Загрузка…</div>
      ) : promos.length === 0 ? (
        <div className={s.msg}>Промокодов пока нет. Создайте первый!</div>
      ) : (
        <table className={s.table}>
          <thead>
            <tr>
              <th>Код</th>
              <th>Скидка</th>
              <th>Мин. сумма</th>
              <th>Использований</th>
              <th>Истекает</th>
              <th>Статус</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {promos.map(p => (
              <tr key={p.id} className={!p.is_active ? s.inactive : ''}>
                <td><code className={s.code}>{p.code}</code></td>
                <td className={s.discount}>{fmtValue(p)}</td>
                <td>{p.min_order_amount != null ? `${p.min_order_amount} ₽` : '—'}</td>
                <td className={s.num}>
                  {p.used_count}
                  {p.max_uses != null ? ` / ${p.max_uses}` : ''}
                </td>
                <td>{fmtDate(p.expires_at)}</td>
                <td>
                  <span className={p.is_active ? s.active : s.disabled}>
                    {p.is_active ? 'Активен' : 'Отключён'}
                  </span>
                </td>
                <td className={s.actions}>
                  <button className={s.btnEdit} onClick={() => openEdit(p)}>✏️</button>
                  <button
                    className={p.is_active ? s.btnOff : s.btnOn}
                    onClick={() => toggleActive(p)}
                    title={p.is_active ? 'Отключить' : 'Включить'}
                  >
                    {p.is_active ? '⏸' : '▶️'}
                  </button>
                  <button
                    className={s.btnDelete}
                    onClick={() => deletePromo(p.id)}
                    disabled={deleting === p.id}
                  >🗑</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {showForm && (
        <div className={s.overlay} onClick={e => e.target === e.currentTarget && closeForm()}>
          <div className={s.modal}>
            <div className={s.modalHeader}>
              <span>{editing ? 'Редактировать промокод' : 'Новый промокод'}</span>
              <button className={s.btnClose} onClick={closeForm}>✕</button>
            </div>

            <div className={s.field}>
              <label>Код промокода *</label>
              <input
                className={s.input}
                value={form.code}
                onChange={e => set('code', e.target.value.toUpperCase())}
                placeholder="SUMMER20"
                disabled={!!editing}
              />
            </div>

            <div className={s.row}>
              <div className={s.field}>
                <label>Тип скидки *</label>
                <select
                  className={s.input}
                  value={form.discount_type}
                  onChange={e => set('discount_type', e.target.value)}
                >
                  <option value="percent">Процент (%)</option>
                  <option value="fixed">Фиксированная (₽)</option>
                </select>
              </div>
              <div className={s.field}>
                <label>
                  {form.discount_type === 'percent' ? 'Процент скидки *' : 'Сумма скидки (₽) *'}
                </label>
                <input
                  className={s.input}
                  type="number"
                  min={1}
                  max={form.discount_type === 'percent' ? 100 : undefined}
                  value={form.value}
                  onChange={e => set('value', e.target.value)}
                  placeholder={form.discount_type === 'percent' ? '10' : '500'}
                />
              </div>
            </div>

            <div className={s.row}>
              <div className={s.field}>
                <label>Мин. сумма заказа (₽)</label>
                <input
                  className={s.input}
                  type="number"
                  min={0}
                  value={form.min_order_amount}
                  onChange={e => set('min_order_amount', e.target.value)}
                  placeholder="1000"
                />
              </div>
              <div className={s.field}>
                <label>Макс. использований</label>
                <input
                  className={s.input}
                  type="number"
                  min={1}
                  value={form.max_uses}
                  onChange={e => set('max_uses', e.target.value)}
                  placeholder="Без ограничений"
                />
              </div>
            </div>

            <div className={s.field}>
              <label>Действует до</label>
              <input
                className={s.input}
                type="date"
                value={form.expires_at}
                onChange={e => set('expires_at', e.target.value)}
              />
            </div>

            <div className={s.checkRow}>
              <input
                type="checkbox"
                id="promo_active"
                checked={form.is_active}
                onChange={e => set('is_active', e.target.checked)}
              />
              <label htmlFor="promo_active">Активен</label>
            </div>

            {formErr && <div className={s.error}>{formErr}</div>}

            <div className={s.modalFooter}>
              <button className={s.btnCancel} onClick={closeForm}>Отмена</button>
              <button className={s.btnSave} onClick={save} disabled={saving}>
                {saving ? 'Сохранение…' : 'Сохранить'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
