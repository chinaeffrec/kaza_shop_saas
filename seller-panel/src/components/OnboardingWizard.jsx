import { useState } from 'react'
import s from './OnboardingWizard.module.css'

const STORAGE_KEY = 'kaza_onboarding_done'

const STEPS = [
  {
    id: 'bot',
    icon: '🤖',
    title: 'Подключите Telegram-бота',
    description: 'Создайте бота через @BotFather и вставьте токен в Настройки → Telegram бот.',
    tip: 'Совет: дайте боту понятное имя — например, «Мой магазин Bot».',
    cta: 'Перейти в Настройки',
    ctaPage: 'settings',
  },
  {
    id: 'product',
    icon: '📦',
    title: 'Добавьте первый товар',
    description: 'Создайте карточку товара: название, цена, фото. Бот сразу покажет его покупателям.',
    tip: 'Совет: добавьте качественное фото — конверсия растёт на 30%.',
    cta: 'Добавить товар',
    ctaPage: 'products',
  },
  {
    id: 'order',
    icon: '🧾',
    title: 'Сделайте тест-заказ',
    description: 'Откройте своего бота в Telegram и оформите тестовый заказ. Убедитесь, что уведомление дошло.',
    tip: 'Совет: настройте Telegram ID для уведомлений в Настройках → Магазин.',
    cta: 'Посмотреть заказы',
    ctaPage: 'orders',
  },
  {
    id: 'done',
    icon: '🎉',
    title: 'Всё готово!',
    description: 'Ваш магазин настроен. Делитесь ссылкой на бота и принимайте заказы!',
    tip: null,
    cta: null,
    ctaPage: null,
  },
]

export function isOnboardingDone() {
  return localStorage.getItem(STORAGE_KEY) === '1'
}

export function markOnboardingDone() {
  localStorage.setItem(STORAGE_KEY, '1')
}

/**
 * Onboarding wizard modal for new shop owners.
 *
 * Props:
 *   onNavigate  — (page: string) => void
 *   onClose     — () => void
 */
export default function OnboardingWizard({ onNavigate, onClose }) {
  const [step, setStep] = useState(0)
  const current = STEPS[step]
  const isLast = step === STEPS.length - 1
  const progress = ((step) / (STEPS.length - 1)) * 100

  function handleCta() {
    if (current.ctaPage) {
      onNavigate?.(current.ctaPage)
    }
    if (!isLast) setStep(s => s + 1)
  }

  function handleSkip() {
    markOnboardingDone()
    onClose?.()
  }

  function handleFinish() {
    markOnboardingDone()
    onClose?.()
  }

  return (
    <div className={s.overlay} role="dialog" aria-modal="true" aria-label="Быстрый старт">
      <div className={s.modal}>
        {/* Progress bar */}
        <div className={s.progressTrack}>
          <div className={s.progressFill} style={{ width: `${progress}%` }} />
        </div>

        {/* Step indicators */}
        <div className={s.dots}>
          {STEPS.map((_, i) => (
            <button
              key={i}
              className={`${s.dot} ${i === step ? s.dotActive : ''} ${i < step ? s.dotDone : ''}`}
              onClick={() => setStep(i)}
              aria-label={`Шаг ${i + 1}`}
            />
          ))}
        </div>

        {/* Content */}
        <div className={s.content}>
          <div className={s.icon}>{current.icon}</div>
          <h2 className={s.title}>{current.title}</h2>
          <p className={s.desc}>{current.description}</p>
          {current.tip && (
            <div className={s.tip}>💡 {current.tip}</div>
          )}
        </div>

        {/* Actions */}
        <div className={s.actions}>
          {step > 0 && !isLast && (
            <button className={s.back} onClick={() => setStep(s => s - 1)}>← Назад</button>
          )}

          {isLast ? (
            <button className={s.primary} onClick={handleFinish}>
              Начать работу 🚀
            </button>
          ) : (
            <>
              {current.cta && (
                <button className={s.primary} onClick={handleCta}>
                  {current.cta}
                </button>
              )}
              <button className={s.next} onClick={() => setStep(s => s + 1)}>
                Далее →
              </button>
            </>
          )}
        </div>

        {!isLast && (
          <button className={s.skip} onClick={handleSkip}>
            Пропустить настройку
          </button>
        )}
      </div>
    </div>
  )
}
