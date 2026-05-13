"""initial schema

Revision ID: 20260509_0001
Revises:
Create Date: 2026-05-09 12:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260509_0001"
down_revision = None
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return inspector.has_table(name)


def upgrade() -> None:
    if not _has_table("categories"):
        op.create_table(
            "categories",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(length=100), nullable=False, unique=True),
        )

    if not _has_table("subcategories"):
        op.create_table(
            "subcategories",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id", ondelete="CASCADE"), nullable=False),
        )

    if not _has_table("products"):
        op.create_table(
            "products",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("subcategory_id", sa.Integer(), sa.ForeignKey("subcategories.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("price", sa.Integer(), nullable=False),
            sa.Column("discount_price", sa.Integer(), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("characteristics", sa.Text(), nullable=True),
            sa.Column("image_file_id", sa.String(length=512), nullable=True),
            sa.Column("image_file_id_2", sa.String(length=512), nullable=True),
            sa.Column("image_file_id_3", sa.String(length=512), nullable=True),
            sa.Column("stock", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        )

    if not _has_table("users"):
        op.create_table(
            "users",
            sa.Column("id", sa.BigInteger(), primary_key=True),
            sa.Column("username", sa.String(length=64), nullable=True),
            sa.Column("first_name", sa.String(length=64), nullable=True),
            sa.Column("last_name", sa.String(length=64), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        )

    if not _has_table("shop_settings"):
        op.create_table(
            "shop_settings",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("shop_name", sa.String(length=128), nullable=False, server_default="Kaza Shop"),
            sa.Column("logo_filename", sa.String(length=256), nullable=True),
            sa.Column("reviews_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("hide_out_of_stock", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("welcome_message", sa.Text(), nullable=True),
            sa.Column("seller_contact", sa.String(length=256), nullable=True),
            sa.Column("admin_contact", sa.String(length=256), nullable=True),
            sa.Column("stamp_filename", sa.String(), nullable=True),
            sa.Column("payment_qr_filename", sa.String(), nullable=True),
            sa.Column("payment_qr_comment", sa.String(), nullable=True),
            sa.Column("legal_name", sa.String(), nullable=True),
        )

    if not _has_table("faq_items"):
        op.create_table(
            "faq_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("question", sa.String(length=512), nullable=False),
            sa.Column("answer", sa.Text(), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        )

    if not _has_table("orders"):
        op.create_table(
            "orders",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("total", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="new"),
            sa.Column("comment", sa.Text(), nullable=True),
            sa.Column("delivery_address", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        )

    if not _has_table("order_items"):
        op.create_table(
            "order_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
            sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="SET NULL"), nullable=True),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("price", sa.Integer(), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        )

    if not _has_table("product_stats"):
        op.create_table(
            "product_stats",
            sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), primary_key=True),
            sa.Column("added_to_cart", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("ordered", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("returned", sa.Integer(), nullable=False, server_default="0"),
        )

    if not _has_table("cart"):
        op.create_table(
            "cart",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.UniqueConstraint("user_id", "product_id", name="uq_cart_user_product"),
        )

    op.execute("CREATE INDEX IF NOT EXISTS ix_products_subcategory_active ON products (subcategory_id, is_active)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_products_stock ON products (stock)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_products_name ON products (name)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_products_name_ci ON products (lower(translate(name, 'АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ', 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя')))")
    op.execute("CREATE INDEX IF NOT EXISTS ix_orders_status ON orders (status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_orders_user_id ON orders (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_orders_created_at ON orders (created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_orders_status_created ON orders (status, created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_order_items_order_id ON order_items (order_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_order_items_product_id ON order_items (product_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_cart_user_id ON cart (user_id)")


def downgrade() -> None:
    op.drop_table("cart")
    op.drop_table("product_stats")
    op.drop_table("order_items")
    op.drop_table("orders")
    op.drop_table("faq_items")
    op.drop_table("shop_settings")
    op.drop_table("users")
    op.drop_table("products")
    op.drop_table("subcategories")
    op.drop_table("categories")
