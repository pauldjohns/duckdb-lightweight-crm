import pytest
import duckdb
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).parent.parent / "db" / "migrations"


@pytest.fixture
def db():
    """In-memory DuckDB with all migrations applied."""
    conn = duckdb.connect(":memory:")
    for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
        conn.execute(sql_file.read_text())
    yield conn
    conn.close()
