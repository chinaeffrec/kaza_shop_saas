"""add shop_id to all tenant tables; refactor user PK to surrogate

Phase 3 multi-tenant migration:
- categories, subcategories, products, shop_settings, faq_items, carts, orders:
  add nullable shop_id FK → shops(id)
- users: add surrogate autoincrement PK (new column `id`), rename old bigint PK
  column to `telegram_id`, add shop_id FK
- Update indexes and unique constraints accordingly

All shop_id columns are NULLABLE to allow zero-downtime deployment on existing
data. NOT NULL constraint will be added in Phase 7 after data backfill.

Revision ID: 20260513_0004
Revises: 20260513_0003
Create Date: 2026-05-13
"""

from alembic import op
import sqlalchemy as sa


revision = "20260513_0004"
down_revision = "20260513_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── categories ────────────────────────────────────────────────────────────
    op.add_column("categories", sa.Column("shop_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_categories_shop_id", "categories", "shops", ["shop_id"], ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_categories_shop_id", "categories", ["shop_id"])
    # Remove old unique constraint on name alone; add composite unique
    op.drop_constraint("categories_name_key", "categories", type_="unique")
    op.create_unique_constraint("uq_category_shop_name", "categories", ["shop_id", "name"])

    # ── subcategories ─────────────────────────────────────────────────────────
    op.add_column("subcategories", sa.Column("shop_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_subcategories_shop_id", "subcategories", "shops", ["shop_id"], ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_subcategories_shop_id", "subcategories", ["shop_id"])

    # ── products ──────────────────────────────────────────────────────────────
    op.add_column("products", sa.Column("shop_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_products_shop_id", "products", "shops", ["shop_id"], ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_products_shop_id", "products", ["shop_id"])

    # ── shop_settings ─────────────────────────────────────────────────────────
    op.add_column("shop_settings", sa.Column("shop_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_shop_settings_shop_id", "shop_settings", "shops", ["shop_id"], ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_shop_settings_shop_id", "shop_settings", ["shop_id"], unique=True)

    # ── faq_items ─────────────────────────────────────────────────────────────
    op.add_column("faq_items", sa.Column("shop_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_faq_items_shop_id", "faq_items", "shops", ["shop_id"], ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_faq_items_shop_id", "faq_items", ["shop_id"])

    # ── users: add surrogate PK + telegram_id + shop_id ──────────────────────
    # Step 1: add new surrogate PK column (nullable first)
    op.add_column("users", sa.Column("new_id", sa.Integer(), nullable=True))
    op.execute("CREATE SEQUENCE IF NOT EXISTS users_new_id_seq")
    op.execute("UPDATE users SET new_id = nextval('users_new_id_seq')")
    op.alter_column("users", "new_id", nullable=False)

    # Step 2: add telegram_id column (copy of old id)
    op.add_column("users", sa.Column("telegram_id", sa.BigInteger(), nullable=True))
    op.execute("UPDATE users SET telegram_id = id")
    op.alter_column("users", "telegram_id", nullable=False)

    # Step 3: add shop_id
    op.add_column("users", sa.Column("shop_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_users_shop_id", "users", "shops", ["shop_id"], ["id"],
        ondelete="CASCADE",
    )

    # Step 4: swap the PK — drop old PK on id (bigint telegram id), promote new_id
    op.drop_constraint("users_pkey", "users", type_="primary")
    op.execute("ALTER TABLE users RENAME COLUMN id TO _old_tg_id")
    op.execute("ALTER TABLE users RENAME COLUMN new_id TO id")
    op.execute("ALTER TABLE users ADD PRIMARY KEY (id)")
    op.execute("ALTER TABLE users ALTER COLUMN id SET DEFAULT nextval('users_new_id_seq')")
    # Drop the old telegram_id column (was pointing to same data as _old_tg_id)
    # telegram_id already holds the value — drop the temp column
    op.execute("ALTER TABLE users DROP COLUMN _old_tg_id")

    # Step 5: indexes and unique constraint
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"])
    op.create_index("ix_users_shop_id", "users", ["shop_id"])
    op.create_unique_constraint(
        "uq_user_telegram_shop", "users", ["telegram_id", "shop_id"]
    )

    # ── carts ─────────────────────────────────────────────────────────────────
    op.add_column("carts", sa.Column("shop_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_carts_shop_id", "carts", "shops", ["shop_id"], ["id"],
        ondelete="CASCADE",
    )
    # Replace old unique constraint and index
    op.drop_constraint("carts_user_id_product_id_key", "carts", type_="unique")
    op.drop_index("ix_cart_user_id", "carts")
    op.create_unique_constraint(
        "uq_cart_shop_user_product", "carts", ["shop_id", "user_id", "product_id"]
    )
    op.create_index("ix_cart_shop_user", "carts", ["shop_id", "user_id"])

    # ── orders ────────────────────────────────────────────────────────────────
    op.add_column("orders", sa.Column("shop_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_orders_shop_id", "orders", "shops", ["shop_id"], ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_orders_shop_id", "orders", ["shop_id"])
    # Replace old composite index
    try:
        op.drop_index("ix_orders_status_created", "orders")
    except Exception:
        pass
    op.create_index(
        "ix_orders_shop_status_created", "orders", ["shop_id", "status", "created_at"]
    )


def downgrade() -> None:
    # ── orders ────────────────────────────────────────────────────────────────
    op.drop_index("ix_orders_shop_status_created", "orders")
    op.create_index("ix_orders_status_created", "orders", ["status", "created_at"])
    op.drop_constraint("fk_orders_shop_id", "orders", type_="foreignkey")
    op.drop_index("ix_orders_shop_id", "orders")
    op.drop_column("orders", "shop_id")

    # ── carts ─────────────────────────────────────────────────────────────────
    op.drop_index("ix_cart_shop_user", "carts")
    op.drop_constraint("uq_cart_shop_user_product", "carts", type_="unique")
    op.create_index("ix_cart_user_id", "carts", ["user_id"])
    op.create_unique_constraint(
        "carts_user_id_product_id_key", "carts", ["user_id", "product_id"]
    )
    op.drop_constraint("fk_carts_shop_id", "carts", type_="foreignkey")
    op.drop_column("carts", "shop_id")

    # ── users: reverse surrogate PK swap ─────────────────────────────────────
    op.drop_constraint("uq_user_telegram_shop", "users", type_="unique")
    op.drop_index("ix_users_shop_id", "users")
    op.drop_index("ix_users_telegram_id", "users")
    op.drop_constraint("fk_users_shop_id", "users", type_="foreignkey")
    op.drop_column("users", "shop_id")
    # Restore original bigint PK from telegram_id
    op.execute("ALTER TABLE users DROP CONSTRAINT users_pkey")
    op.execute("ALTER TABLE users RENAME COLUMN id TO _surrogate_id")
    op.execute("ALTER TABLE users RENAME COLUMN telegram_id TO id")
    op.execute("ALTER TABLE users ADD PRIMARY KEY (id)")
    op.execute("ALTER TABLE users DROP COLUMN _surrogate_id")

    # ── faq_items ─────────────────────────────────────────────────────────────
    op.drop_index("ix_faq_items_shop_id", "faq_items")
    op.drop_constraint("fk_faq_items_shop_id", "faq_items", type_="foreignkey")
    op.drop_column("faq_items", "shop_id")

    # ── shop_settings ─────────────────────────────────────────────────────────
    op.drop_index("ix_shop_settings_shop_id", "shop_settings")
    op.drop_constraint("fk_shop_settings_shop_id", "shop_settings", type_="foreignkey")
    op.drop_column("shop_settings", "shop_id")

    # ── products ──────────────────────────────────────────────────────────────
    op.drop_index("ix_products_shop_id", "products")
    op.drop_constraint("fk_products_shop_id", "products", type_="foreignkey")
    op.drop_column("products", "shop_id")

    # ── subcategories ─────────────────────────────────────────────────────────
    op.drop_index("ix_subcategories_shop_id", "subcategories")
    op.drop_constraint("fk_subcategories_shop_id", "subcategories", type_="foreignkey")
    op.drop_column("subcategories", "shop_id")

    # ── categories ────────────────────────────────────────────────────────────
    op.drop_constraint("uq_category_shop_name", "categories", type_="unique")
    op.create_unique_constraint("categories_name_key", "categories", ["name"])
    op.drop_index("ix_categories_shop_id", "categories")
    op.drop_constraint("fk_categories_shop_id", "categories", type_="foreignkey")
    op.drop_column("categories", "shop_id")
