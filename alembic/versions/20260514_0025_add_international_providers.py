"""Add international payment and delivery provider fields

Revision ID: 0025
Revises: 0024
Create Date: 2026-05-14
"""
from alembic import op
import sqlalchemy as sa

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Платёжный провайдер ──────────────────────────────────────────────────
    # Код провайдера: yookassa | stripe | paypal | checkout
    op.add_column("shop_settings", sa.Column(
        "payment_provider",
        sa.String(32),
        nullable=False,
        server_default="yookassa",
    ))

    # Stripe
    op.add_column("shop_settings", sa.Column(
        "stripe_secret_key", sa.String(512), nullable=True,
        comment="Fernet-зашифрованный Stripe Secret Key (sk_live_… / sk_test_…)",
    ))
    op.add_column("shop_settings", sa.Column(
        "stripe_webhook_secret", sa.String(512), nullable=True,
        comment="Fernet-зашифрованный Stripe Webhook Secret (whsec_…)",
    ))
    op.add_column("shop_settings", sa.Column(
        "stripe_publishable_key", sa.String(512), nullable=True,
        comment="Stripe Publishable Key для фронтенда (pk_live_… / pk_test_…)",
    ))

    # PayPal
    op.add_column("shop_settings", sa.Column(
        "paypal_client_id", sa.String(512), nullable=True,
    ))
    op.add_column("shop_settings", sa.Column(
        "paypal_client_secret", sa.String(512), nullable=True,
        comment="Fernet-зашифрованный PayPal Client Secret",
    ))
    op.add_column("shop_settings", sa.Column(
        "paypal_sandbox", sa.Boolean(), nullable=False, server_default="false",
    ))

    # Checkout.com (опционально — для крупных европейских рынков)
    op.add_column("shop_settings", sa.Column(
        "checkout_secret_key", sa.String(512), nullable=True,
        comment="Fernet-зашифрованный Checkout.com Secret Key",
    ))
    op.add_column("shop_settings", sa.Column(
        "checkout_public_key", sa.String(512), nullable=True,
    ))

    # ── Провайдер доставки ───────────────────────────────────────────────────
    # Код провайдера: cdek | dhl | easypost | shippo | fedex
    op.add_column("shop_settings", sa.Column(
        "delivery_provider",
        sa.String(32),
        nullable=False,
        server_default="cdek",
    ))

    # DHL Express
    op.add_column("shop_settings", sa.Column(
        "dhl_api_key", sa.String(512), nullable=True,
        comment="Fernet-зашифрованный DHL API Key",
    ))
    op.add_column("shop_settings", sa.Column(
        "dhl_api_password", sa.String(512), nullable=True,
        comment="Fernet-зашифрованный DHL API Password",
    ))
    op.add_column("shop_settings", sa.Column(
        "dhl_account_number", sa.String(64), nullable=True,
    ))
    op.add_column("shop_settings", sa.Column(
        "dhl_test_mode", sa.Boolean(), nullable=False, server_default="true",
    ))

    # EasyPost (агрегатор — один ключ для всех перевозчиков)
    op.add_column("shop_settings", sa.Column(
        "easypost_api_key", sa.String(512), nullable=True,
        comment="Fernet-зашифрованный EasyPost API Key",
    ))

    # FedEx
    op.add_column("shop_settings", sa.Column(
        "fedex_client_id", sa.String(512), nullable=True,
    ))
    op.add_column("shop_settings", sa.Column(
        "fedex_client_secret", sa.String(512), nullable=True,
        comment="Fernet-зашифрованный FedEx Client Secret",
    ))
    op.add_column("shop_settings", sa.Column(
        "fedex_account_number", sa.String(64), nullable=True,
    ))

    # ── Адрес отправителя (используется всеми провайдерами доставки) ─────────
    # CDEK уже имеет cdek_sender_city_code/cdek_sender_address.
    # Для международных провайдеров нужен полный структурированный адрес.
    op.add_column("shop_settings", sa.Column(
        "sender_country", sa.String(2), nullable=True,
        comment="ISO 3166-1 alpha-2: RU, DE, US, …",
    ))
    op.add_column("shop_settings", sa.Column(
        "sender_city", sa.String(128), nullable=True,
    ))
    op.add_column("shop_settings", sa.Column(
        "sender_street", sa.String(256), nullable=True,
    ))
    op.add_column("shop_settings", sa.Column(
        "sender_postal_code", sa.String(16), nullable=True,
    ))
    op.add_column("shop_settings", sa.Column(
        "sender_name", sa.String(128), nullable=True,
        comment="Имя/название компании отправителя",
    ))
    op.add_column("shop_settings", sa.Column(
        "sender_phone", sa.String(32), nullable=True,
    ))

    # ── Валюта магазина ──────────────────────────────────────────────────────
    # При международных платежах валюта может отличаться от RUB.
    op.add_column("shop_settings", sa.Column(
        "currency", sa.String(3), nullable=False, server_default="RUB",
        comment="ISO 4217: RUB, USD, EUR, GBP, TRY, …",
    ))


def downgrade() -> None:
    cols = [
        # payment
        "payment_provider",
        "stripe_secret_key", "stripe_webhook_secret", "stripe_publishable_key",
        "paypal_client_id", "paypal_client_secret", "paypal_sandbox",
        "checkout_secret_key", "checkout_public_key",
        # delivery
        "delivery_provider",
        "dhl_api_key", "dhl_api_password", "dhl_account_number", "dhl_test_mode",
        "easypost_api_key",
        "fedex_client_id", "fedex_client_secret", "fedex_account_number",
        # sender address
        "sender_country", "sender_city", "sender_street",
        "sender_postal_code", "sender_name", "sender_phone",
        # currency
        "currency",
    ]
    for col in cols:
        op.drop_column("shop_settings", col)
