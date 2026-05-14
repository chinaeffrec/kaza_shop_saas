"""Русский язык (эталонный, используется как fallback)."""

STRINGS: dict[str, str] = {
    # ── Приветствие ────────────────────────────────────────────────────────────
    "welcome.default": "👋 Добро пожаловать!\n\nВыберите действие:",

    # ── Главное меню (кнопки) ──────────────────────────────────────────────────
    "btn.catalog":    "🗂  Каталог товаров  ",
    "btn.cart":       "🛒  Корзина          ",
    "btn.orders":     "📦  Мои заказы       ",
    "btn.faq":        "❓  FAQ               ",
    "btn.contact":    "💬  Написать нам     ",
    "btn.open_shop":  "🛍  Открыть магазин  ",
    "btn.skip":       "⏭ Пропустить",
    "btn.back_menu":  "🏠 В меню",
    "btn.back_orders":"⬅️ Мои заказы",
    "btn.refresh":    "🔄 Обновить",

    # ── Корзина ────────────────────────────────────────────────────────────────
    "cart.empty":     "🛒 Ваша корзина пуста",
    "cart.title":     "🛒 <b>Ваша корзина</b>",
    "cart.total":     "Итого",
    "cart.checkout":  "✅ Оформить заказ",
    "cart.added":     "✅ Добавлено в корзину",

    # ── Оформление заказа ──────────────────────────────────────────────────────
    "checkout.comment_prompt":
        "💬 Оставьте комментарий к заказу\n(или нажмите «Пропустить»):",
    "checkout.comment_non_text":
        "💬 Комментарий можно отправить только текстом.\nИли нажмите «Пропустить».",
    "checkout.delivery_title":     "🚚 Выберите способ доставки:",
    "checkout.delivery_address_title": "🏠 Укажите адрес доставки:",
    "checkout.btn_cdek":   "📦 СДЭК: выбрать ПВЗ",
    "checkout.btn_manual": "✏️ Ввести адрес вручную",
    "checkout.btn_skip_delivery": "⏭ Без доставки",
    "checkout.btn_skip_address":  "⏭ Пропустить",
    "checkout.city_prompt":
        "🏙 Введите название города для доставки СДЭК:\n(например: Москва, Казань, Новосибирск)",
    "checkout.city_searching":     "🔍 Ищу город…",
    "checkout.city_not_found":
        "❌ Город не найден. Попробуйте ввести ещё раз или выберите другой способ:",
    "checkout.btn_another_city":   "🔄 Другой город",
    "checkout.city_no_pvz":
        "😔 В городе <b>{city}</b> нет доступных ПВЗ.\nВведите другой город или выберите другой способ доставки:",
    "checkout.pvz_title":          "📍 <b>{city}</b> — {count} ПВЗ\nВыберите пункт выдачи:",
    "checkout.pvz_selected":
        "✅ ПВЗ выбран:\n📍 <b>{city}</b>\n{address}",
    "checkout.delivery_cost":      "\n💰 Стоимость доставки: <b>{cost} ₽</b>{period}",
    "checkout.pvz_continue":       "\n\nПродолжаем…",
    "checkout.btn_cancel_cdek":    "❌ Отмена",
    "checkout.address_prompt":     "🏠 Введите адрес доставки:",
    "checkout.address_non_text":
        "🏠 Адрес доставки можно отправить только текстом.\nИли нажмите «Пропустить».",
    "checkout.promo_prompt":
        "🏷 Введите промокод для получения скидки\n(или нажмите «Пропустить»):",
    "checkout.promo_non_text":
        "🏷 Промокод нужно ввести текстом.\nИли нажмите кнопку «Пропустить».",
    "checkout.promo_error":
        "❌ Ошибка при проверке промокода. Пропустите или попробуйте снова.",
    "checkout.promo_invalid":
        "❌ {error}\n\nВведите другой промокод или пропустите:",
    "checkout.promo_applied":
        "✅ Промокод <b>{code}</b> применён!\nСкидка: <b>{discount} ₽</b>\nИтого со скидкой: <b>{final} ₽</b>",
    "checkout.order_created":      "✅ <b>Заказ #{id} оформлен!</b>",
    "checkout.order_sum":          "Сумма: {total}",
    "checkout.order_discount":     "💰 Скидка: {discount}",
    "checkout.order_promo":        "🏷 Промокод: <b>{code}</b>",
    "checkout.order_status_new":   "Статус: 🆕 Новый",
    "checkout.order_pvz":          "📦 СДЭК ПВЗ: {pvz}",
    "checkout.order_delivery_cost":"🚚 Доставка: {cost} ₽",
    "checkout.order_address":      "📍 Адрес: {address}",
    "checkout.order_comment":      "💬 Комментарий: {comment}",
    "checkout.order_pay_online":   "\n💳 <b>Оплатите заказ онлайн</b> по кнопке ниже.",
    "checkout.order_contact_seller":"\nДля оплаты свяжитесь с продавцом.",
    "checkout.btn_pay":            "💳 Оплатить онлайн",
    "checkout.btn_check_pay":      "🔄 Проверить оплату",
    "checkout.btn_contact_seller": "💬 Связаться с продавцом",

    # ── Мои заказы ─────────────────────────────────────────────────────────────
    "orders.none":             "📦 У вас пока нет заказов.",
    "orders.active_title":     "📦 <b>Активные заказы</b>",
    "orders.no_active":        "📦 Активных заказов нет.",
    "orders.history_btn":      "📋 История заказов ({count})",
    "orders.history_empty":    "📋 История заказов пуста.",
    "orders.history_title":    "📋 <b>История заказов</b>",
    "orders.order_line":       "📦 Заказ #{id}",
    "orders.total_line":       "💰 <b>Итого: {total}</b>",
    "orders.status_line":      "Статус: <b>{label}</b> · {date}",

    # ── Статусы заказа (уведомления) ───────────────────────────────────────────
    "notify.order_status":     "📦 <b>Заказ #{id}</b>\nСтатус обновлён: <b>{label}</b>",
    "notify.payment_succeeded":"💳 <b>Заказ #{id}</b>\nСтатус оплаты: <b>Оплачен</b>",
    "notify.payment_canceled": "💳 <b>Заказ #{id}</b>\nСтатус оплаты: <b>Отменён</b>",
    "notify.refund_succeeded": "💳 <b>Заказ #{id}</b>\nВозврат выполнен.\n↩️ Средства возвращены на вашу карту в течение 3–10 рабочих дней.",
    "notify.amount":           "Сумма: {amount} ₽",
    "notify.payment_confirm":  "✅ Оплата подтверждена. Мы начали обработку заказа!",

    # ── Контакты / FAQ ─────────────────────────────────────────────────────────
    "contact.title":  "💬 <b>Написать нам</b>\n\nСвяжитесь с нами напрямую:\n{contact}",
    "faq.none":       "❓ FAQ пока не заполнен.",

    # ── Оплата (кнопки check_payment) ─────────────────────────────────────────
    "payment.check.paid":    "✅ Заказ оплачен!",
    "payment.check.status":  "Статус оплаты: {label}",
    "payment.status.pending":             "⏳ Ожидает оплаты",
    "payment.status.waiting_for_capture": "🔄 Подтверждение…",
    "payment.status.succeeded":           "✅ Оплачен",
    "payment.status.canceled":            "❌ Отменён",
    "payment.status.refunded":            "↩️ Возврат",

    # ── Ошибки ─────────────────────────────────────────────────────────────────
    "error.connection":  "❌ Ошибка соединения. Попробуйте ещё раз.",
    "error.order_failed":"❌ Ошибка при оформлении заказа. Попробуйте ещё раз.",
    "error.unexpected":
        "ℹ️ Бот принимает свободный текст только там, где сам его запрашивает.\n"
        "В остальных случаях используйте кнопки меню.",

    # ── Выбор языка ────────────────────────────────────────────────────────────
    "lang.title":   "🌐 Выберите язык / Select language / Тілді таңдаңыз:",
    "lang.changed": "✅ Язык изменён на Русский 🇷🇺",

    # ── Отзывы ─────────────────────────────────────────────────────────────────
    "review.rated":            "Вы поставили {stars}",
    "review.text_prompt":      "💬 Хотите добавить комментарий?\n(или нажмите «Пропустить»):",
    "review.skip_btn":         "⏭ Пропустить",
    "review.saved":            "✅ Спасибо за отзыв! Ваша оценка принята.",
    "review.text_must_be_text":"💬 Комментарий можно отправить только текстом.\nИли нажмите «Пропустить».",
}
