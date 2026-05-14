"""English translations."""

STRINGS: dict[str, str] = {
    "welcome.default": "👋 Welcome!\n\nPlease choose an action:",

    "btn.catalog":    "🗂  Product Catalog  ",
    "btn.cart":       "🛒  Cart             ",
    "btn.orders":     "📦  My Orders        ",
    "btn.faq":        "❓  FAQ              ",
    "btn.contact":    "💬  Contact Us       ",
    "btn.open_shop":  "🛍  Open Shop        ",
    "btn.skip":       "⏭ Skip",
    "btn.back_menu":  "🏠 Main Menu",
    "btn.back_orders":"⬅️ My Orders",
    "btn.refresh":    "🔄 Refresh",

    "cart.empty":     "🛒 Your cart is empty",
    "cart.title":     "🛒 <b>Your Cart</b>",
    "cart.total":     "Total",
    "cart.checkout":  "✅ Place Order",
    "cart.added":     "✅ Added to cart",

    "checkout.comment_prompt":
        "💬 Leave a comment for your order\n(or press Skip):",
    "checkout.comment_non_text":
        "💬 Please send your comment as text.\nOr press Skip.",
    "checkout.delivery_title":     "🚚 Choose delivery method:",
    "checkout.delivery_address_title": "🏠 Enter your delivery address:",
    "checkout.btn_cdek":   "📦 CDEK: choose pickup point",
    "checkout.btn_manual": "✏️ Enter address manually",
    "checkout.btn_skip_delivery": "⏭ No delivery",
    "checkout.btn_skip_address":  "⏭ Skip",
    "checkout.city_prompt":
        "🏙 Enter city name for CDEK delivery:\n(e.g.: Moscow, Kazan, Novosibirsk)",
    "checkout.city_searching":     "🔍 Searching for city…",
    "checkout.city_not_found":
        "❌ City not found. Please try again or choose another method:",
    "checkout.btn_another_city":   "🔄 Another city",
    "checkout.city_no_pvz":
        "😔 No pickup points in <b>{city}</b>.\nTry another city or choose another delivery method:",
    "checkout.pvz_title":          "📍 <b>{city}</b> — {count} pickup points\nChoose a pickup point:",
    "checkout.pvz_selected":
        "✅ Pickup point selected:\n📍 <b>{city}</b>\n{address}",
    "checkout.delivery_cost":      "\n💰 Delivery cost: <b>{cost} ₽</b>{period}",
    "checkout.pvz_continue":       "\n\nContinuing…",
    "checkout.btn_cancel_cdek":    "❌ Cancel",
    "checkout.address_prompt":     "🏠 Enter your delivery address:",
    "checkout.address_non_text":
        "🏠 Please send your address as text.\nOr press Skip.",
    "checkout.promo_prompt":
        "🏷 Enter a promo code for a discount\n(or press Skip):",
    "checkout.promo_non_text":
        "🏷 Please send the promo code as text.\nOr press Skip.",
    "checkout.promo_error":
        "❌ Error checking promo code. Skip or try again.",
    "checkout.promo_invalid":
        "❌ {error}\n\nEnter another promo code or skip:",
    "checkout.promo_applied":
        "✅ Promo code <b>{code}</b> applied!\nDiscount: <b>{discount} ₽</b>\nTotal with discount: <b>{final} ₽</b>",
    "checkout.order_created":      "✅ <b>Order #{id} placed!</b>",
    "checkout.order_sum":          "Amount: {total}",
    "checkout.order_discount":     "💰 Discount: {discount}",
    "checkout.order_promo":        "🏷 Promo code: <b>{code}</b>",
    "checkout.order_status_new":   "Status: 🆕 New",
    "checkout.order_pvz":          "📦 CDEK pickup: {pvz}",
    "checkout.order_delivery_cost":"🚚 Delivery: {cost} ₽",
    "checkout.order_address":      "📍 Address: {address}",
    "checkout.order_comment":      "💬 Comment: {comment}",
    "checkout.order_pay_online":   "\n💳 <b>Pay for your order online</b> using the button below.",
    "checkout.order_contact_seller":"\nPlease contact the seller to pay.",
    "checkout.btn_pay":            "💳 Pay Online",
    "checkout.btn_check_pay":      "🔄 Check Payment",
    "checkout.btn_contact_seller": "💬 Contact Seller",

    "orders.none":             "📦 You have no orders yet.",
    "orders.active_title":     "📦 <b>Active Orders</b>",
    "orders.no_active":        "📦 No active orders.",
    "orders.history_btn":      "📋 Order History ({count})",
    "orders.history_empty":    "📋 Order history is empty.",
    "orders.history_title":    "📋 <b>Order History</b>",
    "orders.order_line":       "📦 Order #{id}",
    "orders.total_line":       "💰 <b>Total: {total}</b>",
    "orders.status_line":      "Status: <b>{label}</b> · {date}",

    "notify.order_status":     "📦 <b>Order #{id}</b>\nStatus updated: <b>{label}</b>",
    "notify.payment_succeeded":"💳 <b>Order #{id}</b>\nPayment status: <b>Paid</b>",
    "notify.payment_canceled": "💳 <b>Order #{id}</b>\nPayment status: <b>Cancelled</b>",
    "notify.refund_succeeded": "💳 <b>Order #{id}</b>\nRefund processed.\n↩️ Funds will be returned to your card within 3–10 business days.",
    "notify.amount":           "Amount: {amount} ₽",
    "notify.payment_confirm":  "✅ Payment confirmed. We have started processing your order!",

    "contact.title":  "💬 <b>Contact Us</b>\n\nReach us directly:\n{contact}",
    "faq.none":       "❓ No FAQ available yet.",

    "payment.check.paid":    "✅ Order paid!",
    "payment.check.status":  "Payment status: {label}",
    "payment.status.pending":             "⏳ Awaiting payment",
    "payment.status.waiting_for_capture": "🔄 Confirming…",
    "payment.status.succeeded":           "✅ Paid",
    "payment.status.canceled":            "❌ Cancelled",
    "payment.status.refunded":            "↩️ Refunded",

    "error.connection":  "❌ Connection error. Please try again.",
    "error.order_failed":"❌ Failed to place order. Please try again.",
    "error.unexpected":
        "ℹ️ The bot accepts free text only when it requests it.\n"
        "Please use the menu buttons.",

    "lang.title":   "🌐 Выберите язык / Select language / Тілді таңдаңыз:",
    "lang.changed": "✅ Language changed to English 🇬🇧",

    # ── Reviews ─────────────────────────────────────────────────────────────────
    "review.rated":            "You rated {stars}",
    "review.text_prompt":      "💬 Want to add a comment?\n(or press Skip):",
    "review.skip_btn":         "⏭ Skip",
    "review.saved":            "✅ Thank you for your review!",
    "review.text_must_be_text":"💬 Please send your comment as text.\nOr press Skip.",
}
