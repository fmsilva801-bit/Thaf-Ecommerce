import json
import os
import sqlite3
import hashlib
import secrets
import re
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
from io import BytesIO
from flask import Flask, Response, redirect, request, send_from_directory

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "ecommerce.db")
STATIC_DIR = os.path.join(BASE_DIR, "static")
PUBLIC_DIR = os.path.join(BASE_DIR, "public")

MODULE_KEYS = (
    "dashboard",
    "products",
    "costs",
    "purchases",
    "inventory",
    "sales",
    "finance",
    "users",
)

ROLE_BASE_PERMISSIONS = {
    "master": list(MODULE_KEYS),
    "admin": ["dashboard", "products", "costs", "purchases", "inventory", "sales", "finance"],
    "member": ["dashboard"],
}


def utc_now_iso():
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def slugify(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", str(value or "").strip().lower())
    text = text.strip("-")
    return text or "empresa"


class BadRequestError(Exception):
    pass


def parse_json_body(handler):
    length = int(handler.headers.get("Content-Length", 0))
    if length == 0:
        return {}
    raw = handler.rfile.read(length)
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise BadRequestError("JSON inválido no corpo da requisição.")


def db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = db_connection()
    cur = conn.cursor()

    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            slug TEXT NOT NULL UNIQUE,
            trade_name TEXT,
            email TEXT,
            phone TEXT,
            document TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('master','admin','member')),
            is_active INTEGER NOT NULL DEFAULT 1,
            module_permissions TEXT,
            avatar_url TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(company_id) REFERENCES companies(id)
        );

        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            company_id INTEGER,
            user_id INTEGER NOT NULL,
            expires_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(company_id) REFERENCES companies(id)
        );

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL DEFAULT 1,
            sku TEXT,
            barcode TEXT,
            name TEXT NOT NULL,
            category TEXT,
            brand TEXT,
            unit TEXT DEFAULT 'un',
            description TEXT,
            cost_price REAL NOT NULL DEFAULT 0,
            desired_margin_percent REAL NOT NULL DEFAULT 30,
            stock_qty INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_by INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(company_id) REFERENCES companies(id),
            FOREIGN KEY(created_by) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS product_cost_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL DEFAULT 1,
            product_id INTEGER NOT NULL,
            label TEXT NOT NULL,
            value_type TEXT NOT NULL CHECK(value_type IN ('fixed','percent')),
            value REAL NOT NULL,
            FOREIGN KEY(company_id) REFERENCES companies(id),
            FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS inventory_movements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL DEFAULT 1,
            product_id INTEGER NOT NULL,
            movement_type TEXT NOT NULL CHECK(movement_type IN ('entry','exit')),
            qty INTEGER NOT NULL,
            note TEXT,
            sale_id INTEGER,
            purchase_id INTEGER,
            created_by INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(company_id) REFERENCES companies(id),
            FOREIGN KEY(product_id) REFERENCES products(id),
            FOREIGN KEY(created_by) REFERENCES users(id),
            FOREIGN KEY(sale_id) REFERENCES sales(id) ON DELETE SET NULL,
            FOREIGN KEY(purchase_id) REFERENCES purchases(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL DEFAULT 1,
            product_id INTEGER NOT NULL,
            qty INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            total REAL NOT NULL,
            cogs_total REAL NOT NULL DEFAULT 0,
            taxes_total REAL NOT NULL DEFAULT 0,
            extra_expenses_total REAL NOT NULL DEFAULT 0,
            gross_profit REAL NOT NULL DEFAULT 0,
            net_profit REAL NOT NULL DEFAULT 0,
            created_by INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(company_id) REFERENCES companies(id),
            FOREIGN KEY(product_id) REFERENCES products(id),
            FOREIGN KEY(created_by) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS financial_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL DEFAULT 1,
            entry_type TEXT NOT NULL CHECK(entry_type IN ('income','expense')),
            category TEXT NOT NULL,
            description TEXT,
            amount REAL NOT NULL,
            sale_id INTEGER,
            purchase_id INTEGER,
            payment_method TEXT,
            payment_terms TEXT,
            notes TEXT,
            payment_status TEXT,
            origin TEXT NOT NULL DEFAULT 'manual',
            created_by INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(company_id) REFERENCES companies(id),
            FOREIGN KEY(created_by) REFERENCES users(id),
            FOREIGN KEY(sale_id) REFERENCES sales(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL DEFAULT 1,
            name TEXT NOT NULL,
            description TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_by INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            updated_by INTEGER,
            updated_at TEXT,
            inactivated_by INTEGER,
            inactivated_at TEXT,
            FOREIGN KEY(company_id) REFERENCES companies(id),
            FOREIGN KEY(created_by) REFERENCES users(id),
            FOREIGN KEY(updated_by) REFERENCES users(id),
            FOREIGN KEY(inactivated_by) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL DEFAULT 1,
            name TEXT NOT NULL,
            contact TEXT,
            phone TEXT,
            email TEXT,
            notes TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_by INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(company_id) REFERENCES companies(id),
            FOREIGN KEY(created_by) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL DEFAULT 1,
            supplier_id INTEGER,
            purchase_type TEXT NOT NULL CHECK(purchase_type IN ('inventory','operational')),
            payment_method TEXT,
            payment_terms TEXT,
            notes TEXT,
            total_amount REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'confirmada',
            created_by INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(company_id) REFERENCES companies(id),
            FOREIGN KEY(supplier_id) REFERENCES suppliers(id),
            FOREIGN KEY(created_by) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS purchase_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL DEFAULT 1,
            purchase_id INTEGER NOT NULL,
            product_id INTEGER,
            label TEXT NOT NULL,
            qty INTEGER NOT NULL DEFAULT 1,
            unit_cost REAL NOT NULL DEFAULT 0,
            total_cost REAL NOT NULL DEFAULT 0,
            affects_stock INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(company_id) REFERENCES companies(id),
            FOREIGN KEY(purchase_id) REFERENCES purchases(id) ON DELETE CASCADE,
            FOREIGN KEY(product_id) REFERENCES products(id)
        );

        CREATE TABLE IF NOT EXISTS cost_calculations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL DEFAULT 1,
            product_id INTEGER,
            product_name TEXT,
            cost_amount REAL NOT NULL DEFAULT 0,
            shipping_amount REAL NOT NULL DEFAULT 0,
            other_costs_amount REAL NOT NULL DEFAULT 0,
            tax_percent REAL NOT NULL DEFAULT 0,
            commission_percent REAL NOT NULL DEFAULT 0,
            margin_percent REAL NOT NULL DEFAULT 0,
            tax_amount REAL NOT NULL DEFAULT 0,
            commission_amount REAL NOT NULL DEFAULT 0,
            profit_amount REAL NOT NULL DEFAULT 0,
            sale_price REAL NOT NULL DEFAULT 0,
            created_by INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(company_id) REFERENCES companies(id),
            FOREIGN KEY(product_id) REFERENCES products(id),
            FOREIGN KEY(created_by) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL DEFAULT 1,
            module TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id INTEGER,
            action TEXT NOT NULL,
            payload_json TEXT,
            created_by INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(company_id) REFERENCES companies(id),
            FOREIGN KEY(created_by) REFERENCES users(id)
        );
        """
    )

    products_columns = {row["name"] for row in cur.execute("PRAGMA table_info(products)").fetchall()}
    if "is_active" not in products_columns:
        cur.execute("ALTER TABLE products ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")
    if "category" not in products_columns:
        cur.execute("ALTER TABLE products ADD COLUMN category TEXT")
    if "description" not in products_columns:
        cur.execute("ALTER TABLE products ADD COLUMN description TEXT")
    if "barcode" not in products_columns:
        cur.execute("ALTER TABLE products ADD COLUMN barcode TEXT")
    if "category_id" not in products_columns:
        cur.execute("ALTER TABLE products ADD COLUMN category_id INTEGER")
    if "brand" not in products_columns:
        cur.execute("ALTER TABLE products ADD COLUMN brand TEXT")
    if "unit" not in products_columns:
        cur.execute("ALTER TABLE products ADD COLUMN unit TEXT DEFAULT 'un'")

    users_columns = {row["name"] for row in cur.execute("PRAGMA table_info(users)").fetchall()}
    if "is_active" not in users_columns:
        cur.execute("ALTER TABLE users ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")
    if "module_permissions" not in users_columns:
        cur.execute("ALTER TABLE users ADD COLUMN module_permissions TEXT")
    if "avatar_url" not in users_columns:
        cur.execute("ALTER TABLE users ADD COLUMN avatar_url TEXT")

    inventory_columns = {row["name"] for row in cur.execute("PRAGMA table_info(inventory_movements)").fetchall()}
    if "sale_id" not in inventory_columns:
        cur.execute("ALTER TABLE inventory_movements ADD COLUMN sale_id INTEGER")
    if "purchase_id" not in inventory_columns:
        cur.execute("ALTER TABLE inventory_movements ADD COLUMN purchase_id INTEGER")
    cur.execute(
        """
        UPDATE inventory_movements
        SET purchase_id = CAST(REPLACE(note, 'Entrada por compra #', '') AS INTEGER)
        WHERE purchase_id IS NULL
          AND movement_type = 'entry'
          AND note LIKE 'Entrada por compra #%'
        """
    )

    finance_columns = {row["name"] for row in cur.execute("PRAGMA table_info(financial_entries)").fetchall()}
    if "sale_id" not in finance_columns:
        cur.execute("ALTER TABLE financial_entries ADD COLUMN sale_id INTEGER")
    finance_columns = {row["name"] for row in cur.execute("PRAGMA table_info(financial_entries)").fetchall()}
    finance_extra_columns = [
        ("purchase_id", "INTEGER"),
        ("payment_method", "TEXT"),
        ("payment_terms", "TEXT"),
        ("notes", "TEXT"),
        ("payment_status", "TEXT"),
        ("origin", "TEXT NOT NULL DEFAULT 'manual'"),
    ]
    for col_name, col_def in finance_extra_columns:
        if col_name not in finance_columns:
            cur.execute(f"ALTER TABLE financial_entries ADD COLUMN {col_name} {col_def}")

    sales_columns = {row["name"] for row in cur.execute("PRAGMA table_info(sales)").fetchall()}
    sales_columns_migration = [
        ("cogs_total", "REAL NOT NULL DEFAULT 0"),
        ("taxes_total", "REAL NOT NULL DEFAULT 0"),
        ("extra_expenses_total", "REAL NOT NULL DEFAULT 0"),
        ("gross_profit", "REAL NOT NULL DEFAULT 0"),
        ("net_profit", "REAL NOT NULL DEFAULT 0"),
    ]
    for column_name, column_def in sales_columns_migration:
        if column_name not in sales_columns:
            cur.execute(f"ALTER TABLE sales ADD COLUMN {column_name} {column_def}")

    tenant_columns = [
        ("users", "company_id", "INTEGER"),
        ("sessions", "company_id", "INTEGER"),
        ("products", "company_id", "INTEGER NOT NULL DEFAULT 1"),
        ("product_cost_items", "company_id", "INTEGER NOT NULL DEFAULT 1"),
        ("inventory_movements", "company_id", "INTEGER NOT NULL DEFAULT 1"),
        ("sales", "company_id", "INTEGER NOT NULL DEFAULT 1"),
        ("financial_entries", "company_id", "INTEGER NOT NULL DEFAULT 1"),
        ("categories", "company_id", "INTEGER NOT NULL DEFAULT 1"),
        ("suppliers", "company_id", "INTEGER NOT NULL DEFAULT 1"),
        ("purchases", "company_id", "INTEGER NOT NULL DEFAULT 1"),
        ("purchase_items", "company_id", "INTEGER NOT NULL DEFAULT 1"),
        ("cost_calculations", "company_id", "INTEGER NOT NULL DEFAULT 1"),
        ("audit_logs", "company_id", "INTEGER NOT NULL DEFAULT 1"),
    ]
    for table_name, col_name, col_def in tenant_columns:
        table_cols = {row["name"] for row in cur.execute(f"PRAGMA table_info({table_name})").fetchall()}
        if col_name not in table_cols:
            cur.execute(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_def}")

    # Legacy migration: categories previously had UNIQUE(name) global.
    category_indexes = cur.execute("PRAGMA index_list(categories)").fetchall()
    rebuild_categories = False
    for idx in category_indexes:
        if int(idx["unique"] or 0) != 1:
            continue
        idx_name = idx["name"]
        idx_cols = [r["name"] for r in cur.execute(f"PRAGMA index_info('{idx_name}')").fetchall()]
        if idx_cols == ["name"]:
            rebuild_categories = True
            break
    if rebuild_categories:
        cur.executescript(
            """
            ALTER TABLE categories RENAME TO categories_legacy;
            CREATE TABLE categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL DEFAULT 1,
                name TEXT NOT NULL,
                description TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_by INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_by INTEGER,
                updated_at TEXT,
                inactivated_by INTEGER,
                inactivated_at TEXT,
                FOREIGN KEY(company_id) REFERENCES companies(id),
                FOREIGN KEY(created_by) REFERENCES users(id),
                FOREIGN KEY(updated_by) REFERENCES users(id),
                FOREIGN KEY(inactivated_by) REFERENCES users(id)
            );
            INSERT INTO categories (
                id, company_id, name, description, is_active,
                created_by, created_at, updated_by, updated_at, inactivated_by, inactivated_at
            )
            SELECT
                id, COALESCE(company_id, 1), name, description, is_active,
                created_by, created_at, updated_by, updated_at, inactivated_by, inactivated_at
            FROM categories_legacy;
            DROP TABLE categories_legacy;
            """
        )

    cur.execute("SELECT id FROM companies ORDER BY id ASC LIMIT 1")
    default_company = cur.fetchone()
    if default_company:
        default_company_id = int(default_company["id"])
    else:
        base_slug = slugify("empresa-principal")
        company_slug = base_slug
        suffix = 1
        while cur.execute("SELECT 1 FROM companies WHERE slug = ?", (company_slug,)).fetchone():
            company_slug = f"{base_slug}-{suffix}"
            suffix += 1
        cur.execute(
            """
            INSERT INTO companies (name, slug, trade_name, email, phone, document, is_active, created_at)
            VALUES (?, ?, ?, '', '', '', 1, ?)
            """,
            ("Empresa Principal", company_slug, "Empresa Principal", utc_now_iso()),
        )
        default_company_id = int(cur.lastrowid)

    cur.execute("UPDATE users SET company_id = ? WHERE company_id IS NULL OR company_id = 0", (default_company_id,))
    cur.execute(
        """
        UPDATE sessions
        SET company_id = (
            SELECT u.company_id
            FROM users u
            WHERE u.id = sessions.user_id
        )
        WHERE company_id IS NULL OR company_id = 0
        """
    )
    cur.execute(
        """
        UPDATE products
        SET company_id = COALESCE(
            (SELECT u.company_id FROM users u WHERE u.id = products.created_by),
            ?
        )
        WHERE company_id IS NULL OR company_id = 0
        """,
        (default_company_id,),
    )
    cur.execute(
        """
        UPDATE categories
        SET company_id = COALESCE(
            (SELECT u.company_id FROM users u WHERE u.id = categories.created_by),
            ?
        )
        WHERE company_id IS NULL OR company_id = 0
        """,
        (default_company_id,),
    )
    cur.execute(
        """
        UPDATE suppliers
        SET company_id = COALESCE(
            (SELECT u.company_id FROM users u WHERE u.id = suppliers.created_by),
            ?
        )
        WHERE company_id IS NULL OR company_id = 0
        """,
        (default_company_id,),
    )
    cur.execute(
        """
        UPDATE purchases
        SET company_id = COALESCE(
            (SELECT s.company_id FROM suppliers s WHERE s.id = purchases.supplier_id),
            (SELECT u.company_id FROM users u WHERE u.id = purchases.created_by),
            ?
        )
        WHERE company_id IS NULL OR company_id = 0
        """,
        (default_company_id,),
    )
    cur.execute(
        """
        UPDATE purchase_items
        SET company_id = COALESCE(
            (SELECT p.company_id FROM purchases p WHERE p.id = purchase_items.purchase_id),
            (SELECT pr.company_id FROM products pr WHERE pr.id = purchase_items.product_id),
            ?
        )
        WHERE company_id IS NULL OR company_id = 0
        """,
        (default_company_id,),
    )
    cur.execute(
        """
        UPDATE product_cost_items
        SET company_id = COALESCE(
            (SELECT p.company_id FROM products p WHERE p.id = product_cost_items.product_id),
            ?
        )
        WHERE company_id IS NULL OR company_id = 0
        """,
        (default_company_id,),
    )
    cur.execute(
        """
        UPDATE inventory_movements
        SET company_id = COALESCE(
            (SELECT p.company_id FROM products p WHERE p.id = inventory_movements.product_id),
            (SELECT u.company_id FROM users u WHERE u.id = inventory_movements.created_by),
            ?
        )
        WHERE company_id IS NULL OR company_id = 0
        """,
        (default_company_id,),
    )
    cur.execute(
        """
        UPDATE sales
        SET company_id = COALESCE(
            (SELECT p.company_id FROM products p WHERE p.id = sales.product_id),
            (SELECT u.company_id FROM users u WHERE u.id = sales.created_by),
            ?
        )
        WHERE company_id IS NULL OR company_id = 0
        """,
        (default_company_id,),
    )
    cur.execute(
        """
        UPDATE financial_entries
        SET company_id = COALESCE(
            (SELECT s.company_id FROM sales s WHERE s.id = financial_entries.sale_id),
            (SELECT p.company_id FROM purchases p WHERE p.id = financial_entries.purchase_id),
            (SELECT u.company_id FROM users u WHERE u.id = financial_entries.created_by),
            ?
        )
        WHERE company_id IS NULL OR company_id = 0
        """,
        (default_company_id,),
    )
    cur.execute(
        """
        UPDATE cost_calculations
        SET company_id = COALESCE(
            (SELECT p.company_id FROM products p WHERE p.id = cost_calculations.product_id),
            (SELECT u.company_id FROM users u WHERE u.id = cost_calculations.created_by),
            ?
        )
        WHERE company_id IS NULL OR company_id = 0
        """,
        (default_company_id,),
    )
    cur.execute(
        """
        UPDATE audit_logs
        SET company_id = COALESCE(
            (SELECT u.company_id FROM users u WHERE u.id = audit_logs.created_by),
            ?
        )
        WHERE company_id IS NULL OR company_id = 0
        """,
        (default_company_id,),
    )

    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_categories_company_name ON categories(company_id, name)")
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_products_company_sku ON products(company_id, sku)")
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_products_company_barcode ON products(company_id, barcode)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_products_company ON products(company_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sales_company_created ON sales(company_id, created_at)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_finance_company_created ON financial_entries(company_id, created_at)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_inventory_company ON inventory_movements(company_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_purchases_company_created ON purchases(company_id, created_at)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_users_company ON users(company_id)")

    cur.execute("SELECT COUNT(*) as c FROM users")
    total_users = cur.fetchone()["c"]
    if total_users == 0:
        cur.execute(
            """
            INSERT INTO users (company_id, name, email, password_hash, role, module_permissions, created_at)
            VALUES (?, ?, ?, ?, 'master', ?, ?)
            """,
            (
                default_company_id,
                "Administrador Master",
                "master@admin.local",
                hash_password("admin123"),
                json.dumps(ROLE_BASE_PERMISSIONS["master"], ensure_ascii=False),
                utc_now_iso(),
            ),
        )

    product_categories = cur.execute(
        """
        SELECT DISTINCT company_id, TRIM(category) AS name
        FROM products
        WHERE category IS NOT NULL AND TRIM(category) <> ''
        """
    ).fetchall()
    for row in product_categories:
        cat_name = row["name"]
        if not cat_name:
            continue
        cur.execute(
            """
            INSERT OR IGNORE INTO categories (company_id, name, description, is_active, created_by, created_at)
            VALUES (?, ?, '', 1, 1, ?)
            """,
            (int(row["company_id"] or default_company_id), cat_name, utc_now_iso()),
        )

    category_rows = cur.execute("SELECT id, company_id, name FROM categories").fetchall()
    category_map = {
        (int(r["company_id"] or default_company_id), str(r["name"]).strip().lower()): int(r["id"])
        for r in category_rows
        if r["name"]
    }
    products_without_category_id = cur.execute(
        """
        SELECT id, company_id, category
        FROM products
        WHERE (category_id IS NULL OR category_id = 0)
          AND category IS NOT NULL
          AND TRIM(category) <> ''
        """
    ).fetchall()
    for row in products_without_category_id:
        key = (int(row["company_id"] or default_company_id), str(row["category"]).strip().lower())
        cat_id = category_map.get(key)
        if cat_id:
            cur.execute("UPDATE products SET category_id = ? WHERE id = ? AND company_id = ?", (cat_id, row["id"], int(row["company_id"] or default_company_id)))

    conn.commit()
    conn.close()


def get_user_by_token(conn, token):
    if not token:
        return None
    row = conn.execute(
        """
        SELECT u.*, c.name AS company_name, c.slug AS company_slug FROM sessions s
        JOIN users u ON u.id = s.user_id
        JOIN companies c ON c.id = u.company_id
        WHERE s.token = ? AND s.expires_at > ? AND u.is_active = 1 AND c.is_active = 1
          AND (s.company_id IS NULL OR s.company_id = u.company_id)
        """,
        (token, utc_now_iso()),
    ).fetchone()
    return row


def require_auth(handler, conn):
    auth = handler.headers.get("Authorization", "")
    token = ""
    if auth.startswith("Bearer "):
        token = auth.split(" ", 1)[1].strip()
    user = get_user_by_token(conn, token)
    if not user:
        handler.send_json({"error": "Nao autorizado"}, status=401)
        return None
    return user


def company_id_from_user(user):
    return int(user["company_id"] or 0)


def require_admin(handler, user):
    if user["role"] not in ("master", "admin"):
        handler.send_json({"error": "Permissao insuficiente"}, status=403)
        return False
    return True


def parse_module_permissions(raw_value, role):
    if role == "master":
        return list(MODULE_KEYS)

    allowed = set(MODULE_KEYS)
    parsed = []
    if isinstance(raw_value, str) and raw_value.strip():
        try:
            value = json.loads(raw_value)
            if isinstance(value, list):
                parsed = value
        except Exception:
            parsed = [item.strip() for item in raw_value.split(",") if item.strip()]
    elif isinstance(raw_value, list):
        parsed = raw_value

    normalized = []
    seen = set()
    for item in parsed:
        key = str(item or "").strip()
        if key in allowed and key not in seen:
            seen.add(key)
            normalized.append(key)

    if not normalized:
        return list(ROLE_BASE_PERMISSIONS.get(role, ROLE_BASE_PERMISSIONS["member"]))
    return normalized


def permissions_json_for_role(role, raw_permissions):
    permissions = parse_module_permissions(raw_permissions, role)
    return json.dumps(permissions, ensure_ascii=False)


def user_permissions(user_row):
    role = str(user_row["role"] or "member").strip().lower()
    raw = user_row["module_permissions"] if "module_permissions" in user_row.keys() else None
    return parse_module_permissions(raw, role)


def require_module_permission(handler, user, module_key):
    if module_key not in MODULE_KEYS:
        return True
    if str(user["role"] or "").strip().lower() == "master":
        return True
    if module_key in set(user_permissions(user)):
        return True
    handler.send_json({"error": "Você não tem permissão para acessar este módulo."}, status=403)
    return False


def module_key_for_path(path):
    if path.startswith("/api/dashboard"):
        return "dashboard"
    if path.startswith("/api/products"):
        return "products"
    if path.startswith("/api/categories"):
        return "products"
    if path.startswith("/api/cost-calculations"):
        return "costs"
    if path.startswith("/api/suppliers") or path.startswith("/api/purchases"):
        return "purchases"
    if path.startswith("/api/inventory"):
        return "inventory"
    if path.startswith("/api/sales"):
        return "sales"
    if path.startswith("/api/finance"):
        return "finance"
    if path.startswith("/api/users"):
        return "users"
    return None


def count_active_masters(conn, company_id=None):
    if company_id is None:
        row = conn.execute("SELECT COUNT(*) AS c FROM users WHERE role = 'master' AND is_active = 1").fetchone()
    else:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM users WHERE role = 'master' AND is_active = 1 AND company_id = ?",
            (int(company_id),),
        ).fetchone()
    return int(row["c"] or 0)


def user_history_summary(conn, user_id, company_id=None):
    checks = [
        ("products", "SELECT COUNT(*) AS c FROM products WHERE created_by = ? {scope}"),
        ("inventory_movements", "SELECT COUNT(*) AS c FROM inventory_movements WHERE created_by = ? {scope}"),
        ("sales", "SELECT COUNT(*) AS c FROM sales WHERE created_by = ? {scope}"),
        ("financial_entries", "SELECT COUNT(*) AS c FROM financial_entries WHERE created_by = ? {scope}"),
        ("suppliers", "SELECT COUNT(*) AS c FROM suppliers WHERE created_by = ? {scope}"),
        ("purchases", "SELECT COUNT(*) AS c FROM purchases WHERE created_by = ? {scope}"),
        ("categories_created", "SELECT COUNT(*) AS c FROM categories WHERE created_by = ? {scope}"),
        ("categories_updated", "SELECT COUNT(*) AS c FROM categories WHERE updated_by = ? {scope}"),
        ("categories_inactivated", "SELECT COUNT(*) AS c FROM categories WHERE inactivated_by = ? {scope}"),
        ("cost_calculations", "SELECT COUNT(*) AS c FROM cost_calculations WHERE created_by = ? {scope}"),
        ("audit_logs", "SELECT COUNT(*) AS c FROM audit_logs WHERE created_by = ? {scope}"),
    ]
    summary = {}
    for key, query in checks:
        if company_id is None:
            final_query = query.format(scope="")
            params = (user_id,)
        else:
            final_query = query.format(scope="AND company_id = ?")
            params = (user_id, int(company_id))
        summary[key] = int(conn.execute(final_query, params).fetchone()["c"] or 0)
    return summary


def user_has_critical_history(conn, user_id, company_id=None):
    summary = user_history_summary(conn, user_id, company_id)
    return any(v > 0 for v in summary.values()), summary


def log_audit(conn, module, entity_type, entity_id, action, created_by, payload=None, company_id=None):
    safe_payload = None
    if payload is not None:
        try:
            safe_payload = json.dumps(payload, ensure_ascii=False)
        except Exception:
            safe_payload = None
    resolved_company_id = company_id
    if not resolved_company_id:
        user_row = conn.execute("SELECT company_id FROM users WHERE id = ?", (int(created_by),)).fetchone()
        if user_row and user_row["company_id"]:
            resolved_company_id = int(user_row["company_id"])
    if not resolved_company_id:
        resolved_company_id = 1
    conn.execute(
        """
        INSERT INTO audit_logs (company_id, module, entity_type, entity_id, action, payload_json, created_by, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(resolved_company_id),
            str(module or "").strip() or "system",
            str(entity_type or "").strip() or "entity",
            int(entity_id) if entity_id is not None else None,
            str(action or "").strip() or "change",
            safe_payload,
            int(created_by),
            utc_now_iso(),
        ),
    )


def product_analysis(conn, product_id, company_id=None):
    if company_id is None:
        product = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    else:
        product = conn.execute("SELECT * FROM products WHERE id = ? AND company_id = ?", (product_id, int(company_id))).fetchone()
    if not product:
        return None
    category_name = (product["category"] or "").strip()
    category_id = None
    if "category_id" in product.keys() and product["category_id"]:
        try:
            category_id = int(product["category_id"])
        except (TypeError, ValueError):
            category_id = None
    if category_id:
        if company_id is None:
            category_row = conn.execute("SELECT id, name, is_active FROM categories WHERE id = ?", (category_id,)).fetchone()
        else:
            category_row = conn.execute(
                "SELECT id, name, is_active FROM categories WHERE id = ? AND company_id = ?",
                (category_id, int(company_id)),
            ).fetchone()
        if category_row:
            category_name = category_row["name"] or category_name

    if company_id is None:
        costs = conn.execute(
            "SELECT label, value_type, value FROM product_cost_items WHERE product_id = ?",
            (product_id,),
        ).fetchall()
    else:
        costs = conn.execute(
            "SELECT label, value_type, value FROM product_cost_items WHERE product_id = ? AND company_id = ?",
            (product_id, int(company_id)),
        ).fetchall()

    base_cost = float(product["cost_price"])
    fixed_costs = 0.0
    percent_costs = 0.0
    for c in costs:
        if c["value_type"] == "fixed":
            fixed_costs += float(c["value"])
        else:
            percent_costs += float(c["value"])

    total_unit_cost = base_cost + fixed_costs
    if percent_costs >= 100:
        suggested_price = None
    else:
        margin = float(product["desired_margin_percent"]) / 100.0
        denominator = 1 - (percent_costs / 100.0) - margin
        suggested_price = total_unit_cost / denominator if denominator > 0 else None

    suggested_price = round(suggested_price, 2) if suggested_price else 0.0
    estimated_profit = round(
        suggested_price - (suggested_price * (percent_costs / 100.0)) - total_unit_cost,
        2,
    ) if suggested_price else 0.0

    return {
        "id": product["id"],
        "sku": product["sku"],
        "barcode": product["barcode"] if "barcode" in product.keys() else None,
        "name": product["name"],
        "category": category_name,
        "category_id": category_id,
        "brand": product["brand"] if "brand" in product.keys() else "",
        "unit": product["unit"] if "unit" in product.keys() else "un",
        "description": product["description"],
        "created_at": product["created_at"],
        "cost_price": round(base_cost, 2),
        "desired_margin_percent": round(float(product["desired_margin_percent"]), 2),
        "stock_qty": int(product["stock_qty"]),
        "is_active": int(product["is_active"] or 0) == 1,
        "fixed_costs": round(fixed_costs, 2),
        "percent_costs": round(percent_costs, 2),
        "total_unit_cost": round(total_unit_cost, 2),
        "suggested_price": suggested_price,
        "estimated_profit_per_unit": estimated_profit,
        "cost_items": [
            {
                "label": c["label"],
                "value_type": c["value_type"],
                "value": float(c["value"]),
            }
            for c in costs
        ],
    }


def parse_product_id(path):
    parts = path.strip("/").split("/")
    if len(parts) >= 3 and parts[0] == "api" and parts[1] == "products":
        try:
            return int(parts[2])
        except (TypeError, ValueError):
            return None
    return None


def parse_sale_id(path):
    parts = path.strip("/").split("/")
    if len(parts) >= 3 and parts[0] == "api" and parts[1] == "sales":
        try:
            return int(parts[2])
        except (TypeError, ValueError):
            return None
    return None


def parse_movement_id(path):
    parts = path.strip("/").split("/")
    if len(parts) >= 4 and parts[0] == "api" and parts[1] == "inventory" and parts[2] == "movements":
        try:
            return int(parts[3])
        except (TypeError, ValueError):
            return None
    return None


def parse_user_id(path):
    parts = path.strip("/").split("/")
    if len(parts) >= 3 and parts[0] == "api" and parts[1] == "users":
        try:
            return int(parts[2])
        except (TypeError, ValueError):
            return None
    return None


def parse_finance_entry_id(path):
    parts = path.strip("/").split("/")
    if len(parts) >= 4 and parts[0] == "api" and parts[1] == "finance" and parts[2] == "entries":
        try:
            return int(parts[3])
        except (TypeError, ValueError):
            return None
    return None


def parse_supplier_id(path):
    parts = path.strip("/").split("/")
    if len(parts) >= 3 and parts[0] == "api" and parts[1] == "suppliers":
        try:
            return int(parts[2])
        except (TypeError, ValueError):
            return None
    return None


def parse_purchase_id(path):
    parts = path.strip("/").split("/")
    if len(parts) >= 3 and parts[0] == "api" and parts[1] == "purchases":
        try:
            return int(parts[2])
        except (TypeError, ValueError):
            return None
    return None


def parse_category_id(path):
    parts = path.strip("/").split("/")
    if len(parts) >= 3 and parts[0] == "api" and parts[1] == "categories":
        try:
            return int(parts[2])
        except (TypeError, ValueError):
            return None
    return None


def parse_dashboard_period(parsed_url):
    query = parse_qs(parsed_url.query or "")
    today = datetime.utcnow().date()
    default_start = today - timedelta(days=29)

    start_str = (query.get("start", [default_start.strftime("%Y-%m-%d")])[0] or "").strip()
    end_str = (query.get("end", [today.strftime("%Y-%m-%d")])[0] or "").strip()

    try:
        start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
    except ValueError:
        return None

    if start_date > end_date:
        return None

    start_iso = f"{start_date.strftime('%Y-%m-%d')}T00:00:00Z"
    end_iso_exclusive = f"{(end_date + timedelta(days=1)).strftime('%Y-%m-%d')}T00:00:00Z"
    days_count = (end_date - start_date).days + 1

    return {
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "start_iso": start_iso,
        "end_iso_exclusive": end_iso_exclusive,
        "days_count": days_count,
    }


def parse_optional_period(parsed_url):
    query = parse_qs(parsed_url.query or "")
    has_start = bool((query.get("start", [""])[0] or "").strip())
    has_end = bool((query.get("end", [""])[0] or "").strip())
    if not has_start and not has_end:
        return None
    return parse_dashboard_period(parsed_url)


def parse_client_timestamp(raw_value):
    if raw_value is None:
        return utc_now_iso()

    value = str(raw_value).strip()
    if not value:
        return utc_now_iso()

    normalized = value.replace(" ", "T")
    if normalized.endswith("Z"):
        normalized = normalized[:-1]

    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            parsed = datetime.strptime(normalized, fmt)
            return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            continue

    return None


def parse_positive_int(value, field_label):
    if isinstance(value, bool):
        raise ValueError(f"{field_label} deve ser um número inteiro maior que zero.")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_label} deve ser um número inteiro maior que zero.")
    if not number.is_integer():
        raise ValueError(f"{field_label} deve ser um número inteiro maior que zero.")
    parsed = int(number)
    if parsed <= 0:
        raise ValueError(f"{field_label} deve ser um número inteiro maior que zero.")
    return parsed


def parse_boolish(value, default=False):
    if value is None:
        return bool(default)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value or "").strip().lower()
    if text in ("1", "true", "t", "yes", "y", "sim", "s", "on"):
        return True
    if text in ("0", "false", "f", "no", "n", "nao", "não", "off", ""):
        return False
    return bool(default)


def normalize_avatar_data(raw_value):
    if raw_value in (None, ""):
        return None
    avatar = str(raw_value).strip()
    if not avatar:
        return None
    if not avatar.startswith("data:image/") or ";base64," not in avatar:
        raise ValueError("Imagem de avatar inválida.")
    if len(avatar) > 1_500_000:
        raise ValueError("Imagem de avatar muito grande. Use um arquivo menor.")
    return avatar


def sale_cost_snapshot(conn, product_id, qty, unit_price, company_id=None):
    if company_id is None:
        product = conn.execute(
            "SELECT id, name, cost_price, stock_qty, is_active FROM products WHERE id = ?",
            (product_id,),
        ).fetchone()
    else:
        product = conn.execute(
            "SELECT id, name, cost_price, stock_qty, is_active FROM products WHERE id = ? AND company_id = ?",
            (product_id, int(company_id)),
        ).fetchone()
    if not product:
        return None

    if company_id is None:
        costs = conn.execute(
            """
            SELECT
              COALESCE(SUM(CASE WHEN value_type='fixed' THEN value ELSE 0 END),0) as fixed_costs,
              COALESCE(SUM(CASE WHEN value_type='percent' THEN value ELSE 0 END),0) as percent_costs
            FROM product_cost_items
            WHERE product_id = ?
            """,
            (product_id,),
        ).fetchone()
    else:
        costs = conn.execute(
            """
            SELECT
              COALESCE(SUM(CASE WHEN value_type='fixed' THEN value ELSE 0 END),0) as fixed_costs,
              COALESCE(SUM(CASE WHEN value_type='percent' THEN value ELSE 0 END),0) as percent_costs
            FROM product_cost_items
            WHERE product_id = ? AND company_id = ?
            """,
            (product_id, int(company_id)),
        ).fetchone()

    base_cost = float(product["cost_price"] or 0)
    fixed_costs = float(costs["fixed_costs"] or 0)
    percent_costs = float(costs["percent_costs"] or 0)
    unit_cost = base_cost + fixed_costs
    total = round(float(qty) * float(unit_price), 2)
    cogs_total = round(float(qty) * unit_cost, 2)
    taxes_total = round(total * (percent_costs / 100.0), 2)
    extra_expenses_total = 0.0
    gross_profit = round(total - cogs_total, 2)
    net_profit = round(total - cogs_total - taxes_total - extra_expenses_total, 2)

    return {
        "product": product,
        "total": total,
        "cogs_total": cogs_total,
        "taxes_total": taxes_total,
        "extra_expenses_total": extra_expenses_total,
        "gross_profit": gross_profit,
        "net_profit": net_profit,
    }


def remove_sale_side_effects(conn, sale_row, company_id=None):
    sale_id = int(sale_row["id"])
    product_id = int(sale_row["product_id"])
    qty = int(sale_row["qty"])
    if company_id is None:
        conn.execute("UPDATE products SET stock_qty = stock_qty + ? WHERE id = ?", (qty, product_id))
        conn.execute("DELETE FROM inventory_movements WHERE sale_id = ?", (sale_id,))
        conn.execute("DELETE FROM financial_entries WHERE sale_id = ?", (sale_id,))
    else:
        company = int(company_id)
        conn.execute("UPDATE products SET stock_qty = stock_qty + ? WHERE id = ? AND company_id = ?", (qty, product_id, company))
        conn.execute("DELETE FROM inventory_movements WHERE sale_id = ? AND company_id = ?", (sale_id, company))
        conn.execute("DELETE FROM financial_entries WHERE sale_id = ? AND company_id = ?", (sale_id, company))


class AppHandler(BaseHTTPRequestHandler):
    def send_json(self, data, status=200):
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def serve_file(self, filename, content_type="text/plain; charset=utf-8"):
        filepath = os.path.join(STATIC_DIR, filename)
        if not os.path.exists(filepath):
            self.send_error(404)
            return
        with open(filepath, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/":
            self.send_response(307)
            self.send_header("Location", "/index.html")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        if path == "/index.html":
            return self.serve_file("index.html", "text/html; charset=utf-8")
        if path == "/app.js":
            return self.serve_file("app.js", "application/javascript; charset=utf-8")
        if path == "/styles.css":
            return self.serve_file("styles.css", "text/css; charset=utf-8")

        conn = db_connection()
        try:
            if path == "/api/me":
                user = require_auth(self, conn)
                if not user:
                    return
                return self.send_json({
                    "id": user["id"],
                    "name": user["name"],
                    "email": user["email"],
                    "role": user["role"],
                    "is_active": int(user["is_active"] or 0) == 1,
                    "module_permissions": user_permissions(user),
                    "avatar_url": user["avatar_url"] if "avatar_url" in user.keys() else None,
                    "company_id": int(user["company_id"] or 0),
                    "company_name": user["company_name"] if "company_name" in user.keys() else None,
                    "company_slug": user["company_slug"] if "company_slug" in user.keys() else None,
                })

            if path == "/api/users":
                user = require_auth(self, conn)
                if not user:
                    return
                if not require_module_permission(self, user, "users"):
                    return
                if user["role"] != "master":
                    return self.send_json({"error": "Somente o master pode listar usuários"}, status=403)
                company_id = company_id_from_user(user)
                users = conn.execute(
                    "SELECT id, name, email, role, is_active, module_permissions, avatar_url, created_at FROM users WHERE company_id = ? ORDER BY id DESC",
                    (company_id,),
                ).fetchall()
                return self.send_json([
                    {
                        "id": row["id"],
                        "name": row["name"],
                        "email": row["email"],
                        "role": row["role"],
                        "is_active": row["is_active"],
                        "module_permissions": user_permissions(row),
                        "avatar_url": row["avatar_url"] if "avatar_url" in row.keys() else None,
                        "created_at": row["created_at"],
                    }
                    for row in users
                ])

            if path == "/api/products":
                user = require_auth(self, conn)
                if not user:
                    return
                if not require_module_permission(self, user, "products"):
                    return
                company_id = company_id_from_user(user)
                rows = conn.execute("SELECT id FROM products WHERE company_id = ? ORDER BY id DESC", (company_id,)).fetchall()
                products = [product_analysis(conn, row["id"], company_id) for row in rows]
                return self.send_json(products)

            if path == "/api/sales":
                user = require_auth(self, conn)
                if not user:
                    return
                if not require_module_permission(self, user, "sales"):
                    return
                company_id = company_id_from_user(user)

                period = parse_optional_period(parsed)
                if period is None and ("start=" in parsed.query or "end=" in parsed.query):
                    return self.send_json({"error": "Período inválido. Use formato YYYY-MM-DD."}, status=400)

                if period:
                    rows = conn.execute(
                        """
                        SELECT s.id, s.qty, s.unit_price, s.total,
                               s.cogs_total, s.taxes_total, s.extra_expenses_total,
                               s.gross_profit, s.net_profit, s.product_id,
                               s.created_at, p.name as product_name, p.sku, p.barcode, p.category
                        FROM sales s
                        JOIN products p ON p.id = s.product_id
                        WHERE s.company_id = ? AND p.company_id = ? AND s.created_at >= ? AND s.created_at < ?
                        ORDER BY s.created_at DESC, s.id DESC
                        LIMIT 300
                        """,
                        (company_id, company_id, period["start_iso"], period["end_iso_exclusive"]),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT s.id, s.qty, s.unit_price, s.total,
                               s.cogs_total, s.taxes_total, s.extra_expenses_total,
                               s.gross_profit, s.net_profit, s.product_id,
                               s.created_at, p.name as product_name, p.sku, p.barcode, p.category
                        FROM sales s
                        JOIN products p ON p.id = s.product_id
                        WHERE s.company_id = ? AND p.company_id = ?
                        ORDER BY s.created_at DESC, s.id DESC
                        LIMIT 300
                        """,
                        (company_id, company_id),
                    ).fetchall()
                return self.send_json([{k: r[k] for k in r.keys()} for r in rows])

            if path == "/api/inventory/movements":
                user = require_auth(self, conn)
                if not user:
                    return
                if not require_module_permission(self, user, "inventory"):
                    return
                company_id = company_id_from_user(user)
                rows = conn.execute(
                    """
                    SELECT m.id, m.product_id, p.name as product_name, p.sku, p.barcode, p.category, p.description,
                           p.cost_price, p.stock_qty, m.movement_type, m.qty, m.note, m.sale_id, m.purchase_id, m.created_at
                    FROM inventory_movements m
                    JOIN products p ON p.id = m.product_id
                    WHERE m.company_id = ? AND p.company_id = ?
                    ORDER BY m.id DESC LIMIT 100
                    """,
                    (company_id, company_id),
                ).fetchall()
                return self.send_json([{k: r[k] for k in r.keys()} for r in rows])

            if path == "/api/categories":
                user = require_auth(self, conn)
                if not user:
                    return
                if not require_module_permission(self, user, "products"):
                    return
                company_id = company_id_from_user(user)
                rows = conn.execute(
                    """
                    SELECT c.id, c.name, c.description, c.is_active, c.created_at,
                           COUNT(p.id) AS products_count
                    FROM categories c
                    LEFT JOIN products p ON p.category_id = c.id AND p.company_id = c.company_id
                    WHERE c.company_id = ?
                    GROUP BY c.id
                    ORDER BY c.name COLLATE NOCASE ASC
                    """,
                    (company_id,),
                ).fetchall()
                return self.send_json([{k: r[k] for k in r.keys()} for r in rows])

            if path == "/api/finance/entries":
                user = require_auth(self, conn)
                if not user:
                    return
                if not require_module_permission(self, user, "finance"):
                    return
                company_id = company_id_from_user(user)
                period = parse_optional_period(parsed)
                if period is None and ("start=" in parsed.query or "end=" in parsed.query):
                    return self.send_json({"error": "Período inválido. Use formato YYYY-MM-DD."}, status=400)

                if period:
                    rows = conn.execute(
                        """
                        SELECT id, entry_type, category, description, amount,
                               payment_method, payment_terms, notes, payment_status, origin,
                               sale_id, purchase_id, created_at
                        FROM financial_entries
                        WHERE company_id = ? AND created_at >= ? AND created_at < ?
                        ORDER BY created_at DESC, id DESC
                        LIMIT 300
                        """,
                        (company_id, period["start_iso"], period["end_iso_exclusive"]),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT id, entry_type, category, description, amount,
                               payment_method, payment_terms, notes, payment_status, origin,
                               sale_id, purchase_id, created_at
                        FROM financial_entries
                        WHERE company_id = ?
                        ORDER BY created_at DESC, id DESC
                        LIMIT 300
                        """,
                        (company_id,),
                    ).fetchall()
                return self.send_json([{k: r[k] for k in r.keys()} for r in rows])

            if path == "/api/suppliers":
                user = require_auth(self, conn)
                if not user:
                    return
                if not require_module_permission(self, user, "purchases"):
                    return
                company_id = company_id_from_user(user)
                rows = conn.execute(
                    """
                    SELECT id, name, contact, phone, email, notes, is_active, created_at
                    FROM suppliers
                    WHERE company_id = ?
                    ORDER BY id DESC
                    """,
                    (company_id,),
                ).fetchall()
                return self.send_json([{k: r[k] for k in r.keys()} for r in rows])

            if path == "/api/purchases":
                user = require_auth(self, conn)
                if not user:
                    return
                if not require_module_permission(self, user, "purchases"):
                    return
                company_id = company_id_from_user(user)
                rows = conn.execute(
                    """
                    SELECT p.id, p.supplier_id, s.name as supplier_name, p.purchase_type, p.payment_method,
                           p.payment_terms, p.notes, p.total_amount, p.status, p.created_at
                    FROM purchases p
                    LEFT JOIN suppliers s ON s.id = p.supplier_id AND s.company_id = p.company_id
                    WHERE p.company_id = ?
                    ORDER BY p.created_at DESC, p.id DESC
                    LIMIT 300
                    """,
                    (company_id,),
                ).fetchall()
                data = []
                for row in rows:
                    items = conn.execute(
                        """
                        SELECT i.id, i.product_id, pr.name as product_name, i.label, i.qty, i.unit_cost, i.total_cost, i.affects_stock
                        FROM purchase_items i
                        LEFT JOIN products pr ON pr.id = i.product_id AND pr.company_id = i.company_id
                        WHERE i.purchase_id = ? AND i.company_id = ?
                        ORDER BY i.id ASC
                        """,
                        (row["id"], company_id),
                    ).fetchall()
                    payload = {k: row[k] for k in row.keys()}
                    payload["items"] = [{k: i[k] for k in i.keys()} for i in items]
                    data.append(payload)
                return self.send_json(data)

            if path == "/api/cost-calculations":
                user = require_auth(self, conn)
                if not user:
                    return
                if not require_module_permission(self, user, "costs"):
                    return
                company_id = company_id_from_user(user)
                rows = conn.execute(
                    """
                    SELECT id, product_id, product_name, cost_amount, shipping_amount, other_costs_amount,
                           tax_percent, commission_percent, margin_percent,
                           tax_amount, commission_amount, profit_amount, sale_price, created_at
                    FROM cost_calculations
                    WHERE company_id = ?
                    ORDER BY created_at DESC, id DESC
                    LIMIT 300
                    """,
                    (company_id,),
                ).fetchall()
                return self.send_json([{k: r[k] for k in r.keys()} for r in rows])

            if path == "/api/dashboard":
                user = require_auth(self, conn)
                if not user:
                    return
                if not require_module_permission(self, user, "dashboard"):
                    return
                company_id = company_id_from_user(user)

                period = parse_dashboard_period(parsed)
                if not period:
                    return self.send_json({"error": "Período inválido. Use formato YYYY-MM-DD."}, status=400)

                start_iso = period["start_iso"]
                end_iso = period["end_iso_exclusive"]
                days_count = int(period["days_count"])
                if days_count <= 31:
                    grouping = "day"
                    grouping_label = "Agrupado por dia"
                elif days_count <= 90:
                    grouping = "week"
                    grouping_label = "Agrupado por semana"
                else:
                    grouping = "month"
                    grouping_label = "Agrupado por mes"

                total_products = conn.execute(
                    "SELECT COUNT(*) c FROM products WHERE is_active = 1 AND company_id = ?",
                    (company_id,),
                ).fetchone()["c"]
                stock_snapshot = conn.execute(
                    """
                    SELECT COALESCE(SUM(stock_qty),0) as total_units,
                           COALESCE(SUM(stock_qty * cost_price),0) as stock_cost_value
                    FROM products
                    WHERE is_active = 1 AND company_id = ?
                    """
                    ,
                    (company_id,),
                ).fetchone()
                total_stock_units = int(stock_snapshot["total_units"] or 0)
                stock_cost_value = float(stock_snapshot["stock_cost_value"] or 0)

                product_cost_rows = conn.execute(
                    """
                    SELECT p.id as product_id,
                           p.name as product_name,
                           p.cost_price as cost_price,
                           COALESCE(SUM(CASE WHEN c.value_type='fixed' THEN c.value ELSE 0 END),0) as fixed_costs,
                           COALESCE(SUM(CASE WHEN c.value_type='percent' THEN c.value ELSE 0 END),0) as percent_costs
                    FROM products p
                    LEFT JOIN product_cost_items c ON c.product_id = p.id AND c.company_id = p.company_id
                    WHERE p.company_id = ?
                    GROUP BY p.id
                    """,
                    (company_id,),
                ).fetchall()
                product_cost_map = {
                    int(r["product_id"]): {
                        "name": r["product_name"] or "Produto sem nome",
                        "cost_price": float(r["cost_price"] or 0),
                        "fixed_costs": float(r["fixed_costs"] or 0),
                        "percent_costs": float(r["percent_costs"] or 0),
                    }
                    for r in product_cost_rows
                }

                sales_rows = conn.execute(
                    """
                    SELECT product_id, qty, total, created_at,
                           cogs_total, taxes_total, net_profit
                    FROM sales
                    WHERE company_id = ? AND created_at >= ? AND created_at < ?
                    """,
                    (company_id, start_iso, end_iso),
                ).fetchall()
                expense_rows = conn.execute(
                    """
                    SELECT amount, created_at
                    FROM financial_entries
                    WHERE company_id = ? AND entry_type='expense' AND created_at >= ? AND created_at < ?
                    """,
                    (company_id, start_iso, end_iso),
                ).fetchall()
                income_rows = conn.execute(
                    """
                    SELECT amount, created_at
                    FROM financial_entries
                    WHERE company_id = ? AND entry_type='income' AND created_at >= ? AND created_at < ?
                    """,
                    (company_id, start_iso, end_iso),
                ).fetchall()

                gross_revenue = 0.0
                cogs_total = 0.0
                taxes_total = 0.0
                product_performance = {}
                for s in sales_rows:
                    qty = int(s["qty"] or 0)
                    total = float(s["total"] or 0)
                    product_cost = product_cost_map.get(int(s["product_id"]), {"cost_price": 0.0, "fixed_costs": 0.0, "percent_costs": 0.0})
                    unit_cost = product_cost["cost_price"] + product_cost["fixed_costs"]
                    line_cogs_fallback = qty * unit_cost
                    line_taxes_fallback = total * (product_cost["percent_costs"] / 100.0)

                    line_cogs_stored = float(s["cogs_total"] or 0)
                    line_taxes_stored = float(s["taxes_total"] or 0)
                    line_net_stored = float(s["net_profit"] or 0)

                    line_cogs = line_cogs_stored
                    line_taxes = line_taxes_stored
                    if abs(line_cogs_stored) < 0.0001 and abs(line_taxes_stored) < 0.0001 and (line_cogs_fallback > 0 or line_taxes_fallback > 0):
                        line_cogs = line_cogs_fallback
                        line_taxes = line_taxes_fallback

                    line_profit = line_net_stored
                    if abs(line_net_stored) < 0.0001 and (line_cogs > 0 or line_taxes > 0):
                        line_profit = total - line_cogs - line_taxes
                    gross_revenue += total
                    cogs_total += line_cogs
                    taxes_total += line_taxes

                    product_id = int(s["product_id"])
                    if product_id not in product_performance:
                        product_performance[product_id] = {
                            "name": product_cost.get("name", "Produto sem nome"),
                            "units": 0,
                            "revenue": 0.0,
                            "profit": 0.0,
                        }
                    product_performance[product_id]["units"] += qty
                    product_performance[product_id]["revenue"] += total
                    product_performance[product_id]["profit"] += line_profit

                expense_total = float(sum(float(r["amount"] or 0) for r in expense_rows))
                income_total = float(sum(float(r["amount"] or 0) for r in income_rows))

                gross_result = gross_revenue
                gross_profit = gross_revenue - cogs_total
                net_result = gross_revenue - cogs_total - taxes_total - expense_total
                gross_margin_percent = (gross_profit / gross_revenue * 100.0) if gross_revenue > 0 else 0.0
                net_margin_percent = (net_result / gross_revenue * 100.0) if gross_revenue > 0 else 0.0

                start_date = datetime.strptime(period["start_date"], "%Y-%m-%d").date()
                end_date = datetime.strptime(period["end_date"], "%Y-%m-%d").date()
                bucket_order = []
                bucket_labels = {}

                if grouping == "day":
                    cursor = start_date
                    while cursor <= end_date:
                        key = cursor.strftime("%Y-%m-%d")
                        bucket_order.append(key)
                        bucket_labels[key] = cursor.strftime("%d/%m")
                        cursor += timedelta(days=1)
                elif grouping == "week":
                    cursor = start_date - timedelta(days=start_date.weekday())
                    seen_weeks = set()
                    while cursor <= end_date:
                        iso_year, iso_week, _ = cursor.isocalendar()
                        key = f"{iso_year}-W{iso_week:02d}"
                        if key not in seen_weeks:
                            seen_weeks.add(key)
                            bucket_order.append(key)
                            bucket_labels[key] = f"Sem {iso_week:02d}/{str(iso_year)[2:]}"
                        cursor += timedelta(days=7)
                else:
                    cursor = start_date.replace(day=1)
                    while cursor <= end_date:
                        key = cursor.strftime("%Y-%m")
                        bucket_order.append(key)
                        bucket_labels[key] = cursor.strftime("%m/%Y")
                        if cursor.month == 12:
                            cursor = cursor.replace(year=cursor.year + 1, month=1, day=1)
                        else:
                            cursor = cursor.replace(month=cursor.month + 1, day=1)

                income_map = {key: 0.0 for key in bucket_order}
                expense_map = {key: 0.0 for key in bucket_order}

                def resolve_bucket_key(created_at_value):
                    if not created_at_value:
                        return None
                    try:
                        date_obj = datetime.strptime(str(created_at_value)[:10], "%Y-%m-%d").date()
                    except ValueError:
                        return None
                    if grouping == "day":
                        return date_obj.strftime("%Y-%m-%d")
                    if grouping == "week":
                        iso_year, iso_week, _ = date_obj.isocalendar()
                        return f"{iso_year}-W{iso_week:02d}"
                    return date_obj.strftime("%Y-%m")

                for inc in income_rows:
                    bucket = resolve_bucket_key(inc["created_at"])
                    if bucket in income_map:
                        income_map[bucket] += float(inc["amount"] or 0)

                for exp in expense_rows:
                    bucket = resolve_bucket_key(exp["created_at"])
                    if bucket in expense_map:
                        expense_map[bucket] += float(exp["amount"] or 0)

                monthly = []
                for key in bucket_order:
                    incomes_value = float(income_map.get(key, 0.0))
                    expenses_value = float(expense_map.get(key, 0.0))
                    monthly.append({
                        "month": key,
                        "bucket": key,
                        "label": bucket_labels.get(key, key),
                        "incomes": round(incomes_value, 2),
                        "expenses": round(expenses_value, 2),
                        "net": round(incomes_value - expenses_value, 2),
                    })

                best_products = sorted(
                    product_performance.values(),
                    key=lambda item: item["revenue"],
                    reverse=True,
                )[:5]
                has_deductions = (taxes_total + expense_total) > 0.0001
                gross_equals_net = abs(gross_result - net_result) < 0.0001

                return self.send_json({
                    "period": {
                        "start": period["start_date"],
                        "end": period["end_date"],
                    },
                    "kpis": {
                        "total_products": int(total_products),
                        "total_stock_units": total_stock_units,
                        "stock_value": round(stock_cost_value, 2),
                        "stock_cost_value": round(stock_cost_value, 2),
                        "gross_result": round(gross_result, 2),
                        "gross_revenue": round(gross_revenue, 2),
                        "sales_total": round(gross_revenue, 2),
                        "cogs_total": round(cogs_total, 2),
                        "taxes_total": round(taxes_total, 2),
                        "expense_total": round(expense_total, 2),
                        "deductions_total": round(taxes_total + expense_total, 2),
                        "gross_profit": round(gross_profit, 2),
                        "net_result": round(net_result, 2),
                        "gross_margin_percent": round(gross_margin_percent, 2),
                        "net_margin_percent": round(net_margin_percent, 2),
                        "income_total": round(income_total, 2),
                        "has_deductions": has_deductions,
                        "gross_equals_net": gross_equals_net,
                    },
                    "grouping": grouping,
                    "grouping_label": grouping_label,
                    "monthly": monthly,
                    "best_products": [
                        {
                            "name": r["name"],
                            "units": int(r["units"] or 0),
                            "revenue": round(float(r["revenue"] or 0), 2),
                            "profit": round(float(r["profit"] or 0), 2),
                        }
                        for r in best_products
                    ],
                })

            self.send_json({"error": "Rota não encontrada"}, status=404)
        finally:
            conn.close()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        conn = db_connection()
        try:
            if path == "/api/signup":
                body = parse_json_body(self)
                company_name = str(body.get("company_name") or "").strip()
                trade_name = str(body.get("trade_name") or "").strip()
                company_email = str(body.get("company_email") or "").strip().lower()
                company_phone = str(body.get("company_phone") or "").strip()
                company_document = str(body.get("company_document") or "").strip()
                owner_name = str(body.get("owner_name") or "").strip()
                owner_email = str(body.get("owner_email") or "").strip().lower()
                owner_password = str(body.get("owner_password") or "")
                if not company_name:
                    return self.send_json({"error": "Nome da empresa é obrigatório."}, status=400)
                if not owner_name:
                    return self.send_json({"error": "Nome do usuário master é obrigatório."}, status=400)
                if not owner_email or "@" not in owner_email:
                    return self.send_json({"error": "Email do usuário master inválido."}, status=400)
                if len(owner_password) < 4:
                    return self.send_json({"error": "Senha deve ter pelo menos 4 caracteres."}, status=400)
                if company_email and "@" not in company_email:
                    return self.send_json({"error": "Email principal da empresa inválido."}, status=400)
                existing_user = conn.execute("SELECT id FROM users WHERE LOWER(email) = LOWER(?)", (owner_email,)).fetchone()
                if existing_user:
                    return self.send_json({"error": "Já existe um usuário com este email."}, status=400)
                base_slug = slugify(str(body.get("company_slug") or company_name))
                company_slug = base_slug
                suffix = 2
                while conn.execute("SELECT 1 FROM companies WHERE slug = ?", (company_slug,)).fetchone():
                    company_slug = f"{base_slug}-{suffix}"
                    suffix += 1
                try:
                    avatar_url = normalize_avatar_data(body.get("owner_avatar_url"))
                except ValueError as e:
                    return self.send_json({"error": str(e)}, status=400)
                company_cur = conn.cursor()
                company_cur.execute(
                    """
                    INSERT INTO companies (name, slug, trade_name, email, phone, document, is_active, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, 1, ?)
                    """,
                    (
                        company_name,
                        company_slug,
                        trade_name or company_name,
                        company_email or owner_email,
                        company_phone,
                        company_document,
                        utc_now_iso(),
                    ),
                )
                company_id = company_cur.lastrowid
                permissions_json = permissions_json_for_role("master", list(MODULE_KEYS))
                user_cur = conn.cursor()
                user_cur.execute(
                    """
                    INSERT INTO users (company_id, name, email, password_hash, role, module_permissions, avatar_url, created_at)
                    VALUES (?, ?, ?, ?, 'master', ?, ?, ?)
                    """,
                    (
                        company_id,
                        owner_name,
                        owner_email,
                        hash_password(owner_password),
                        permissions_json,
                        avatar_url,
                        utc_now_iso(),
                    ),
                )
                user_id = user_cur.lastrowid
                token = secrets.token_hex(24)
                expires = (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
                conn.execute(
                    "INSERT INTO sessions (token, company_id, user_id, expires_at) VALUES (?,?,?,?)",
                    (token, company_id, user_id, expires),
                )
                log_audit(
                    conn,
                    "users",
                    "user",
                    user_id,
                    "create_master_on_signup",
                    user_id,
                    {"company_name": company_name, "company_slug": company_slug},
                    company_id=company_id,
                )
                conn.commit()
                return self.send_json(
                    {
                        "token": token,
                        "user": {
                            "id": user_id,
                            "name": owner_name,
                            "email": owner_email,
                            "role": "master",
                            "is_active": True,
                            "module_permissions": list(MODULE_KEYS),
                            "avatar_url": avatar_url,
                            "company_id": company_id,
                            "company_name": company_name,
                            "company_slug": company_slug,
                        },
                    }
                )

            if path == "/api/login":
                body = parse_json_body(self)
                email = (body.get("email") or "").strip().lower()
                password = body.get("password") or ""
                row = conn.execute(
                    """
                    SELECT u.*, c.name AS company_name, c.slug AS company_slug
                    FROM users u
                    JOIN companies c ON c.id = u.company_id
                    WHERE u.email = ? AND u.password_hash = ? AND u.is_active = 1 AND c.is_active = 1
                    """,
                    (email, hash_password(password)),
                ).fetchone()
                if not row:
                    return self.send_json({"error": "Credenciais inválidas"}, status=401)

                company_id = int(row["company_id"] or 0)
                if company_id <= 0:
                    return self.send_json({"error": "Usuário sem empresa vinculada."}, status=400)
                token = secrets.token_hex(24)
                expires = (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
                conn.execute(
                    "INSERT INTO sessions (token, company_id, user_id, expires_at) VALUES (?,?,?,?)",
                    (token, company_id, row["id"], expires),
                )
                conn.commit()
                return self.send_json({
                    "token": token,
                    "user": {
                        "id": row["id"],
                        "name": row["name"],
                        "email": row["email"],
                        "role": row["role"],
                        "is_active": int(row["is_active"] or 0) == 1,
                        "module_permissions": user_permissions(row),
                        "avatar_url": row["avatar_url"] if "avatar_url" in row.keys() else None,
                        "company_id": company_id,
                        "company_name": row["company_name"] if "company_name" in row.keys() else None,
                        "company_slug": row["company_slug"] if "company_slug" in row.keys() else None,
                    },
                })

            user = require_auth(self, conn)
            if not user:
                return
            module_key = module_key_for_path(path)
            if module_key and not require_module_permission(self, user, module_key):
                return
            if path.startswith("/api/") and module_key is None:
                return self.send_json({"error": "Rota de API sem módulo mapeado."}, status=403)
            company_id = company_id_from_user(user)
            if company_id <= 0:
                return self.send_json({"error": "Usuário sem empresa vinculada."}, status=400)
            company_id = company_id_from_user(user)
            if company_id <= 0:
                return self.send_json({"error": "Usuário sem empresa vinculada."}, status=400)

            if path == "/api/users":
                if user["role"] != "master":
                    return self.send_json({"error": "Somente master pode criar usuários"}, status=403)
                body = parse_json_body(self)
                role = str(body.get("role", "member")).strip().lower()
                if role not in ("master", "admin", "member"):
                    return self.send_json({"error": "Role inválida"}, status=400)
                name = (body.get("name") or "").strip()
                email = (body.get("email") or "").strip().lower()
                password = body.get("password") or ""
                if not name or not email or "@" not in email:
                    return self.send_json({"error": "Nome e email válido são obrigatórios."}, status=400)
                if len(password) < 4:
                    return self.send_json({"error": "Senha deve ter pelo menos 4 caracteres."}, status=400)
                email_exists = conn.execute("SELECT id FROM users WHERE LOWER(email) = LOWER(?)", (email,)).fetchone()
                if email_exists:
                    return self.send_json({"error": "Já existe um usuário com este email."}, status=400)
                try:
                    avatar_url = normalize_avatar_data(body.get("avatar_url"))
                except ValueError as e:
                    return self.send_json({"error": str(e)}, status=400)
                permissions_json = permissions_json_for_role(role, body.get("module_permissions"))
                conn.execute(
                    "INSERT INTO users (company_id, name, email, password_hash, role, module_permissions, avatar_url, created_at) VALUES (?,?,?,?,?,?,?,?)",
                    (
                        company_id,
                        name,
                        email,
                        hash_password(password),
                        role,
                        permissions_json,
                        avatar_url,
                        utc_now_iso(),
                    ),
                )
                created_user_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
                log_audit(
                    conn,
                    "users",
                    "user",
                    created_user_id,
                    "create",
                    user["id"],
                    {"name": name, "email": email, "role": role},
                )
                conn.commit()
                return self.send_json({"ok": True, "user_id": created_user_id})

            if path == "/api/products":
                body = parse_json_body(self)
                name = body.get("name", "").strip()
                try:
                    cost_price = float(body.get("cost_price") or 0)
                    desired_margin = float(body.get("desired_margin_percent") or 30)
                except (TypeError, ValueError):
                    return self.send_json({"error": "Valores numéricos inválidos no produto."}, status=400)
                if not name:
                    return self.send_json({"error": "Nome do produto é obrigatório"}, status=400)
                if cost_price < 0 or desired_margin < 0:
                    return self.send_json({"error": "Valores de produto inválidos"}, status=400)
                sku = str(body.get("sku", "") or "").strip()
                barcode = str(body.get("barcode", "") or "").strip()
                if sku:
                    existing_sku = conn.execute(
                        "SELECT id FROM products WHERE company_id = ? AND LOWER(TRIM(COALESCE(sku,''))) = LOWER(TRIM(?))",
                        (company_id, sku),
                    ).fetchone()
                    if existing_sku:
                        return self.send_json({"error": "SKU já cadastrado em outro produto."}, status=400)
                if barcode:
                    existing_barcode = conn.execute(
                        "SELECT id FROM products WHERE company_id = ? AND LOWER(TRIM(COALESCE(barcode,''))) = LOWER(TRIM(?))",
                        (company_id, barcode),
                    ).fetchone()
                    if existing_barcode:
                        return self.send_json({"error": "Código de barras já cadastrado em outro produto."}, status=400)

                category_id = body.get("category_id")
                category_id_value = None
                category_name = ""
                if category_id not in (None, "", 0, "0"):
                    try:
                        category_id_value = int(category_id)
                    except (TypeError, ValueError):
                        return self.send_json({"error": "Categoria inválida."}, status=400)
                    category_row = conn.execute(
                        "SELECT id, name, is_active FROM categories WHERE id = ? AND company_id = ?",
                        (category_id_value, company_id),
                    ).fetchone()
                    if not category_row:
                        return self.send_json({"error": "Categoria não encontrada."}, status=404)
                    if int(category_row["is_active"] or 0) != 1:
                        return self.send_json({"error": "Categoria inativa não pode ser usada em novos produtos."}, status=400)
                    category_name = category_row["name"] or ""

                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO products (company_id, sku, barcode, name, category, category_id, brand, unit, description, cost_price, desired_margin_percent, stock_qty, is_active, created_by, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)
                    """,
                    (
                        company_id,
                        sku,
                        barcode,
                        name,
                        category_name,
                        category_id_value,
                        str(body.get("brand") or "").strip(),
                        str(body.get("unit") or "un").strip() or "un",
                        (body.get("description") or "").strip(),
                        cost_price,
                        desired_margin,
                        1 if str(body.get("status") or "active").strip().lower() != "inactive" else 0,
                        user["id"],
                        utc_now_iso(),
                    ),
                )
                product_id = cur.lastrowid
                costs = body.get("cost_items") or []
                for item in costs:
                    label = (item.get("label") or "").strip()
                    value_type = item.get("value_type", "fixed")
                    try:
                        value = float(item.get("value") or 0)
                    except (TypeError, ValueError):
                        continue
                    if label and value >= 0 and value_type in ("fixed", "percent"):
                        conn.execute(
                            "INSERT INTO product_cost_items (company_id, product_id, label, value_type, value) VALUES (?, ?, ?, ?, ?)",
                            (company_id, product_id, label, value_type, value),
                        )
                log_audit(
                    conn,
                    "products",
                    "product",
                    product_id,
                    "create",
                    user["id"],
                    {"name": name, "sku": sku, "barcode": barcode, "category_id": category_id_value},
                )
                conn.commit()
                return self.send_json({"ok": True, "product_id": product_id})

            if path == "/api/categories":
                body = parse_json_body(self)
                name = str(body.get("name") or "").strip()
                if not name:
                    return self.send_json({"error": "Nome da categoria é obrigatório."}, status=400)
                description = str(body.get("description") or "").strip()
                is_active = 1 if str(body.get("status") or "active").strip().lower() != "inactive" else 0
                exists = conn.execute(
                    "SELECT id FROM categories WHERE company_id = ? AND LOWER(TRIM(name)) = LOWER(TRIM(?))",
                    (company_id, name),
                ).fetchone()
                if exists:
                    return self.send_json({"error": "Já existe uma categoria com esse nome."}, status=400)
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO categories (company_id, name, description, is_active, created_by, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (company_id, name, description, is_active, user["id"], utc_now_iso()),
                )
                category_id = cur.lastrowid
                log_audit(
                    conn,
                    "products",
                    "category",
                    category_id,
                    "create",
                    user["id"],
                    {"name": name, "status": "active" if is_active == 1 else "inactive"},
                )
                conn.commit()
                return self.send_json({"ok": True, "category_id": category_id})

            if path.startswith("/api/products/") and path.endswith("/costs"):
                body = parse_json_body(self)
                parts = path.strip("/").split("/")
                product_id = int(parts[2])
                product = conn.execute("SELECT id FROM products WHERE id = ? AND company_id = ?", (product_id, company_id)).fetchone()
                if not product:
                    return self.send_json({"error": "Produto não encontrado."}, status=404)
                conn.execute(
                    "INSERT INTO product_cost_items (company_id, product_id, label, value_type, value) VALUES (?, ?, ?, ?, ?)",
                    (
                        company_id,
                        product_id,
                        body.get("label", "").strip(),
                        body.get("value_type", "fixed"),
                        float(body.get("value") or 0),
                    ),
                )
                conn.commit()
                return self.send_json({"ok": True})

            if path == "/api/inventory/entry":
                body = parse_json_body(self)
                try:
                    product_id = int(body.get("product_id"))
                    qty = parse_positive_int(body.get("qty"), "Quantidade de entrada")
                except (TypeError, ValueError):
                    return self.send_json({"error": "Produto e quantidade são obrigatórios para entrada."}, status=400)
                operation_timestamp = parse_client_timestamp(body.get("created_at"))
                if not operation_timestamp:
                    return self.send_json({"error": "Data/hora inválida para entrada de estoque."}, status=400)
                exists = conn.execute(
                    "SELECT id FROM products WHERE id = ? AND company_id = ? AND is_active = 1",
                    (product_id, company_id),
                ).fetchone()
                if not exists:
                    return self.send_json({"error": "Produto não encontrado."}, status=404)
                conn.execute("UPDATE products SET stock_qty = stock_qty + ? WHERE id = ? AND company_id = ?", (qty, product_id, company_id))
                conn.execute(
                    """
                    INSERT INTO inventory_movements (company_id, product_id, movement_type, qty, note, created_by, created_at)
                    VALUES (?, ?, 'entry', ?, ?, ?, ?)
                    """,
                    (company_id, product_id, qty, body.get("note", "Entrada de estoque"), user["id"], operation_timestamp),
                )
                log_audit(
                    conn,
                    "inventory",
                    "movement",
                    None,
                    "entry",
                    user["id"],
                    {"product_id": product_id, "qty": qty, "note": body.get("note", "Entrada de estoque")},
                )
                conn.commit()
                return self.send_json({"ok": True})

            if path == "/api/inventory/exit":
                body = parse_json_body(self)
                try:
                    product_id = int(body.get("product_id"))
                    qty = parse_positive_int(body.get("qty"), "Quantidade de saída")
                except (TypeError, ValueError):
                    return self.send_json({"error": "Produto e quantidade são obrigatórios para saída."}, status=400)
                operation_timestamp = parse_client_timestamp(body.get("created_at"))
                if not operation_timestamp:
                    return self.send_json({"error": "Data/hora inválida para saída de estoque."}, status=400)
                p = conn.execute(
                    "SELECT stock_qty FROM products WHERE id = ? AND company_id = ? AND is_active = 1",
                    (product_id, company_id),
                ).fetchone()
                if not p:
                    return self.send_json({"error": "Produto não encontrado"}, status=404)
                if int(p["stock_qty"]) < qty:
                    return self.send_json({"error": "Estoque insuficiente"}, status=400)
                conn.execute("UPDATE products SET stock_qty = stock_qty - ? WHERE id = ? AND company_id = ?", (qty, product_id, company_id))
                conn.execute(
                    """
                    INSERT INTO inventory_movements (company_id, product_id, movement_type, qty, note, created_by, created_at)
                    VALUES (?, ?, 'exit', ?, ?, ?, ?)
                    """,
                    (company_id, product_id, qty, body.get("note", "Saída de estoque"), user["id"], operation_timestamp),
                )
                log_audit(
                    conn,
                    "inventory",
                    "movement",
                    None,
                    "exit",
                    user["id"],
                    {"product_id": product_id, "qty": qty, "note": body.get("note", "Saída de estoque")},
                )
                conn.commit()
                return self.send_json({"ok": True})

            if path == "/api/sales":
                body = parse_json_body(self)
                try:
                    product_id = int(body.get("product_id"))
                    qty = parse_positive_int(body.get("qty"), "Quantidade da venda")
                    unit_price = float(body.get("unit_price"))
                except (TypeError, ValueError):
                    return self.send_json({"error": "Produto, quantidade e preço unitário são obrigatórios."}, status=400)
                if unit_price <= 0:
                    return self.send_json({"error": "Preço unitário da venda deve ser maior que zero."}, status=400)
                operation_timestamp = parse_client_timestamp(body.get("created_at"))
                if not operation_timestamp:
                    return self.send_json({"error": "Data/hora inválida para venda."}, status=400)

                snapshot = sale_cost_snapshot(conn, product_id, qty, unit_price, company_id=company_id)
                if not snapshot:
                    return self.send_json({"error": "Produto não encontrado"}, status=404)
                product = snapshot["product"]
                if int(product["is_active"] or 0) != 1:
                    return self.send_json({"error": "Produto inativo não pode receber novas vendas."}, status=400)
                if int(product["stock_qty"]) < qty:
                    return self.send_json({"error": "Estoque insuficiente para venda"}, status=400)
                total = snapshot["total"]
                cogs_total = snapshot["cogs_total"]
                taxes_total = snapshot["taxes_total"]
                extra_expenses_total = snapshot["extra_expenses_total"]
                gross_profit = snapshot["gross_profit"]
                net_profit = snapshot["net_profit"]

                conn.execute("UPDATE products SET stock_qty = stock_qty - ? WHERE id = ? AND company_id = ?", (qty, product_id, company_id))
                sale_cursor = conn.execute(
                    """
                    INSERT INTO sales (
                        company_id, product_id, qty, unit_price, total,
                        cogs_total, taxes_total, extra_expenses_total,
                        gross_profit, net_profit, created_by, created_at
                    )
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        company_id,
                        product_id,
                        qty,
                        unit_price,
                        total,
                        cogs_total,
                        taxes_total,
                        extra_expenses_total,
                        gross_profit,
                        net_profit,
                        user["id"],
                        operation_timestamp,
                    ),
                )
                sale_id = sale_cursor.lastrowid
                conn.execute(
                    """
                    INSERT INTO inventory_movements (company_id, product_id, movement_type, qty, note, sale_id, created_by, created_at)
                    VALUES (?, ?, 'exit', ?, 'Saída por venda', ?, ?, ?)
                    """,
                    (company_id, product_id, qty, sale_id, user["id"], operation_timestamp),
                )
                conn.execute(
                    """
                    INSERT INTO financial_entries (
                        company_id, entry_type, category, description, amount, sale_id,
                        payment_method, payment_terms, notes, payment_status, origin,
                        created_by, created_at
                    )
                    VALUES (?, 'income', 'Venda', ?, ?, ?, ?, ?, ?, ?, 'sale', ?, ?)
                    """,
                    (
                        company_id,
                        f"Venda de {qty}x {product['name']}",
                        total,
                        sale_id,
                        "N/A",
                        "À vista",
                        "",
                        "pago",
                        user["id"],
                        operation_timestamp,
                    ),
                )
                log_audit(
                    conn,
                    "sales",
                    "sale",
                    sale_id,
                    "create",
                    user["id"],
                    {"product_id": product_id, "qty": qty, "unit_price": unit_price, "total": total},
                )
                conn.commit()
                return self.send_json({
                    "ok": True,
                    "sale_id": sale_id,
                    "total": total,
                    "cogs_total": cogs_total,
                    "taxes_total": taxes_total,
                    "gross_profit": gross_profit,
                    "net_profit": net_profit,
                })

            if path == "/api/finance/expense":
                body = parse_json_body(self)
                operation_timestamp = parse_client_timestamp(body.get("created_at"))
                if not operation_timestamp:
                    return self.send_json({"error": "Data/hora inválida para gasto."}, status=400)
                try:
                    amount = float(body.get("amount") or 0)
                except (TypeError, ValueError):
                    return self.send_json({"error": "Valor do gasto inválido."}, status=400)
                if amount <= 0:
                    return self.send_json({"error": "Valor do gasto deve ser maior que zero."}, status=400)
                conn.execute(
                    """
                    INSERT INTO financial_entries (
                        company_id, entry_type, category, description, amount,
                        payment_method, payment_terms, notes, payment_status, origin,
                        created_by, created_at
                    )
                    VALUES (?, 'expense', ?, ?, ?, ?, ?, ?, ?, 'manual', ?, ?)
                    """,
                    (
                        company_id,
                        body.get("category", "Outros"),
                        body.get("description", ""),
                        amount,
                        body.get("payment_method", "N/A"),
                        body.get("payment_terms", "À vista"),
                        body.get("notes", ""),
                        body.get("payment_status", "pago"),
                        user["id"],
                        operation_timestamp,
                    ),
                )
                created_finance_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
                log_audit(
                    conn,
                    "finance",
                    "entry",
                    created_finance_id,
                    "create",
                    user["id"],
                    {"type": "expense", "category": body.get("category", "Outros"), "amount": amount},
                )
                conn.commit()
                return self.send_json({"ok": True})

            if path == "/api/finance/income":
                body = parse_json_body(self)
                operation_timestamp = parse_client_timestamp(body.get("created_at"))
                if not operation_timestamp:
                    return self.send_json({"error": "Data/hora inválida para ganho."}, status=400)
                try:
                    amount = float(body.get("amount") or 0)
                except (TypeError, ValueError):
                    return self.send_json({"error": "Valor do ganho inválido."}, status=400)
                if amount <= 0:
                    return self.send_json({"error": "Valor do ganho deve ser maior que zero."}, status=400)
                conn.execute(
                    """
                    INSERT INTO financial_entries (
                        company_id, entry_type, category, description, amount,
                        payment_method, payment_terms, notes, payment_status, origin,
                        created_by, created_at
                    )
                    VALUES (?, 'income', ?, ?, ?, ?, ?, ?, ?, 'manual', ?, ?)
                    """,
                    (
                        company_id,
                        body.get("category", "Outros"),
                        body.get("description", ""),
                        amount,
                        body.get("payment_method", "N/A"),
                        body.get("payment_terms", "À vista"),
                        body.get("notes", ""),
                        body.get("payment_status", "pago"),
                        user["id"],
                        operation_timestamp,
                    ),
                )
                created_finance_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
                log_audit(
                    conn,
                    "finance",
                    "entry",
                    created_finance_id,
                    "create",
                    user["id"],
                    {"type": "income", "category": body.get("category", "Outros"), "amount": amount},
                )
                conn.commit()
                return self.send_json({"ok": True})

            if path == "/api/suppliers":
                body = parse_json_body(self)
                name = str(body.get("name") or "").strip()
                if not name:
                    return self.send_json({"error": "Nome do fornecedor é obrigatório."}, status=400)
                conn.execute(
                    """
                    INSERT INTO suppliers (company_id, name, contact, phone, email, notes, is_active, created_by, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
                    """,
                    (
                        company_id,
                        name,
                        str(body.get("contact") or "").strip(),
                        str(body.get("phone") or "").strip(),
                        str(body.get("email") or "").strip(),
                        str(body.get("notes") or "").strip(),
                        user["id"],
                        utc_now_iso(),
                    ),
                )
                supplier_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
                log_audit(conn, "purchases", "supplier", supplier_id, "create", user["id"], {"name": name})
                conn.commit()
                return self.send_json({"ok": True})

            if path == "/api/purchases":
                body = parse_json_body(self)
                purchase_type = str(body.get("purchase_type") or "inventory").strip().lower()
                if purchase_type not in ("inventory", "operational"):
                    return self.send_json({"error": "Tipo de compra inválido."}, status=400)
                operation_timestamp = parse_client_timestamp(body.get("created_at"))
                if not operation_timestamp:
                    return self.send_json({"error": "Data/hora inválida para compra."}, status=400)
                supplier_id = body.get("supplier_id")
                supplier_id_val = None
                if supplier_id not in (None, "", 0, "0"):
                    try:
                        supplier_id_val = int(supplier_id)
                    except (TypeError, ValueError):
                        return self.send_json({"error": "Fornecedor inválido."}, status=400)
                if supplier_id_val is not None:
                    supplier_row = conn.execute(
                        "SELECT id, is_active FROM suppliers WHERE id = ? AND company_id = ?",
                        (supplier_id_val, company_id),
                    ).fetchone()
                    if not supplier_row:
                        return self.send_json({"error": "Fornecedor não encontrado."}, status=404)
                    if int(supplier_row["is_active"] or 0) != 1:
                        return self.send_json({"error": "Fornecedor inativo não pode ser usado em novas compras."}, status=400)
                items = body.get("items") or []
                if not isinstance(items, list) or len(items) == 0:
                    return self.send_json({"error": "Adicione ao menos um item na compra."}, status=400)

                normalized_items = []
                total_amount = 0.0
                for item in items:
                    label = str(item.get("label") or "").strip()
                    product_id = item.get("product_id")
                    product_id_val = None
                    if product_id not in (None, "", 0):
                        try:
                            product_id_val = int(product_id)
                        except (TypeError, ValueError):
                            return self.send_json({"error": "Produto inválido em item da compra."}, status=400)
                    if not label and product_id_val is None:
                        return self.send_json({"error": "Cada item deve ter produto ou descrição."}, status=400)
                    try:
                        qty = parse_positive_int(item.get("qty"), "Quantidade da compra")
                        unit_cost = float(item.get("unit_cost") or 0)
                    except (TypeError, ValueError):
                        return self.send_json({"error": "Quantidade/custo inválidos em item da compra."}, status=400)
                    if unit_cost < 0:
                        return self.send_json({"error": "Quantidade deve ser > 0 e custo >= 0."}, status=400)
                    total_cost = round(float(item.get("total_cost") or (qty * unit_cost)), 2)
                    affects_stock_raw = item.get("affects_stock", None)
                    if purchase_type == "inventory" and product_id_val is not None:
                        affects_stock = parse_boolish(affects_stock_raw, default=True)
                    else:
                        affects_stock = False
                    if product_id_val is not None:
                        product_row = conn.execute(
                            "SELECT id, name, is_active FROM products WHERE id = ? AND company_id = ?",
                            (product_id_val, company_id),
                        ).fetchone()
                        if not product_row:
                            return self.send_json({"error": "Produto da compra não encontrado."}, status=404)
                        if int(product_row["is_active"] or 0) != 1 and int(affects_stock) == 1:
                            return self.send_json({"error": "Produto inativo não pode receber entrada por compra."}, status=400)
                        if not label:
                            label = str(product_row["name"] or "").strip() or label
                    total_amount += total_cost
                    normalized_items.append({
                        "label": label,
                        "product_id": product_id_val,
                        "qty": qty,
                        "unit_cost": unit_cost,
                        "total_cost": total_cost,
                        "affects_stock": 1 if affects_stock else 0,
                    })

                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO purchases (
                        company_id, supplier_id, purchase_type, payment_method, payment_terms,
                        notes, total_amount, status, created_by, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        company_id,
                        supplier_id_val,
                        purchase_type,
                        str(body.get("payment_method") or "N/A").strip(),
                        str(body.get("payment_terms") or "À vista").strip(),
                        str(body.get("notes") or "").strip(),
                        round(total_amount, 2),
                        str(body.get("payment_status") or "pendente").strip() or "pendente",
                        user["id"],
                        operation_timestamp,
                    ),
                )
                purchase_id = cur.lastrowid

                for item in normalized_items:
                    conn.execute(
                        """
                        INSERT INTO purchase_items (company_id, purchase_id, product_id, label, qty, unit_cost, total_cost, affects_stock)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            company_id,
                            purchase_id,
                            item["product_id"],
                            item["label"],
                            item["qty"],
                            item["unit_cost"],
                            item["total_cost"],
                            item["affects_stock"],
                        ),
                    )
                    if item["affects_stock"] and item["product_id"] is not None:
                        product_row = conn.execute(
                            "SELECT id, is_active FROM products WHERE id = ? AND company_id = ?",
                            (item["product_id"], company_id),
                        ).fetchone()
                        if not product_row:
                            return self.send_json({"error": "Produto da compra não encontrado."}, status=404)
                        if int(product_row["is_active"] or 0) != 1:
                            return self.send_json({"error": "Produto inativo não pode receber entrada por compra."}, status=400)
                        conn.execute(
                            "UPDATE products SET stock_qty = stock_qty + ? WHERE id = ? AND company_id = ?",
                            (item["qty"], item["product_id"], company_id),
                        )
                        conn.execute(
                            """
                            INSERT INTO inventory_movements (company_id, product_id, movement_type, qty, note, purchase_id, created_by, created_at)
                            VALUES (?, ?, 'entry', ?, ?, ?, ?, ?)
                            """,
                            (
                                company_id,
                                item["product_id"],
                                item["qty"],
                                f"Entrada por compra #{purchase_id}",
                                purchase_id,
                                user["id"],
                                operation_timestamp,
                            ),
                        )

                conn.execute(
                    """
                    INSERT INTO financial_entries (
                        company_id, entry_type, category, description, amount, purchase_id,
                        payment_method, payment_terms, notes, payment_status, origin,
                        created_by, created_at
                    )
                    VALUES (
                        ?, 'expense', 'Compra', ?, ?, ?,
                        ?, ?, ?, ?, 'purchase',
                        ?, ?
                    )
                    """,
                    (
                        company_id,
                        f"Compra #{purchase_id}",
                        round(total_amount, 2),
                        purchase_id,
                        str(body.get("payment_method") or "N/A").strip(),
                        str(body.get("payment_terms") or "À vista").strip(),
                        str(body.get("notes") or "").strip(),
                        str(body.get("payment_status") or "pendente").strip(),
                        user["id"],
                        operation_timestamp,
                    ),
                )
                log_audit(
                    conn,
                    "purchases",
                    "purchase",
                    purchase_id,
                    "create",
                    user["id"],
                    {"purchase_type": purchase_type, "total_amount": round(total_amount, 2), "items_count": len(normalized_items)},
                )
                conn.commit()
                return self.send_json({"ok": True, "purchase_id": purchase_id})

            if path == "/api/cost-calculations":
                body = parse_json_body(self)
                try:
                    cost_amount = float(body.get("cost_amount") or 0)
                    shipping_amount = float(body.get("shipping_amount") or 0)
                    other_costs_amount = float(body.get("other_costs_amount") or 0)
                    tax_percent = float(body.get("tax_percent") or 0)
                    commission_percent = float(body.get("commission_percent") or 0)
                    margin_percent = float(body.get("margin_percent") or 0)
                    tax_amount = float(body.get("tax_amount") or 0)
                    commission_amount = float(body.get("commission_amount") or 0)
                    profit_amount = float(body.get("profit_amount") or 0)
                    sale_price = float(body.get("sale_price") or 0)
                except (TypeError, ValueError):
                    return self.send_json({"error": "Valores inválidos no cálculo de custos."}, status=400)
                if min(cost_amount, shipping_amount, other_costs_amount, tax_percent, commission_percent, margin_percent, tax_amount, commission_amount, profit_amount, sale_price) < 0:
                    return self.send_json({"error": "Valores do cálculo não podem ser negativos."}, status=400)
                product_id = body.get("product_id")
                product_id_val = None
                product_name = str(body.get("product_name") or "").strip()
                if product_id not in (None, "", 0):
                    try:
                        product_id_val = int(product_id)
                    except (TypeError, ValueError):
                        return self.send_json({"error": "Produto inválido para salvar cálculo."}, status=400)
                    product = conn.execute("SELECT name FROM products WHERE id = ? AND company_id = ?", (product_id_val, company_id)).fetchone()
                    if not product:
                        return self.send_json({"error": "Produto não encontrado para salvar cálculo."}, status=404)
                    product_name = product["name"]
                conn.execute(
                    """
                    INSERT INTO cost_calculations (
                        company_id, product_id, product_name, cost_amount, shipping_amount, other_costs_amount,
                        tax_percent, commission_percent, margin_percent,
                        tax_amount, commission_amount, profit_amount, sale_price,
                        created_by, created_at
                    )
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        company_id,
                        product_id_val,
                        product_name,
                        cost_amount,
                        shipping_amount,
                        other_costs_amount,
                        tax_percent,
                        commission_percent,
                        margin_percent,
                        tax_amount,
                        commission_amount,
                        profit_amount,
                        sale_price,
                        user["id"],
                        utc_now_iso(),
                    ),
                )
                conn.commit()
                return self.send_json({"ok": True})

            self.send_json({"error": "Rota não encontrada"}, status=404)
        except sqlite3.IntegrityError as e:
            self.send_json({"error": f"Erro de integridade: {str(e)}"}, status=400)
        except BadRequestError as e:
            self.send_json({"error": str(e)}, status=400)
        except Exception as e:
            self.send_json({"error": f"Erro interno: {str(e)}"}, status=500)
        finally:
            conn.close()

    def do_PUT(self):
        parsed = urlparse(self.path)
        path = parsed.path

        conn = db_connection()
        try:
            user = require_auth(self, conn)
            if not user:
                return
            module_key = module_key_for_path(path)
            if module_key and not require_module_permission(self, user, module_key):
                return
            if path.startswith("/api/") and module_key is None:
                return self.send_json({"error": "Rota de API sem módulo mapeado."}, status=403)
            company_id = company_id_from_user(user)
            if company_id <= 0:
                return self.send_json({"error": "Usuário sem empresa vinculada."}, status=400)

            if path.startswith("/api/sales/"):
                sale_id = parse_sale_id(path)
                if not sale_id:
                    return self.send_json({"error": "ID de venda inválido"}, status=400)

                sale_row = conn.execute(
                    """
                    SELECT s.id, s.company_id, s.product_id, s.qty, s.unit_price, s.total, s.created_at, p.name as product_name
                    FROM sales s
                    JOIN products p ON p.id = s.product_id AND p.company_id = s.company_id
                    WHERE s.id = ? AND s.company_id = ?
                    """,
                    (sale_id, company_id),
                ).fetchone()
                if not sale_row:
                    return self.send_json({"error": "Venda não encontrada"}, status=404)

                body = parse_json_body(self)
                try:
                    product_id = int(body.get("product_id"))
                    qty = parse_positive_int(body.get("qty"), "Quantidade da venda")
                    unit_price = float(body.get("unit_price"))
                except (TypeError, ValueError):
                    return self.send_json({"error": "Produto, quantidade e preço unitário são obrigatórios."}, status=400)
                if unit_price <= 0:
                    return self.send_json({"error": "Preço unitário da venda deve ser maior que zero."}, status=400)
                operation_timestamp = parse_client_timestamp(body.get("created_at"))
                if not operation_timestamp:
                    return self.send_json({"error": "Data/hora inválida para venda."}, status=400)

                remove_sale_side_effects(conn, sale_row, company_id=company_id)

                snapshot = sale_cost_snapshot(conn, product_id, qty, unit_price, company_id=company_id)
                if not snapshot:
                    return self.send_json({"error": "Produto não encontrado"}, status=404)
                product = snapshot["product"]
                if int(product["is_active"] or 0) != 1:
                    return self.send_json({"error": "Produto inativo não pode receber novas vendas."}, status=400)
                if int(product["stock_qty"]) < qty:
                    return self.send_json({"error": "Estoque insuficiente para venda"}, status=400)

                total = snapshot["total"]
                cogs_total = snapshot["cogs_total"]
                taxes_total = snapshot["taxes_total"]
                extra_expenses_total = snapshot["extra_expenses_total"]
                gross_profit = snapshot["gross_profit"]
                net_profit = snapshot["net_profit"]

                conn.execute("UPDATE products SET stock_qty = stock_qty - ? WHERE id = ? AND company_id = ?", (qty, product_id, company_id))
                conn.execute(
                    """
                    UPDATE sales
                    SET product_id = ?, qty = ?, unit_price = ?, total = ?,
                        cogs_total = ?, taxes_total = ?, extra_expenses_total = ?,
                        gross_profit = ?, net_profit = ?, created_at = ?
                    WHERE id = ? AND company_id = ?
                    """,
                    (
                        product_id,
                        qty,
                        unit_price,
                        total,
                        cogs_total,
                        taxes_total,
                        extra_expenses_total,
                        gross_profit,
                        net_profit,
                        operation_timestamp,
                        sale_id,
                        company_id,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO inventory_movements (company_id, product_id, movement_type, qty, note, sale_id, created_by, created_at)
                    VALUES (?, ?, 'exit', ?, 'Saída por venda', ?, ?, ?)
                    """,
                    (company_id, product_id, qty, sale_id, user["id"], operation_timestamp),
                )
                conn.execute(
                    """
                    INSERT INTO financial_entries (company_id, entry_type, category, description, amount, sale_id, created_by, created_at)
                    VALUES (?, 'income', 'Venda', ?, ?, ?, ?, ?)
                    """,
                    (company_id, f"Venda de {qty}x {product['name']}", total, sale_id, user["id"], operation_timestamp),
                )
                log_audit(
                    conn,
                    "sales",
                    "sale",
                    sale_id,
                    "update",
                    user["id"],
                    {"product_id": product_id, "qty": qty, "unit_price": unit_price, "total": total},
                )
                conn.commit()
                return self.send_json({
                    "ok": True,
                    "total": total,
                    "cogs_total": cogs_total,
                    "taxes_total": taxes_total,
                    "gross_profit": gross_profit,
                    "net_profit": net_profit,
                })

            if path.startswith("/api/finance/entries/"):
                finance_id = parse_finance_entry_id(path)
                if not finance_id:
                    return self.send_json({"error": "ID de lançamento inválido"}, status=400)

                entry = conn.execute(
                    """
                    SELECT id, entry_type, sale_id, purchase_id FROM financial_entries WHERE id = ? AND company_id = ?
                    """,
                    (finance_id, company_id),
                ).fetchone()
                if not entry:
                    return self.send_json({"error": "Lançamento não encontrado"}, status=404)
                if entry["sale_id"] is not None:
                    return self.send_json(
                        {"error": "Lançamento vinculado a venda. Edite/exclua a venda para ajustar este registro."},
                        status=400,
                    )
                if entry["purchase_id"] is not None:
                    return self.send_json(
                        {"error": "Lançamento vinculado a compra. Edite/exclua a compra para ajustar este registro."},
                        status=400,
                    )

                body = parse_json_body(self)
                entry_type = (body.get("entry_type") or entry["entry_type"] or "").strip().lower()
                if entry_type not in ("income", "expense"):
                    return self.send_json({"error": "Tipo de lançamento inválido."}, status=400)
                category = (body.get("category") or "").strip()
                description = (body.get("description") or "").strip()
                if not category:
                    return self.send_json({"error": "Categoria é obrigatória."}, status=400)
                try:
                    amount = float(body.get("amount") or 0)
                except (TypeError, ValueError):
                    return self.send_json({"error": "Valor do lançamento inválido."}, status=400)
                if amount <= 0:
                    return self.send_json({"error": "Valor do lançamento deve ser maior que zero."}, status=400)
                operation_timestamp = parse_client_timestamp(body.get("created_at"))
                if not operation_timestamp:
                    return self.send_json({"error": "Data/hora inválida para lançamento."}, status=400)

                conn.execute(
                    """
                    UPDATE financial_entries
                    SET entry_type = ?, category = ?, description = ?, amount = ?,
                        payment_method = ?, payment_terms = ?, notes = ?, payment_status = ?,
                        created_at = ?
                    WHERE id = ? AND company_id = ?
                    """,
                    (
                        entry_type,
                        category,
                        description,
                        amount,
                        str(body.get("payment_method") or "N/A").strip(),
                        str(body.get("payment_terms") or "À vista").strip(),
                        str(body.get("notes") or "").strip(),
                        str(body.get("payment_status") or "pago").strip(),
                        operation_timestamp,
                        finance_id,
                        company_id,
                    ),
                )
                log_audit(
                    conn,
                    "finance",
                    "entry",
                    finance_id,
                    "update",
                    user["id"],
                    {"entry_type": entry_type, "category": category, "amount": amount},
                )
                conn.commit()
                return self.send_json({"ok": True})

            if path.startswith("/api/users/") and path.endswith("/reset-password"):
                if user["role"] != "master":
                    return self.send_json({"error": "Somente master pode redefinir senha."}, status=403)
                user_id = parse_user_id(path)
                if not user_id:
                    return self.send_json({"error": "ID de usuário inválido"}, status=400)
                target = conn.execute(
                    "SELECT id, role FROM users WHERE id = ? AND company_id = ?",
                    (user_id, company_id),
                ).fetchone()
                if not target:
                    return self.send_json({"error": "Usuário não encontrado"}, status=404)
                body = parse_json_body(self)
                new_password = str(body.get("new_password") or "").strip()
                if len(new_password) < 4:
                    return self.send_json({"error": "Nova senha deve ter pelo menos 4 caracteres."}, status=400)
                conn.execute(
                    "UPDATE users SET password_hash = ? WHERE id = ? AND company_id = ?",
                    (hash_password(new_password), user_id, company_id),
                )
                conn.execute("DELETE FROM sessions WHERE user_id = ? AND company_id = ?", (user_id, company_id))
                log_audit(conn, "users", "user", user_id, "reset_password", user["id"], {})
                conn.commit()
                return self.send_json({"ok": True})

            if path.startswith("/api/users/") and path.endswith("/reactivate"):
                if user["role"] != "master":
                    return self.send_json({"error": "Somente master pode reativar usuários."}, status=403)
                user_id = parse_user_id(path)
                if not user_id:
                    return self.send_json({"error": "ID de usuário inválido"}, status=400)
                target = conn.execute(
                    "SELECT id, role, is_active FROM users WHERE id = ? AND company_id = ?",
                    (user_id, company_id),
                ).fetchone()
                if not target:
                    return self.send_json({"error": "Usuário não encontrado"}, status=404)
                if int(target["is_active"] or 0) == 1:
                    return self.send_json({"ok": True, "mode": "already_active"})
                conn.execute("UPDATE users SET is_active = 1 WHERE id = ? AND company_id = ?", (user_id, company_id))
                log_audit(conn, "users", "user", user_id, "reactivate", user["id"], {})
                conn.commit()
                return self.send_json({"ok": True, "mode": "reactivated"})

            if path.startswith("/api/users/") and path.endswith("/deactivate"):
                if user["role"] != "master":
                    return self.send_json({"error": "Somente master pode inativar usuários."}, status=403)
                user_id = parse_user_id(path)
                if not user_id:
                    return self.send_json({"error": "ID de usuário inválido"}, status=400)
                target = conn.execute(
                    "SELECT id, role, is_active FROM users WHERE id = ? AND company_id = ?",
                    (user_id, company_id),
                ).fetchone()
                if not target:
                    return self.send_json({"error": "Usuário não encontrado"}, status=404)
                if int(user["id"]) == int(user_id):
                    return self.send_json({"error": "Não é possível inativar o próprio usuário logado."}, status=400)
                if target["role"] == "master" and int(target["is_active"] or 0) == 1 and count_active_masters(conn, company_id) <= 1:
                    return self.send_json({"error": "É obrigatório manter pelo menos 1 usuário master ativo."}, status=400)
                if int(target["is_active"] or 0) != 1:
                    return self.send_json({"ok": True, "mode": "already_inactive"})
                conn.execute("UPDATE users SET is_active = 0 WHERE id = ? AND company_id = ?", (user_id, company_id))
                conn.execute("DELETE FROM sessions WHERE user_id = ? AND company_id = ?", (user_id, company_id))
                log_audit(conn, "users", "user", user_id, "deactivate", user["id"], {"source": "put_deactivate"})
                conn.commit()
                return self.send_json({"ok": True, "mode": "deactivated"})

            if path.startswith("/api/suppliers/"):
                supplier_id = parse_supplier_id(path)
                if not supplier_id:
                    return self.send_json({"error": "ID de fornecedor inválido"}, status=400)
                body = parse_json_body(self)
                name = str(body.get("name") or "").strip()
                if not name:
                    return self.send_json({"error": "Nome do fornecedor é obrigatório."}, status=400)
                is_active = 1 if bool(body.get("is_active", True)) else 0
                conn.execute(
                    """
                    UPDATE suppliers
                    SET name = ?, contact = ?, phone = ?, email = ?, notes = ?, is_active = ?
                    WHERE id = ? AND company_id = ?
                    """,
                    (
                        name,
                        str(body.get("contact") or "").strip(),
                        str(body.get("phone") or "").strip(),
                        str(body.get("email") or "").strip(),
                        str(body.get("notes") or "").strip(),
                        is_active,
                        supplier_id,
                        company_id,
                    ),
                )
                log_audit(conn, "purchases", "supplier", supplier_id, "update", user["id"], {"name": name, "is_active": is_active})
                conn.commit()
                return self.send_json({"ok": True})

            if path.startswith("/api/purchases/"):
                purchase_id = parse_purchase_id(path)
                if not purchase_id:
                    return self.send_json({"error": "ID de compra inválido"}, status=400)
                current = conn.execute(
                    "SELECT id FROM purchases WHERE id = ? AND company_id = ?",
                    (purchase_id, company_id),
                ).fetchone()
                if not current:
                    return self.send_json({"error": "Compra não encontrada"}, status=404)

                existing_items = conn.execute(
                    """
                    SELECT product_id, qty, affects_stock
                    FROM purchase_items
                    WHERE purchase_id = ? AND company_id = ?
                    """,
                    (purchase_id, company_id),
                ).fetchall()

                # Reverte impacto antigo de estoque de forma segura antes de aplicar a edição.
                for item in existing_items:
                    if not item["product_id"] or int(item["affects_stock"] or 0) != 1:
                        continue
                    product_row = conn.execute(
                        "SELECT id, stock_qty FROM products WHERE id = ? AND company_id = ?",
                        (item["product_id"], company_id),
                    ).fetchone()
                    if not product_row:
                        continue
                    if int(product_row["stock_qty"] or 0) - int(item["qty"] or 0) < 0:
                        return self.send_json(
                            {"error": "Não é possível editar esta compra pois o estoque atual não permite reverter a entrada antiga."},
                            status=400,
                        )

                for item in existing_items:
                    if item["product_id"] and int(item["affects_stock"] or 0) == 1:
                        conn.execute(
                            "UPDATE products SET stock_qty = stock_qty - ? WHERE id = ? AND company_id = ?",
                            (int(item["qty"] or 0), int(item["product_id"]), company_id),
                        )

                conn.execute(
                    "DELETE FROM inventory_movements WHERE purchase_id = ? AND company_id = ?",
                    (purchase_id, company_id),
                )
                conn.execute("DELETE FROM financial_entries WHERE purchase_id = ? AND company_id = ?", (purchase_id, company_id))
                conn.execute("DELETE FROM purchase_items WHERE purchase_id = ? AND company_id = ?", (purchase_id, company_id))

                body = parse_json_body(self)
                purchase_type = str(body.get("purchase_type") or "inventory").strip().lower()
                if purchase_type not in ("inventory", "operational"):
                    return self.send_json({"error": "Tipo de compra inválido."}, status=400)
                operation_timestamp = parse_client_timestamp(body.get("created_at"))
                if not operation_timestamp:
                    return self.send_json({"error": "Data/hora inválida para compra."}, status=400)
                supplier_id = body.get("supplier_id")
                supplier_id_val = None
                if supplier_id not in (None, "", 0, "0"):
                    try:
                        supplier_id_val = int(supplier_id)
                    except (TypeError, ValueError):
                        return self.send_json({"error": "Fornecedor inválido."}, status=400)
                if supplier_id_val is not None:
                    supplier_row = conn.execute(
                        "SELECT id, is_active FROM suppliers WHERE id = ? AND company_id = ?",
                        (supplier_id_val, company_id),
                    ).fetchone()
                    if not supplier_row:
                        return self.send_json({"error": "Fornecedor não encontrado."}, status=404)
                    if int(supplier_row["is_active"] or 0) != 1:
                        return self.send_json({"error": "Fornecedor inativo não pode ser usado em novas compras."}, status=400)

                items = body.get("items") or []
                if not isinstance(items, list) or len(items) == 0:
                    return self.send_json({"error": "Informe ao menos um item na compra."}, status=400)

                normalized_items = []
                total_amount = 0.0
                for item in items:
                    product_id = item.get("product_id")
                    product_id_val = None
                    if product_id not in (None, "", 0):
                        try:
                            product_id_val = int(product_id)
                        except (TypeError, ValueError):
                            return self.send_json({"error": "Produto inválido na compra."}, status=400)

                    label = str(item.get("label") or "").strip()
                    try:
                        qty = parse_positive_int(item.get("qty"), "Quantidade da compra")
                        unit_cost = float(item.get("unit_cost") or 0)
                    except (TypeError, ValueError):
                        return self.send_json({"error": "Quantidade/custo inválidos na compra."}, status=400)
                    if unit_cost < 0:
                        return self.send_json({"error": "Custo unitário da compra inválido."}, status=400)
                    total_cost = round(float(item.get("total_cost") or (qty * unit_cost)), 2)
                    affects_stock_raw = item.get("affects_stock", None)
                    if purchase_type == "inventory" and product_id_val is not None:
                        affects_stock = parse_boolish(affects_stock_raw, default=True)
                    else:
                        affects_stock = False
                    if not label and not product_id_val:
                        return self.send_json({"error": "Item da compra sem descrição/produto."}, status=400)

                    if product_id_val:
                        product_row = conn.execute(
                            "SELECT id, name, is_active FROM products WHERE id = ? AND company_id = ?",
                            (product_id_val, company_id),
                        ).fetchone()
                        if not product_row:
                            return self.send_json({"error": "Produto da compra não encontrado."}, status=404)
                        if int(product_row["is_active"] or 0) != 1:
                            return self.send_json({"error": "Produto inativo não pode ser usado em nova compra de mercadoria."}, status=400)
                        if not label:
                            label = product_row["name"]

                    normalized_items.append({
                        "product_id": product_id_val,
                        "label": label or "Item da compra",
                        "qty": qty,
                        "unit_cost": unit_cost,
                        "total_cost": total_cost,
                        "affects_stock": 1 if affects_stock else 0,
                    })
                    total_amount += total_cost

                conn.execute(
                    """
                    UPDATE purchases
                    SET supplier_id = ?, purchase_type = ?, payment_method = ?, payment_terms = ?,
                        notes = ?, total_amount = ?, status = ?, created_at = ?
                    WHERE id = ? AND company_id = ?
                    """,
                    (
                        supplier_id_val,
                        purchase_type,
                        str(body.get("payment_method") or "N/A").strip(),
                        str(body.get("payment_terms") or "À vista").strip(),
                        str(body.get("notes") or "").strip(),
                        round(total_amount, 2),
                        str(body.get("payment_status") or "pendente").strip() or "pendente",
                        operation_timestamp,
                        purchase_id,
                        company_id,
                    ),
                )

                for item in normalized_items:
                    conn.execute(
                        """
                        INSERT INTO purchase_items (company_id, purchase_id, product_id, label, qty, unit_cost, total_cost, affects_stock)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            company_id,
                            purchase_id,
                            item["product_id"],
                            item["label"],
                            item["qty"],
                            item["unit_cost"],
                            item["total_cost"],
                            item["affects_stock"],
                        ),
                    )

                    if item["product_id"] and item["affects_stock"] == 1:
                        conn.execute(
                            "UPDATE products SET stock_qty = stock_qty + ? WHERE id = ? AND company_id = ?",
                            (item["qty"], item["product_id"], company_id),
                        )
                        conn.execute(
                            """
                            INSERT INTO inventory_movements (company_id, product_id, movement_type, qty, note, purchase_id, created_by, created_at)
                            VALUES (?, ?, 'entry', ?, ?, ?, ?, ?)
                            """,
                            (
                                company_id,
                                item["product_id"],
                                item["qty"],
                                f"Entrada por compra #{purchase_id}",
                                purchase_id,
                                user["id"],
                                operation_timestamp,
                            ),
                        )

                conn.execute(
                    """
                    INSERT INTO financial_entries (
                        company_id, entry_type, category, description, amount, purchase_id,
                        payment_method, payment_terms, notes, payment_status, origin,
                        created_by, created_at
                    )
                    VALUES (
                        ?, 'expense', 'Compra', ?, ?, ?,
                        ?, ?, ?, ?, 'purchase',
                        ?, ?
                    )
                    """,
                    (
                        company_id,
                        f"Compra #{purchase_id}",
                        round(total_amount, 2),
                        purchase_id,
                        str(body.get("payment_method") or "N/A").strip(),
                        str(body.get("payment_terms") or "À vista").strip(),
                        str(body.get("notes") or "").strip(),
                        str(body.get("payment_status") or "pendente").strip(),
                        user["id"],
                        operation_timestamp,
                    ),
                )
                log_audit(
                    conn,
                    "purchases",
                    "purchase",
                    purchase_id,
                    "update",
                    user["id"],
                    {"purchase_type": purchase_type, "total_amount": round(total_amount, 2), "items_count": len(normalized_items)},
                )
                conn.commit()
                return self.send_json({"ok": True, "purchase_id": purchase_id})

            if path.startswith("/api/users/"):
                if user["role"] != "master":
                    return self.send_json({"error": "Somente master pode editar usuários."}, status=403)
                user_id = parse_user_id(path)
                if not user_id:
                    return self.send_json({"error": "ID de usuário inválido"}, status=400)
                target = conn.execute(
                    "SELECT id, role, is_active, avatar_url FROM users WHERE id = ? AND company_id = ?",
                    (user_id, company_id),
                ).fetchone()
                if not target:
                    return self.send_json({"error": "Usuário não encontrado"}, status=404)
                body = parse_json_body(self)
                name = str(body.get("name") or "").strip()
                role = str(body.get("role") or target["role"] or "").strip().lower()
                if not name:
                    return self.send_json({"error": "Nome é obrigatório."}, status=400)
                if role not in ("master", "admin", "member"):
                    return self.send_json({"error": "Perfil inválido."}, status=400)
                if target["role"] == "master" and role != "master" and int(target["is_active"] or 0) == 1:
                    if count_active_masters(conn, company_id) <= 1:
                        return self.send_json({"error": "É obrigatório manter pelo menos 1 usuário master ativo."}, status=400)
                try:
                    avatar_url = (
                        normalize_avatar_data(body.get("avatar_url"))
                        if "avatar_url" in body
                        else (target["avatar_url"] if "avatar_url" in target.keys() else None)
                    )
                except ValueError as e:
                    return self.send_json({"error": str(e)}, status=400)
                permissions_json = permissions_json_for_role(role, body.get("module_permissions"))
                conn.execute(
                    "UPDATE users SET name = ?, role = ?, module_permissions = ?, avatar_url = ? WHERE id = ? AND company_id = ?",
                    (name, role, permissions_json, avatar_url, user_id, company_id),
                )
                log_audit(conn, "users", "user", user_id, "update", user["id"], {"name": name, "role": role})
                conn.commit()
                return self.send_json({"ok": True})

            if path.startswith("/api/categories/"):
                category_id = parse_category_id(path)
                if not category_id:
                    return self.send_json({"error": "ID de categoria inválido"}, status=400)
                body = parse_json_body(self)
                name = str(body.get("name") or "").strip()
                if not name:
                    return self.send_json({"error": "Nome da categoria é obrigatório."}, status=400)
                description = str(body.get("description") or "").strip()
                status = str(body.get("status") or "active").strip().lower()
                if status not in ("active", "inactive"):
                    return self.send_json({"error": "Status inválido para categoria."}, status=400)
                existing = conn.execute(
                    """
                    SELECT id FROM categories
                    WHERE company_id = ?
                      AND LOWER(TRIM(name)) = LOWER(TRIM(?))
                      AND id <> ?
                    """,
                    (company_id, name, category_id),
                ).fetchone()
                if existing:
                    return self.send_json({"error": "Já existe uma categoria com esse nome."}, status=400)
                conn.execute(
                    """
                    UPDATE categories
                    SET name = ?, description = ?, is_active = ?, updated_by = ?, updated_at = ?
                    WHERE id = ? AND company_id = ?
                    """,
                    (
                        name,
                        description,
                        1 if status == "active" else 0,
                        user["id"],
                        utc_now_iso(),
                        category_id,
                        company_id,
                    ),
                )
                conn.execute("UPDATE products SET category = ? WHERE category_id = ? AND company_id = ?", (name, category_id, company_id))
                log_audit(conn, "products", "category", category_id, "update", user["id"], {"name": name, "status": status})
                conn.commit()
                return self.send_json({"ok": True})

            if path.startswith("/api/products/") and path.endswith("/deactivate"):
                product_id = parse_product_id(path)
                if not product_id:
                    return self.send_json({"error": "ID de produto inválido"}, status=400)
                product = conn.execute(
                    "SELECT id FROM products WHERE id = ? AND company_id = ?",
                    (product_id, company_id),
                ).fetchone()
                if not product:
                    return self.send_json({"error": "Produto não encontrado"}, status=404)
                conn.execute("UPDATE products SET is_active = 0 WHERE id = ? AND company_id = ?", (product_id, company_id))
                log_audit(conn, "products", "product", product_id, "deactivate", user["id"], {})
                conn.commit()
                return self.send_json({"ok": True, "mode": "deactivated"})

            if path.startswith("/api/products/"):
                product_id = parse_product_id(path)
                if not product_id:
                    return self.send_json({"error": "ID de produto inválido"}, status=400)

                product = conn.execute(
                    "SELECT id, stock_qty, category_id FROM products WHERE id = ? AND company_id = ?",
                    (product_id, company_id),
                ).fetchone()
                if not product:
                    return self.send_json({"error": "Produto não encontrado"}, status=404)

                body = parse_json_body(self)
                name = body.get("name", "").strip()
                try:
                    cost_price = float(body.get("cost_price") or 0)
                    desired_margin = float(body.get("desired_margin_percent") or 30)
                except (TypeError, ValueError):
                    return self.send_json({"error": "Valores numéricos inválidos no produto."}, status=400)
                if not name:
                    return self.send_json({"error": "Nome do produto é obrigatório"}, status=400)
                if cost_price < 0 or desired_margin < 0:
                    return self.send_json({"error": "Valores de produto inválidos"}, status=400)
                sku = str(body.get("sku", "") or "").strip()
                barcode = str(body.get("barcode", "") or "").strip()
                if sku:
                    existing_sku = conn.execute(
                        """
                        SELECT id FROM products
                        WHERE company_id = ?
                          AND LOWER(TRIM(COALESCE(sku,''))) = LOWER(TRIM(?))
                          AND id <> ?
                        """,
                        (company_id, sku, product_id),
                    ).fetchone()
                    if existing_sku:
                        return self.send_json({"error": "SKU já cadastrado em outro produto."}, status=400)
                if barcode:
                    existing_barcode = conn.execute(
                        """
                        SELECT id FROM products
                        WHERE company_id = ?
                          AND LOWER(TRIM(COALESCE(barcode,''))) = LOWER(TRIM(?))
                          AND id <> ?
                        """,
                        (company_id, barcode, product_id),
                    ).fetchone()
                    if existing_barcode:
                        return self.send_json({"error": "Código de barras já cadastrado em outro produto."}, status=400)

                category_id = body.get("category_id")
                category_id_value = None
                category_name = ""
                if category_id not in (None, "", 0, "0"):
                    try:
                        category_id_value = int(category_id)
                    except (TypeError, ValueError):
                        return self.send_json({"error": "Categoria inválida."}, status=400)
                    category_row = conn.execute(
                        "SELECT id, name, is_active FROM categories WHERE id = ? AND company_id = ?",
                        (category_id_value, company_id),
                    ).fetchone()
                    if not category_row:
                        return self.send_json({"error": "Categoria não encontrada."}, status=404)
                    if int(category_row["is_active"] or 0) != 1:
                        current_category_id = int(product["category_id"] or 0) if product["category_id"] is not None else 0
                        if current_category_id != category_id_value:
                            return self.send_json({"error": "Categoria inativa não pode ser usada em novos produtos."}, status=400)
                    category_name = category_row["name"] or ""

                conn.execute(
                    """
                    UPDATE products
                    SET sku = ?, barcode = ?, name = ?, category = ?, category_id = ?, brand = ?, unit = ?, description = ?, cost_price = ?, desired_margin_percent = ?, is_active = ?
                    WHERE id = ? AND company_id = ?
                    """,
                    (
                        sku,
                        barcode,
                        name,
                        category_name,
                        category_id_value,
                        str(body.get("brand") or "").strip(),
                        str(body.get("unit") or "un").strip() or "un",
                        (body.get("description") or "").strip(),
                        cost_price,
                        desired_margin,
                        1 if str(body.get("status") or "active").strip().lower() != "inactive" else 0,
                        product_id,
                        company_id,
                    ),
                )

                conn.execute("DELETE FROM product_cost_items WHERE product_id = ? AND company_id = ?", (product_id, company_id))
                costs = body.get("cost_items") or []
                for item in costs:
                    label = (item.get("label") or "").strip()
                    value_type = item.get("value_type", "fixed")
                    try:
                        value = float(item.get("value") or 0)
                    except (TypeError, ValueError):
                        continue
                    if label and value >= 0 and value_type in ("fixed", "percent"):
                        conn.execute(
                            "INSERT INTO product_cost_items (company_id, product_id, label, value_type, value) VALUES (?, ?, ?, ?, ?)",
                            (company_id, product_id, label, value_type, value),
                        )

                log_audit(
                    conn,
                    "products",
                    "product",
                    product_id,
                    "update",
                    user["id"],
                    {"name": name, "sku": sku, "barcode": barcode, "category_id": category_id_value},
                )
                conn.commit()
                return self.send_json({"ok": True})

            self.send_json({"error": "Rota não encontrada"}, status=404)
        except sqlite3.IntegrityError as e:
            self.send_json({"error": f"Erro de integridade: {str(e)}"}, status=400)
        except BadRequestError as e:
            self.send_json({"error": str(e)}, status=400)
        except Exception as e:
            self.send_json({"error": f"Erro interno: {str(e)}"}, status=500)
        finally:
            conn.close()

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query or "")

        conn = db_connection()
        try:
            user = require_auth(self, conn)
            if not user:
                return
            module_key = module_key_for_path(path)
            if module_key and not require_module_permission(self, user, module_key):
                return
            if path.startswith("/api/") and module_key is None:
                return self.send_json({"error": "Rota de API sem módulo mapeado."}, status=403)
            company_id = company_id_from_user(user)
            if company_id <= 0:
                return self.send_json({"error": "Usuário sem empresa vinculada."}, status=400)

            if path.startswith("/api/sales/"):
                sale_id = parse_sale_id(path)
                if not sale_id:
                    return self.send_json({"error": "ID de venda inválido"}, status=400)

                sale_row = conn.execute(
                    """
                    SELECT s.id, s.company_id, s.product_id, s.qty, s.unit_price, s.total, s.created_at, p.name as product_name
                    FROM sales s
                    JOIN products p ON p.id = s.product_id AND p.company_id = s.company_id
                    WHERE s.id = ? AND s.company_id = ?
                    """,
                    (sale_id, company_id),
                ).fetchone()
                if not sale_row:
                    return self.send_json({"error": "Venda não encontrada"}, status=404)

                remove_sale_side_effects(conn, sale_row, company_id=company_id)
                conn.execute("DELETE FROM sales WHERE id = ? AND company_id = ?", (sale_id, company_id))
                log_audit(conn, "sales", "sale", sale_id, "delete", user["id"], {"product_id": sale_row["product_id"], "qty": sale_row["qty"]})
                conn.commit()
                return self.send_json({"ok": True})

            if path.startswith("/api/inventory/movements/"):
                movement_id = parse_movement_id(path)
                if not movement_id:
                    return self.send_json({"error": "ID de movimentação inválido"}, status=400)
                force_delete = str((query.get("force", ["0"])[0] or "0")).strip().lower() in ("1", "true", "yes", "y")

                movement = conn.execute(
                    """
                    SELECT m.id, m.product_id, m.movement_type, m.qty, m.note, m.created_at, m.sale_id, m.purchase_id,
                           p.stock_qty, p.name as product_name
                    FROM inventory_movements m
                    JOIN products p ON p.id = m.product_id AND p.company_id = m.company_id
                    WHERE m.id = ? AND m.company_id = ?
                    """,
                    (movement_id, company_id),
                ).fetchone()
                if not movement:
                    return self.send_json({"error": "Movimentação não encontrada"}, status=404)

                if movement["sale_id"] is not None:
                    linked_sale = conn.execute(
                        """
                        SELECT s.id, s.product_id, s.qty, s.unit_price, s.total, s.created_at, p.name as product_name
                        FROM sales s
                        JOIN products p ON p.id = s.product_id AND p.company_id = s.company_id
                        WHERE s.id = ? AND s.company_id = ?
                        """,
                        (movement["sale_id"], company_id),
                    ).fetchone()
                    if linked_sale:
                        remove_sale_side_effects(conn, linked_sale, company_id=company_id)
                        conn.execute("DELETE FROM sales WHERE id = ? AND company_id = ?", (movement["sale_id"], company_id))
                        log_audit(
                            conn,
                            "sales",
                            "sale",
                            movement["sale_id"],
                            "delete",
                            user["id"],
                            {"source": "inventory_movement_delete", "movement_id": movement_id},
                        )
                        log_audit(
                            conn,
                            "inventory",
                            "movement",
                            movement_id,
                            "delete",
                            user["id"],
                            {"mode": "sale_deleted"},
                        )
                        conn.commit()
                        return self.send_json({
                            "ok": True,
                            "mode": "sale_deleted",
                            "message": "Venda vinculada excluída para manter integridade.",
                        })
                    return self.send_json(
                        {"error": "Movimentação vinculada a venda. Exclua/edite a venda para ajustar este registro."},
                        status=400,
                    )

                if movement["purchase_id"] is not None:
                    return self.send_json(
                        {"error": "Movimentação vinculada a compra. Exclua/edite a compra para ajustar este registro."},
                        status=400,
                    )

                qty = int(movement["qty"] or 0)
                stock_qty = int(movement["stock_qty"] or 0)
                if movement["movement_type"] == "entry":
                    if stock_qty < qty:
                        if force_delete:
                            new_stock = stock_qty - qty
                            conn.execute("UPDATE products SET stock_qty = stock_qty - ? WHERE id = ? AND company_id = ?", (qty, movement["product_id"], company_id))
                            conn.execute("DELETE FROM inventory_movements WHERE id = ? AND company_id = ?", (movement_id, company_id))
                            log_audit(
                                conn,
                                "inventory",
                                "movement",
                                movement_id,
                                "delete",
                                user["id"],
                                {"mode": "forced_negative_stock", "new_stock_qty": new_stock},
                            )
                            conn.commit()
                            return self.send_json({"ok": True, "mode": "forced_negative_stock"})
                        return self.send_json(
                            {"error": "Não é possível excluir esta entrada pois o estoque atual ficaria negativo."},
                            status=400,
                        )
                    conn.execute("UPDATE products SET stock_qty = stock_qty - ? WHERE id = ? AND company_id = ?", (qty, movement["product_id"], company_id))
                else:
                    conn.execute("UPDATE products SET stock_qty = stock_qty + ? WHERE id = ? AND company_id = ?", (qty, movement["product_id"], company_id))

                conn.execute("DELETE FROM inventory_movements WHERE id = ? AND company_id = ?", (movement_id, company_id))
                log_audit(conn, "inventory", "movement", movement_id, "delete", user["id"], {"mode": "normal"})
                conn.commit()
                return self.send_json({"ok": True})

            if path.startswith("/api/finance/entries/"):
                finance_id = parse_finance_entry_id(path)
                if not finance_id:
                    return self.send_json({"error": "ID de lançamento inválido"}, status=400)
                entry = conn.execute(
                    "SELECT id, sale_id, purchase_id FROM financial_entries WHERE id = ? AND company_id = ?",
                    (finance_id, company_id),
                ).fetchone()
                if not entry:
                    return self.send_json({"error": "Lançamento não encontrado"}, status=404)
                if entry["sale_id"] is not None:
                    return self.send_json(
                        {"error": "Lançamento vinculado a venda. Exclua/edite a venda para ajustar este registro."},
                        status=400,
                    )
                if entry["purchase_id"] is not None:
                    return self.send_json(
                        {"error": "Lançamento vinculado a compra. Exclua/edite a compra para ajustar este registro."},
                        status=400,
                    )
                conn.execute("DELETE FROM financial_entries WHERE id = ? AND company_id = ?", (finance_id, company_id))
                log_audit(conn, "finance", "entry", finance_id, "delete", user["id"], {})
                conn.commit()
                return self.send_json({"ok": True})

            if path.startswith("/api/purchases/"):
                purchase_id = parse_purchase_id(path)
                if not purchase_id:
                    return self.send_json({"error": "ID de compra inválido"}, status=400)
                purchase = conn.execute(
                    "SELECT id FROM purchases WHERE id = ? AND company_id = ?",
                    (purchase_id, company_id),
                ).fetchone()
                if not purchase:
                    return self.send_json({"error": "Compra não encontrada"}, status=404)
                items = conn.execute(
                    """
                    SELECT product_id, qty, affects_stock
                    FROM purchase_items
                    WHERE purchase_id = ? AND company_id = ?
                    """,
                    (purchase_id, company_id),
                ).fetchall()
                for item in items:
                    if int(item["affects_stock"] or 0) == 1 and item["product_id"] is not None:
                        product = conn.execute(
                            "SELECT stock_qty FROM products WHERE id = ? AND company_id = ?",
                            (item["product_id"], company_id),
                        ).fetchone()
                        if product and int(product["stock_qty"] or 0) < int(item["qty"] or 0):
                            return self.send_json(
                                {"error": "Não é possível excluir compra: estoque atual ficaria negativo."},
                                status=400,
                            )
                for item in items:
                    if int(item["affects_stock"] or 0) == 1 and item["product_id"] is not None:
                        conn.execute(
                            "UPDATE products SET stock_qty = stock_qty - ? WHERE id = ? AND company_id = ?",
                            (int(item["qty"] or 0), item["product_id"], company_id),
                        )
                conn.execute(
                    "DELETE FROM inventory_movements WHERE purchase_id = ? AND company_id = ?",
                    (purchase_id, company_id),
                )
                conn.execute("DELETE FROM financial_entries WHERE purchase_id = ? AND company_id = ?", (purchase_id, company_id))
                conn.execute("DELETE FROM purchase_items WHERE purchase_id = ? AND company_id = ?", (purchase_id, company_id))
                conn.execute("DELETE FROM purchases WHERE id = ? AND company_id = ?", (purchase_id, company_id))
                log_audit(conn, "purchases", "purchase", purchase_id, "delete", user["id"], {})
                conn.commit()
                return self.send_json({"ok": True})

            if path.startswith("/api/suppliers/"):
                supplier_id = parse_supplier_id(path)
                if not supplier_id:
                    return self.send_json({"error": "ID de fornecedor inválido"}, status=400)
                supplier = conn.execute(
                    "SELECT id FROM suppliers WHERE id = ? AND company_id = ?",
                    (supplier_id, company_id),
                ).fetchone()
                if not supplier:
                    return self.send_json({"error": "Fornecedor não encontrado"}, status=404)
                linked = conn.execute(
                    "SELECT COUNT(*) as c FROM purchases WHERE supplier_id = ? AND company_id = ?",
                    (supplier_id, company_id),
                ).fetchone()["c"]
                if int(linked or 0) > 0:
                    conn.execute("UPDATE suppliers SET is_active = 0 WHERE id = ? AND company_id = ?", (supplier_id, company_id))
                    log_audit(conn, "purchases", "supplier", supplier_id, "deactivate", user["id"], {"reason": "linked_purchases"})
                    conn.commit()
                    return self.send_json({"ok": True, "mode": "deactivated"})
                conn.execute("DELETE FROM suppliers WHERE id = ? AND company_id = ?", (supplier_id, company_id))
                log_audit(conn, "purchases", "supplier", supplier_id, "delete", user["id"], {})
                conn.commit()
                return self.send_json({"ok": True, "mode": "deleted"})

            if path.startswith("/api/cost-calculations/"):
                parts = path.strip("/").split("/")
                calc_id = None
                if len(parts) >= 3:
                    try:
                        calc_id = int(parts[2])
                    except (TypeError, ValueError):
                        calc_id = None
                if not calc_id:
                    return self.send_json({"error": "ID de cálculo inválido"}, status=400)
                conn.execute("DELETE FROM cost_calculations WHERE id = ? AND company_id = ?", (calc_id, company_id))
                conn.commit()
                return self.send_json({"ok": True})

            if path.startswith("/api/categories/"):
                category_id = parse_category_id(path)
                if not category_id:
                    return self.send_json({"error": "ID de categoria inválido"}, status=400)
                row = conn.execute(
                    "SELECT id, name, is_active FROM categories WHERE id = ? AND company_id = ?",
                    (category_id, company_id),
                ).fetchone()
                if not row:
                    return self.send_json({"error": "Categoria não encontrada"}, status=404)
                linked_products = conn.execute(
                    "SELECT COUNT(*) AS c FROM products WHERE category_id = ? AND company_id = ?",
                    (category_id, company_id),
                ).fetchone()["c"]
                if int(linked_products or 0) > 0:
                    conn.execute(
                        """
                        UPDATE categories
                        SET is_active = 0, inactivated_by = ?, inactivated_at = ?, updated_by = ?, updated_at = ?
                        WHERE id = ? AND company_id = ?
                        """,
                        (user["id"], utc_now_iso(), user["id"], utc_now_iso(), category_id, company_id),
                    )
                    log_audit(conn, "products", "category", category_id, "deactivate", user["id"], {"name": row["name"]})
                    conn.commit()
                    return self.send_json({
                        "ok": True,
                        "mode": "deactivated",
                        "message": "Categoria inativada para preservar vínculo com produtos.",
                    })
                conn.execute("DELETE FROM categories WHERE id = ? AND company_id = ?", (category_id, company_id))
                log_audit(conn, "products", "category", category_id, "delete", user["id"], {"name": row["name"]})
                conn.commit()
                return self.send_json({"ok": True, "mode": "deleted"})

            if path.startswith("/api/users/"):
                if user["role"] != "master":
                    return self.send_json({"error": "Somente master pode inativar usuários."}, status=403)
                user_id = parse_user_id(path)
                if not user_id:
                    return self.send_json({"error": "ID de usuário inválido"}, status=400)
                target = conn.execute(
                    "SELECT id, role, is_active FROM users WHERE id = ? AND company_id = ?",
                    (user_id, company_id),
                ).fetchone()
                if not target:
                    return self.send_json({"error": "Usuário não encontrado"}, status=404)
                if int(user["id"]) == int(user_id):
                    return self.send_json({"error": "Não é possível inativar o próprio usuário logado."}, status=400)
                if target["role"] == "master" and int(target["is_active"] or 0) == 1 and count_active_masters(conn, company_id) <= 1:
                    return self.send_json({"error": "É obrigatório manter pelo menos 1 usuário master ativo."}, status=400)
                delete_mode = str((query.get("mode", ["deactivate"])[0] or "deactivate")).strip().lower()
                if delete_mode in ("delete", "hard"):
                    has_history, history_summary = user_has_critical_history(conn, user_id, company_id)
                    if has_history:
                        mode = "deactivated" if int(target["is_active"] or 0) == 1 else "already_inactive"
                        if int(target["is_active"] or 0) == 1:
                            conn.execute("UPDATE users SET is_active = 0 WHERE id = ? AND company_id = ?", (user_id, company_id))
                            conn.execute("DELETE FROM sessions WHERE user_id = ? AND company_id = ?", (user_id, company_id))
                        log_audit(
                            conn,
                            "users",
                            "user",
                            user_id,
                            "deactivate",
                            user["id"],
                            {"reason": "critical_history_on_delete", "history_summary": history_summary},
                        )
                        conn.commit()
                        return self.send_json({
                            "ok": True,
                            "mode": mode,
                            "message": "Usuário possui histórico crítico e foi inativado por segurança.",
                        })
                    conn.execute("DELETE FROM users WHERE id = ? AND company_id = ?", (user_id, company_id))
                    log_audit(conn, "users", "user", user_id, "delete", user["id"], {})
                    conn.commit()
                    return self.send_json({"ok": True, "mode": "deleted"})
                if int(target["is_active"] or 0) != 1:
                    return self.send_json({"ok": True, "mode": "already_inactive"})
                conn.execute("UPDATE users SET is_active = 0 WHERE id = ? AND company_id = ?", (user_id, company_id))
                conn.execute("DELETE FROM sessions WHERE user_id = ? AND company_id = ?", (user_id, company_id))
                log_audit(conn, "users", "user", user_id, "deactivate", user["id"], {})
                conn.commit()
                return self.send_json({"ok": True, "mode": "deactivated"})

            if path.startswith("/api/products/"):
                product_id = parse_product_id(path)
                if not product_id:
                    return self.send_json({"error": "ID de produto inválido"}, status=400)

                product = conn.execute("SELECT id, name FROM products WHERE id = ? AND company_id = ?", (product_id, company_id)).fetchone()
                if not product:
                    return self.send_json({"error": "Produto não encontrado"}, status=404)

                sales_count = conn.execute(
                    "SELECT COUNT(*) as c FROM sales WHERE product_id = ? AND company_id = ?",
                    (product_id, company_id),
                ).fetchone()["c"]
                movement_count = conn.execute(
                    """
                    SELECT COUNT(*) as c
                    FROM inventory_movements
                    WHERE product_id = ? AND company_id = ? AND COALESCE(note, '') <> 'Estoque inicial'
                    """,
                    (product_id, company_id),
                ).fetchone()["c"]
                purchase_item_count = conn.execute(
                    "SELECT COUNT(*) as c FROM purchase_items WHERE product_id = ? AND company_id = ?",
                    (product_id, company_id),
                ).fetchone()["c"]
                calc_count = conn.execute(
                    "SELECT COUNT(*) as c FROM cost_calculations WHERE product_id = ? AND company_id = ?",
                    (product_id, company_id),
                ).fetchone()["c"]
                has_history = (
                    int(sales_count or 0) > 0
                    or int(movement_count or 0) > 0
                    or int(purchase_item_count or 0) > 0
                    or int(calc_count or 0) > 0
                )
                if has_history:
                    conn.execute(
                        "UPDATE products SET is_active = 0 WHERE id = ? AND company_id = ?",
                        (product_id, company_id),
                    )
                    log_audit(conn, "products", "product", product_id, "deactivate", user["id"], {"name": product["name"]})
                    conn.commit()
                    return self.send_json({
                        "ok": True,
                        "mode": "deactivated",
                        "message": "Produto inativado para preservar histórico.",
                    })

                conn.execute("DELETE FROM inventory_movements WHERE product_id = ? AND company_id = ?", (product_id, company_id))
                conn.execute("DELETE FROM product_cost_items WHERE product_id = ? AND company_id = ?", (product_id, company_id))
                conn.execute("DELETE FROM products WHERE id = ? AND company_id = ?", (product_id, company_id))
                log_audit(conn, "products", "product", product_id, "delete", user["id"], {"name": product["name"]})
                conn.commit()
                return self.send_json({"ok": True, "mode": "deleted"})

            self.send_json({"error": "Rota não encontrada"}, status=404)
        except sqlite3.IntegrityError as e:
            self.send_json({"error": f"Erro de integridade: {str(e)}"}, status=400)
        except BadRequestError as e:
            self.send_json({"error": str(e)}, status=400)
        except Exception as e:
            self.send_json({"error": f"Erro interno: {str(e)}"}, status=500)
        finally:
            conn.close()


app = Flask(__name__)
_DB_INITIALIZED = False


def ensure_db_initialized():
    global _DB_INITIALIZED
    if not _DB_INITIALIZED:
        init_db()
        _DB_INITIALIZED = True


class FlaskAdapterHandler(AppHandler):
    def __init__(self, flask_request):
        self._status_code = 200
        self._headers = []
        self._error_message = ""
        self.headers = flask_request.headers
        self.command = flask_request.method.upper()
        self.path = flask_request.full_path if flask_request.query_string else flask_request.path
        self.rfile = BytesIO(flask_request.get_data() or b"")
        self.wfile = BytesIO()

    def send_response(self, code, message=None):
        self._status_code = int(code)

    def send_header(self, keyword, value):
        self._headers.append((str(keyword), str(value)))

    def end_headers(self):
        return

    def send_error(self, code, message=None, explain=None):
        self._status_code = int(code)
        self._headers = [("Content-Type", "text/plain; charset=utf-8")]
        msg = message or "Erro"
        self.wfile = BytesIO(str(msg).encode("utf-8"))

    def log_message(self, format, *args):
        return


def dispatch_legacy_handler(flask_request):
    ensure_db_initialized()
    adapter = FlaskAdapterHandler(flask_request)
    method = adapter.command

    if method == "GET":
        AppHandler.do_GET(adapter)
    elif method == "POST":
        AppHandler.do_POST(adapter)
    elif method == "PUT":
        AppHandler.do_PUT(adapter)
    elif method == "DELETE":
        AppHandler.do_DELETE(adapter)
    elif method == "OPTIONS":
        AppHandler.do_OPTIONS(adapter)
    else:
        return Response("Método não suportado", status=405, content_type="text/plain; charset=utf-8")

    payload = adapter.wfile.getvalue()
    response = Response(payload, status=adapter._status_code)
    for key, value in adapter._headers:
        if key.lower() == "content-length":
            continue
        response.headers.add(key, value)
    return response


@app.route("/")
def home():
    return redirect("/index.html", code=307)


@app.route("/index.html")
def public_index():
    if os.path.exists(os.path.join(PUBLIC_DIR, "index.html")):
        return send_from_directory(PUBLIC_DIR, "index.html")
    if os.path.exists(os.path.join(STATIC_DIR, "index.html")):
        return send_from_directory(STATIC_DIR, "index.html")
    return Response("index.html não encontrado", status=404, content_type="text/plain; charset=utf-8")


@app.route("/<path:path>", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
def legacy_routes(path):
    return dispatch_legacy_handler(request)


def run():
    ensure_db_initialized()
    host = "127.0.0.1"
    port = 8000
    server = HTTPServer((host, port), AppHandler)
    print("Plataforma de Gestão E-commerce")
    print(f"Acesse: http://{host}:{port}")
    print("Login master inicial -> email: master@admin.local | senha: admin123")
    server.serve_forever()


if __name__ == "__main__":
    run()
