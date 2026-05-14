"""Қазақ тілі (Kazakh)."""

STRINGS: dict[str, str] = {
    "welcome.default": "👋 Қош келдіңіз!\n\nӘрекетті таңдаңыз:",

    "btn.catalog":    "🗂  Тауарлар каталогы",
    "btn.cart":       "🛒  Себет            ",
    "btn.orders":     "📦  Менің тапсырыстарым",
    "btn.faq":        "❓  Жиі қойылатын сұрақтар",
    "btn.contact":    "💬  Бізге жазыңыз   ",
    "btn.open_shop":  "🛍  Дүкенді ашу     ",
    "btn.skip":       "⏭ Өткізіп жіберу",
    "btn.back_menu":  "🏠 Басты мәзір",
    "btn.back_orders":"⬅️ Менің тапсырыстарым",
    "btn.refresh":    "🔄 Жаңарту",

    "cart.empty":     "🛒 Себетіңіз бос",
    "cart.title":     "🛒 <b>Сіздің себетіңіз</b>",
    "cart.total":     "Барлығы",
    "cart.checkout":  "✅ Тапсырыс беру",
    "cart.added":     "✅ Себетке қосылды",

    "checkout.comment_prompt":
        "💬 Тапсырысқа пікір қалдырыңыз\n(немесе «Өткізіп жіберу» батырмасын басыңыз):",
    "checkout.comment_non_text":
        "💬 Пікірді тек мәтін ретінде жіберіңіз.\nНемесе «Өткізіп жіберу» батырмасын басыңыз.",
    "checkout.delivery_title":     "🚚 Жеткізу тәсілін таңдаңыз:",
    "checkout.delivery_address_title": "🏠 Жеткізу мекенжайын енгізіңіз:",
    "checkout.btn_cdek":   "📦 CDEK: бөлу нүктесін таңдау",
    "checkout.btn_manual": "✏️ Мекенжайды қолмен енгізу",
    "checkout.btn_skip_delivery": "⏭ Жеткізусіз",
    "checkout.btn_skip_address":  "⏭ Өткізіп жіберу",
    "checkout.city_prompt":
        "🏙 CDEK жеткізуіне арналған қала атауын енгізіңіз:",
    "checkout.city_searching":     "🔍 Қала іздеуде…",
    "checkout.city_not_found":
        "❌ Қала табылмады. Қайтадан енгізіп көріңіз немесе басқа тәсілді таңдаңыз:",
    "checkout.btn_another_city":   "🔄 Басқа қала",
    "checkout.city_no_pvz":
        "😔 <b>{city}</b> қаласында қолжетімді бөлу нүктелері жоқ.\nБасқа қаланы енгізіңіз немесе басқа жеткізу тәсілін таңдаңыз:",
    "checkout.pvz_title":          "📍 <b>{city}</b> — {count} бөлу нүктесі\nБөлу нүктесін таңдаңыз:",
    "checkout.pvz_selected":
        "✅ Бөлу нүктесі таңдалды:\n📍 <b>{city}</b>\n{address}",
    "checkout.delivery_cost":      "\n💰 Жеткізу құны: <b>{cost} ₽</b>{period}",
    "checkout.pvz_continue":       "\n\nЖалғастырамыз…",
    "checkout.btn_cancel_cdek":    "❌ Болдырмау",
    "checkout.address_prompt":     "🏠 Жеткізу мекенжайын енгізіңіз:",
    "checkout.address_non_text":
        "🏠 Мекенжайды тек мәтін ретінде жіберіңіз.\nНемесе «Өткізіп жіберу» батырмасын басыңыз.",
    "checkout.promo_prompt":
        "🏷 Жеңілдік алу үшін промокод енгізіңіз\n(немесе «Өткізіп жіберу» батырмасын басыңыз):",
    "checkout.promo_non_text":
        "🏷 Промокодты мәтін ретінде жіберіңіз.\nНемесе «Өткізіп жіберу» батырмасын басыңыз.",
    "checkout.promo_error":
        "❌ Промокодты тексеру кезінде қате шықты. Өткізіп жіберіңіз немесе қайталап көріңіз.",
    "checkout.promo_invalid":
        "❌ {error}\n\nБасқа промокод енгізіңіз немесе өткізіп жіберіңіз:",
    "checkout.promo_applied":
        "✅ <b>{code}</b> промокоды қолданылды!\nЖеңілдік: <b>{discount} ₽</b>\nЖеңілдікпен жалпы: <b>{final} ₽</b>",
    "checkout.order_created":      "✅ <b>#{id} тапсырысы ресімделді!</b>",
    "checkout.order_sum":          "Сомасы: {total}",
    "checkout.order_discount":     "💰 Жеңілдік: {discount}",
    "checkout.order_promo":        "🏷 Промокод: <b>{code}</b>",
    "checkout.order_status_new":   "Күй: 🆕 Жаңа",
    "checkout.order_pvz":          "📦 CDEK бөлу нүктесі: {pvz}",
    "checkout.order_delivery_cost":"🚚 Жеткізу: {cost} ₽",
    "checkout.order_address":      "📍 Мекенжай: {address}",
    "checkout.order_comment":      "💬 Пікір: {comment}",
    "checkout.order_pay_online":   "\n💳 <b>Тапсырысты онлайн төлеңіз</b> төмендегі батырма арқылы.",
    "checkout.order_contact_seller":"\nТөлем үшін сатушымен байланысыңыз.",
    "checkout.btn_pay":            "💳 Онлайн төлеу",
    "checkout.btn_check_pay":      "🔄 Төлемді тексеру",
    "checkout.btn_contact_seller": "💬 Сатушымен байланысу",

    "orders.none":             "📦 Сізде әлі тапсырыстар жоқ.",
    "orders.active_title":     "📦 <b>Белсенді тапсырыстар</b>",
    "orders.no_active":        "📦 Белсенді тапсырыстар жоқ.",
    "orders.history_btn":      "📋 Тапсырыстар тарихы ({count})",
    "orders.history_empty":    "📋 Тапсырыстар тарихы бос.",
    "orders.history_title":    "📋 <b>Тапсырыстар тарихы</b>",
    "orders.order_line":       "📦 #{id} тапсырысы",
    "orders.total_line":       "💰 <b>Жалпы: {total}</b>",
    "orders.status_line":      "Күй: <b>{label}</b> · {date}",

    "notify.order_status":     "📦 <b>#{id} тапсырысы</b>\nКүй жаңартылды: <b>{label}</b>",
    "notify.payment_succeeded":"💳 <b>#{id} тапсырысы</b>\nТөлем күйі: <b>Төленді</b>",
    "notify.payment_canceled": "💳 <b>#{id} тапсырысы</b>\nТөлем күйі: <b>Болдырылмады</b>",
    "notify.refund_succeeded": "💳 <b>#{id} тапсырысы</b>\nҚайтару орындалды.\n↩️ Қаражат 3–10 жұмыс күні ішінде картаңызға қайтарылады.",
    "notify.amount":           "Сомасы: {amount} ₽",
    "notify.payment_confirm":  "✅ Төлем расталды. Тапсырысыңызды өңдеуді бастадық!",

    "contact.title":  "💬 <b>Бізге жазыңыз</b>\n\nБізбен тікелей байланысыңыз:\n{contact}",
    "faq.none":       "❓ Жиі қойылатын сұрақтар әлі толтырылмаған.",

    "payment.check.paid":    "✅ Тапсырыс төленді!",
    "payment.check.status":  "Төлем күйі: {label}",
    "payment.status.pending":             "⏳ Төлем күтілуде",
    "payment.status.waiting_for_capture": "🔄 Растауда…",
    "payment.status.succeeded":           "✅ Төленді",
    "payment.status.canceled":            "❌ Болдырылмады",
    "payment.status.refunded":            "↩️ Қайтарылды",

    "error.connection":  "❌ Қосылым қатесі. Қайтадан байқап көріңіз.",
    "error.order_failed":"❌ Тапсырысты ресімдеу кезінде қате шықты. Қайтадан байқап көріңіз.",
    "error.unexpected":
        "ℹ️ Бот тек өзі сұраған кезде ғана еркін мәтін қабылдайды.\n"
        "Қалған жағдайларда мәзір батырмаларын пайдаланыңыз.",

    "lang.title":   "🌐 Выберите язык / Select language / Тілді таңдаңыз:",
    "lang.changed": "✅ Тіл қазақ тіліне өзгертілді 🇰🇿",

    # ── Пікірлер ───────────────────────────────────────────────────────────────
    "review.rated":            "Сіз {stars} қойдыңыз",
    "review.text_prompt":      "💬 Пікір қалдырғыңыз келе ме?\n(немесе «Өткізіп жіберу» батырмасын басыңыз):",
    "review.skip_btn":         "⏭ Өткізіп жіберу",
    "review.saved":            "✅ Пікіріңіз үшін рақмет!",
    "review.text_must_be_text":"💬 Пікірді тек мәтін ретінде жіберіңіз.\nНемесе «Өткізіп жіберу» батырмасын басыңыз.",
}
