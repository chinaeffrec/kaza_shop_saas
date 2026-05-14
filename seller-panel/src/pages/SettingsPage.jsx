import { useState, useEffect } from 'react'
import { api } from '../api.js'
import { useToast } from '../components/Toast.jsx'
import s from './SettingsPage.module.css'

export default function SettingsPage({ onSaved, userEmail, shopId, isSuperAdmin = false }) {
  const toast = useToast()
  const [shopName, setShopName]         = useState('')
  const [welcomeMsg, setWelcomeMsg]     = useState('')
  const [sellerContact, setSellerContact] = useState('')
  const [adminContact, setAdminContact] = useState('')
  const [saving, setSaving]             = useState(false)
  const [stampUrl, setStampUrl]         = useState('')
  const [paymentQrUrl, setPaymentQrUrl] = useState('')
  const [paymentQrComment, setPaymentQrComment] = useState('')
  const [legalName, setLegalName]       = useState('')

  const [faq, setFaq]         = useState([])
  const [faqForm, setFaqForm] = useState({ question:'', answer:'' })
  const [dragIdx, setDragIdx] = useState(null)
  const [editFaqId, setEditFaqId] = useState(null)

  const [pwForm, setPwForm]   = useState({ current_password:'', new_password:'' })
  const [pwSaving, setPwSaving] = useState(false)
  const [pwMsg, setPwMsg]     = useState('')

  const [botToken, setBotToken]   = useState('')
  const [botSaving, setBotSaving] = useState(false)
  const [botMsg, setBotMsg]       = useState('')

  const [dbExporting, setDbExporting]       = useState(false)
  const [dbImporting, setDbImporting]       = useState(false)
  const [dbImportMsg, setDbImportMsg]       = useState('')
  const [mediaExporting, setMediaExporting] = useState(false)
  const [mediaImporting, setMediaImporting] = useState(false)
  const [mediaImportMsg, setMediaImportMsg] = useState('')

  const [logs, setLogs]         = useState([])
  const [logsOpen, setLogsOpen] = useState(false)
  const [logsLoading, setLogsLoading] = useState(false)
  const [logsDownloading, setLogsDownloading] = useState(false)

  // CDEK
  const [cdek, setCdek] = useState({
    cdek_enabled: false,
    cdek_test_mode: true,
    cdek_client_id: '',
    cdek_client_secret: '',
    cdek_sender_city_code: '',
    cdek_sender_address: '',
    cdek_default_weight: 500,
  })
  const [cdekSaving, setCdekSaving] = useState(false)
  const [cdekCitySearch, setCdekCitySearch] = useState('')
  const [cdekCities, setCdekCities]         = useState([])
  const [cdekSearching, setCdekSearching]   = useState(false)

  // Mini App
  const [miniappUrl, setMiniappUrl] = useState('')
  const [miniappSaving, setMiniappSaving] = useState(false)

  // i18n
  const [defaultLang, setDefaultLang] = useState('ru')
  const [shopLangs, setShopLangs] = useState(['ru'])
  const [langSaving, setLangSaving] = useState(false)

  // YooKassa
  const [yoo, setYoo] = useState({
    yookassa_enabled: false,
    yookassa_shop_id: '',
    yookassa_secret_key: '',
    yookassa_return_url: '',
  })
  const [yooSaving, setYooSaving] = useState(false)

  useEffect(() => {
    api.getSettings().then(cfg => {
      setShopName(cfg.shop_name || 'Kaza Shop')
      setWelcomeMsg(cfg.welcome_message || '👋 Добро пожаловать!\n\nВыберите действие:')
      setSellerContact(cfg.seller_contact || '')
      setAdminContact(cfg.admin_contact || '')
      setStampUrl(cfg.stamp_url || '')
      setPaymentQrUrl(cfg.payment_qr_url || '')
      setPaymentQrComment(cfg.payment_qr_comment || '')
      setLegalName(cfg.legal_name || '')
      setCdek({
        cdek_enabled: cfg.cdek_enabled ?? false,
        cdek_test_mode: cfg.cdek_test_mode ?? true,
        cdek_client_id: cfg.cdek_client_id || '',
        cdek_client_secret: cfg.cdek_client_secret || '',
        cdek_sender_city_code: cfg.cdek_sender_city_code ?? '',
        cdek_sender_address: cfg.cdek_sender_address || '',
        cdek_default_weight: cfg.cdek_default_weight ?? 500,
      })
      setMiniappUrl(cfg.miniapp_url || '')
      setDefaultLang(cfg.default_language || 'ru')
      setShopLangs((cfg.shop_languages || 'ru').split(',').map(s => s.trim()).filter(Boolean))
      setYoo({
        yookassa_enabled: cfg.yookassa_enabled ?? false,
        yookassa_shop_id: cfg.yookassa_shop_id || '',
        yookassa_secret_key: cfg.yookassa_secret_key || '',
        yookassa_return_url: cfg.yookassa_return_url || '',
      })
    }).catch(() => {})
    api.getFaq().then(setFaq).catch(() => {})
  }, [])

    async function saveSettings() {
    setSaving(true)
    try {
      const payload = {
        shop_name: shopName,
        welcome_message: welcomeMsg,
        seller_contact: sellerContact,
        admin_contact: adminContact,
        payment_qr_comment: paymentQrComment,
        legal_name: legalName,
      }
      const updated = await api.updateSettings(payload)
      onSaved?.(updated)
      toast('Настройки сохранены', 'success')
    } catch(e) { toast(e.message, 'error') }
    finally { setSaving(false) }
  }

  // Password change
  async function saveCredentials() {
    if (!pwForm.new_password || !pwForm.current_password) {
      setPwMsg('Заполните все поля'); return
    }
    setPwSaving(true); setPwMsg('')
    try {
      await api.changePassword(pwForm.current_password, pwForm.new_password)
      setPwMsg('✅ Пароль изменён. Выполните повторный вход.')
      setPwForm({ current_password:'', new_password:'' })
    } catch(e) {
      setPwMsg('❌ ' + e.message)
    } finally { setPwSaving(false) }
  }

  // Bot token
  async function saveBotToken() {
    if (!botToken.trim() || !shopId) return
    setBotSaving(true); setBotMsg('')
    try {
      await api.setShopBotToken(shopId, botToken)
      setBotMsg('✅ Токен сохранён')
      setBotToken('')
    } catch(e) {
      setBotMsg('❌ ' + e.message)
    } finally { setBotSaving(false) }
  }

  // CDEK
  async function saveCdek() {
    setCdekSaving(true)
    try {
      const payload = {
        cdek_enabled: cdek.cdek_enabled,
        cdek_test_mode: cdek.cdek_test_mode,
        cdek_client_id: cdek.cdek_client_id || null,
        cdek_sender_city_code: cdek.cdek_sender_city_code ? parseInt(cdek.cdek_sender_city_code) : null,
        cdek_sender_address: cdek.cdek_sender_address || null,
        cdek_default_weight: parseInt(cdek.cdek_default_weight) || 500,
      }
      // только если секрет изменён (не маскированное значение)
      if (cdek.cdek_client_secret && !cdek.cdek_client_secret.startsWith('••••')) {
        payload.cdek_client_secret = cdek.cdek_client_secret
      }
      await api.updateSettings(payload)
      toast('Настройки СДЭК сохранены', 'success')
    } catch(e) { toast(e.message, 'error') }
    finally { setCdekSaving(false) }
  }

  // Mini App
  async function saveMiniappUrl() {
    setMiniappSaving(true)
    try {
      await api.updateSettings({ miniapp_url: miniappUrl || null })
      toast('URL Mini App сохранён', 'success')
    } catch(e) { toast(e.message, 'error') }
    finally { setMiniappSaving(false) }
  }

  // i18n
  async function saveLangSettings() {
    setLangSaving(true)
    try {
      await api.updateSettings({
        default_language: defaultLang,
        shop_languages: shopLangs.join(',') || 'ru',
      })
      toast('Языковые настройки сохранены', 'success')
    } catch(e) { toast(e.message, 'error') }
    finally { setLangSaving(false) }
  }

  function toggleShopLang(code) {
    setShopLangs(prev => {
      if (prev.includes(code)) {
        // keep at least one
        return prev.length > 1 ? prev.filter(l => l !== code) : prev
      }
      return [...prev, code]
    })
  }

  // YooKassa
  async function saveYoo() {
    setYooSaving(true)
    try {
      const payload = {
        yookassa_enabled: yoo.yookassa_enabled,
        yookassa_shop_id: yoo.yookassa_shop_id || null,
        yookassa_return_url: yoo.yookassa_return_url || null,
      }
      // Не отправляем замаскированный секрет обратно
      if (yoo.yookassa_secret_key && !yoo.yookassa_secret_key.startsWith('••••')) {
        payload.yookassa_secret_key = yoo.yookassa_secret_key
      }
      await api.updateSettings(payload)
      toast('Настройки ЮКасса сохранены', 'success')
    } catch(e) { toast(e.message, 'error') }
    finally { setYooSaving(false) }
  }

  async function searchCdekCity() {
    if (cdekCitySearch.length < 2) return
    setCdekSearching(true)
    try {
      const cities = await api.searchCdekCities(cdekCitySearch)
      setCdekCities(cities || [])
    } catch(e) { toast('Ошибка поиска города: ' + e.message, 'error') }
    finally { setCdekSearching(false) }
  }

  // FAQ
  async function saveFaq() {
    if (!faqForm.question.trim() || !faqForm.answer.trim()) return toast('Заполните вопрос и ответ', 'error')
    try {
      if (editFaqId) {
        const upd = await api.updateFaq(editFaqId, faqForm)
        setFaq(f => f.map(i => i.id === editFaqId ? upd : i))
      } else {
        const created = await api.createFaq({ ...faqForm, sort_order: faq.length })
        setFaq(f => [...f, created])
      }
      setFaqForm({ question:'', answer:'' }); setEditFaqId(null)
    } catch(e) { toast(e.message, 'error') }
  }

  async function onDrop(targetIdx) {
    if (dragIdx === null || dragIdx === targetIdx) return
    const reordered = [...faq]
    const [moved] = reordered.splice(dragIdx, 1)
    reordered.splice(targetIdx, 0, moved)
    setFaq(reordered); setDragIdx(null)
    for (let i = 0; i < reordered.length; i++)
      await api.updateFaq(reordered[i].id, { sort_order: i }).catch(() => {})
  }

  async function deleteFaq(id) {
    if (!confirm('Удалить вопрос?')) return
    await api.deleteFaq(id).catch(e => toast(e.message, 'error'))
    setFaq(f => f.filter(i => i.id !== id))
  }

  async function toggleFaqActive(item) {
    const upd = await api.updateFaq(item.id, { is_active: !item.is_active }).catch(e => { toast(e.message, 'error'); return null })
    if (upd) setFaq(f => f.map(i => i.id === item.id ? upd : i))
  }

  async function loadLogs() {
    setLogsLoading(true); setLogsOpen(true); setLogs([])
    const lines = []
    const ts = () => new Date().toLocaleTimeString()
    try {
      const health = await fetch(`${api.BASE}/health`).then(r => r.json())
      lines.push(`[${ts()}] ✅ Сервис работает — статус: ${health.status}`)
    } catch { lines.push(`[${ts()}] ❌ Сервис недоступен`) }
    try {
      const dash = await api.getDashboard()
      const byStatus = (dash.orders_by_status || []).map(s => `${s.label}: ${s.count}`).join(', ')
      lines.push(`[${ts()}] 🧾 Заказов всего: ${dash.total_orders} — ${byStatus || 'нет'}`)
    } catch { lines.push(`[${ts()}] 🧾 Заказы: ⚠️ ошибка`) }
    try {
      const [allProds, noPhotoProds] = await Promise.all([
        api.getProducts(1, 1),
        api.getProducts(1, 1, { has_image: false }),
      ])
      lines.push(`[${ts()}] 📦 Товаров: ${allProds.total}, без фото: ${noPhotoProds.total}`)
    } catch { lines.push(`[${ts()}] 📦 Товары: ⚠️ ошибка`) }
    lines.push(`[${ts()}] 🕐 Проверено: ${new Date().toLocaleString()}`)
    setLogs(lines); setLogsLoading(false)
  }

  async function downloadLogs() {
    setLogsDownloading(true)
    try {
      await api.downloadLogs()
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      setLogsDownloading(false)
    }
  }

  return (
    <div className={s.page}>
      <h1 className={s.title}>Настройки</h1>

      {/* Магазин */}
      <section className={s.section}>
        <h2 className={s.sectionTitle}>Магазин</h2>
        <label className={s.label}>Название магазина
          <input className={s.input} value={shopName} onChange={e=>setShopName(e.target.value)} />
        </label>
        <label className={s.label}>Приветственное сообщение (отображается при /start в боте)
          <textarea className={s.input} rows={4} value={welcomeMsg}
            onChange={e=>setWelcomeMsg(e.target.value)}
            placeholder="👋 Добро пожаловать!..." />
        </label>
        <label className={s.label}>Контакт продавца (для кнопки «Написать нам»)
          <input className={s.input} value={sellerContact} onChange={e=>setSellerContact(e.target.value)}
            placeholder="@username или https://t.me/username" />
        </label>
        <label className={s.label}>
          Telegram ID для уведомлений о заказах
          <input className={s.input} value={adminContact}
                 onChange={e => setAdminContact(e.target.value)}
                 placeholder="123456789 (числовой ID из @userinfobot)" />
          <span style={{fontSize:11,color:'#aaa',marginTop:2}}>
            Узнать свой ID: напишите боту @userinfobot в Telegram
          </span>
        </label>

        <h3 style={{fontSize:14, fontWeight:600, color:'#333', marginTop:20, marginBottom:8}}>
          🖼 Факсимиле (печать)
        </h3>
        <p style={{fontSize:12, color:'#888', marginBottom:8}}>
          Загрузите изображение печати (будет отображаться в товарном чеке).
        </p>
        <input type="file" accept="image/jpeg,image/png,image/webp"
          onChange={async e => {
            const f = e.target.files[0]
            if (!f) return
            try {
              const fd = new FormData()
              fd.append('file', f)
              const token = localStorage.getItem(api.TOKEN_KEY)
              const res = await fetch(`${api.BASE}/settings/stamp`, {
                method: 'POST',
                headers: { Authorization: `Bearer ${token}` },
                body: fd,
              })
              if (res.ok) {
                const data = await res.json()
                setStampUrl(data.stamp_url)
                toast('Печать загружена', 'success')
              } else toast('Ошибка загрузки', 'error')
            } catch { toast('Ошибка', 'error') }
          }}
        />
        {stampUrl && (
          <img src={`${api.BASE}${stampUrl}`} alt="Печать"
            style={{width:80, height:80, objectFit:'contain', marginTop:8, borderRadius:8, border:'1px solid #eee'}} />
        )}

        <h3 style={{fontSize:14, fontWeight:600, color:'#333', marginTop:20, marginBottom:8}}>
          📱 QR-код для оплаты
        </h3>
        <p style={{fontSize:12, color:'#888', marginBottom:12}}>
          Сгенерируйте QR в приложении банка («Принять оплату» → QR-код). Загрузите сюда. Покупатель увидит QR после оформления заказа.
        </p>
        <label className={s.label}>QR-код (изображение)
          <input type="file" accept="image/jpeg,image/png,image/webp"
            onChange={async e => {
              const f = e.target.files[0]
              if (!f) return
              try {
                const fd = new FormData()
                fd.append('file', f)
                const token = localStorage.getItem(api.TOKEN_KEY)
                const res = await fetch(`${api.BASE}/settings/payment-qr`, {
                  method: 'POST',
                  headers: { Authorization: `Bearer ${token}` },
                  body: fd,
                })
                if (res.ok) {
                  const data = await res.json()
                  setPaymentQrUrl(data.payment_qr_url)
                  toast('QR-код загружен', 'success')
                } else {
                  toast('Ошибка загрузки', 'error')
                }
              } catch { toast('Ошибка', 'error') }
            }}
          />
          {paymentQrUrl && (
            <img src={`${api.BASE}${paymentQrUrl}`} alt="QR"
              style={{width:200, height:200, objectFit:'contain', marginTop:8, borderRadius:8, border:'2px solid #ccc', background:'#fff'}} />
          )}
        </label>
        <label className={s.label}>Комментарий к оплате
          <input className={s.input} value={paymentQrComment}
            onChange={e=>setPaymentQrComment(e.target.value)}
            placeholder="Отсканируйте QR-код в приложении банка, введите сумму и оплатите" />
        </label>

        <h3 style={{fontSize:14, fontWeight:600, color:'#333', marginTop:20, marginBottom:8}}>
          📋 Юридическая информация
        </h3>
        <label className={s.label}>Юридическое наименование продавца (для чеков)
          <textarea className={s.input} rows={4} value={legalName}
                    onChange={e=>setLegalName(e.target.value)}
                    placeholder={"ИП Иванов Иван Иванович\nИНН 1234567890\nОГРНИП 123456789012345\nАдрес: г. Москва, ул. Примерная, д. 1"} />
        </label>

        <button className={s.btnSave} onClick={saveSettings} disabled={saving}>
          {saving ? 'Сохранение...' : 'Сохранить настройки'}
        </button>
      </section>

      {/* CDEK */}
      {!isSuperAdmin && (
        <section className={s.section}>
          <h2 className={s.sectionTitle}>📦 Доставка СДЭК</h2>

          <label className={s.checkLabel}>
            <input type="checkbox" checked={cdek.cdek_enabled}
              onChange={e => setCdek(c => ({...c, cdek_enabled: e.target.checked}))} />
            Включить доставку через СДЭК в боте
          </label>

          <label className={s.checkLabel} style={{marginTop: 6}}>
            <input type="checkbox" checked={cdek.cdek_test_mode}
              onChange={e => setCdek(c => ({...c, cdek_test_mode: e.target.checked}))} />
            Тестовый режим (api.edu.cdek.ru)
          </label>

          <div className={s.row2}>
            <label className={s.label}>Client ID
              <input className={s.input} value={cdek.cdek_client_id}
                onChange={e => setCdek(c => ({...c, cdek_client_id: e.target.value}))}
                placeholder="EMscd6r9JnFiQ3bLoyjJY6eM" />
            </label>
            <label className={s.label}>Client Secret
              <input className={s.input} type="password" value={cdek.cdek_client_secret}
                onChange={e => setCdek(c => ({...c, cdek_client_secret: e.target.value}))}
                placeholder={cdek.cdek_client_secret?.startsWith('••••') ? 'Уже задан (••••)' : 'Введите секрет'}
                autoComplete="new-password" />
            </label>
          </div>

          <label className={s.label} style={{marginBottom: 4}}>Город отправки (СДЭК)</label>
          <div style={{display:'flex', gap: 8, marginBottom: 8}}>
            <input className={s.input} style={{flex:1}} value={cdekCitySearch}
              onChange={e => setCdekCitySearch(e.target.value)}
              placeholder="Введите название города…"
              onKeyDown={e => e.key === 'Enter' && searchCdekCity()} />
            <button className={s.btnSmall} onClick={searchCdekCity} disabled={cdekSearching}>
              {cdekSearching ? '…' : 'Найти'}
            </button>
          </div>
          {cdekCities.length > 0 && (
            <div className={s.cityList}>
              {cdekCities.map(c => (
                <div key={c.code} className={s.cityItem}
                  onClick={() => {
                    setCdek(d => ({...d, cdek_sender_city_code: String(c.code)}))
                    setCdekCities([])
                    setCdekCitySearch(`${c.city}${c.region ? ', ' + c.region : ''} (код: ${c.code})`)
                  }}>
                  {c.city}{c.region ? ', ' + c.region : ''} — <code>{c.code}</code>
                </div>
              ))}
            </div>
          )}
          {cdek.cdek_sender_city_code && (
            <div className={s.infoChip}>Код города: <b>{cdek.cdek_sender_city_code}</b></div>
          )}

          <label className={s.label} style={{marginTop: 10}}>Адрес отправки (склад/офис)
            <input className={s.input} value={cdek.cdek_sender_address}
              onChange={e => setCdek(c => ({...c, cdek_sender_address: e.target.value}))}
              placeholder="ул. Примерная, д. 1, офис 5" />
          </label>

          <label className={s.label}>Вес посылки по умолчанию (г)
            <input className={s.input} type="number" min={50} max={31000}
              value={cdek.cdek_default_weight}
              onChange={e => setCdek(c => ({...c, cdek_default_weight: e.target.value}))} />
          </label>

          <button className={s.btnSave} onClick={saveCdek} disabled={cdekSaving}>
            {cdekSaving ? 'Сохранение…' : 'Сохранить настройки СДЭК'}
          </button>
        </section>
      )}

      {/* Mini App */}
      {!isSuperAdmin && (
        <section className={s.section}>
          <h2 className={s.sectionTitle}>🛍 Telegram Mini App</h2>
          <p style={{fontSize:13, color:'#777', marginBottom:10}}>
            HTTPS-ссылка на Mini App, которая будет открываться кнопкой «Открыть магазин» в боте.
            Оставьте пустым, чтобы скрыть кнопку.
          </p>
          <label className={s.label}>URL Mini App
            <input className={s.input} value={miniappUrl}
              onChange={e => setMiniappUrl(e.target.value)}
              placeholder="https://example.com/miniapp/?shop_id=1" />
          </label>
          <button className={s.btnSave} onClick={saveMiniappUrl} disabled={miniappSaving}>
            {miniappSaving ? 'Сохранение…' : 'Сохранить URL Mini App'}
          </button>
        </section>
      )}

      {/* i18n / Language */}
      {!isSuperAdmin && (
        <section className={s.section}>
          <h2 className={s.sectionTitle}>🌐 Язык бота</h2>
          <p style={{fontSize:13, color:'#777', marginBottom:12}}>
            Выберите языки, доступные покупателям. Язык по умолчанию используется,
            если у пользователя нет сохранённых предпочтений.
          </p>

          <label className={s.label} style={{marginBottom:8}}>Языки магазина</label>
          {[['ru','🇷🇺 Русский'],['en','🇬🇧 English'],['kk','🇰🇿 Қазақша']].map(([code, label]) => (
            <label key={code} className={s.toggleRow} style={{marginBottom:6}}>
              <input type="checkbox"
                checked={shopLangs.includes(code)}
                onChange={() => toggleShopLang(code)} />
              {label}
            </label>
          ))}

          <label className={s.label} style={{marginTop:14}}>Язык по умолчанию
            <select className={s.input} value={defaultLang} onChange={e => setDefaultLang(e.target.value)}>
              {shopLangs.map(code => (
                <option key={code} value={code}>
                  {code === 'ru' ? '🇷🇺 Русский' : code === 'en' ? '🇬🇧 English' : '🇰🇿 Қазақша'}
                </option>
              ))}
            </select>
          </label>

          <button className={s.btnSave} onClick={saveLangSettings} disabled={langSaving}>
            {langSaving ? 'Сохранение…' : 'Сохранить языки'}
          </button>
        </section>
      )}

      {/* YooKassa */}
      {!isSuperAdmin && (
        <section className={s.section}>
          <h2 className={s.sectionTitle}>💳 ЮКасса — онлайн-оплата</h2>

          <label className={s.toggleRow}>
            <input type="checkbox" checked={yoo.yookassa_enabled}
              onChange={e => setYoo(y => ({...y, yookassa_enabled: e.target.checked}))} />
            Включить онлайн-оплату через ЮКасса
          </label>

          {yoo.yookassa_enabled && (<>
            <label className={s.label}>Shop ID (числовой идентификатор магазина ЮКасса)
              <input className={s.input} value={yoo.yookassa_shop_id}
                onChange={e => setYoo(y => ({...y, yookassa_shop_id: e.target.value}))}
                placeholder="123456" />
            </label>

            <label className={s.label}>Secret Key
              <input className={s.input} type="password" value={yoo.yookassa_secret_key}
                onChange={e => setYoo(y => ({...y, yookassa_secret_key: e.target.value}))}
                placeholder={yoo.yookassa_secret_key?.startsWith('••••') ? 'Уже задан (••••)' : 'test_…  или  live_…'} />
            </label>

            <label className={s.label}>URL возврата после оплаты (сайт или t.me/ваш_бот)
              <input className={s.input} value={yoo.yookassa_return_url}
                onChange={e => setYoo(y => ({...y, yookassa_return_url: e.target.value}))}
                placeholder="https://t.me/mybot" />
            </label>
          </>)}

          <button className={s.btnSave} onClick={saveYoo} disabled={yooSaving}>
            {yooSaving ? 'Сохранение…' : 'Сохранить настройки ЮКасса'}
          </button>
        </section>
      )}

      {/* FAQ */}
      <section className={s.section}>
        <h2 className={s.sectionTitle}>FAQ для бота</h2>
        <div style={{position:'absolute',opacity:0,height:0,overflow:'hidden'}}>
          <input type="text" name="fake_username" autoComplete="username" tabIndex="-1" />
          <input type="password" name="fake_password" autoComplete="current-password" tabIndex="-1" />
        </div>
        <div className={s.faqForm}>
          <input className={s.input} placeholder="Вопрос" value={faqForm.question}
            onChange={e=>setFaqForm(f=>({...f,question:e.target.value}))} />
          <textarea className={s.input} rows={3} placeholder="Ответ" value={faqForm.answer}
            onChange={e=>setFaqForm(f=>({...f,answer:e.target.value}))} />
          <div className={s.faqFooter}>
            <button className={s.btnSave} onClick={saveFaq}>{editFaqId ? 'Сохранить' : '+ Добавить'}</button>
            {editFaqId && <button className={s.btnCancel} onClick={()=>{setEditFaqId(null);setFaqForm({question:'',answer:''})}}>Отмена</button>}
          </div>
        </div>
        <div className={s.faqList}>
          {faq.length===0 && <p className={s.empty}>FAQ пуст — добавьте первый вопрос</p>}
          {faq.map(item => (
            <div key={item.id}
              className={`${s.faqItem} ${!item.is_active?s.faqInactive:''}`}
              draggable onDragStart={()=>setDragIdx(faq.indexOf(item))}
              onDragOver={e=>e.preventDefault()} onDrop={()=>onDrop(faq.indexOf(item))}
              style={{cursor:'grab'}}>
              <div className={s.faqQ}>{item.question}</div>
              <div className={s.faqA}>{item.answer}</div>
              <div className={s.faqActions}>
                <button className={s.btnSm} onClick={()=>toggleFaqActive(item)}>
                  {item.is_active ? '🙈 Скрыть' : '👁 Показать'}
                </button>
                <button className={s.btnSm} onClick={()=>{setEditFaqId(item.id);setFaqForm({question:item.question,answer:item.answer})}}>✏️</button>
                <button className={s.btnSmDanger} onClick={()=>deleteFaq(item.id)}>🗑</button>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Telegram бот (только для владельцев) */}
      {!isSuperAdmin && (
        <section className={s.section}>
          <h2 className={s.sectionTitle}>Telegram бот</h2>
          <p className={s.hint}>
            Токен бота из <a href="https://t.me/BotFather" target="_blank" rel="noopener noreferrer">@BotFather</a>.
            После сохранения сервис автоматически перезапустит бота с новым токеном.
          </p>
          <label className={s.label}>Новый токен
            <input type="password" className={s.input}
              value={botToken} onChange={e=>setBotToken(e.target.value)}
              placeholder="123456789:AAFxxxx..." autoComplete="off" />
          </label>
          {botMsg && <p className={s.pwMsg}>{botMsg}</p>}
          <button className={s.btnSave} onClick={saveBotToken} disabled={botSaving || !botToken}>
            {botSaving ? 'Сохранение...' : 'Сохранить токен'}
          </button>
        </section>
      )}

      {/* Безопасность */}
      <section className={s.section}>
        <h2 className={s.sectionTitle}>Безопасность</h2>
        <p className={s.hint}>Аккаунт: <b>{userEmail}</b></p>
        <label className={s.label}>Текущий пароль
          <input type="password" className={s.input} value={pwForm.current_password}
            onChange={e=>setPwForm(f=>({...f,current_password:e.target.value}))} autoComplete="current-password" />
        </label>
        <label className={s.label}>Новый пароль
          <input type="password" className={s.input} value={pwForm.new_password}
            onChange={e=>setPwForm(f=>({...f,new_password:e.target.value}))}
            placeholder="Минимум 10 символов, буква и цифра" autoComplete="new-password" />
        </label>
        {pwMsg && <p className={s.pwMsg}>{pwMsg}</p>}
        <button className={s.btnSave} onClick={saveCredentials} disabled={pwSaving}>
          {pwSaving ? 'Сохранение...' : 'Изменить пароль'}
        </button>
      </section>

      {/* База данных */}
      <section className={s.section}>
        <h2 className={s.sectionTitle}>Перенос данных</h2>

        <p className={s.hint} style={{marginBottom: 4}}>
          Для полного переноса на другой сервер нужны <b>оба файла</b>: база данных + медиафайлы.
          Сначала экспортируйте оба, затем на новом сервере импортируйте в том же порядке.
        </p>
        <p style={{fontSize: 12, color: '#e67e22', marginBottom: 16, padding: '8px 12px',
          background: '#fffbf0', border: '1px solid #f0d080', borderRadius: 6}}>
          ⚠️ Учётные данные администратора (логин/пароль) хранятся отдельно и <b>не переносятся</b>.
          На новом сервере используйте пароль из его файла .env.
        </p>

        {/* Шаг 1: База данных */}
        <h3 style={{fontSize: 14, fontWeight: 600, color: '#333', marginBottom: 8}}>
          Шаг 1 — База данных (товары, заказы, настройки, FAQ)
        </h3>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 8 }}>
          <button className={s.btnSave} disabled={dbExporting}
            onClick={async () => {
              setDbExporting(true)
              try { await api.exportDb(); toast('База данных экспортирована', 'success') }
              catch (e) { toast(e.message, 'error') }
              finally { setDbExporting(false) }
            }}>
            {dbExporting ? 'Подготовка...' : '⬇️ Скачать базу данных (.json)'}
          </button>

          <label style={{
            display: 'inline-flex', alignItems: 'center', gap: 8,
            padding: '8px 16px', borderRadius: 8, cursor: 'pointer',
            background: '#f5f5f5', border: '1px solid #ddd',
            fontSize: 14, fontWeight: 500, color: '#333',
            opacity: dbImporting ? 0.6 : 1,
            pointerEvents: dbImporting ? 'none' : 'auto',
          }}>
            {dbImporting ? '⏳ Импорт...' : '⬆️ Загрузить базу данных (.json)'}
            <input type="file" accept=".json" style={{ display: 'none' }}
              onChange={async e => {
                const file = e.target.files?.[0]; e.target.value = ''
                if (!file) return
                if (!confirm('⚠️ Все текущие данные (товары, заказы, настройки, FAQ) будут заменены данными из файла.\n\nПродолжить?')) return
                setDbImporting(true); setDbImportMsg('')
                try {
                  const res = await api.importDb(file)
                  const total = Object.values(res.counts || {}).reduce((a, b) => a + b, 0)
                  setDbImportMsg(`✅ База восстановлена. Записей: ${total}`)
                  toast('База данных успешно восстановлена', 'success')
                } catch (e) {
                  setDbImportMsg(`❌ ${e.message}`); toast(e.message, 'error')
                } finally { setDbImporting(false) }
              }} />
          </label>
        </div>
        {dbImportMsg && (
          <p style={{fontSize:13, padding:'8px 12px', borderRadius:6, marginBottom:8,
            background: dbImportMsg.startsWith('✅') ? '#f0fff4' : '#fff0f0',
            border:`1px solid ${dbImportMsg.startsWith('✅') ? '#b2dfdb' : '#ffcdd2'}`, color:'#333'}}>
            {dbImportMsg}
          </p>
        )}

        {/* Шаг 2: Медиафайлы */}
        <h3 style={{fontSize: 14, fontWeight: 600, color: '#333', marginBottom: 4, marginTop: 20}}>
          Шаг 2 — Медиафайлы (фото товаров, печать, QR-код)
        </h3>
        <p style={{fontSize: 12, color: '#888', marginBottom: 8}}>
          Без медиафайлов изображения товаров не будут отображаться на новом сервере.
        </p>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 8 }}>
          <button className={s.btnSave} disabled={mediaExporting}
            onClick={async () => {
              setMediaExporting(true)
              try { await api.exportMedia(); toast('Медиафайлы экспортированы', 'success') }
              catch (e) { toast(e.message, 'error') }
              finally { setMediaExporting(false) }
            }}>
            {mediaExporting ? 'Архивирование...' : '⬇️ Скачать медиафайлы (.zip)'}
          </button>

          <label style={{
            display: 'inline-flex', alignItems: 'center', gap: 8,
            padding: '8px 16px', borderRadius: 8, cursor: 'pointer',
            background: '#f5f5f5', border: '1px solid #ddd',
            fontSize: 14, fontWeight: 500, color: '#333',
            opacity: mediaImporting ? 0.6 : 1,
            pointerEvents: mediaImporting ? 'none' : 'auto',
          }}>
            {mediaImporting ? '⏳ Загрузка...' : '⬆️ Загрузить медиафайлы (.zip)'}
            <input type="file" accept=".zip" style={{ display: 'none' }}
              onChange={async e => {
                const file = e.target.files?.[0]; e.target.value = ''
                if (!file) return
                setMediaImporting(true); setMediaImportMsg('')
                try {
                  const res = await api.importMedia(file)
                  setMediaImportMsg(`✅ Загружено файлов: ${res.files}`)
                  toast(`Медиафайлы загружены (${res.files} шт.)`, 'success')
                } catch (e) {
                  setMediaImportMsg(`❌ ${e.message}`); toast(e.message, 'error')
                } finally { setMediaImporting(false) }
              }} />
          </label>
        </div>
        {mediaImportMsg && (
          <p style={{fontSize:13, padding:'8px 12px', borderRadius:6,
            background: mediaImportMsg.startsWith('✅') ? '#f0fff4' : '#fff0f0',
            border:`1px solid ${mediaImportMsg.startsWith('✅') ? '#b2dfdb' : '#ffcdd2'}`, color:'#333'}}>
            {mediaImportMsg}
          </p>
        )}
        <p style={{ fontSize: 11, color: '#aaa', marginTop: 8 }}>
          После импорта нажмите «Сбросить кэш каталога» в разделе «Системный журнал», чтобы бот показал актуальные данные.
        </p>
      </section>

      {/* Системный журнал */}
      <section className={s.section}>
        <div className={s.logsHead}>
          <h2 className={s.sectionTitle} style={{margin:0}}>Системный журнал</h2>
          <div className={s.logsActions}>
            <button className={s.btnRefresh} onClick={loadLogs} disabled={logsLoading}>
              {logsLoading ? 'Проверка...' : '🔍 Проверить состояние'}
            </button>
            <button className={s.btnCacheReset} onClick={async()=>{
              try {
                const r = await api.reloadCache()
                toast(r.message || 'Кэш перезагружен', 'success')
              } catch { toast('Ошибка сброса кэша', 'error') }
            }}>
              🔄 Сбросить кэш каталога
            </button>
            <button className={s.btnLogsDownload} onClick={downloadLogs} disabled={logsDownloading}>
              {logsDownloading ? 'Подготовка...' : '⬇️ Скачать логи'}
            </button>
          </div>
        </div>
        <p className={s.logsHint}>
          Docker автоматически ограничивает размер контейнерных логов. Для выгрузки здесь доступен архив актуальных логов приложения и бота.
        </p>
        {logsOpen && (
          <div className={s.logsBox}>
            {logs.length===0 ? <span className={s.empty}>Нет данных</span>
              : logs.map((l,i)=><div key={i} className={s.logLine}>{l}</div>)}
          </div>
        )}
      </section>
    </div>
  )
}
