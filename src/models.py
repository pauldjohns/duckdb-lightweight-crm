import subprocess

import duckdb
from pathlib import Path


def _find_repo_root():
    """Resolve the main git repo root, even when running inside a worktree."""
    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True, text=True, check=True,
        )
        # First line is always the main worktree
        return Path(result.stdout.split("\n")[0].replace("worktree ", ""))
    except Exception:
        return Path(__file__).parent.parent


_REPO_ROOT = _find_repo_root()
DEFAULT_DB_PATH = _REPO_ROOT / "db" / "crm.duckdb"
DEFAULT_MIGRATIONS_DIR = _REPO_ROOT / "db" / "migrations"


def get_connection(db_path=None):
    """Return a DuckDB connection."""
    return duckdb.connect(str(db_path or DEFAULT_DB_PATH))


def run_migrations(conn, migrations_dir=None):
    """Run all pending SQL migrations in alphabetical order."""
    migrations_dir = Path(migrations_dir or DEFAULT_MIGRATIONS_DIR)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS _migrations_applied (
            name VARCHAR PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT now()
        )
    """)
    applied = {
        row[0]
        for row in conn.execute("SELECT name FROM _migrations_applied").fetchall()
    }
    for sql_file in sorted(migrations_dir.glob("*.sql")):
        if sql_file.name not in applied:
            conn.execute(sql_file.read_text())
            conn.execute(
                "INSERT INTO _migrations_applied (name) VALUES (?)",
                [sql_file.name],
            )


def to_dict(result):
    """Convert a single DuckDB result row to a dict."""
    row = result.fetchone()
    if row is None:
        return None
    return dict(zip([desc[0] for desc in result.description], row))


def to_dicts(result):
    """Convert DuckDB result rows to a list of dicts."""
    rows = result.fetchall()
    if not rows:
        return []
    return [dict(zip([desc[0] for desc in result.description], row)) for row in rows]
