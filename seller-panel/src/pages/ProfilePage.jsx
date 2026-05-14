import { useState, useEffect, useRef } from 'react'
import { api } from '../api.js'
import { useToast } from '../components/Toast.jsx'
import s from './ProfilePage.module.css'

const BASE = import.meta.env.VITE_API_URL ?? ''

export default function ProfilePage({ userEmail }) {
  const toast = useToast()
  const fileRef = useRef(null)

  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)

  // Edit fields
  const [displayName, setDisplayName] = useState('')
  const [nameSaving, setNameSaving] = useState(false)

  // Avatar
  const [avatarUploading, setAvatarUploading] = useState(false)

  // 2FA
  const [totpUri, setTotpUri] = useState('')
  const [totpSecret, setTotpSecret] = useState('')
  const [totpCode, setTotpCode] = useState('')
  const [totpLoading, setTotpLoading] = useState(false)
  const [show2FASetup, setShow2FASetup] = useState(false)

  useEffect(() => {
    api.getProfile()
      .then(p => {
        setProfile(p)
        setDisplayName(p.display_name || '')
      })
      .catch(() => toast('Ошибка загрузки профиля', 'error'))
      .finally(() => setLoading(false))
  }, [])

  async function saveName() {
    setNameSaving(true)
    try {
      const updated = await api.updateProfile({ display_name: displayName || null })
      setProfile(updated)
      toast('Имя обновлено', 'success')
    } catch(e) { toast(e.message, 'error') }
    finally { setNameSaving(false) }
  }

  async function uploadAvatar(file) {
    if (!file) return
    setAvatarUploading(true)
    try {
      const fd = new FormData()
      fd.append('file', file)
      const token = localStorage.getItem(api.TOKEN_KEY)
      const res = await fetch(`${BASE}/api/v1/profile/avatar`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: fd,
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || 'Ошибка загрузки')
      }
      const updated = await res.json()
      setProfile(updated)
      toast('Аватар обновлён', 'success')
    } catch(e) { toast(e.message, 'error') }
    finally { setAvatarUploading(false) }
  }

  async function start2FASetup() {
    setTotpLoading(true)
    try {
      const res = await api.setup2FA()
      setTotpUri(res.otpauth_uri)
      setTotpSecret(res.secret)
      setShow2FASetup(true)
      setTotpCode('')
    } catch(e) { toast(e.message, 'error') }
    finally { setTotpLoading(false) }
  }

  async function verify2FA() {
    if (totpCode.length < 6) { toast('Введите 6-значный код', 'error'); return }
    setTotpLoading(true)
    try {
      const updated = await api.verify2FA(totpCode)
      setProfile(updated)
      setShow2FASetup(false)
      setTotpCode('')
      toast('Двухфакторная аутентификация включена', 'success')
    } catch(e) { toast(e.message, 'error') }
    finally { setTotpLoading(false) }
  }

  async function disable2FA() {
    if (!confirm('Отключить двухфакторную аутентификацию?')) return
    setTotpLoading(true)
    try {
      const updated = await api.disable2FA()
      setProfile(updated)
      setShow2FASetup(false)
      toast('Двухфакторная аутентификация отключена', 'success')
    } catch(e) { toast(e.message, 'error') }
    finally { setTotpLoading(false) }
  }

  if (loading) return <div className={s.loading}>Загрузка…</div>
  if (!profile) return null

  const avatarSrc = profile.avatar_url ? `${BASE}${profile.avatar_url}` : null
  const initials = (profile.display_name || profile.email || '?')
    .split(' ').slice(0, 2).map(w => w[0].toUpperCase()).join('')

  return (
    <div className={s.page}>
      <h1 className={s.title}>Профиль</h1>

      {/* ── Avatar + display name ─────────────────────────────────────────── */}
      <section className={s.section}>
        <h2 className={s.sectionTitle}>Личные данные</h2>

        <div className={s.avatarRow}>
          <div className={s.avatarWrap}>
            {avatarSrc
              ? <img src={avatarSrc} alt="Аватар" className={s.avatarImg} />
              : <div className={s.avatarPlaceholder}>{initials}</div>
            }
            <button
              className={s.avatarOverlay}
              onClick={() => fileRef.current?.click()}
              disabled={avatarUploading}
              title="Изменить аватар"
            >
              {avatarUploading ? '⏳' : '📷'}
            </button>
            <input
              ref={fileRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              style={{ display: 'none' }}
              onChange={e => { uploadAvatar(e.target.files[0]); e.target.value = '' }}
            />
          </div>

          <div className={s.avatarInfo}>
            <div className={s.avatarEmail}>{profile.email}</div>
            {profile.is_super_admin && (
              <span className={s.adminBadge}>Super Admin</span>
            )}
            <p className={s.avatarHint}>JPG, PNG или WebP, до 5 МБ</p>
          </div>
        </div>

        <label className={s.label}>Отображаемое имя
          <div className={s.inputRow}>
            <input
              className={s.input}
              value={displayName}
              onChange={e => setDisplayName(e.target.value)}
              placeholder="Ваше имя"
              maxLength={128}
            />
            <button className={s.btnSave} onClick={saveName} disabled={nameSaving}>
              {nameSaving ? '…' : 'Сохранить'}
            </button>
          </div>
        </label>
      </section>

      {/* ── 2FA ──────────────────────────────────────────────────────────── */}
      <section className={s.section}>
        <h2 className={s.sectionTitle}>Двухфакторная аутентификация (2FA)</h2>

        {profile.totp_enabled ? (
          <div className={s.twoFAActive}>
            <span className={s.twoFAStatus}>🛡 2FA включена</span>
            <p className={s.hint}>
              При входе в систему требуется код из приложения-аутентификатора
              (Google Authenticator, Яндекс Ключ, Authy и др.).
            </p>
            <button
              className={s.btnDanger}
              onClick={disable2FA}
              disabled={totpLoading}
            >
              {totpLoading ? 'Отключение…' : 'Отключить 2FA'}
            </button>
          </div>
        ) : (
          <>
            <p className={s.hint}>
              Двухфакторная аутентификация добавляет дополнительный уровень защиты.
              При входе потребуется одноразовый код из приложения-аутентификатора.
            </p>

            {!show2FASetup ? (
              <button className={s.btnPrimary} onClick={start2FASetup} disabled={totpLoading}>
                {totpLoading ? 'Подготовка…' : '🔐 Включить 2FA'}
              </button>
            ) : (
              <div className={s.twoFASetup}>
                <p className={s.setupStep}>
                  <strong>Шаг 1.</strong> Отсканируйте QR-код в приложении-аутентификаторе
                  (Google Authenticator, Authy, Яндекс Ключ).
                </p>

                {/* QR code rendered as an <img> from otpauth URI via Google Charts */}
                <div className={s.qrWrap}>
                  <img
                    src={`https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(totpUri)}`}
                    alt="QR для 2FA"
                    className={s.qr}
                    width={180}
                    height={180}
                  />
                </div>

                <details className={s.secretDetails}>
                  <summary className={s.secretSummary}>Не удаётся отсканировать? Ввести ключ вручную</summary>
                  <code className={s.secretCode}>{totpSecret}</code>
                </details>

                <p className={s.setupStep} style={{ marginTop: 18 }}>
                  <strong>Шаг 2.</strong> Введите 6-значный код из приложения для подтверждения.
                </p>

                <div className={s.codeRow}>
                  <input
                    className={s.codeInput}
                    value={totpCode}
                    onChange={e => setTotpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                    placeholder="000000"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    maxLength={6}
                  />
                  <button
                    className={s.btnPrimary}
                    onClick={verify2FA}
                    disabled={totpLoading || totpCode.length < 6}
                  >
                    {totpLoading ? 'Проверка…' : 'Подтвердить'}
                  </button>
                </div>

                <button
                  className={s.btnCancel}
                  onClick={() => { setShow2FASetup(false); setTotpCode('') }}
                >
                  Отмена
                </button>
              </div>
            )}
          </>
        )}
      </section>
    </div>
  )
}
