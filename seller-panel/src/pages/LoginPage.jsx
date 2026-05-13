import { useState } from 'react'
import { api } from '../api.js'

export default function LoginPage({ onLogin }) {
  const [login, setLogin]     = useState('')
  const [password, setPassword] = useState('')
  const [error, setError]     = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setLoading(true); setError('')
    try {
      const data = await api.login(login, password)
      localStorage.setItem('admin_token', data.token)
      onLogin(data.login)
    } catch(err) {
      setError(err.message || 'Неверный логин или пароль')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight:'100vh', display:'flex', alignItems:'center', justifyContent:'center',
      background:'#f5f5f5'
    }}>
      <div style={{
        background:'#fff', borderRadius:14, padding:'40px 36px', width:340,
        boxShadow:'0 4px 24px rgba(0,0,0,.10)'
      }}>
        <h1 style={{fontSize:22,fontWeight:600,marginBottom:8,textAlign:'center'}}>Kaza Shop</h1>
        <p style={{color:'#888',fontSize:13,textAlign:'center',marginBottom:28}}>Панель администратора</p>

        <form onSubmit={handleSubmit}>
          <label style={{display:'flex',flexDirection:'column',gap:4,fontSize:13,color:'#555',marginBottom:14}}>
            Логин
            <input
              style={{padding:'9px 12px',border:'1px solid #ddd',borderRadius:8,fontSize:14}}
              value={login} onChange={e=>setLogin(e.target.value)}
              autoFocus autoComplete="username"
            />
          </label>
          <label style={{display:'flex',flexDirection:'column',gap:4,fontSize:13,color:'#555',marginBottom:20}}>
            Пароль
            <input
              type="password"
              style={{padding:'9px 12px',border:'1px solid #ddd',borderRadius:8,fontSize:14}}
              value={password} onChange={e=>setPassword(e.target.value)}
              autoComplete="current-password"
            />
          </label>
          {error && <p style={{color:'#c62828',fontSize:13,marginBottom:12,textAlign:'center'}}>{error}</p>}
          <button
            type="submit"
            disabled={loading || !login || !password}
            style={{
              width:'100%',background:'#6c63ff',color:'#fff',padding:'10px',
              borderRadius:8,fontSize:15,fontWeight:500,border:'none',cursor:'pointer',
              opacity: (loading||!login||!password) ? .6 : 1
            }}
          >
            {loading ? 'Вход...' : 'Войти'}
          </button>
        </form>
        <p style={{fontSize:11,color:'#bbb',textAlign:'center',marginTop:20}}>
          Дефолт: admin / из .env ADMIN_PASSWORD
        </p>
      </div>
    </div>
  )
}