import { useState } from 'react'
import { api } from '../api.js'

const CARD = {
  background: 'var(--bg-card)',
  borderRadius: 16,
  padding: '40px 36px',
  width: 340,
  boxShadow: 'var(--shadow-lg)',
  border: '1px solid var(--border)',
}
const FIELD = {
  padding: '9px 12px',
  border: '1px solid var(--border)',
  borderRadius: 8,
  fontSize: 14,
  background: 'var(--bg-input)',
  color: 'var(--text-primary)',
  width: '100%',
}
const BTN = (disabled) => ({
  width: '100%',
  background: 'var(--accent)',
  color: 'var(--accent-text)',
  padding: '11px',
  borderRadius: 8,
  fontSize: 15,
  fontWeight: 600,
  border: 'none',
  cursor: disabled ? 'default' : 'pointer',
  opacity: disabled ? 0.6 : 1,
  transition: 'background .18s',
})

export default function LoginPage({ onLogin }) {
  const [step, setStep]           = useState('credentials') // 'credentials' | 'totp'
  const [email, setEmail]         = useState('')
  const [password, setPassword]   = useState('')
  const [totpCode, setTotpCode]   = useState('')
  const [challengeToken, setChallenge] = useState('')
  const [error, setError]         = useState('')
  const [loading, setLoading]     = useState(false)

  async function handleCredentials(e) {
    e.preventDefault()
    setLoading(true); setError('')
    try {
      const result = await api.login(email, password)

      if (result.requires_totp) {
        // Server is asking for second factor
        setChallenge(result.challenge_token)
        setStep('totp')
        return
      }

      // Full login
      localStorage.setItem(api.TOKEN_KEY, result.access_token)
      const me = await api.me()
      onLogin({ email: me.email, role: me.role, shopId: me.shop_id, permissions: me.permissions ?? [] })
    } catch(err) {
      setError(err.message || 'Неверный email или пароль')
    } finally {
      setLoading(false)
    }
  }

  async function handleTotp(e) {
    e.preventDefault()
    setLoading(true); setError('')
    try {
      const tokens = await api.verify2FALogin(challengeToken, totpCode)
      localStorage.setItem(api.TOKEN_KEY, tokens.access_token)
      const me = await api.me()
      onLogin({ email: me.email, role: me.role, shopId: me.shop_id, permissions: me.permissions ?? [] })
    } catch(err) {
      setError(err.message || 'Неверный код')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'var(--bg-page)',
    }}>
      <div style={CARD}>
        <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 6, textAlign: 'center', color: 'var(--text-primary)' }}>
          Kaza Shop
        </h1>
        <p style={{ color: 'var(--text-muted)', fontSize: 13, textAlign: 'center', marginBottom: 28 }}>
          Панель управления
        </p>

        {step === 'credentials' ? (
          <form onSubmit={handleCredentials}>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 13, color: 'var(--text-secondary)', marginBottom: 14 }}>
              Email
              <input
                type="email"
                style={FIELD}
                value={email}
                onChange={e => setEmail(e.target.value)}
                autoFocus
                autoComplete="email"
              />
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 13, color: 'var(--text-secondary)', marginBottom: 20 }}>
              Пароль
              <input
                type="password"
                style={FIELD}
                value={password}
                onChange={e => setPassword(e.target.value)}
                autoComplete="current-password"
              />
            </label>
            {error && <p style={{ color: 'var(--danger)', fontSize: 13, marginBottom: 12, textAlign: 'center' }}>{error}</p>}
            <button type="submit" disabled={loading || !email || !password} style={BTN(loading || !email || !password)}>
              {loading ? 'Вход…' : 'Войти'}
            </button>
          </form>
        ) : (
          <form onSubmit={handleTotp}>
            <div style={{ textAlign: 'center', marginBottom: 20 }}>
              <div style={{ fontSize: 36, marginBottom: 10 }}>🔐</div>
              <p style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 6 }}>
                Двухфакторная аутентификация
              </p>
              <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>
                Введите 6-значный код из приложения-аутентификатора
              </p>
            </div>
            <input
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              placeholder="000000"
              style={{
                ...FIELD,
                textAlign: 'center',
                fontSize: 24,
                fontWeight: 700,
                letterSpacing: '0.25em',
                marginBottom: 16,
              }}
              value={totpCode}
              onChange={e => setTotpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
              autoFocus
            />
            {error && <p style={{ color: 'var(--danger)', fontSize: 13, marginBottom: 12, textAlign: 'center' }}>{error}</p>}
            <button type="submit" disabled={loading || totpCode.length < 6} style={BTN(loading || totpCode.length < 6)}>
              {loading ? 'Проверка…' : 'Подтвердить'}
            </button>
            <button
              type="button"
              onClick={() => { setStep('credentials'); setError(''); setTotpCode('') }}
              style={{
                width: '100%', background: 'transparent', border: 'none',
                color: 'var(--text-muted)', fontSize: 13, marginTop: 12, cursor: 'pointer',
              }}
            >
              ← Назад к входу
            </button>
          </form>
        )}
      </div>
    </div>
  )
}
