import duckdb
import tempfile
from pathlib import Path
from src.models import run_migrations


def test_run_migrations_creates_tracking_table():
    conn = duckdb.connect(":memory:")
    migrations_dir = Path(tempfile.mkdtemp())
    run_migrations(conn, migrations_dir)
    result = conn.execute(
        "SELECT COUNT(*) FROM _migrations_applied"
    ).fetchone()
    assert result[0] == 0
    conn.close()


def test_run_migrations_applies_sql_file():
    conn = duckdb.connect(":memory:")
    migrations_dir = Path(tempfile.mkdtemp())
    sql_file = migrations_dir / "001_test.sql"
    sql_file.write_text("CREATE TABLE test_table (id INTEGER);")
    run_migrations(conn, migrations_dir)
    # Table should exist
    result = conn.execute(
        "SELECT COUNT(*) FROM test_table"
    ).fetchone()
    assert result[0] == 0
    # Migration should be tracked
    applied = conn.execute(
        "SELECT name FROM _migrations_applied"
    ).fetchone()
    assert applied[0] == "001_test.sql"
    conn.close()


def test_run_migrations_is_idempotent():
    conn = duckdb.connect(":memory:")
    migrations_dir = Path(tempfile.mkdtemp())
    sql_file = migrations_dir / "001_test.sql"
    sql_file.write_text("CREATE TABLE test_table (id INTEGER);")
    run_migrations(conn, migrations_dir)
    run_migrations(conn, migrations_dir)  # Should not raise
    result = conn.execute(
        "SELECT COUNT(*) FROM _migrations_applied"
    ).fetchone()
    assert result[0] == 1
    conn.close()


def test_schema_creates_all_tables(db):
    tables = db.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'main'
        ORDER BY table_name
    """).fetchall()
    table_names = [t[0] for t in tables]
    expected = [
        "action_items", "contact_emails", "contacts", "deals",
        "interactions", "notes", "pipeline_stages", "stage_history",
    ]
    for table in expected:
        assert table in table_names, f"Missing table: {table}"


def test_pipeline_stages_seeded(db):
    stages = db.execute(
        "SELECT name, category FROM pipeline_stages ORDER BY sort_order"
    ).fetchall()
    assert len(stages) == 14
    assert stages[0] == ("Responded", "active")
    assert stages[-1] == ("Not a Fit - No Need", "closed")
