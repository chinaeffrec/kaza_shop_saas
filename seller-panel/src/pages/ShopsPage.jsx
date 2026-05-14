import { useState, useEffect, useCallback } from 'react'
import { api } from '../api.js'
import { useToast } from '../components/Toast.jsx'

const STATUS_LABELS = { trial: 'Триал', active: 'Активен', suspended: 'Заблокирован' }
const STATUS_COLORS = { trial: '#f0a500', active: '#2e7d32', suspended: '#c62828' }
const PLAN_LABELS   = { free: 'Free', trial: 'Триал', basic: 'Basic', pro: 'Pro' }

const EMPTY_FORM = {
  owner_id: '', name: '', bot_token: '', plan: 'trial',
}

export default function ShopsPage() {
  const toast = useToast()

  // ── List state ────────────────────────────────────────────────────────────────
  const [shops, setShops]       = useState([])
  const [total, setTotal]       = useState(0)
  const [page, setPage]         = useState(1)
  const [loading, setLoading]   = useState(false)
  const [filterStatus, setFilterStatus] = useState('')

  // ── Detail / edit state ───────────────────────────────────────────────────────
  const [selected, setSelected] = useState(null)   // full shop object
  const [stats, setStats]       = useState(null)
  const [statsLoading, setStatsLoading] = useState(false)

  // ── Modals ────────────────────────────────────────────────────────────────────
  const [showCreate, setShowCreate] = useState(false)
  const [createForm, setCreateForm] = useState(EMPTY_FORM)
  const [createSaving, setCreateSaving] = useState(false)

  // ── Inline editing ────────────────────────────────────────────────────────────
  const [editName, setEditName]     = useState('')
  const [editStatus, setEditStatus] = useState('')
  const [editPlan, setEditPlan]     = useState('')
  const [editBotToken, setEditBotToken] = useState('')
  const [editOwnerId, setEditOwnerId]   = useState('')
  const [saving, setSaving]         = useState(false)

  // ── Users (for assign dropdown) ───────────────────────────────────────────────
  const [users, setUsers]           = useState([])

  const PER_PAGE = 20

  const loadShops = useCallback(async (p = page) => {
    setLoading(true)
    try {
      const filters = filterStatus ? { status: filterStatus } : {}
      const res = await api.getShops(p, PER_PAGE, filters)
      setShops(res.items)
      setTotal(res.total)
    } catch (e) {
      toast.error(e.message)
    } finally {
      setLoading(false)
    }
  }, [page, filterStatus])

  useEffect(() => { loadShops() }, [loadShops])

  useEffect(() => {
    api.getPlatformUsers().then(setUsers).catch(() => {})
  }, [])

  function openShop(shop) {
    setSelected(shop)
    setEditName(shop.name)
    setEditStatus(shop.status)
    setEditPlan(shop.plan)
    setEditBotToken('')
    setEditOwnerId(shop.owner_id)
    setStats(null)
    // load stats
    setStatsLoading(true)
    api.getShopStats(shop.id)
      .then(setStats)
      .catch(() => {})
      .finally(() => setStatsLoading(false))
  }

  function closeDetail() {
    setSelected(null); setStats(null)
  }

  // ── CRUD helpers ──────────────────────────────────────────────────────────────
  async function createShop() {
    if (!createForm.owner_id || !createForm.name) return
    setCreateSaving(true)
    try {
      const payload = {
        owner_id: parseInt(createForm.owner_id),
        name: createForm.name,
        plan: createForm.plan,
      }
      if (createForm.bot_token) payload.bot_token = createForm.bot_token
      await api.createShop(payload)
      toast.success('Магазин создан')
      setShowCreate(false)
      setCreateForm(EMPTY_FORM)
      loadShops(1); setPage(1)
    } catch (e) {
      toast.error(e.message)
    } finally {
      setCreateSaving(false)
    }
  }

  async function saveName() {
    if (!editName.trim() || editName === selected.name) return
    setSaving(true)
    try {
      const updated = await api.updateShop(selected.id, { name: editName })
      setSelected(updated)
      toast.success('Название обновлено')
      loadShops()
    } catch (e) { toast.error(e.message) }
    finally { setSaving(false) }
  }

  async function saveStatus() {
    if (editStatus === selected.status) return
    setSaving(true)
    try {
      const updated = await api.setShopStatus(selected.id, editStatus)
      setSelected(updated)
      toast.success('Статус обновлён')
      loadShops()
    } catch (e) { toast.error(e.message) }
    finally { setSaving(false) }
  }

  async function savePlan() {
    if (editPlan === selected.plan) return
    setSaving(true)
    try {
      // Update both the legacy shop.plan field and the new subscriptions table
      const [updated] = await Promise.all([
        api.setShopPlan(selected.id, editPlan),
        api.assignPlan(selected.id, editPlan).catch(() => {}),  // best-effort sync
      ])
      setSelected(updated)
      toast.success('Тариф обновлён')
      loadShops()
    } catch (e) { toast.error(e.message) }
    finally { setSaving(false) }
  }

  async function saveBotToken() {
    if (!editBotToken.trim()) return
    setSaving(true)
    try {
      const updated = await api.setShopBotToken(selected.id, editBotToken)
      setSelected(updated)
      setEditBotToken('')
      toast.success('Токен сохранён')
    } catch (e) { toast.error(e.message) }
    finally { setSaving(false) }
  }

  async function removeBotToken() {
    if (!confirm('Удалить бот-токен?')) return
    setSaving(true)
    try {
      const updated = await api.deleteShopBotToken(selected.id)
      setSelected(updated)
      toast.success('Токен удалён')
    } catch (e) { toast.error(e.message) }
    finally { setSaving(false) }
  }

  async function saveOwner() {
    const ownerId = parseInt(editOwnerId)
    if (!ownerId || ownerId === selected.owner_id) return
    setSaving(true)
    try {
      const updated = await api.assignShopOwner(selected.id, ownerId)
      setSelected(updated)
      toast.success('Владелец назначен')
      loadShops()
    } catch (e) { toast.error(e.message) }
    finally { setSaving(false) }
  }

  async function deleteShop() {
    if (!confirm(`Удалить магазин «${selected.name}»? Это действие необратимо.`)) return
    setSaving(true)
    try {
      await api.deleteShop(selected.id)
      toast.success('Магазин удалён')
      closeDetail()
      loadShops(1); setPage(1)
    } catch (e) { toast.error(e.message) }
    finally { setSaving(false) }
  }

  // ── Render ────────────────────────────────────────────────────────────────────
  const totalPages = Math.max(1, Math.ceil(total / PER_PAGE))

  return (
    <div style={{ padding: 24, maxWidth: 1100, margin: '0 auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
        <h2 style={{ margin: 0, fontSize: 22, fontWeight: 600 }}>Магазины</h2>
        <button onClick={() => setShowCreate(true)} style={btnStyle('#6c63ff')}>
          + Создать
        </button>
        <select
          value={filterStatus}
          onChange={e => { setFilterStatus(e.target.value); setPage(1) }}
          style={{ marginLeft: 'auto', padding: '6px 10px', borderRadius: 8, border: '1px solid #ddd', fontSize: 13 }}
        >
          <option value="">Все статусы</option>
          {Object.entries(STATUS_LABELS).map(([v, l]) => (
            <option key={v} value={v}>{l}</option>
          ))}
        </select>
      </div>

      {/* ── Shop list ── */}
      {loading ? (
        <p style={{ color: '#888' }}>Загрузка...</p>
      ) : (
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
          <thead>
            <tr style={{ background: '#f7f7f7' }}>
              {['ID', 'Название', 'Владелец', 'Статус', 'Тариф', 'Бот', 'Создан'].map(h => (
                <th key={h} style={thStyle}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {shops.map(shop => (
              <tr key={shop.id}
                onClick={() => openShop(shop)}
                style={{ cursor: 'pointer', borderBottom: '1px solid #f0f0f0' }}
                onMouseEnter={e => e.currentTarget.style.background = '#fafafa'}
                onMouseLeave={e => e.currentTarget.style.background = ''}
              >
                <td style={tdStyle}>{shop.id}</td>
                <td style={{ ...tdStyle, fontWeight: 500 }}>{shop.name}</td>
                <td style={{ ...tdStyle, color: '#666' }}>{shop.owner_email || shop.owner_id}</td>
                <td style={tdStyle}>
                  <span style={{
                    padding: '2px 8px', borderRadius: 10, fontSize: 12, fontWeight: 500,
                    background: STATUS_COLORS[shop.status] + '22',
                    color: STATUS_COLORS[shop.status],
                  }}>
                    {STATUS_LABELS[shop.status] || shop.status}
                  </span>
                </td>
                <td style={tdStyle}>{PLAN_LABELS[shop.plan] || shop.plan}</td>
                <td style={tdStyle}>{shop.has_bot_token ? '✓' : '—'}</td>
                <td style={{ ...tdStyle, color: '#888', fontSize: 12 }}>
                  {new Date(shop.created_at).toLocaleDateString('ru-RU')}
                </td>
              </tr>
            ))}
            {shops.length === 0 && (
              <tr><td colSpan={7} style={{ textAlign: 'center', color: '#aaa', padding: 32 }}>Нет магазинов</td></tr>
            )}
          </tbody>
        </table>
      )}

      {/* ── Pagination ── */}
      {totalPages > 1 && (
        <div style={{ display: 'flex', gap: 6, marginTop: 16, justifyContent: 'center' }}>
          {Array.from({ length: totalPages }, (_, i) => i + 1).map(p => (
            <button key={p} onClick={() => { setPage(p); loadShops(p) }}
              style={{
                padding: '4px 10px', borderRadius: 6, border: '1px solid #ddd',
                background: p === page ? '#6c63ff' : '#fff',
                color: p === page ? '#fff' : '#333',
                cursor: 'pointer', fontSize: 13,
              }}
            >{p}</button>
          ))}
        </div>
      )}

      {/* ── Detail panel ── */}
      {selected && (
        <div style={overlayStyle} onClick={e => e.target === e.currentTarget && closeDetail()}>
          <div style={panelStyle}>
            <div style={{ display: 'flex', alignItems: 'center', marginBottom: 20 }}>
              <h3 style={{ margin: 0, fontSize: 18, fontWeight: 600 }}>#{selected.id} {selected.name}</h3>
              <button onClick={closeDetail} style={{ marginLeft: 'auto', background: 'none', border: 'none', fontSize: 22, cursor: 'pointer', color: '#888' }}>×</button>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>

              {/* Name */}
              <Section title="Название">
                <Row>
                  <input value={editName} onChange={e => setEditName(e.target.value)}
                    style={inputStyle} />
                  <button onClick={saveName} disabled={saving} style={btnStyle('#6c63ff')}>Сохранить</button>
                </Row>
              </Section>

              {/* Status */}
              <Section title="Статус">
                <Row>
                  <select value={editStatus} onChange={e => setEditStatus(e.target.value)} style={selectStyle}>
                    {Object.entries(STATUS_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                  </select>
                  <button onClick={saveStatus} disabled={saving} style={btnStyle('#6c63ff')}>Изменить</button>
                </Row>
              </Section>

              {/* Plan */}
              <Section title="Тариф">
                <Row>
                  <select value={editPlan} onChange={e => setEditPlan(e.target.value)} style={selectStyle}>
                    {Object.entries(PLAN_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                  </select>
                  <button onClick={savePlan} disabled={saving} style={btnStyle('#6c63ff')}>Изменить</button>
                </Row>
                <div style={{ fontSize: 12, color: '#888', marginTop: 4 }}>
                  Лимит товаров: {selected.max_products === 0 ? 'Без лимита' : selected.max_products}
                </div>
              </Section>

              {/* Owner */}
              <Section title="Владелец">
                <Row>
                  <select value={editOwnerId} onChange={e => setEditOwnerId(e.target.value)} style={selectStyle}>
                    {users.map(u => (
                      <option key={u.user_id} value={u.user_id}>{u.email}</option>
                    ))}
                  </select>
                  <button onClick={saveOwner} disabled={saving} style={btnStyle('#6c63ff')}>Назначить</button>
                </Row>
              </Section>

              {/* Bot token */}
              <Section title={`Бот-токен ${selected.has_bot_token ? '(установлен)' : '(не задан)'}`}>
                <Row>
                  <input
                    type="password"
                    placeholder="Новый токен..."
                    value={editBotToken}
                    onChange={e => setEditBotToken(e.target.value)}
                    style={inputStyle}
                  />
                  <button onClick={saveBotToken} disabled={saving || !editBotToken} style={btnStyle('#6c63ff')}>Сохранить</button>
                </Row>
                {selected.has_bot_token && (
                  <button onClick={removeBotToken} disabled={saving}
                    style={{ ...btnStyle('#c62828'), marginTop: 6, fontSize: 12 }}>
                    Удалить токен
                  </button>
                )}
              </Section>

              {/* Stats */}
              <Section title="Статистика">
                {statsLoading && <p style={{ color: '#aaa', margin: 0 }}>Загрузка...</p>}
                {stats && (
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, fontSize: 13 }}>
                    {[
                      ['Заказы', stats.total_orders],
                      ['Активные', stats.active_orders],
                      ['Товары', stats.total_products],
                      ['Клиенты', stats.total_users],
                      ['Выручка', `${stats.total_revenue.toLocaleString('ru-RU')} ₸`],
                    ].map(([label, val]) => (
                      <div key={label} style={{ background: '#f7f7f7', borderRadius: 8, padding: '8px 12px' }}>
                        <div style={{ color: '#888', fontSize: 11 }}>{label}</div>
                        <div style={{ fontWeight: 600, fontSize: 16 }}>{val}</div>
                      </div>
                    ))}
                  </div>
                )}
              </Section>
            </div>

            {/* Delete */}
            <div style={{ marginTop: 20, paddingTop: 16, borderTop: '1px solid #f0f0f0' }}>
              <button onClick={deleteShop} disabled={saving}
                style={{ ...btnStyle('#c62828'), fontSize: 13 }}>
                Удалить магазин
              </button>
              <span style={{ marginLeft: 8, fontSize: 12, color: '#aaa' }}>Необратимо</span>
            </div>
          </div>
        </div>
      )}

      {/* ── Create modal ── */}
      {showCreate && (
        <div style={overlayStyle} onClick={e => e.target === e.currentTarget && setShowCreate(false)}>
          <div style={{ ...panelStyle, maxWidth: 480 }}>
            <div style={{ display: 'flex', alignItems: 'center', marginBottom: 20 }}>
              <h3 style={{ margin: 0, fontSize: 18, fontWeight: 600 }}>Новый магазин</h3>
              <button onClick={() => setShowCreate(false)} style={{ marginLeft: 'auto', background: 'none', border: 'none', fontSize: 22, cursor: 'pointer', color: '#888' }}>×</button>
            </div>

            <FormField label="Владелец *">
              <select value={createForm.owner_id}
                onChange={e => setCreateForm(f => ({ ...f, owner_id: e.target.value }))}
                style={selectStyle}>
                <option value="">— выберите —</option>
                {users.filter(u => !u.is_super_admin).map(u => (
                  <option key={u.user_id} value={u.user_id}>{u.email}</option>
                ))}
              </select>
            </FormField>

            <FormField label="Название *">
              <input value={createForm.name}
                onChange={e => setCreateForm(f => ({ ...f, name: e.target.value }))}
                placeholder="Мой магазин" style={inputStyle} />
            </FormField>

            <FormField label="Тариф">
              <select value={createForm.plan}
                onChange={e => setCreateForm(f => ({ ...f, plan: e.target.value }))}
                style={selectStyle}>
                {Object.entries(PLAN_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </FormField>

            <FormField label="Бот-токен (необязательно)">
              <input type="password" value={createForm.bot_token}
                onChange={e => setCreateForm(f => ({ ...f, bot_token: e.target.value }))}
                placeholder="123456789:AAF..." style={inputStyle} />
            </FormField>

            <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
              <button onClick={createShop}
                disabled={createSaving || !createForm.owner_id || !createForm.name}
                style={btnStyle('#6c63ff')}>
                {createSaving ? 'Создание...' : 'Создать'}
              </button>
              <button onClick={() => setShowCreate(false)} style={btnStyle('#888')}>Отмена</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Small layout helpers ───────────────────────────────────────────────────────

function Section({ title, children }) {
  return (
    <div style={{ background: '#fafafa', borderRadius: 10, padding: 14 }}>
      <div style={{ fontSize: 11, color: '#999', fontWeight: 600, textTransform: 'uppercase', marginBottom: 8 }}>{title}</div>
      {children}
    </div>
  )
}

function Row({ children }) {
  return <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>{children}</div>
}

function FormField({ label, children }) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 13, color: '#555', marginBottom: 14 }}>
      {label}
      {children}
    </label>
  )
}

const btnStyle = (bg) => ({
  background: bg, color: '#fff', border: 'none', borderRadius: 8,
  padding: '7px 14px', fontSize: 13, fontWeight: 500, cursor: 'pointer',
  whiteSpace: 'nowrap',
})

const inputStyle = {
  flex: 1, padding: '7px 10px', border: '1px solid #ddd',
  borderRadius: 8, fontSize: 13, minWidth: 0,
}

const selectStyle = {
  flex: 1, padding: '7px 10px', border: '1px solid #ddd',
  borderRadius: 8, fontSize: 13, background: '#fff', minWidth: 0,
}

const thStyle = {
  padding: '10px 12px', textAlign: 'left', fontSize: 12,
  fontWeight: 600, color: '#666', whiteSpace: 'nowrap',
}

const tdStyle = {
  padding: '10px 12px', fontSize: 13, verticalAlign: 'middle',
}

const overlayStyle = {
  position: 'fixed', inset: 0, background: 'rgba(0,0,0,.35)',
  display: 'flex', alignItems: 'flex-start', justifyContent: 'flex-end',
  zIndex: 1000, overflowY: 'auto',
}

const panelStyle = {
  background: '#fff', width: '100%', maxWidth: 700,
  minHeight: '100vh', padding: 28, boxShadow: '-4px 0 24px rgba(0,0,0,.12)',
}
