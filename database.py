"""
database.py
=============================================================================
SQLite Database Manager & Synthetic Enterprise Analytics Engine.

Provides:
- Fully normalized relational schema (Categories, Customers, Products, Orders, Order Items)
- Deterministic synthetic dataset (60 customers, 25 products, 160 orders, 450 items)
- Safe read-only SQL query execution with runtime benchmarking
- Dynamic DDL & sample data extraction for LLM prompt context
- Metadata & table preview utilities for Streamlit UI inspection
=============================================================================
"""

import os
import sqlite3
import random
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import pandas as pd

DEFAULT_DB_PATH = "analytics.db"


def get_db_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Creates and returns a connection to the SQLite database."""
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_database(db_path: str = DEFAULT_DB_PATH, force_recreate: bool = False) -> None:
    """
    Initializes the SQLite database with rich synthetic enterprise data
    if it does not exist or if force_recreate is True.
    """
    if os.path.exists(db_path) and not force_recreate:
        try:
            conn = get_db_connection(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='order_items'")
            has_items = cursor.fetchone()[0] > 0
            conn.close()
            if has_items:
                return
        except Exception:
            pass

    # Remove existing db file if forced
    if force_recreate and os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass

    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # Enable foreign keys
    cursor.execute("PRAGMA foreign_keys = ON;")

    # 1. Categories Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        category_id INTEGER PRIMARY KEY,
        category_name TEXT NOT NULL UNIQUE,
        department TEXT NOT NULL
    );
    """)

    # 2. Customers Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        customer_id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        segment TEXT NOT NULL CHECK(segment IN ('Enterprise', 'SMB', 'Consumer')),
        region TEXT NOT NULL CHECK(region IN ('North America', 'Europe', 'Asia-Pacific', 'Latin America')),
        signup_date DATE NOT NULL
    );
    """)

    # 3. Products Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        product_id INTEGER PRIMARY KEY,
        category_id INTEGER NOT NULL,
        product_name TEXT NOT NULL,
        unit_price REAL NOT NULL,
        cost_price REAL NOT NULL,
        stock_quantity INTEGER NOT NULL,
        FOREIGN KEY (category_id) REFERENCES categories (category_id)
    );
    """)

    # 4. Orders Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        order_id INTEGER PRIMARY KEY,
        customer_id INTEGER NOT NULL,
        order_date DATE NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('Completed', 'Shipped', 'Pending', 'Cancelled')),
        payment_method TEXT NOT NULL CHECK(payment_method IN ('Credit Card', 'Wire Transfer', 'ACH', 'PayPal')),
        discount_percent REAL NOT NULL DEFAULT 0.0,
        shipping_cost REAL NOT NULL DEFAULT 0.0,
        FOREIGN KEY (customer_id) REFERENCES customers (customer_id)
    );
    """)

    # 5. Order Items Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS order_items (
        item_id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL CHECK(quantity > 0),
        unit_price REAL NOT NULL,
        total_price REAL NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders (order_id),
        FOREIGN KEY (product_id) REFERENCES products (product_id)
    );
    """)

    # Create Indexes for Query Optimization
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_customers_segment_region ON customers(segment, region);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_customer_date ON orders(customer_id, order_date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_order_items_order_prod ON order_items(order_id, product_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);")

    conn.commit()

    # Seed data
    _populate_sample_data(conn)
    conn.close()


def _populate_sample_data(conn: sqlite3.Connection) -> None:
    """Populates realistic, deterministic e-commerce & enterprise data."""
    cursor = conn.cursor()
    rng = random.Random(42)

    # Categories Data
    categories = [
        (1, "Enterprise Software", "Technology"),
        (2, "Hardware & Devices", "Technology"),
        (3, "Cloud Infrastructure", "Technology"),
        (4, "Office & Workstations", "Workplace"),
        (5, "Cybersecurity & Identity", "Security"),
    ]
    cursor.executemany("INSERT INTO categories VALUES (?, ?, ?)", categories)

    # Products Data (25 items)
    products = [
        # Enterprise Software
        (101, 1, "ERP Cloud Suite", 12500.00, 3500.00, 100),
        (102, 1, "CRM Intelligence Pro", 4800.00, 1100.00, 150),
        (103, 1, "BI Analytics Studio", 3200.00, 800.00, 200),
        (104, 1, "HR & Payroll Engine", 2100.00, 500.00, 180),
        (105, 1, "Financial Ledger API", 5500.00, 1200.00, 120),
        # Hardware & Devices
        (201, 2, "UltraBook Developer Edition", 1899.00, 1250.00, 85),
        (202, 2, "4K Ergonomic Studio Monitor", 799.00, 480.00, 140),
        (203, 2, "AI Edge Server Node", 4500.00, 2900.00, 45),
        (204, 2, "Wireless Mechanical Keyboard", 189.00, 95.00, 300),
        (205, 2, "Noise-Cancelling Executive Headset", 349.00, 180.00, 220),
        # Cloud Infrastructure
        (301, 3, "Kubernetes Dedicated Cluster", 8500.00, 3100.00, 60),
        (302, 3, "Managed Vector Database Tier", 2400.00, 750.00, 120),
        (303, 3, "High-Throughput Object Store", 1500.00, 420.00, 250),
        (304, 3, "Global CDN & Edge Compute", 1950.00, 600.00, 180),
        (305, 3, "Serverless Compute Pool", 3100.00, 950.00, 140),
        # Office & Workstations
        (401, 4, "Motorized Dual-Motor Standing Desk", 950.00, 520.00, 75),
        (402, 4, "Aeron Ergonomic Task Chair", 1200.00, 680.00, 90),
        (403, 4, "Conference Room Smart Display 65-inch", 2499.00, 1600.00, 35),
        (404, 4, "Acoustic Focus Privacy Pod", 4200.00, 2600.00, 20),
        (405, 4, "Docking Station Thunderbolt 4", 280.00, 140.00, 210),
        # Cybersecurity & Identity
        (501, 5, "Zero-Trust Identity Broker", 6200.00, 1800.00, 80),
        (502, 5, "Next-Gen Firewall Appliance", 3800.00, 2100.00, 55),
        (503, 5, "Endpoint Detection & Response (EDR)", 2900.00, 900.00, 110),
        (504, 5, "Hardware Security Key Pack (50x)", 1500.00, 750.00, 160),
        (505, 5, "Automated Penetration Test Suite", 4900.00, 1300.00, 70),
    ]
    cursor.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?, ?)", products)

    # Customers Data (60 customers)
    customer_first_names = [
        "Alex", "David", "Elena", "Sophia", "Marcus", "Emily", "Liam", "Olivia",
        "Vikram", "Chloe", "Mateo", "Priya", "Carlos", "Aria", "Ethan", "Fatima",
        "Lucas", "Hannah", "Julian", "Zoe"
    ]
    customer_last_names = [
        "Vance", "Mercer", "Rostova", "Patel", "Chen", "Sterling", "Nakamura", "Novak",
        "Kim", "Dubois", "Santos", "Goldman", "Fischer", "Larsson", "O'Connor", "Sinclair",
        "Al-Mansoor", "Zhao", "Lindqvist", "Kovacs"
    ]
    company_prefixes = [
        "Apex", "Quantum", "Nexus", "Vertex", "Cipher", "Aether", "Omni", "Hyperion",
        "Strata", "Vanguard", "Horizon", "Pinnacle", "Solaria", "Terran", "Echo"
    ]
    company_suffixes = [
        "Enterprises", "Dynamics", "Technologies", "Labs", "Systems", "Global", "Analytics",
        "Solutions", "Networks", "Capital"
    ]

    segments = ["Enterprise", "SMB", "Consumer"]
    segment_weights = [0.35, 0.45, 0.20]

    regions = ["North America", "Europe", "Asia-Pacific", "Latin America"]
    region_weights = [0.45, 0.30, 0.18, 0.07]

    customers = []
    base_signup = datetime(2023, 1, 15)

    for cid in range(1, 61):
        seg = rng.choices(segments, weights=segment_weights, k=1)[0]
        reg = rng.choices(regions, weights=region_weights, k=1)[0]
        signup_dt = base_signup + timedelta(days=rng.randint(0, 700))
        signup_str = signup_dt.strftime("%Y-%m-%d")

        if seg in ["Enterprise", "SMB"]:
            name = f"{rng.choice(company_prefixes)} {rng.choice(company_suffixes)}"
            domain = name.lower().replace(" ", "").replace("-", "") + ".com"
            email = f"procurement@{domain}"
        else:
            fn = rng.choice(customer_first_names)
            ln = rng.choice(customer_last_names)
            name = f"{fn} {ln}"
            email = f"{fn.lower()}.{ln.lower()}{rng.randint(10, 99)}@example.com"

        email = f"c{cid}_{email}"
        customers.append((cid, name, email, seg, reg, signup_str))

    cursor.executemany("INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?)", customers)

    # Orders & Order Items Data (160 orders, ~450 items)
    statuses = ["Completed", "Shipped", "Pending", "Cancelled"]
    status_weights = [0.75, 0.15, 0.06, 0.04]

    payment_methods = ["Credit Card", "Wire Transfer", "ACH", "PayPal"]
    payment_weights = [0.45, 0.30, 0.15, 0.10]

    orders = []
    order_items = []
    item_counter = 1

    start_date = datetime(2024, 1, 10)
    end_date = datetime(2026, 3, 15)
    days_range = (end_date - start_date).days

    for oid in range(1001, 1161):
        cid = rng.randint(1, 60)
        order_dt = start_date + timedelta(days=rng.randint(0, days_range))
        order_str = order_dt.strftime("%Y-%m-%d")

        status = rng.choices(statuses, weights=status_weights, k=1)[0]
        pay_method = rng.choices(payment_methods, weights=payment_weights, k=1)[0]
        discount = rng.choice([0.0, 0.0, 0.05, 0.10, 0.15, 0.20])
        shipping = rng.choice([0.0, 15.00, 25.00, 50.00, 120.00])

        orders.append((oid, cid, order_str, status, pay_method, discount, shipping))

        num_items = rng.randint(1, 5)
        chosen_products = rng.sample(products, num_items)

        for prod in chosen_products:
            pid = prod[0]
            price = prod[3]
            qty = rng.randint(1, 8) if prod[1] not in [1, 3] else rng.randint(1, 3)
            tot = round(qty * price, 2)
            order_items.append((item_counter, oid, pid, qty, price, tot))
            item_counter += 1

    cursor.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?)", orders)
    cursor.executemany("INSERT INTO order_items VALUES (?, ?, ?, ?, ?, ?)", order_items)

    conn.commit()


def get_schema_string(db_path: str = DEFAULT_DB_PATH) -> str:
    """
    Returns clean, comprehensive DDL statements and sample rows for LLM prompting.
    """
    init_database(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
    tables = cursor.fetchall()

    schema_lines = ["-- SQLite Database Schema Definition"]
    for table_name, sql in tables:
        schema_lines.append(f"\n{sql};")

        cursor.execute(f"SELECT * FROM {table_name} LIMIT 2")
        rows = cursor.fetchall()
        cursor.execute(f"PRAGMA table_info({table_name})")
        col_names = [col[1] for col in cursor.fetchall()]

        if rows:
            schema_lines.append(f"-- Example rows from '{table_name}':")
            schema_lines.append(f"-- Columns: {', '.join(col_names)}")
            for r in rows:
                schema_lines.append(f"-- Sample: {dict(zip(col_names, r))}")

    conn.close()
    return "\n".join(schema_lines)


def get_schema_metadata(db_path: str = DEFAULT_DB_PATH) -> Dict[str, Any]:
    """
    Returns structured metadata of all tables, columns, and row counts
    for Streamlit sidebar visual inspection.
    """
    init_database(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
    table_names = [row[0] for row in cursor.fetchall()]

    metadata = {}
    for t in table_names:
        cursor.execute(f"PRAGMA table_info({t})")
        columns = [{"name": c[1], "type": c[2], "pk": bool(c[5])} for c in cursor.fetchall()]
        cursor.execute(f"SELECT COUNT(*) FROM {t}")
        count = cursor.fetchone()[0]
        metadata[t] = {
            "columns": columns,
            "row_count": count
        }

    conn.close()
    return metadata


def get_table_preview(table_name: str, limit: int = 5, db_path: str = DEFAULT_DB_PATH) -> pd.DataFrame:
    """Returns a preview DataFrame of the requested table."""
    init_database(db_path)
    conn = get_db_connection(db_path)
    try:
        # Validate table name to avoid injection
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        if not cursor.fetchone():
            raise ValueError(f"Table '{table_name}' does not exist.")
        df = pd.read_sql_query(f"SELECT * FROM {table_name} LIMIT {int(limit)}", conn)
        return df
    finally:
        conn.close()


def get_db_metrics(db_path: str = DEFAULT_DB_PATH) -> Dict[str, Any]:
    """Returns high-level business intelligence metrics from the database."""
    init_database(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM customers")
        total_customers = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM orders WHERE status != 'Cancelled'")
        completed_orders = cursor.fetchone()[0]

        cursor.execute("""
            SELECT ROUND(SUM(oi.total_price), 2)
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.order_id
            WHERE o.status != 'Cancelled'
        """)
        total_revenue = cursor.fetchone()[0] or 0.0

        cursor.execute("SELECT COUNT(*) FROM products")
        total_products = cursor.fetchone()[0]

        avg_order_value = round(total_revenue / completed_orders, 2) if completed_orders > 0 else 0.0

        return {
            "total_revenue": total_revenue,
            "completed_orders": completed_orders,
            "total_customers": total_customers,
            "total_products": total_products,
            "avg_order_value": avg_order_value
        }
    finally:
        conn.close()


def execute_query(sql: str, db_path: str = DEFAULT_DB_PATH) -> Tuple[pd.DataFrame, float]:
    """
    Executes a SQL query against SQLite, enforces safety guardrails,
    and returns (DataFrame, execution_duration_ms).
    Raises Exception on syntax or execution failure.
    """
    start_time = time.perf_counter()
    conn = get_db_connection(db_path)
    try:
        # Prevent harmful or mutating queries
        stripped = sql.strip().upper()
        forbidden_keywords = [
            "DROP", "DELETE", "TRUNCATE", "ALTER", "INSERT", "UPDATE",
            "REPLACE", "CREATE", "ATTACH", "DETACH", "PRAGMA"
        ]
        first_token = stripped.split()[0] if stripped.split() else ""
        if first_token in forbidden_keywords or any(f" {kw} " in f" {stripped} " for kw in ["DROP TABLE", "DELETE FROM", "UPDATE "]):
            raise ValueError(f"Security Alert: Mutating operation '{first_token}' is not permitted. Only read-only SELECT queries are allowed.")

        df = pd.read_sql_query(sql, conn)
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        return df, round(elapsed_ms, 2)
    finally:
        conn.close()


if __name__ == "__main__":
    init_database(force_recreate=True)
    print("Database initialized successfully.")
    metrics = get_db_metrics()
    print("DB Metrics:", metrics)
    df, duration = execute_query("SELECT c.segment, COUNT(o.order_id) as orders FROM customers c JOIN orders o ON c.customer_id = o.customer_id GROUP BY c.segment")
    print(f"Sample Query ({duration}ms):\n", df)
