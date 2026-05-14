import { useState, useEffect, useCallback } from 'react'
import { api } from '../api.js'
import s from './MonitoringPage.module.css'

const POLL_INTERVAL = 5000

function MetricCard({ label, value, sub, status = 'ok', icon }) {
  return (
    <div className={`${s.card} ${s[`card_${status}`]}`}>
      <div className={s.cardIcon}>{icon}</div>
      <div className={s.cardBody}>
        <div className={s.cardValue}>{value}</div>
        <div className={s.cardLabel}>{label}</div>
        {sub && <div className={s.cardSub}>{sub}</div>}
      </div>
      <div className={`${s.dot} ${s[`dot_${status}`]}`} title={status} />
    </div>
  )
}

function StatusChip({ status, label }) {
  return (
    <span className={`${s.chip} ${s[`chip_${status}`]}`}>{label}</span>
  )
}

function HealthRow({ name, check }) {
  if (!check) return null
  const st = check.status || 'ok'
  return (
    <div className={s.healthRow}>
      <span className={`${s.healthDot} ${s[`dot_${st}`]}`} />
      <span className={s.healthName}>{name}</span>
      <span className={s.healthStatus}>{st.toUpperCase()}</span>
      <span className={s.healthDetails}>
        {check.latency_ms !== undefined && `${check.latency_ms}мс`}
        {check.free_mb !== undefined && `${check.free_mb} MB свободно`}
        {check.free_gb !== undefined && `${check.free_gb} GB свободно`}
        {check.used_pct !== undefined && ` (${check.used_pct}%)`}
        {check.version && ` v${check.version}`}
        {check.active_count !== undefined && ` ${check.active_count} бот(ов)`}
        {check.error && <span style={{ color: '#ef4444' }}> {check.error}</span>}
      </span>
    </div>
  )
}

export default function MonitoringPage() {
  const [metrics, setMetrics]     = useState(null)
  const [health,  setHealth]      = useState(null)
  const [loading, setLoading]     = useState(true)
  const [error,   setError]       = useState('')
  const [lastUpd, setLastUpd]     = useState(null)
  const [live,    setLive]        = useState(true)

  const fetchAll = useCallback(async () => {
    try {
      const [m, h] = await Promise.all([
        api.getMonitoring(),
        api.getHealthDetailed(),
      ])
      setMetrics(m)
      setHealth(h)
      setError('')
      setLastUpd(new Date())
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchAll()
  }, [fetchAll])

  useEffect(() => {
    if (!live) return
    const t = setInterval(fetchAll, POLL_INTERVAL)
    return () => clearInterval(t)
  }, [live, fetchAll])

  const overallStatus = health?.status ?? (error ? 'error' : 'ok')

  return (
    <div className={s.page}>
      {/* Header */}
      <div className={s.header}>
        <div>
          <h1 className={s.title}>📡 Мониторинг</h1>
          {lastUpd && (
            <span className={s.lastUpd}>
              Обновлено {lastUpd.toLocaleTimeString('ru-RU')}
            </span>
          )}
        </div>
        <div className={s.headerRight}>
          <StatusChip
            status={overallStatus === 'ok' ? 'green' : overallStatus === 'warn' ? 'yellow' : 'red'}
            label={overallStatus === 'ok' ? '✓ Всё в норме' : overallStatus === 'warn' ? '⚠ Предупреждения' : '✕ Ошибки'}
          />
          <button
            className={`${s.liveBtn} ${live ? s.liveBtnActive : ''}`}
            onClick={() => setLive(v => !v)}
          >
            {live ? '⏸ Пауза' : '▶ Live'}
          </button>
          <button className={s.refreshBtn} onClick={fetchAll} disabled={loading}>
            {loading ? '…' : '↺'}
          </button>
        </div>
      </div>

      {error && <div className={s.error}>{error}</div>}

      {/* Maintenance banner */}
      {metrics?.maintenance_active && (
        <div className={s.maintenanceBanner}>
          🔧 Режим обслуживания АКТИВЕН — платформа возвращает 503 для пользователей
        </div>
      )}

      {/* Metrics grid */}
      {metrics && (
        <div className={s.grid}>
          <MetricCard
            icon="🏪"
            label="Активные магазины"
            value={metrics.active_shops}
            sub={`~${metrics.active_shops} ботов`}
            status="ok"
          />
          <MetricCard
            icon="🗄"
            label="Размер БД"
            value={metrics.db_size_human}
            status="ok"
          />
          <MetricCard
            icon="⚡"
            label="Redis"
            value={metrics.redis_memory_human}
            status={metrics.redis_memory_human === 'N/A' ? 'warn' : 'ok'}
          />
          <MetricCard
            icon="⏱"
            label="Аптайм"
            value={metrics.uptime_human}
            status="ok"
          />
          <MetricCard
            icon="🧾"
            label="Заказов за час"
            value={metrics.orders_last_hour}
            status="ok"
          />
          <MetricCard
            icon="📅"
            label="Заказов сегодня"
            value={metrics.orders_today}
            status="ok"
          />
          <MetricCard
            icon="🆕"
            label="Новых заказов"
            value={metrics.new_orders_count}
            status={metrics.new_orders_count > 0 ? 'warn' : 'ok'}
          />
        </div>
      )}

      {/* Health checks */}
      {health && (
        <div className={s.section}>
          <h2 className={s.sectionTitle}>Статусы компонентов</h2>
          <div className={s.healthList}>
            <HealthRow name="База данных"   check={health.checks?.database} />
            <HealthRow name="Redis"         check={health.checks?.redis} />
            <HealthRow name="Диск"          check={health.checks?.disk} />
            <HealthRow name="Память"        check={health.checks?.memory} />
            <HealthRow name="Боты"          check={health.checks?.bots} />
            <HealthRow name="Обслуживание"  check={health.checks?.maintenance} />
          </div>
        </div>
      )}

      {loading && !metrics && (
        <div className={s.spinner}>Загрузка метрик…</div>
      )}
    </div>
  )
}
