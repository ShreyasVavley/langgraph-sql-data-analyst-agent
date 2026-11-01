"""
database.py
=============================================================================
Dynamic Multi-Database Engine & Schema Inspector (SQLAlchemy 2.0).

Supports:
- Dynamic connection switching (SQLite, PostgreSQL, MySQL, Custom URIs)
- File uploads for custom SQLite .db files
- Dynamic schema introspection using SQLAlchemy `inspect(engine)`
- Dialect-aware DDL extraction (column types, primary keys, foreign keys)
- Safe read-only execution benchmarking with execution time tracking
- Default seeded SQLite database for instant zero-config demonstrations
=============================================================================
"""

import os
import re
import time
import sqlite3
import random
import urllib.parse
import concurrent.futures
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple

import pandas as pd
from sqlalchemy import create_engine, inspect, text, Engine

DEFAULT_DB_PATH = "analytics.db"
_ENGINE_CACHE: Dict[str, Engine] = {}


# =============================================================================
# 1. SQLAlchemy Engine Factory & Connection Management
# =============================================================================

def get_sqlite_engine(db_path: str = DEFAULT_DB_PATH) -> Engine:
    """Returns a cached SQLAlchemy engine for a local SQLite database."""
    global _ENGINE_CACHE
    init_database(db_path)
    normalized_path = os.path.abspath(db_path)
    if normalized_path not in _ENGINE_CACHE:
        _ENGINE_CACHE[normalized_path] = create_engine(
            f"sqlite:///{normalized_path}",
            connect_args={"check_same_thread": False}
        )
    return _ENGINE_CACHE[normalized_path]


def get_default_engine(db_path: str = DEFAULT_DB_PATH) -> Engine:
    """Returns the cached engine for the default local SQLite database."""
    return get_sqlite_engine(db_path)


def dispose_engine(db_path_or_uri: str) -> None:
    """Disposes cached engine connection pool to release file locks on Windows."""
    global _ENGINE_CACHE
    norm = os.path.abspath(db_path_or_uri)
    if norm in _ENGINE_CACHE:
        try:
            _ENGINE_CACHE[norm].dispose()
        except Exception:
            pass
        del _ENGINE_CACHE[norm]


def create_custom_engine(connection_uri: str) -> Engine:
    """
    Creates and returns a new SQLAlchemy Engine from a connection URI.
    Supports SQLite, PostgreSQL (psycopg2/psycopg), MySQL (pymysql), etc.
    """
    # SQLite specific configuration
    if connection_uri.startswith("sqlite"):
        return create_engine(connection_uri, connect_args={"check_same_thread": False})

    # PostgreSQL / MySQL connection pool configuration
    return create_engine(
        connection_uri,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10
    )


def build_connection_uri(
    db_type: str,
    host: str = "localhost",
    port: int = 5432,
    database: str = "analytics",
    username: str = "postgres",
    password: str = ""
) -> str:
    """Constructs a standardized, URL-encoded SQLAlchemy connection string."""
    encoded_user = urllib.parse.quote_plus(username)
    encoded_pass = urllib.parse.quote_plus(password)

    db_lower = db_type.lower()
    if "postgres" in db_lower:
        return f"postgresql+psycopg2://{encoded_user}:{encoded_pass}@{host}:{port}/{database}"
    elif "mysql" in db_lower:
        return f"mysql+pymysql://{encoded_user}:{encoded_pass}@{host}:{port}/{database}"
    elif "sqlite" in db_lower:
        return f"sqlite:///{database}"
    else:
        raise ValueError(f"Unsupported database type: '{db_type}'. Choose PostgreSQL, MySQL, or SQLite.")


def test_engine_connection(engine: Engine) -> Tuple[bool, str]:
    """
    Tests whether the engine can successfully connect and execute a lightweight ping.
    Returns (is_successful, message).
    """
    try:
        with engine.connect() as conn:
            # Universal test query across SQL dialects
            conn.execute(text("SELECT 1"))
        insp = inspect(engine)
        table_count = len(insp.get_table_names())
        dialect = engine.dialect.name
        return True, f"Connected successfully to {dialect.upper()} database. Found {table_count} table(s)."
    except Exception as err:
        return False, str(err)


# =============================================================================
# 2. Dynamic Schema Introspection & Schema RAG (Table Pruning)
# =============================================================================

STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", "aren't",
    "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but", "by",
    "can", "could", "did", "do", "does", "doing", "don't", "down", "during", "each", "few", "for",
    "from", "further", "had", "has", "have", "having", "he", "her", "here", "hers", "herself", "him",
    "himself", "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself", "just", "me", "more",
    "most", "my", "myself", "no", "nor", "not", "now", "of", "off", "on", "once", "only", "or", "other",
    "our", "ours", "ourselves", "out", "over", "own", "same", "she", "should", "so", "some", "such",
    "than", "that", "the", "their", "theirs", "them", "themselves", "then", "there", "these", "they",
    "this", "those", "through", "to", "too", "under", "until", "up", "very", "was", "wasn't", "we",
    "were", "what", "when", "where", "which", "while", "who", "whom", "why", "will", "with", "would",
    "show", "give", "list", "display", "find", "get", "calculate", "tell", "top", "per", "across", "by"
}


def prune_schema_tables(
    engine: Engine,
    query: Optional[str] = None,
    max_tables: int = 15
) -> List[str]:
    """
    Intelligently selects the most relevant tables for a user query when a database
    contains a large number of tables (> max_tables), preserving foreign key relationships.
    If total tables <= max_tables or query is None/empty, returns all table names.
    """
    insp = inspect(engine)
    all_tables = insp.get_table_names()

    if len(all_tables) <= max_tables or not query or not query.strip():
        return all_tables

    words = re.findall(r"[a-zA-Z0-9_]+", query.lower())
    tokens = {w for w in words if len(w) > 2 and w not in STOPWORDS}

    if not tokens:
        return all_tables[:max_tables]

    table_scores: Dict[str, float] = {t: 0.0 for t in all_tables}
    table_fk_map: Dict[str, set] = {t: set() for t in all_tables}

    for t in all_tables:
        t_lower = t.lower()
        # Direct table name matching
        for token in tokens:
            if token == t_lower:
                table_scores[t] += 10.0
            elif token in t_lower or t_lower in token:
                table_scores[t] += 5.0
            elif token.rstrip("s") == t_lower.rstrip("s"):
                table_scores[t] += 8.0

        # Column matching
        try:
            cols = insp.get_columns(t)
            for c in cols:
                c_name = c["name"].lower()
                for token in tokens:
                    if token == c_name:
                        table_scores[t] += 4.0
                    elif token in c_name:
                        table_scores[t] += 2.0
                    elif token.rstrip("s") == c_name.rstrip("s"):
                        table_scores[t] += 3.0
        except Exception:
            pass

        # Foreign keys
        try:
            fks = insp.get_foreign_keys(t)
            for fk in fks:
                ref_tbl = fk.get("referred_table")
                if ref_tbl and ref_tbl in table_fk_map:
                    table_fk_map[t].add(ref_tbl)
                    table_fk_map[ref_tbl].add(t)
        except Exception:
            pass

    # FK affinity propagation: Boost tables directly connected to high-scoring tables
    high_scoring = [t for t, s in table_scores.items() if s > 0]
    for ht in high_scoring:
        for neighbor in table_fk_map.get(ht, set()):
            table_scores[neighbor] += 3.0

    # Sort tables by score descending
    sorted_tables = sorted(all_tables, key=lambda t: (table_scores[t], t), reverse=True)
    selected = set(sorted_tables[:max_tables])

    # Preserve natural original ordering from all_tables for predictability
    return [t for t in all_tables if t in selected]


def get_engine_schema_string(
    engine: Engine,
    sample_rows_count: int = 2,
    user_query: Optional[str] = None,
    max_tables: int = 15
) -> str:
    """
    Dynamically inspects the connected database and returns a rich, structured
    DDL representation with column types, primary keys, foreign keys, and sample rows.
    Automatically adapts to SQLite, PostgreSQL, and MySQL dialects.
    Applies Schema RAG / table pruning when database exceeds max_tables.
    """
    insp = inspect(engine)
    dialect_name = engine.dialect.name.upper()
    all_table_names = insp.get_table_names()

    if not all_table_names:
        return f"-- {dialect_name} Database: Connected successfully, but no user tables were found."

    total_count = len(all_table_names)
    table_names = prune_schema_tables(engine, query=user_query, max_tables=max_tables)
    is_pruned = len(table_names) < total_count

    schema_lines = [
        f"-- {dialect_name} Relational Database Schema Definition",
        f"-- Total Tables Detected: {total_count}",
    ]
    if is_pruned:
        schema_lines.append(f"-- Schema Pruned (Schema RAG): Displaying top {len(table_names)} relevant tables for query context.")
    schema_lines.append("")

    with engine.connect() as conn:
        for t in table_names:
            cols = insp.get_columns(t)
            pk_info = insp.get_pk_constraint(t)
            pk_cols = set(pk_info.get("constrained_columns") or [])
            fk_info = insp.get_foreign_keys(t)

            schema_lines.append(f"CREATE TABLE {t} (")
            col_defs = []
            for col in cols:
                col_name = col["name"]
                col_type = str(col["type"])
                is_pk = " PRIMARY KEY" if col_name in pk_cols else ""
                nullable = "" if col.get("nullable", True) else " NOT NULL"
                col_defs.append(f"    {col_name} {col_type}{is_pk}{nullable}")

            # Add Foreign Key constraints
            for fk in fk_info:
                from_cols = ", ".join(fk["constrained_columns"])
                ref_tbl = fk["referred_table"]
                ref_cols = ", ".join(fk["referred_columns"])
                col_defs.append(f"    FOREIGN KEY ({from_cols}) REFERENCES {ref_tbl} ({ref_cols})")

            schema_lines.append(",\n".join(col_defs))
            schema_lines.append(");")

            # Fetch sample rows
            try:
                # Wrap table name safely
                quoted_table = f'"{t}"' if dialect_name == "POSTGRESQL" else f"`{t}`" if dialect_name == "MYSQL" else t
                sample_query = text(f"SELECT * FROM {quoted_table} LIMIT {sample_rows_count}")
                df_sample = pd.read_sql_query(sample_query, conn)
                if not df_sample.empty:
                    schema_lines.append(f"-- Example rows from '{t}':")
                    for _, r in df_sample.iterrows():
                        schema_lines.append(f"-- Sample: {r.to_dict()}")
            except Exception:
                pass

            schema_lines.append("")

    return "\n".join(schema_lines)


def get_engine_schema_metadata(engine: Engine) -> Dict[str, Any]:
    """
    Returns structured metadata for the Streamlit sidebar schema viewer:
    table names, column details, types, primary keys, and exact row counts.
    """
    insp = inspect(engine)
    table_names = insp.get_table_names()
    dialect_name = engine.dialect.name.upper()
    metadata = {}

    with engine.connect() as conn:
        for t in table_names:
            cols = insp.get_columns(t)
            pk_info = insp.get_pk_constraint(t)
            pk_cols = set(pk_info.get("constrained_columns") or [])

            columns = []
            for c in cols:
                columns.append({
                    "name": c["name"],
                    "type": str(c["type"]),
                    "pk": c["name"] in pk_cols
                })

            # Row count calculation
            row_count = 0
            try:
                quoted = f'"{t}"' if dialect_name == "POSTGRESQL" else f"`{t}`" if dialect_name == "MYSQL" else t
                res = conn.execute(text(f"SELECT COUNT(*) FROM {quoted}"))
                row_count = res.scalar() or 0
            except Exception:
                row_count = -1

            metadata[t] = {
                "columns": columns,
                "row_count": row_count
            }

    return metadata


def get_engine_table_preview(engine: Engine, table_name: str, limit: int = 3) -> pd.DataFrame:
    """Returns a preview DataFrame for a specific table in the connected engine."""
    insp = inspect(engine)
    if table_name not in insp.get_table_names():
        raise ValueError(f"Table '{table_name}' does not exist in the active database.")

    dialect_name = engine.dialect.name.upper()
    quoted = f'"{table_name}"' if dialect_name == "POSTGRESQL" else f"`{table_name}`" if dialect_name == "MYSQL" else table_name

    with engine.connect() as conn:
        df = pd.read_sql_query(text(f"SELECT * FROM {quoted} LIMIT {int(limit)}"), conn)
        return df


def get_engine_metrics(engine: Engine) -> Dict[str, Any]:
    """
    Returns dynamic high-level statistics for the active database engine.
    If default e-commerce tables exist, computes commercial KPIs; otherwise returns structural KPIs.
    """
    insp = inspect(engine)
    tables = insp.get_table_names()
    dialect = engine.dialect.name

    # Check for e-commerce tables
    has_ecommerce = {"orders", "customers", "order_items"}.issubset(set(tables))

    if has_ecommerce:
        with engine.connect() as conn:
            try:
                c_cust = conn.execute(text("SELECT COUNT(*) FROM customers")).scalar() or 0
                c_orders = conn.execute(text("SELECT COUNT(*) FROM orders WHERE status != 'Cancelled'")).scalar() or 0
                rev = conn.execute(text("""
                    SELECT ROUND(SUM(oi.total_price), 2)
                    FROM order_items oi
                    JOIN orders o ON oi.order_id = o.order_id
                    WHERE o.status != 'Cancelled'
                """)).scalar() or 0.0
                c_prod = conn.execute(text("SELECT COUNT(*) FROM products")).scalar() or 0
                aov = round(rev / c_orders, 2) if c_orders > 0 else 0.0

                return {
                    "is_ecommerce": True,
                    "total_revenue": rev,
                    "completed_orders": c_orders,
                    "total_customers": c_cust,
                    "total_products": c_prod,
                    "avg_order_value": aov,
                    "dialect": dialect,
                    "table_count": len(tables)
                }
            except Exception:
                pass

    # Generic database metrics
    total_rows = 0
    with engine.connect() as conn:
        for t in tables[:15]:
            try:
                quoted = f'"{t}"' if dialect == "postgresql" else f"`{t}`" if dialect == "mysql" else t
                cnt = conn.execute(text(f"SELECT COUNT(*) FROM {quoted}")).scalar() or 0
                total_rows += cnt
            except Exception:
                pass

    return {
        "is_ecommerce": False,
        "total_tables": len(tables),
        "total_rows": total_rows,
        "dialect": dialect,
        "tables": tables
    }


def execute_engine_query(
    sql: str,
    engine: Engine,
    timeout_seconds: float = 15.0,
    max_rows: int = 1000
) -> Tuple[pd.DataFrame, float]:
    """
    Executes a read-only query against the active SQLAlchemy Engine,
    enforces safety guardrails, query pagination (LIMIT 1000 clamp),
    and statement execution timeout (15s limit).
    Returns (DataFrame, duration_ms).
    """
    start_time = time.perf_counter()

    # Prevent harmful mutating queries
    stripped = sql.strip().upper()
    forbidden_keywords = [
        "DROP", "DELETE", "TRUNCATE", "ALTER", "INSERT", "UPDATE",
        "REPLACE", "CREATE", "ATTACH", "DETACH", "GRANT", "REVOKE",
        "EXEC", "EXECUTE", "PRAGMA"
    ]
    first_token = stripped.split()[0] if stripped.split() else ""
    if first_token in forbidden_keywords or any(
        f" {kw} " in f" {stripped} "
        for kw in ["DROP TABLE", "DELETE FROM", "UPDATE ", "INSERT INTO", "ALTER TABLE"]
    ):
        raise ValueError(f"Security Alert: Operation '{first_token}' is rejected. Only read-only SELECT queries are allowed.")

    # Pagination / Row Limit Clamping Guardrail
    clean_sql = sql.strip().rstrip(";")
    has_limit = bool(re.search(r"\bLIMIT\s+\d+", clean_sql, re.IGNORECASE))
    is_select = clean_sql.upper().startswith("SELECT") or clean_sql.upper().startswith("WITH")

    if not has_limit and is_select:
        exec_sql = f"{clean_sql}\nLIMIT {max_rows}"
    else:
        exec_sql = clean_sql

    def _run_query():
        with engine.connect() as conn:
            return pd.read_sql_query(text(exec_sql), conn)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_run_query)
        try:
            df = future.result(timeout=timeout_seconds)
        except concurrent.futures.TimeoutError:
            raise TimeoutError(f"Query execution timed out after exceeding {timeout_seconds}s limit.")

    # Ensure DataFrame does not exceed max_rows
    if len(df) > max_rows:
        df = df.iloc[:max_rows].copy()

    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
    return df, round(elapsed_ms, 2)


# =============================================================================
# 3. Default SQLite Initialization & Deterministic Seeder
# =============================================================================

def get_db_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Legacy helper: returns a raw sqlite3 connection."""
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_database(db_path: str = DEFAULT_DB_PATH, force_recreate: bool = False) -> None:
    """Initializes the default local SQLite database with realistic enterprise data."""
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

    if force_recreate and os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass

    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        category_id INTEGER PRIMARY KEY,
        category_name TEXT NOT NULL UNIQUE,
        department TEXT NOT NULL
    );
    """)

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

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_customers_segment_region ON customers(segment, region);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_customer_date ON orders(customer_id, order_date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_order_items_order_prod ON order_items(order_id, product_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);")

    conn.commit()
    _populate_sample_data(conn)
    conn.close()


def _populate_sample_data(conn: sqlite3.Connection) -> None:
    """Populates deterministic synthetic enterprise data."""
    cursor = conn.cursor()
    rng = random.Random(42)

    categories = [
        (1, "Enterprise Software", "Technology"),
        (2, "Hardware & Devices", "Technology"),
        (3, "Cloud Infrastructure", "Technology"),
        (4, "Office & Workstations", "Workplace"),
        (5, "Cybersecurity & Identity", "Security"),
    ]
    cursor.executemany("INSERT INTO categories VALUES (?, ?, ?)", categories)

    products = [
        (101, 1, "ERP Cloud Suite", 12500.00, 3500.00, 100),
        (102, 1, "CRM Intelligence Pro", 4800.00, 1100.00, 150),
        (103, 1, "BI Analytics Studio", 3200.00, 800.00, 200),
        (104, 1, "HR & Payroll Engine", 2100.00, 500.00, 180),
        (105, 1, "Financial Ledger API", 5500.00, 1200.00, 120),
        (201, 2, "UltraBook Developer Edition", 1899.00, 1250.00, 85),
        (202, 2, "4K Ergonomic Studio Monitor", 799.00, 480.00, 140),
        (203, 2, "AI Edge Server Node", 4500.00, 2900.00, 45),
        (204, 2, "Wireless Mechanical Keyboard", 189.00, 95.00, 300),
        (205, 2, "Noise-Cancelling Executive Headset", 349.00, 180.00, 220),
        (301, 3, "Kubernetes Dedicated Cluster", 8500.00, 3100.00, 60),
        (302, 3, "Managed Vector Database Tier", 2400.00, 750.00, 120),
        (303, 3, "High-Throughput Object Store", 1500.00, 420.00, 250),
        (304, 3, "Global CDN & Edge Compute", 1950.00, 600.00, 180),
        (305, 3, "Serverless Compute Pool", 3100.00, 950.00, 140),
        (401, 4, "Motorized Dual-Motor Standing Desk", 950.00, 520.00, 75),
        (402, 4, "Aeron Ergonomic Task Chair", 1200.00, 680.00, 90),
        (403, 4, "Conference Room Smart Display 65-inch", 2499.00, 1600.00, 35),
        (404, 4, "Acoustic Focus Privacy Pod", 4200.00, 2600.00, 20),
        (405, 4, "Docking Station Thunderbolt 4", 280.00, 140.00, 210),
        (501, 5, "Zero-Trust Identity Broker", 6200.00, 1800.00, 80),
        (502, 5, "Next-Gen Firewall Appliance", 3800.00, 2100.00, 55),
        (503, 5, "Endpoint Detection & Response (EDR)", 2900.00, 900.00, 110),
        (504, 5, "Hardware Security Key Pack (50x)", 1500.00, 750.00, 160),
        (505, 5, "Automated Penetration Test Suite", 4900.00, 1300.00, 70),
    ]
    cursor.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?, ?)", products)

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


# =============================================================================
# 4. Backwards Compatibility Wrappers (for existing tests & scripts)
# =============================================================================

def get_schema_string(db_path: str = DEFAULT_DB_PATH, user_query: Optional[str] = None) -> str:
    engine = get_default_engine(db_path)
    return get_engine_schema_string(engine, user_query=user_query)


def get_schema_metadata(db_path: str = DEFAULT_DB_PATH) -> Dict[str, Any]:
    engine = get_default_engine(db_path)
    return get_engine_schema_metadata(engine)


def get_table_preview(table_name: str, limit: int = 5, db_path: str = DEFAULT_DB_PATH) -> pd.DataFrame:
    engine = get_default_engine(db_path)
    return get_engine_table_preview(engine, table_name, limit)


def get_db_metrics(db_path: str = DEFAULT_DB_PATH) -> Dict[str, Any]:
    engine = get_default_engine(db_path)
    return get_engine_metrics(engine)


def execute_query(
    sql: str,
    db_path: str = DEFAULT_DB_PATH,
    timeout_seconds: float = 15.0,
    max_rows: int = 1000
) -> Tuple[pd.DataFrame, float]:
    engine = get_default_engine(db_path)
    return execute_engine_query(sql, engine, timeout_seconds=timeout_seconds, max_rows=max_rows)


if __name__ == "__main__":
    init_database(force_recreate=True)
    engine = get_default_engine()
    print("Testing dynamic SQLAlchemy inspection on default engine:")
    print(get_engine_schema_string(engine)[:500])
    print("\nMetrics:", get_engine_metrics(engine))
    df, dur = execute_engine_query("SELECT customer_id, name FROM customers LIMIT 3", engine)
    print(f"\nSample Query ({dur} ms):\n", df)
