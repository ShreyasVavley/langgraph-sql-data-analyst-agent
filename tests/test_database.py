"""
tests/test_database.py
=============================================================================
Automated test suite for database.py (SQLite schema, seeding & security).
=============================================================================
"""

import os
import sqlite3
import pytest
import pandas as pd

import database

TEST_DB_PATH = "test_analytics.db"


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    """Initializes a fresh test database and cleans up after tests."""
    database.init_database(db_path=TEST_DB_PATH, force_recreate=True)
    yield
    database.dispose_engine(TEST_DB_PATH)
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass


def test_tables_exist():
    """Verify all 5 tables exist with rows."""
    meta = database.get_schema_metadata(db_path=TEST_DB_PATH)
    expected_tables = {"categories", "customers", "products", "orders", "order_items"}
    assert expected_tables.issubset(set(meta.keys()))

    for table in expected_tables:
        assert meta[table]["row_count"] > 0, f"Table {table} has 0 rows"


def test_customers_distribution():
    """Verify customer counts and segments."""
    df, duration = database.execute_query(
        "SELECT segment, COUNT(*) as cnt FROM customers GROUP BY segment",
        db_path=TEST_DB_PATH
    )
    assert len(df) == 3
    assert set(df["segment"]) == {"Enterprise", "SMB", "Consumer"}
    assert duration >= 0.0


def test_read_only_security_guardrail():
    """Verify harmful SQL operations are blocked with ValueError."""
    harmful_queries = [
        "DROP TABLE customers;",
        "DELETE FROM orders WHERE order_id = 1001;",
        "UPDATE products SET unit_price = 0;",
        "ALTER TABLE customers ADD COLUMN hacked TEXT;",
        "INSERT INTO categories VALUES (99, 'Hacked', 'None');",
        "TRUNCATE TABLE order_items;"
    ]

    for q in harmful_queries:
        with pytest.raises(ValueError) as excinfo:
            database.execute_query(q, db_path=TEST_DB_PATH)
        assert "not permitted" in str(excinfo.value).lower() or "security" in str(excinfo.value).lower()


def test_schema_string_extraction():
    """Verify schema string extraction contains expected table definitions."""
    schema_str = database.get_schema_string(db_path=TEST_DB_PATH)
    assert "CREATE TABLE customers" in schema_str
    assert "CREATE TABLE orders" in schema_str
    assert "CREATE TABLE order_items" in schema_str
    assert "Example rows from" in schema_str


def test_table_preview():
    """Verify table preview returns correct limit."""
    preview_df = database.get_table_preview("products", limit=3, db_path=TEST_DB_PATH)
    assert len(preview_df) == 3
    assert "product_name" in preview_df.columns

    with pytest.raises(ValueError):
        database.get_table_preview("non_existent_table", limit=3, db_path=TEST_DB_PATH)


def test_db_metrics():
    """Verify high-level metrics calculation."""
    metrics = database.get_db_metrics(db_path=TEST_DB_PATH)
    assert metrics["total_revenue"] > 1000000
    assert metrics["completed_orders"] > 100
    assert metrics["total_customers"] == 60
    assert metrics["total_products"] == 25
    assert metrics["avg_order_value"] > 0


def test_dynamic_sqlalchemy_engine():
    """Verify dynamic SQLAlchemy engine creation, inspection, and execution."""
    # 1. Test build_connection_uri
    pg_uri = database.build_connection_uri("postgresql", "db.example.com", 5432, "my_db", "user1", "pass123")
    assert "postgresql+psycopg2://" in pg_uri
    assert "user1:pass123@db.example.com:5432/my_db" in pg_uri

    mysql_uri = database.build_connection_uri("mysql", "localhost", 3306, "warehouse", "root", "secret")
    assert "mysql+pymysql://" in mysql_uri

    # 2. Test custom engine on SQLite
    engine = database.create_custom_engine(f"sqlite:///{TEST_DB_PATH}")
    ok, msg = database.test_engine_connection(engine)
    assert ok is True
    assert "Found 5 table(s)" in msg

    # 3. Test dynamic inspection
    meta = database.get_engine_schema_metadata(engine)
    assert len(meta) == 5
    assert "customers" in meta
    assert len(meta["customers"]["columns"]) == 6

    # 4. Test dynamic execution
    df, dur = database.execute_engine_query("SELECT customer_id, name FROM customers LIMIT 2", engine)
    assert len(df) == 2
    assert dur >= 0.0


if __name__ == "__main__":
    pytest.main(["-v", "tests/test_database.py"])
