/**
 * Helpers для Telegram WebApp SDK.
 * window.Telegram.WebApp доступен после загрузки telegram-web-app.js
 */

export const tg = window.Telegram?.WebApp ?? null

/** Инициализация: раскрываем на весь экран, подтверждаем готовность */
export function initTelegramApp() {
  if (!tg) return
  tg.expand()
  tg.ready()
  tg.enableClosingConfirmation()
}

/** Текущий user из initData (может быть null в браузере) */
export function getTelegramUser() {
  return tg?.initDataParsed?.user ?? null
}

/** Показать MainButton с текстом и колбеком */
export function showMainButton(text, onClick) {
  if (!tg) return
  tg.MainButton.setText(text)
  tg.MainButton.onClick(onClick)
  tg.MainButton.show()
}

/** Скрыть MainButton */
export function hideMainButton() {
  if (!tg) return
  tg.MainButton.hide()
  tg.MainButton.offClick()
}

/** Задать loading state у MainButton */
export function setMainButtonLoading(loading) {
  if (!tg) return
  if (loading) tg.MainButton.showProgress(false)
  else tg.MainButton.hideProgress()
}

/** Показать BackButton с колбеком */
export function showBackButton(onClick) {
  if (!tg) return
  tg.BackButton.onClick(onClick)
  tg.BackButton.show()
}

/** Скрыть BackButton */
export function hideBackButton() {
  if (!tg) return
  tg.BackButton.offClick()
  tg.BackButton.hide()
}

/** Haptic feedback */
export function haptic(type = 'light') {
  tg?.HapticFeedback?.impactOccurred(type)
}

/** Закрыть Mini App */
export function closeMiniApp() {
  tg?.close()
}

/** Цвета темы Telegram */
export function getThemeParams() {
  return tg?.themeParams ?? {}
}

/** initData (сырая строка для передачи в /miniapp/auth) */
export function getInitData() {
  return tg?.initData ?? ''
}
