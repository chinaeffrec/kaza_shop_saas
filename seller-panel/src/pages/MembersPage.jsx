import { useState, useEffect, useCallback } from 'react'
import { api } from '../api.js'
import s from './MembersPage.module.css'

const ROLE_LABELS = {
  owner:   '👑 Владелец',
  manager: '🛠 Менеджер',
  support: '💬 Поддержка',
}

const ROLE_DESCRIPTIONS = {
  owner:   'Полный доступ: товары, заказы, статистика, настройки, команда',
  manager: 'Товары, заказы, FAQ, импорт. Без деструктивных операций',
  support: 'Только просмотр и обновление статусов заказов',
}

export default function MembersPage({ shopId }) {
  const [members, setMembers]   = useState([])
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState('')

  // invite form
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteRole, setInviteRole]   = useState('manager')
  const [inviting, setInviting]       = useState(false)
  const [inviteError, setInviteError] = useState('')

  // edit role inline
  const [editingId, setEditingId]   = useState(null)
  const [editingRole, setEditingRole] = useState('')
  const [saving, setSaving]           = useState(false)

  const load = useCallback(async () => {
    if (!shopId) return
    setLoading(true); setError('')
    try {
      const data = await api.getMembers(shopId)
      setMembers(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [shopId])

  useEffect(() => { load() }, [load])

  async function handleInvite(e) {
    e.preventDefault()
    if (!inviteEmail.trim()) return
    setInviting(true); setInviteError('')
    try {
      await api.inviteMember(shopId, inviteEmail.trim(), inviteRole)
      setInviteEmail(''); setInviteRole('manager')
      await load()
    } catch (e) {
      setInviteError(e.message)
    } finally {
      setInviting(false)
    }
  }

  async function handleRoleSave(userId) {
    setSaving(true)
    try {
      await api.updateMemberRole(shopId, userId, editingRole)
      setEditingId(null)
      await load()
    } catch (e) {
      alert(e.message)
    } finally {
      setSaving(false)
    }
  }

  async function handleRemove(userId, email) {
    if (!confirm(`Удалить ${email} из команды?`)) return
    try {
      await api.removeMember(shopId, userId)
      await load()
    } catch (e) {
      alert(e.message)
    }
  }

  return (
    <div className={s.page}>
      <h1 className={s.title}>Команда магазина</h1>

      {/* Invite form */}
      <div className={s.card}>
        <h2 className={s.cardTitle}>Добавить участника</h2>
        <p className={s.hint}>
          Участник должен уже иметь аккаунт на платформе. Введите его email — и выберите роль.
        </p>
        <form className={s.inviteForm} onSubmit={handleInvite}>
          <input
            className={s.input}
            type="email"
            placeholder="email@example.com"
            value={inviteEmail}
            onChange={e => setInviteEmail(e.target.value)}
            required
          />
          <select
            className={s.select}
            value={inviteRole}
            onChange={e => setInviteRole(e.target.value)}
          >
            <option value="manager">Менеджер</option>
            <option value="support">Поддержка</option>
            <option value="owner">Владелец</option>
          </select>
          <button className={s.btnPrimary} type="submit" disabled={inviting}>
            {inviting ? 'Добавление…' : '+ Добавить'}
          </button>
        </form>
        {inviteError && <p className={s.error}>{inviteError}</p>}

        {/* Role descriptions */}
        <div className={s.roleDefs}>
          {Object.entries(ROLE_DESCRIPTIONS).map(([role, desc]) => (
            <div key={role} className={s.roleDef}>
              <span className={s.roleChip}>{ROLE_LABELS[role]}</span>
              <span className={s.roleDesc}>{desc}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Members list */}
      <div className={s.card}>
        <h2 className={s.cardTitle}>Участники</h2>
        {loading && <p className={s.muted}>Загрузка…</p>}
        {error   && <p className={s.error}>{error}</p>}
        {!loading && !error && members.length === 0 && (
          <p className={s.muted}>Участников пока нет</p>
        )}
        {!loading && !error && members.length > 0 && (
          <table className={s.table}>
            <thead>
              <tr>
                <th>Email</th>
                <th>Роль</th>
                <th>Добавлен</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {members.map(m => (
                <tr key={m.id}>
                  <td>{m.email}</td>
                  <td>
                    {editingId === m.id ? (
                      <div className={s.editRow}>
                        <select
                          className={s.selectSm}
                          value={editingRole}
                          onChange={e => setEditingRole(e.target.value)}
                        >
                          <option value="owner">Владелец</option>
                          <option value="manager">Менеджер</option>
                          <option value="support">Поддержка</option>
                        </select>
                        <button
                          className={s.btnSmPrimary}
                          onClick={() => handleRoleSave(m.user_id)}
                          disabled={saving}
                        >
                          {saving ? '…' : '✓'}
                        </button>
                        <button
                          className={s.btnSm}
                          onClick={() => setEditingId(null)}
                        >
                          ✕
                        </button>
                      </div>
                    ) : (
                      <span
                        className={s.roleTag}
                        data-role={m.role}
                        onClick={() => { setEditingId(m.id); setEditingRole(m.role) }}
                        title="Нажмите для изменения"
                      >
                        {ROLE_LABELS[m.role] ?? m.role}
                      </span>
                    )}
                  </td>
                  <td className={s.muted}>
                    {new Date(m.created_at).toLocaleDateString('ru-RU')}
                  </td>
                  <td>
                    <button
                      className={s.btnDanger}
                      onClick={() => handleRemove(m.user_id, m.email)}
                      title="Удалить из команды"
                    >
                      Удалить
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
