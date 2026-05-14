import { useEffect, useState } from 'react'
import api from '../api'
import s from './BillingPage.module.css'

const PLAN_EMOJI = { free: '🆓', basic: '⭐', pro: '🚀' }
const STATUS_LABEL = {
  active:    { text: 'Активна',    cls: s.statusActive },
  trialing:  { text: 'Пробный',    cls: s.statusTrial  },
  suspended: { text: 'Приостановлена', cls: s.statusSuspended },
  cancelled: { text: 'Отменена',   cls: s.statusCancelled },
}

function fmt(kopecks) {
  if (kopecks === 0) return 'Бесплатно'
  return `${Math.round(kopecks / 100).toLocaleString('ru-RU')} ₽/мес`
}

function UsageBar({ label, current, limit, pct }) {
  const unlimited = limit < 0
  const barPct = unlimited ? 0 : Math.min(pct, 100)
  const danger = !unlimited && pct >= 90
  const warn   = !unlimited && pct >= 70 && pct < 90

  return (
    <div className={s.usageRow}>
      <div className={s.usageHeader}>
        <span className={s.usageLabel}>{label}</span>
        <span className={s.usageValue}>
          {unlimited
            ? `${current} / ∞`
            : `${current} / ${limit}`}
        </span>
      </div>
      <div className={s.barTrack}>
        <div
          className={`${s.barFill} ${danger ? s.barDanger : warn ? s.barWarn : ''}`}
          style={{ width: unlimited ? '0%' : `${barPct}%` }}
        />
      </div>
      {!unlimited && danger && (
        <p className={s.usageWarn}>⚠️ Лимит почти исчерпан. Рассмотрите обновление тарифа.</p>
      )}
    </div>
  )
}

function FeatureCheck({ value }) {
  return (
    <span className={value ? s.featYes : s.featNo}>
      {value ? '✓' : '—'}
    </span>
  )
}

export default function BillingPage() {
  const [plans, setPlans]           = useState([])
  const [sub, setSub]               = useState(null)
  const [usage, setUsage]           = useState(null)
  const [loading, setLoading]       = useState(true)
  const [error, setError]           = useState(null)

  useEffect(() => {
    setLoading(true)
    Promise.all([
      api.getBillingPlans(),
      api.getBillingSubscription(),
      api.getBillingUsage(),
    ])
      .then(([p, s, u]) => {
        setPlans(p)
        setSub(s)
        setUsage(u)
      })
      .catch(e => setError(e.message || 'Ошибка загрузки'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className={s.center}>Загрузка…</div>
  if (error)   return <div className={s.center} style={{color:'#e55'}}>⚠️ {error}</div>
  if (!sub)    return null

  const currentSlug = sub.plan?.slug || 'free'
  const statusInfo  = STATUS_LABEL[sub.status] || STATUS_LABEL.active

  return (
    <div className={s.page}>
      {/* ── Текущая подписка ─── */}
      <section className={s.card}>
        <div className={s.cardHeader}>
          <h2 className={s.cardTitle}>
            {PLAN_EMOJI[currentSlug] || '📦'} Ваш тариф: {sub.plan?.display_name}
          </h2>
          <span className={`${s.statusBadge} ${statusInfo.cls}`}>
            {statusInfo.text}
          </span>
        </div>

        <p className={s.cardMeta}>
          Тариф активен с {new Date(sub.started_at).toLocaleDateString('ru-RU')}
          {sub.expires_at && (
            <> · действует до <b>{new Date(sub.expires_at).toLocaleDateString('ru-RU')}</b></>
          )}
        </p>

        {usage && (
          <div className={s.usageBlock}>
            <UsageBar
              label="Товары в каталоге"
              current={usage.products_count}
              limit={usage.products_limit}
              pct={usage.products_pct}
            />
            <UsageBar
              label="Заказов в этом месяце"
              current={usage.orders_this_month}
              limit={usage.orders_limit}
              pct={usage.orders_pct}
            />
          </div>
        )}
      </section>

      {/* ── Сравнение тарифов ─── */}
      <section className={s.card}>
        <h2 className={s.cardTitle}>Тарифные планы</h2>

        <div className={s.plansGrid}>
          {plans.map(plan => {
            const isCurrent = plan.slug === currentSlug
            return (
              <div
                key={plan.id}
                className={`${s.planCard} ${isCurrent ? s.planCurrent : ''}`}
              >
                {isCurrent && <div className={s.planCurrentBadge}>Ваш тариф</div>}
                <div className={s.planEmoji}>{PLAN_EMOJI[plan.slug] || '📦'}</div>
                <h3 className={s.planName}>{plan.display_name}</h3>
                <div className={s.planPrice}>{fmt(plan.price_monthly)}</div>

                <ul className={s.planFeatures}>
                  <li>
                    <span className={s.featLabel}>Товаров</span>
                    <span className={s.featValue}>
                      {plan.max_products < 0 ? '∞' : plan.max_products}
                    </span>
                  </li>
                  <li>
                    <span className={s.featLabel}>Заказов/мес</span>
                    <span className={s.featValue}>
                      {plan.max_orders_monthly < 0 ? '∞' : plan.max_orders_monthly}
                    </span>
                  </li>
                  <li>
                    <span className={s.featLabel}>ЮКасса</span>
                    <FeatureCheck value={plan.features?.yookassa} />
                  </li>
                  <li>
                    <span className={s.featLabel}>СДЭК</span>
                    <FeatureCheck value={plan.features?.cdek} />
                  </li>
                  <li>
                    <span className={s.featLabel}>Mini App</span>
                    <FeatureCheck value={plan.features?.miniapp} />
                  </li>
                </ul>

                {!isCurrent && plan.price_monthly > 0 && (
                  <a
                    className={s.upgradeBtn}
                    href="mailto:support@kazashop.ru?subject=Смена тарифа"
                    target="_blank"
                    rel="noreferrer"
                  >
                    Перейти на {plan.display_name}
                  </a>
                )}
                {isCurrent && (
                  <div className={s.currentPill}>Активен</div>
                )}
              </div>
            )
          })}
        </div>

        <p className={s.contactNote}>
          Для смены тарифа, выставления счёта или вопросов по оплате обращайтесь
          к администратору платформы.
        </p>
      </section>
    </div>
  )
}
