# Lightweight CRM Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local-first, CLI-driven CRM on DuckDB and Python that replaces a manual Coda table, with automated MCP integrations and a password-gated Streamlit dashboard.

**Architecture:** DuckDB (embedded, local) stores all CRM data. Python modules provide CRUD, queries, and integration helpers — Claude Code orchestrates via natural language. Parquet exports are committed to git; Streamlit Cloud reads them for the dashboard. MCP integrations (Granola, Gmail, Calendar) sync data for known contacts.

**Tech Stack:** Python 3.11+, DuckDB >= 1.0.0, Streamlit, pandas, pytest

---

## File Structure

```
lightweight-crm/
├── src/
│   ├── __init__.py
│   ├── models.py           # get_connection(), run_migrations(), result helpers
│   ├── crud.py             # All CRUD operations (contacts, deals, interactions, etc.)
│   ├── queries.py          # Reporting and analytical queries
│   ├── import_csv.py       # Coda CSV importer with validation
│   ├── integrations.py     # Helpers for structuring Granola/Gmail/Calendar data
│   └── export.py           # Export tables to Parquet for dashboard
├── dashboard/
│   └── app.py              # Streamlit dashboard (password-gated, reads Parquet)
├── data/
│   └── exports/
│       └── .gitkeep        # Parquet files land here (tracked in git)
├── db/
│   ├── migrations/
│   │   └── 001_initial_schema.sql
│   └── .gitkeep            # crm.duckdb lives here (gitignored)
├── scripts/
│   └── init_db.py          # CLI entry point for database initialization
├── tests/
│   ├── __init__.py
│   ├── conftest.py         # db fixture (in-memory DuckDB with migrations)
│   ├── test_models.py
│   ├── test_crud_contacts.py
│   ├── test_crud_deals.py
│   ├── test_crud_interactions.py
│   ├── test_crud_misc.py   # action_items + notes
│   ├── test_queries.py
│   ├── test_export.py
│   ├── test_import_csv.py
│   └── test_integrations.py
├── requirements.txt
├── .gitignore
├── .env.example
└── CLAUDE.md
```

**Key design decisions locked in here:**
- `models.py` owns connection management AND result-to-dict helpers (shared by crud.py and queries.py)
- CRUD functions take a `conn` parameter — makes testing trivial (pass in-memory DB)
- One test file per CRUD domain — keeps test files focused and parallelizable
- Dashboard reads Parquet via DuckDB's in-process reader — no database file needed on Streamlit Cloud

---

## Phase 1: Foundation

### Task 1: Project Scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `src/__init__.py`
- Create: `tests/__init__.py`
- Create: `db/.gitkeep`
- Create: `data/exports/.gitkeep`

- [ ] **Step 1: Initialize git repo**

Run: `git init`

- [ ] **Step 2: Create requirements.txt**

```
duckdb>=1.0.0
pandas>=2.0.0
streamlit>=1.30.0
pytest>=8.0.0
```

- [ ] **Step 3: Create .gitignore**

```
# DuckDB
db/crm.duckdb
db/crm.duckdb.wal

# Python
__pycache__/
*.pyc
.pytest_cache/
*.egg-info/

# Environment
.env
.venv/
venv/
```

- [ ] **Step 4: Create .env.example**

```
# Streamlit Cloud dashboard password (set in Streamlit secrets, not here)
DASHBOARD_PASSWORD=changeme
```

- [ ] **Step 5: Create empty __init__.py and .gitkeep files**

```bash
touch src/__init__.py tests/__init__.py db/.gitkeep data/exports/.gitkeep
```

- [ ] **Step 6: Install dependencies**

Run: `pip install -r requirements.txt`

- [ ] **Step 7: Commit**

```bash
git add requirements.txt .gitignore .env.example src/__init__.py tests/__init__.py db/.gitkeep data/exports/.gitkeep
git commit -m "chore: scaffold project structure"
```

---

### Task 2: Migration System

**Files:**
- Create: `src/models.py`
- Create: `scripts/init_db.py`
- Create: `tests/conftest.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write failing test for run_migrations**

```python
# tests/test_models.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.models'`

- [ ] **Step 3: Implement models.py**

```python
# src/models.py
import duckdb
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).parent.parent / "db" / "crm.duckdb"
DEFAULT_MIGRATIONS_DIR = Path(__file__).parent.parent / "db" / "migrations"


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
```

- [ ] **Step 4: Create scripts/init_db.py**

```python
# scripts/init_db.py
from src.models import get_connection, run_migrations, DEFAULT_DB_PATH


def main():
    conn = get_connection()
    run_migrations(conn)
    conn.close()
    print(f"Database initialized at {DEFAULT_DB_PATH}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Create test conftest.py**

```python
# tests/conftest.py
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
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_models.py -v`
Expected: 3 passed

- [ ] **Step 7: Commit**

```bash
git add src/models.py scripts/init_db.py tests/conftest.py tests/test_models.py
git commit -m "feat: add migration system and test infrastructure"
```

---

### Task 3: Initial Schema

**Files:**
- Create: `db/migrations/001_initial_schema.sql`
- Modify: `tests/test_models.py` (add schema verification test)

- [ ] **Step 1: Write failing test for schema tables**

Add to `tests/test_models.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py::test_schema_creates_all_tables -v`
Expected: FAIL — no migration files exist yet, conftest finds no SQL to run

- [ ] **Step 3: Create the schema migration**

```sql
-- db/migrations/001_initial_schema.sql

-- Reference table: pipeline stages
CREATE TABLE pipeline_stages (
    name VARCHAR PRIMARY KEY,
    category VARCHAR NOT NULL,
    sort_order INTEGER NOT NULL
);

INSERT INTO pipeline_stages (name, category, sort_order) VALUES
    ('Responded', 'active', 1),
    ('Call Scheduled', 'active', 2),
    ('Discovery & Demo', 'active', 3),
    ('Evaluation', 'active', 4),
    ('Committed', 'active', 5),
    ('Referral Partner', 'active', 6),
    ('Reconnect later', 'paused', 100),
    ('Interest / Blocked - Red Tape (Org)', 'paused', 101),
    ('Interest / Blocked - internal process', 'paused', 102),
    ('Went Dark', 'closed', 200),
    ('No Show', 'closed', 201),
    ('Not a Fit - ICP Mismatch', 'closed', 202),
    ('Not a Fit - Tire Kicker', 'closed', 203),
    ('Not a Fit - No Need', 'closed', 204);

-- Contacts
CREATE SEQUENCE contacts_id_seq START 1;
CREATE TABLE contacts (
    id INTEGER DEFAULT nextval('contacts_id_seq'),
    name VARCHAR NOT NULL,
    company VARCHAR,
    title VARCHAR,
    linkedin_url VARCHAR,
    last_contact_date DATE,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now(),
    PRIMARY KEY (id)
);

-- Contact emails (multiple per contact for integration matching)
CREATE SEQUENCE contact_emails_id_seq START 1;
CREATE TABLE contact_emails (
    id INTEGER DEFAULT nextval('contact_emails_id_seq'),
    contact_id INTEGER NOT NULL REFERENCES contacts(id),
    email VARCHAR NOT NULL UNIQUE,
    is_primary BOOLEAN DEFAULT false,
    PRIMARY KEY (id)
);

-- Deals
CREATE SEQUENCE deals_id_seq START 1;
CREATE TABLE deals (
    id INTEGER DEFAULT nextval('deals_id_seq'),
    contact_id INTEGER NOT NULL REFERENCES contacts(id),
    name VARCHAR NOT NULL,
    stage VARCHAR NOT NULL REFERENCES pipeline_stages(name),
    value DECIMAL(12, 2),
    expected_close DATE,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now(),
    PRIMARY KEY (id)
);

-- Interactions
CREATE SEQUENCE interactions_id_seq START 1;
CREATE TABLE interactions (
    id INTEGER DEFAULT nextval('interactions_id_seq'),
    contact_id INTEGER NOT NULL REFERENCES contacts(id),
    deal_id INTEGER REFERENCES deals(id),
    type VARCHAR NOT NULL,
    summary TEXT,
    next_connect_date DATE,
    source VARCHAR DEFAULT 'manual',
    occurred_at TIMESTAMP DEFAULT now(),
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now(),
    PRIMARY KEY (id)
);

-- Action items (per-item tracking from interactions)
CREATE SEQUENCE action_items_id_seq START 1;
CREATE TABLE action_items (
    id INTEGER DEFAULT nextval('action_items_id_seq'),
    interaction_id INTEGER NOT NULL REFERENCES interactions(id),
    description TEXT NOT NULL,
    owner VARCHAR,
    due_date DATE,
    completed BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT now(),
    PRIMARY KEY (id)
);

-- Notes (persistent context about contacts)
CREATE SEQUENCE notes_id_seq START 1;
CREATE TABLE notes (
    id INTEGER DEFAULT nextval('notes_id_seq'),
    contact_id INTEGER NOT NULL REFERENCES contacts(id),
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT now(),
    PRIMARY KEY (id)
);

-- Stage history (tracks every deal stage change)
CREATE SEQUENCE stage_history_id_seq START 1;
CREATE TABLE stage_history (
    id INTEGER DEFAULT nextval('stage_history_id_seq'),
    deal_id INTEGER NOT NULL REFERENCES deals(id),
    from_stage VARCHAR,
    to_stage VARCHAR NOT NULL REFERENCES pipeline_stages(name),
    changed_at TIMESTAMP DEFAULT now(),
    PRIMARY KEY (id)
);
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_models.py -v`
Expected: 5 passed (3 migration tests + 2 schema tests)

- [ ] **Step 5: Commit**

```bash
git add db/migrations/001_initial_schema.sql tests/test_models.py
git commit -m "feat: add initial schema with all tables and pipeline stages"
```

---

## Phase 2: Data Operations

### Task 4: Contacts & Contact Emails CRUD

**Files:**
- Create: `src/crud.py`
- Create: `tests/test_crud_contacts.py`

- [ ] **Step 1: Write failing tests for contact CRUD**

```python
# tests/test_crud_contacts.py
import pytest
from src import crud


class TestCreateContact:
    def test_creates_with_required_fields(self, db):
        contact = crud.create_contact(db, name="Jane Doe")
        assert contact["name"] == "Jane Doe"
        assert contact["id"] is not None
        assert contact["company"] is None

    def test_creates_with_all_fields(self, db):
        contact = crud.create_contact(
            db,
            name="Jane Doe",
            company="Acme Corp",
            title="VP Engineering",
            linkedin_url="https://linkedin.com/in/janedoe",
        )
        assert contact["company"] == "Acme Corp"
        assert contact["title"] == "VP Engineering"


class TestGetContact:
    def test_returns_existing_contact(self, db):
        created = crud.create_contact(db, name="Jane Doe")
        fetched = crud.get_contact(db, created["id"])
        assert fetched["name"] == "Jane Doe"

    def test_raises_for_missing_contact(self, db):
        with pytest.raises(ValueError, match="not found"):
            crud.get_contact(db, 9999)


class TestGetAllContacts:
    def test_returns_all_contacts_sorted(self, db):
        crud.create_contact(db, name="Zara")
        crud.create_contact(db, name="Alice")
        contacts = crud.get_all_contacts(db)
        assert len(contacts) == 2
        assert contacts[0]["name"] == "Alice"


class TestUpdateContact:
    def test_updates_specified_fields(self, db):
        contact = crud.create_contact(db, name="Jane Doe")
        updated = crud.update_contact(db, contact["id"], company="New Corp")
        assert updated["company"] == "New Corp"
        assert updated["name"] == "Jane Doe"

    def test_rejects_invalid_fields(self, db):
        contact = crud.create_contact(db, name="Jane Doe")
        with pytest.raises(ValueError, match="No valid fields"):
            crud.update_contact(db, contact["id"], fake_field="bad")


class TestDeleteContact:
    def test_deletes_contact_and_related(self, db):
        contact = crud.create_contact(db, name="Jane Doe")
        crud.add_contact_email(db, contact["id"], "jane@acme.com")
        crud.delete_contact(db, contact["id"])
        with pytest.raises(ValueError, match="not found"):
            crud.get_contact(db, contact["id"])

    def test_raises_for_missing_contact(self, db):
        with pytest.raises(ValueError, match="not found"):
            crud.delete_contact(db, 9999)


class TestContactEmails:
    def test_add_email(self, db):
        contact = crud.create_contact(db, name="Jane Doe")
        email = crud.add_contact_email(db, contact["id"], "jane@acme.com")
        assert email["email"] == "jane@acme.com"
        assert email["is_primary"] is False

    def test_add_primary_email(self, db):
        contact = crud.create_contact(db, name="Jane Doe")
        email = crud.add_contact_email(
            db, contact["id"], "jane@acme.com", is_primary=True
        )
        assert email["is_primary"] is True

    def test_set_primary_clears_others(self, db):
        contact = crud.create_contact(db, name="Jane Doe")
        e1 = crud.add_contact_email(
            db, contact["id"], "jane@acme.com", is_primary=True
        )
        e2 = crud.add_contact_email(
            db, contact["id"], "jane@gmail.com", is_primary=True
        )
        emails = crud.get_contact_emails(db, contact["id"])
        primary = [e for e in emails if e["is_primary"]]
        assert len(primary) == 1
        assert primary[0]["email"] == "jane@gmail.com"

    def test_set_primary_email_by_id(self, db):
        contact = crud.create_contact(db, name="Jane Doe")
        e1 = crud.add_contact_email(
            db, contact["id"], "jane@acme.com", is_primary=True
        )
        e2 = crud.add_contact_email(db, contact["id"], "jane@gmail.com")
        crud.set_primary_email(db, contact["id"], e2["id"])
        emails = crud.get_contact_emails(db, contact["id"])
        primary = [e for e in emails if e["is_primary"]]
        assert len(primary) == 1
        assert primary[0]["id"] == e2["id"]

    def test_get_emails_primary_first(self, db):
        contact = crud.create_contact(db, name="Jane Doe")
        crud.add_contact_email(db, contact["id"], "secondary@acme.com")
        crud.add_contact_email(
            db, contact["id"], "primary@acme.com", is_primary=True
        )
        emails = crud.get_contact_emails(db, contact["id"])
        assert emails[0]["email"] == "primary@acme.com"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_crud_contacts.py -v`
Expected: FAIL — `ImportError: cannot import name 'crud' from 'src'`

- [ ] **Step 3: Implement contacts and contact emails CRUD**

```python
# src/crud.py
from datetime import date, datetime

from src.models import to_dict, to_dicts


# --- Contacts ---


def create_contact(conn, *, name, company=None, title=None, linkedin_url=None):
    result = conn.execute(
        """INSERT INTO contacts (name, company, title, linkedin_url)
           VALUES (?, ?, ?, ?) RETURNING *""",
        [name, company, title, linkedin_url],
    )
    return to_dict(result)


def get_contact(conn, contact_id):
    result = conn.execute("SELECT * FROM contacts WHERE id = ?", [contact_id])
    contact = to_dict(result)
    if contact is None:
        raise ValueError(f"Contact {contact_id} not found")
    return contact


def get_all_contacts(conn):
    return to_dicts(conn.execute("SELECT * FROM contacts ORDER BY name"))


def update_contact(conn, contact_id, **fields):
    allowed = {"name", "company", "title", "linkedin_url"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        raise ValueError("No valid fields to update")
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [contact_id]
    conn.execute(
        f"UPDATE contacts SET {set_clause}, updated_at = now() WHERE id = ?",
        values,
    )
    return get_contact(conn, contact_id)


def delete_contact(conn, contact_id):
    get_contact(conn, contact_id)  # Verify exists
    conn.execute("DELETE FROM contact_emails WHERE contact_id = ?", [contact_id])
    conn.execute("DELETE FROM notes WHERE contact_id = ?", [contact_id])
    conn.execute(
        """DELETE FROM action_items WHERE interaction_id IN
           (SELECT id FROM interactions WHERE contact_id = ?)""",
        [contact_id],
    )
    conn.execute("DELETE FROM interactions WHERE contact_id = ?", [contact_id])
    conn.execute(
        """DELETE FROM stage_history WHERE deal_id IN
           (SELECT id FROM deals WHERE contact_id = ?)""",
        [contact_id],
    )
    conn.execute("DELETE FROM deals WHERE contact_id = ?", [contact_id])
    conn.execute("DELETE FROM contacts WHERE id = ?", [contact_id])


# --- Contact Emails ---


def add_contact_email(conn, contact_id, email, is_primary=False):
    get_contact(conn, contact_id)
    if is_primary:
        conn.execute(
            "UPDATE contact_emails SET is_primary = false WHERE contact_id = ?",
            [contact_id],
        )
    result = conn.execute(
        """INSERT INTO contact_emails (contact_id, email, is_primary)
           VALUES (?, ?, ?) RETURNING *""",
        [contact_id, email, is_primary],
    )
    return to_dict(result)


def set_primary_email(conn, contact_id, email_id):
    conn.execute(
        "UPDATE contact_emails SET is_primary = false WHERE contact_id = ?",
        [contact_id],
    )
    conn.execute(
        "UPDATE contact_emails SET is_primary = true WHERE id = ? AND contact_id = ?",
        [email_id, contact_id],
    )


def get_contact_emails(conn, contact_id):
    return to_dicts(
        conn.execute(
            """SELECT * FROM contact_emails
               WHERE contact_id = ? ORDER BY is_primary DESC""",
            [contact_id],
        )
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_crud_contacts.py -v`
Expected: All passed

- [ ] **Step 5: Commit**

```bash
git add src/crud.py tests/test_crud_contacts.py
git commit -m "feat: add contacts and contact emails CRUD"
```

---

### Task 5: Deals CRUD

**Files:**
- Modify: `src/crud.py` (append deal functions)
- Create: `tests/test_crud_deals.py`

- [ ] **Step 1: Write failing tests for deal CRUD**

```python
# tests/test_crud_deals.py
import pytest
from src import crud


@pytest.fixture
def contact(db):
    return crud.create_contact(db, name="Jane Doe", company="Acme Corp")


class TestCreateDeal:
    def test_creates_deal_with_required_fields(self, db, contact):
        deal = crud.create_deal(
            db, contact_id=contact["id"], name="Acme - Opportunity",
            stage="Responded",
        )
        assert deal["name"] == "Acme - Opportunity"
        assert deal["stage"] == "Responded"

    def test_creates_initial_stage_history(self, db, contact):
        deal = crud.create_deal(
            db, contact_id=contact["id"], name="Acme - DP",
            stage="Responded",
        )
        history = db.execute(
            "SELECT * FROM stage_history WHERE deal_id = ?", [deal["id"]]
        ).fetchall()
        assert len(history) == 1

    def test_rejects_invalid_stage(self, db, contact):
        with pytest.raises(ValueError, match="Invalid stage"):
            crud.create_deal(
                db, contact_id=contact["id"], name="Bad",
                stage="Nonexistent Stage",
            )


class TestUpdateDealStage:
    def test_moves_to_valid_stage(self, db, contact):
        deal = crud.create_deal(
            db, contact_id=contact["id"], name="Acme - DP",
            stage="Responded",
        )
        updated = crud.update_deal_stage(db, deal["id"], "Call Scheduled")
        assert updated["stage"] == "Call Scheduled"

    def test_records_stage_history(self, db, contact):
        deal = crud.create_deal(
            db, contact_id=contact["id"], name="Acme - DP",
            stage="Responded",
        )
        crud.update_deal_stage(db, deal["id"], "Call Scheduled")
        history = db.execute(
            "SELECT from_stage, to_stage FROM stage_history WHERE deal_id = ? ORDER BY changed_at",
            [deal["id"]],
        ).fetchall()
        assert len(history) == 2
        assert history[0] == (None, "Responded")
        assert history[1] == ("Responded", "Call Scheduled")

    def test_noop_for_same_stage(self, db, contact):
        deal = crud.create_deal(
            db, contact_id=contact["id"], name="Acme - DP",
            stage="Responded",
        )
        updated = crud.update_deal_stage(db, deal["id"], "Responded")
        assert updated["stage"] == "Responded"
        history = db.execute(
            "SELECT COUNT(*) FROM stage_history WHERE deal_id = ?",
            [deal["id"]],
        ).fetchone()
        assert history[0] == 1  # Only the initial entry

    def test_rejects_invalid_stage(self, db, contact):
        deal = crud.create_deal(
            db, contact_id=contact["id"], name="Acme - DP",
            stage="Responded",
        )
        with pytest.raises(ValueError, match="Invalid stage"):
            crud.update_deal_stage(db, deal["id"], "Fake Stage")


class TestUpdateDeal:
    def test_updates_name(self, db, contact):
        deal = crud.create_deal(
            db, contact_id=contact["id"], name="Old Name",
            stage="Responded",
        )
        updated = crud.update_deal(db, deal["id"], name="New Name")
        assert updated["name"] == "New Name"

    def test_stage_in_fields_delegates_to_update_deal_stage(self, db, contact):
        deal = crud.create_deal(
            db, contact_id=contact["id"], name="Acme - DP",
            stage="Responded",
        )
        updated = crud.update_deal(db, deal["id"], stage="Call Scheduled")
        assert updated["stage"] == "Call Scheduled"


class TestDeleteDeal:
    def test_deletes_deal_and_history(self, db, contact):
        deal = crud.create_deal(
            db, contact_id=contact["id"], name="Acme - DP",
            stage="Responded",
        )
        crud.delete_deal(db, deal["id"])
        with pytest.raises(ValueError, match="not found"):
            crud.get_deal(db, deal["id"])
        history = db.execute(
            "SELECT COUNT(*) FROM stage_history WHERE deal_id = ?",
            [deal["id"]],
        ).fetchone()
        assert history[0] == 0

    def test_nullifies_interaction_deal_id(self, db, contact):
        deal = crud.create_deal(
            db, contact_id=contact["id"], name="Acme - DP",
            stage="Responded",
        )
        interaction = crud.create_interaction(
            db, contact_id=contact["id"], type="meeting",
            deal_id=deal["id"],
        )
        crud.delete_deal(db, deal["id"])
        updated_interaction = db.execute(
            "SELECT deal_id FROM interactions WHERE id = ?",
            [interaction["id"]],
        ).fetchone()
        assert updated_interaction[0] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_crud_deals.py -v`
Expected: FAIL — `AttributeError: module 'src.crud' has no attribute 'create_deal'`

- [ ] **Step 3: Implement deal CRUD**

Append to `src/crud.py`:

```python
# --- Deals ---


def _validate_stage(conn, stage):
    result = conn.execute(
        "SELECT name FROM pipeline_stages WHERE name = ?", [stage]
    ).fetchone()
    if result is None:
        valid = conn.execute(
            "SELECT name FROM pipeline_stages ORDER BY sort_order"
        ).fetchall()
        valid_names = [r[0] for r in valid]
        raise ValueError(f"Invalid stage '{stage}'. Valid stages: {valid_names}")


def create_deal(conn, *, contact_id, name, stage, value=None, expected_close=None):
    get_contact(conn, contact_id)
    _validate_stage(conn, stage)
    result = conn.execute(
        """INSERT INTO deals (contact_id, name, stage, value, expected_close)
           VALUES (?, ?, ?, ?, ?) RETURNING *""",
        [contact_id, name, stage, value, expected_close],
    )
    deal = to_dict(result)
    conn.execute(
        "INSERT INTO stage_history (deal_id, from_stage, to_stage) VALUES (?, NULL, ?)",
        [deal["id"], stage],
    )
    return deal


def get_deal(conn, deal_id):
    result = conn.execute("SELECT * FROM deals WHERE id = ?", [deal_id])
    deal = to_dict(result)
    if deal is None:
        raise ValueError(f"Deal {deal_id} not found")
    return deal


def get_all_deals(conn):
    return to_dicts(conn.execute("SELECT * FROM deals ORDER BY created_at DESC"))


def update_deal_stage(conn, deal_id, new_stage):
    _validate_stage(conn, new_stage)
    deal = get_deal(conn, deal_id)
    old_stage = deal["stage"]
    if old_stage == new_stage:
        return deal
    conn.execute(
        "UPDATE deals SET stage = ?, updated_at = now() WHERE id = ?",
        [new_stage, deal_id],
    )
    conn.execute(
        "INSERT INTO stage_history (deal_id, from_stage, to_stage) VALUES (?, ?, ?)",
        [deal_id, old_stage, new_stage],
    )
    return get_deal(conn, deal_id)


def update_deal(conn, deal_id, **fields):
    if "stage" in fields:
        update_deal_stage(conn, deal_id, fields.pop("stage"))
    allowed = {"name", "value", "expected_close"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if updates:
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [deal_id]
        conn.execute(
            f"UPDATE deals SET {set_clause}, updated_at = now() WHERE id = ?",
            values,
        )
    return get_deal(conn, deal_id)


def delete_deal(conn, deal_id):
    get_deal(conn, deal_id)
    conn.execute("DELETE FROM stage_history WHERE deal_id = ?", [deal_id])
    conn.execute(
        "UPDATE interactions SET deal_id = NULL WHERE deal_id = ?", [deal_id]
    )
    conn.execute("DELETE FROM deals WHERE id = ?", [deal_id])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_crud_deals.py -v`
Expected: All passed

- [ ] **Step 5: Commit**

```bash
git add src/crud.py tests/test_crud_deals.py
git commit -m "feat: add deals CRUD with stage validation and history"
```

---

### Task 6: Interactions CRUD

**Files:**
- Modify: `src/crud.py` (append interaction functions)
- Create: `tests/test_crud_interactions.py`

- [ ] **Step 1: Write failing tests for interaction CRUD**

```python
# tests/test_crud_interactions.py
import pytest
from datetime import date, datetime
from src import crud


@pytest.fixture
def contact(db):
    return crud.create_contact(db, name="Jane Doe")


@pytest.fixture
def deal(db, contact):
    return crud.create_deal(
        db, contact_id=contact["id"], name="Acme - DP", stage="Responded"
    )


class TestCreateInteraction:
    def test_creates_with_required_fields(self, db, contact):
        interaction = crud.create_interaction(
            db, contact_id=contact["id"], type="meeting"
        )
        assert interaction["type"] == "meeting"
        assert interaction["source"] == "manual"

    def test_creates_with_all_fields(self, db, contact, deal):
        interaction = crud.create_interaction(
            db,
            contact_id=contact["id"],
            type="call",
            summary="Discussed timeline",
            deal_id=deal["id"],
            next_connect_date=date(2026, 3, 30),
            source="manual",
        )
        assert interaction["summary"] == "Discussed timeline"
        assert interaction["deal_id"] == deal["id"]

    def test_updates_last_contact_date(self, db, contact):
        crud.create_interaction(db, contact_id=contact["id"], type="meeting")
        updated = crud.get_contact(db, contact["id"])
        assert updated["last_contact_date"] is not None

    def test_custom_occurred_at_sets_last_contact_date(self, db, contact):
        past = datetime(2026, 1, 15, 10, 0, 0)
        crud.create_interaction(
            db, contact_id=contact["id"], type="email", occurred_at=past
        )
        updated = crud.get_contact(db, contact["id"])
        assert updated["last_contact_date"] == date(2026, 1, 15)


class TestGetInteractions:
    def test_returns_by_contact(self, db, contact):
        crud.create_interaction(db, contact_id=contact["id"], type="meeting")
        crud.create_interaction(db, contact_id=contact["id"], type="email")
        interactions = crud.get_interactions(db, contact_id=contact["id"])
        assert len(interactions) == 2

    def test_returns_by_deal(self, db, contact, deal):
        crud.create_interaction(
            db, contact_id=contact["id"], type="meeting", deal_id=deal["id"]
        )
        crud.create_interaction(db, contact_id=contact["id"], type="email")
        interactions = crud.get_interactions(db, deal_id=deal["id"])
        assert len(interactions) == 1

    def test_returns_all_when_no_filter(self, db, contact):
        crud.create_interaction(db, contact_id=contact["id"], type="meeting")
        interactions = crud.get_interactions(db)
        assert len(interactions) == 1


class TestUpdateInteraction:
    def test_updates_summary(self, db, contact):
        interaction = crud.create_interaction(
            db, contact_id=contact["id"], type="meeting", summary="Old"
        )
        updated = crud.update_interaction(
            db, interaction["id"], summary="New summary"
        )
        assert updated["summary"] == "New summary"

    def test_rejects_invalid_fields(self, db, contact):
        interaction = crud.create_interaction(
            db, contact_id=contact["id"], type="meeting"
        )
        with pytest.raises(ValueError, match="No valid fields"):
            crud.update_interaction(db, interaction["id"], bad_field="nope")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_crud_interactions.py -v`
Expected: FAIL — `AttributeError: module 'src.crud' has no attribute 'create_interaction'`

- [ ] **Step 3: Implement interaction CRUD**

Append to `src/crud.py`:

```python
# --- Interactions ---


def create_interaction(conn, *, contact_id, type, summary=None, deal_id=None,
                       next_connect_date=None, source="manual", occurred_at=None):
    get_contact(conn, contact_id)
    if deal_id is not None:
        get_deal(conn, deal_id)
    result = conn.execute(
        """INSERT INTO interactions
           (contact_id, deal_id, type, summary, next_connect_date, source, occurred_at)
           VALUES (?, ?, ?, ?, ?, ?, COALESCE(?, now()))
           RETURNING *""",
        [contact_id, deal_id, type, summary, next_connect_date, source, occurred_at],
    )
    interaction = to_dict(result)
    # Update contact's last_contact_date (only if this interaction is newer)
    contact_date = None
    if occurred_at is not None:
        contact_date = occurred_at.date() if hasattr(occurred_at, "date") else occurred_at
    conn.execute(
        """UPDATE contacts
           SET last_contact_date = GREATEST(
               COALESCE(last_contact_date, '1970-01-01'),
               COALESCE(?, CURRENT_DATE)
           ), updated_at = now()
           WHERE id = ?""",
        [contact_date, contact_id],
    )
    return interaction


def get_interactions(conn, contact_id=None, deal_id=None):
    query = "SELECT * FROM interactions WHERE 1=1"
    params = []
    if contact_id is not None:
        query += " AND contact_id = ?"
        params.append(contact_id)
    if deal_id is not None:
        query += " AND deal_id = ?"
        params.append(deal_id)
    query += " ORDER BY occurred_at DESC"
    return to_dicts(conn.execute(query, params))


def update_interaction(conn, interaction_id, **fields):
    allowed = {"summary", "next_connect_date", "type", "source"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        raise ValueError("No valid fields to update")
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [interaction_id]
    conn.execute(
        f"UPDATE interactions SET {set_clause}, updated_at = now() WHERE id = ?",
        values,
    )
    result = conn.execute(
        "SELECT * FROM interactions WHERE id = ?", [interaction_id]
    )
    return to_dict(result)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_crud_interactions.py -v`
Expected: All passed

- [ ] **Step 5: Run full test suite**

Run: `pytest -v`
Expected: All tests across all files pass

- [ ] **Step 6: Commit**

```bash
git add src/crud.py tests/test_crud_interactions.py
git commit -m "feat: add interactions CRUD with last_contact_date sync"
```

---

### Task 7: Action Items & Notes CRUD

**Files:**
- Modify: `src/crud.py` (append action item and note functions)
- Create: `tests/test_crud_misc.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_crud_misc.py
import pytest
from datetime import date
from src import crud


@pytest.fixture
def contact(db):
    return crud.create_contact(db, name="Jane Doe")


@pytest.fixture
def interaction(db, contact):
    return crud.create_interaction(db, contact_id=contact["id"], type="meeting")


class TestActionItems:
    def test_create_action_item(self, db, interaction):
        item = crud.create_action_item(
            db,
            interaction_id=interaction["id"],
            description="Send proposal",
            owner="operator",
            due_date=date(2026, 4, 1),
        )
        assert item["description"] == "Send proposal"
        assert item["completed"] is False

    def test_get_open_action_items(self, db, interaction):
        crud.create_action_item(
            db, interaction_id=interaction["id"], description="Task 1"
        )
        crud.create_action_item(
            db, interaction_id=interaction["id"], description="Task 2"
        )
        items = crud.get_action_items(db, completed=False)
        assert len(items) == 2

    def test_complete_action_item(self, db, interaction):
        item = crud.create_action_item(
            db, interaction_id=interaction["id"], description="Task 1"
        )
        completed = crud.complete_action_item(db, item["id"])
        assert completed["completed"] is True

    def test_get_filters_by_completed(self, db, interaction):
        item = crud.create_action_item(
            db, interaction_id=interaction["id"], description="Task 1"
        )
        crud.create_action_item(
            db, interaction_id=interaction["id"], description="Task 2"
        )
        crud.complete_action_item(db, item["id"])
        open_items = crud.get_action_items(db, completed=False)
        assert len(open_items) == 1
        assert open_items[0]["description"] == "Task 2"

    def test_complete_nonexistent_raises(self, db):
        with pytest.raises(ValueError, match="not found"):
            crud.complete_action_item(db, 9999)


class TestNotes:
    def test_create_note(self, db, contact):
        note = crud.create_note(
            db, contact_id=contact["id"], content="Prefers async communication"
        )
        assert note["content"] == "Prefers async communication"

    def test_get_notes_for_contact(self, db, contact):
        crud.create_note(db, contact_id=contact["id"], content="Note 1")
        crud.create_note(db, contact_id=contact["id"], content="Note 2")
        notes = crud.get_notes(db, contact["id"])
        assert len(notes) == 2

    def test_delete_note(self, db, contact):
        note = crud.create_note(db, contact_id=contact["id"], content="Temp")
        crud.delete_note(db, note["id"])
        notes = crud.get_notes(db, contact["id"])
        assert len(notes) == 0

    def test_delete_nonexistent_raises(self, db):
        with pytest.raises(ValueError, match="not found"):
            crud.delete_note(db, 9999)

    def test_create_for_invalid_contact_raises(self, db):
        with pytest.raises(ValueError, match="not found"):
            crud.create_note(db, contact_id=9999, content="Bad")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_crud_misc.py -v`
Expected: FAIL — `AttributeError: module 'src.crud' has no attribute 'create_action_item'`

- [ ] **Step 3: Implement action items and notes CRUD**

Append to `src/crud.py`:

```python
# --- Action Items ---


def create_action_item(conn, *, interaction_id, description, owner=None, due_date=None):
    result = conn.execute(
        """INSERT INTO action_items (interaction_id, description, owner, due_date)
           VALUES (?, ?, ?, ?) RETURNING *""",
        [interaction_id, description, owner, due_date],
    )
    return to_dict(result)


def get_action_items(conn, completed=None):
    query = "SELECT * FROM action_items"
    params = []
    if completed is not None:
        query += " WHERE completed = ?"
        params.append(completed)
    query += " ORDER BY due_date ASC NULLS LAST"
    return to_dicts(conn.execute(query, params))


def complete_action_item(conn, action_item_id):
    result = conn.execute(
        "SELECT * FROM action_items WHERE id = ?", [action_item_id]
    )
    if to_dict(result) is None:
        raise ValueError(f"Action item {action_item_id} not found")
    conn.execute(
        "UPDATE action_items SET completed = true WHERE id = ?",
        [action_item_id],
    )
    result = conn.execute(
        "SELECT * FROM action_items WHERE id = ?", [action_item_id]
    )
    return to_dict(result)


# --- Notes ---


def create_note(conn, *, contact_id, content):
    get_contact(conn, contact_id)
    result = conn.execute(
        "INSERT INTO notes (contact_id, content) VALUES (?, ?) RETURNING *",
        [contact_id, content],
    )
    return to_dict(result)


def get_notes(conn, contact_id):
    return to_dicts(
        conn.execute(
            "SELECT * FROM notes WHERE contact_id = ? ORDER BY created_at DESC",
            [contact_id],
        )
    )


def delete_note(conn, note_id):
    result = conn.execute("SELECT id FROM notes WHERE id = ?", [note_id])
    if result.fetchone() is None:
        raise ValueError(f"Note {note_id} not found")
    conn.execute("DELETE FROM notes WHERE id = ?", [note_id])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_crud_misc.py -v`
Expected: All passed

- [ ] **Step 5: Run full test suite**

Run: `pytest -v`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add src/crud.py tests/test_crud_misc.py
git commit -m "feat: add action items and notes CRUD"
```

---

## Phase 3: Analysis & Export

### Task 8: Reporting Queries

**Files:**
- Create: `src/queries.py`
- Create: `tests/test_queries.py`

- [ ] **Step 1: Write failing tests for reporting queries**

```python
# tests/test_queries.py
import pytest
from datetime import date, datetime, timedelta
from src import crud, queries


def _seed_pipeline(db):
    """Create a contact with a deal moving through stages."""
    contact = crud.create_contact(db, name="Jane Doe", company="Acme")
    crud.add_contact_email(db, contact["id"], "jane@acme.com", is_primary=True)
    deal = crud.create_deal(
        db, contact_id=contact["id"], name="Acme - DP", stage="Responded"
    )
    return contact, deal


class TestPipelineSnapshot:
    def test_counts_deals_per_active_stage(self, db):
        c1 = crud.create_contact(db, name="Alice")
        c2 = crud.create_contact(db, name="Bob")
        crud.create_deal(db, contact_id=c1["id"], name="D1", stage="Responded")
        crud.create_deal(db, contact_id=c2["id"], name="D2", stage="Responded")
        snapshot = queries.pipeline_snapshot(db)
        responded = [s for s in snapshot if s["stage"] == "Responded"]
        assert responded[0]["deal_count"] == 2

    def test_includes_empty_stages(self, db):
        snapshot = queries.pipeline_snapshot(db)
        assert len(snapshot) == 6  # All 6 active stages


class TestStaleContacts:
    def test_finds_contacts_with_no_interaction(self, db):
        crud.create_contact(db, name="Ghost")
        stale = queries.stale_contacts(db, days=30)
        assert len(stale) == 1
        assert stale[0]["name"] == "Ghost"

    def test_excludes_recently_contacted(self, db):
        contact = crud.create_contact(db, name="Active")
        crud.create_interaction(db, contact_id=contact["id"], type="meeting")
        stale = queries.stale_contacts(db, days=30)
        assert len(stale) == 0


class TestOpenActionItems:
    def test_returns_open_items_with_context(self, db):
        contact = crud.create_contact(db, name="Jane Doe", company="Acme")
        interaction = crud.create_interaction(
            db, contact_id=contact["id"], type="meeting"
        )
        crud.create_action_item(
            db, interaction_id=interaction["id"], description="Send proposal"
        )
        items = queries.open_action_items(db)
        assert len(items) == 1
        assert items[0]["contact_name"] == "Jane Doe"
        assert items[0]["description"] == "Send proposal"

    def test_excludes_completed_items(self, db):
        contact = crud.create_contact(db, name="Jane")
        interaction = crud.create_interaction(
            db, contact_id=contact["id"], type="call"
        )
        item = crud.create_action_item(
            db, interaction_id=interaction["id"], description="Done"
        )
        crud.complete_action_item(db, item["id"])
        assert len(queries.open_action_items(db)) == 0


class TestActivitySummary:
    def test_counts_by_type(self, db):
        contact = crud.create_contact(db, name="Jane")
        crud.create_interaction(db, contact_id=contact["id"], type="meeting")
        crud.create_interaction(db, contact_id=contact["id"], type="meeting")
        crud.create_interaction(db, contact_id=contact["id"], type="email")
        summary = queries.activity_summary(db, days=30)
        meeting = [s for s in summary if s["type"] == "meeting"]
        assert meeting[0]["count"] == 2


class TestConversionRates:
    def test_sequential_transitions(self, db):
        contact = crud.create_contact(db, name="Jane")
        deal = crud.create_deal(
            db, contact_id=contact["id"], name="D1", stage="Responded"
        )
        crud.update_deal_stage(db, deal["id"], "Call Scheduled")
        rates = queries.conversion_rates(db)
        resp_to_call = [
            r for r in rates if r["from_stage"] == "Responded"
        ]
        assert len(resp_to_call) == 1
        assert resp_to_call[0]["transitions"] == 1


class TestTimeInStage:
    def test_calculates_duration(self, db):
        contact = crud.create_contact(db, name="Jane")
        deal = crud.create_deal(
            db, contact_id=contact["id"], name="D1", stage="Responded"
        )
        crud.update_deal_stage(db, deal["id"], "Call Scheduled")
        result = queries.time_in_stage(db)
        assert len(result) > 0


class TestUpcomingEngagements:
    def test_finds_upcoming(self, db):
        contact = crud.create_contact(db, name="Jane", company="Acme")
        crud.create_interaction(
            db,
            contact_id=contact["id"],
            type="meeting",
            next_connect_date=date.today() + timedelta(days=3),
        )
        upcoming = queries.upcoming_engagements(db, days=14)
        assert len(upcoming) == 1
        assert upcoming[0]["contact_name"] == "Jane"

    def test_excludes_past_dates(self, db):
        contact = crud.create_contact(db, name="Jane")
        crud.create_interaction(
            db,
            contact_id=contact["id"],
            type="call",
            next_connect_date=date.today() - timedelta(days=5),
        )
        upcoming = queries.upcoming_engagements(db, days=14)
        assert len(upcoming) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_queries.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.queries'`

- [ ] **Step 3: Implement queries**

```python
# src/queries.py
from src.models import to_dicts


def pipeline_snapshot(conn):
    """Count of deals at each active stage."""
    return to_dicts(conn.execute("""
        SELECT ps.name AS stage, ps.sort_order, COUNT(d.id) AS deal_count
        FROM pipeline_stages ps
        LEFT JOIN deals d ON d.stage = ps.name
        WHERE ps.category = 'active'
        GROUP BY ps.name, ps.sort_order
        ORDER BY ps.sort_order
    """))


def stale_contacts(conn, days=30):
    """Contacts with no interaction in the last N days."""
    return to_dicts(conn.execute("""
        SELECT c.id, c.name, c.company, c.last_contact_date,
               DATEDIFF('day', c.last_contact_date, CURRENT_DATE) AS days_since_contact
        FROM contacts c
        WHERE c.last_contact_date IS NULL
           OR DATEDIFF('day', c.last_contact_date, CURRENT_DATE) > ?
        ORDER BY c.last_contact_date ASC NULLS FIRST
    """, [days]))


def open_action_items(conn):
    """All incomplete action items with contact context."""
    return to_dicts(conn.execute("""
        SELECT ai.*, i.contact_id, c.name AS contact_name, c.company
        FROM action_items ai
        JOIN interactions i ON ai.interaction_id = i.id
        JOIN contacts c ON i.contact_id = c.id
        WHERE ai.completed = false
        ORDER BY ai.due_date ASC NULLS LAST
    """))


def activity_summary(conn, days=30):
    """Interaction counts by type over the last N days."""
    return to_dicts(conn.execute("""
        SELECT type, COUNT(*) AS count
        FROM interactions
        WHERE occurred_at >= CURRENT_DATE - ?
        GROUP BY type
        ORDER BY count DESC
    """, [days]))


def conversion_rates(conn):
    """Stage-to-stage conversion rates for sequential active transitions."""
    return to_dicts(conn.execute("""
        WITH stage_entries AS (
            SELECT to_stage AS stage, COUNT(DISTINCT deal_id) AS entries
            FROM stage_history
            GROUP BY to_stage
        ),
        sequential_transitions AS (
            SELECT sh.from_stage, sh.to_stage, COUNT(*) AS transitions
            FROM stage_history sh
            JOIN pipeline_stages ps_from ON sh.from_stage = ps_from.name
            JOIN pipeline_stages ps_to ON sh.to_stage = ps_to.name
            WHERE ps_from.category = 'active'
              AND ps_to.category = 'active'
              AND ps_to.sort_order = ps_from.sort_order + 1
            GROUP BY sh.from_stage, sh.to_stage
        )
        SELECT st.from_stage, st.to_stage, st.transitions,
               se.entries AS entered_from_stage,
               ROUND(st.transitions * 100.0 / NULLIF(se.entries, 0), 1) AS conversion_pct
        FROM sequential_transitions st
        LEFT JOIN stage_entries se ON st.from_stage = se.stage
        ORDER BY (SELECT sort_order FROM pipeline_stages WHERE name = st.from_stage)
    """))


def time_in_stage(conn):
    """Average days at each active stage."""
    return to_dicts(conn.execute("""
        WITH stage_durations AS (
            SELECT sh.deal_id, sh.to_stage AS stage, sh.changed_at AS entered_at,
                   LEAD(sh.changed_at) OVER (
                       PARTITION BY sh.deal_id ORDER BY sh.changed_at
                   ) AS exited_at
            FROM stage_history sh
        )
        SELECT sd.stage,
               ROUND(AVG(DATEDIFF('second', sd.entered_at,
                   COALESCE(sd.exited_at, CURRENT_TIMESTAMP)) / 86400.0), 1) AS avg_days,
               COUNT(*) AS deal_count
        FROM stage_durations sd
        JOIN pipeline_stages ps ON sd.stage = ps.name
        WHERE ps.category = 'active'
        GROUP BY sd.stage, ps.sort_order
        ORDER BY ps.sort_order
    """))


def upcoming_engagements(conn, days=14):
    """Scheduled interactions in the next N days."""
    return to_dicts(conn.execute("""
        SELECT i.id, i.next_connect_date, i.type, i.summary,
               c.name AS contact_name, c.company
        FROM interactions i
        JOIN contacts c ON i.contact_id = c.id
        WHERE i.next_connect_date IS NOT NULL
          AND i.next_connect_date >= CURRENT_DATE
          AND i.next_connect_date <= CURRENT_DATE + ?
        ORDER BY i.next_connect_date ASC
    """, [days]))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_queries.py -v`
Expected: All passed

- [ ] **Step 5: Commit**

```bash
git add src/queries.py tests/test_queries.py
git commit -m "feat: add reporting queries (pipeline, stale contacts, conversions, etc.)"
```

---

### Task 9: Parquet Export

**Files:**
- Create: `src/export.py`
- Create: `tests/test_export.py`

- [ ] **Step 1: Write failing tests for Parquet export**

```python
# tests/test_export.py
import pytest
import tempfile
import duckdb
from pathlib import Path
from src import crud
from src.export import export_parquet


EXPECTED_FILES = [
    "contacts.parquet",
    "deals.parquet",
    "interactions.parquet",
    "action_items.parquet",
    "notes.parquet",
    "stage_history.parquet",
    "pipeline_stages.parquet",
]


class TestExportParquet:
    def test_creates_all_parquet_files(self, db):
        export_dir = Path(tempfile.mkdtemp())
        export_parquet(db, export_dir)
        for f in EXPECTED_FILES:
            assert (export_dir / f).exists(), f"Missing: {f}"

    def test_contacts_includes_primary_email(self, db):
        contact = crud.create_contact(db, name="Jane Doe")
        crud.add_contact_email(
            db, contact["id"], "jane@acme.com", is_primary=True
        )
        export_dir = Path(tempfile.mkdtemp())
        export_parquet(db, export_dir)
        result = duckdb.execute(
            f"SELECT primary_email FROM '{export_dir}/contacts.parquet'"
        ).fetchone()
        assert result[0] == "jane@acme.com"

    def test_empty_tables_produce_valid_parquet(self, db):
        export_dir = Path(tempfile.mkdtemp())
        export_parquet(db, export_dir)
        # Should be readable even with zero rows
        result = duckdb.execute(
            f"SELECT COUNT(*) FROM '{export_dir}/contacts.parquet'"
        ).fetchone()
        assert result[0] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_export.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.export'`

- [ ] **Step 3: Implement export**

```python
# src/export.py
from pathlib import Path

DEFAULT_EXPORT_DIR = Path(__file__).parent.parent / "data" / "exports"

EXPORTS = {
    "contacts": """
        SELECT c.*, ce.email AS primary_email
        FROM contacts c
        LEFT JOIN contact_emails ce ON c.id = ce.contact_id AND ce.is_primary = true
    """,
    "deals": "SELECT * FROM deals",
    "interactions": "SELECT * FROM interactions",
    "action_items": "SELECT * FROM action_items",
    "notes": "SELECT * FROM notes",
    "stage_history": "SELECT * FROM stage_history",
    "pipeline_stages": "SELECT * FROM pipeline_stages",
}


def export_parquet(conn, export_dir=None):
    """Export all tables to Parquet files."""
    export_dir = Path(export_dir or DEFAULT_EXPORT_DIR)
    export_dir.mkdir(parents=True, exist_ok=True)
    exported = []
    for name, query in EXPORTS.items():
        path = export_dir / f"{name}.parquet"
        conn.execute(f"COPY ({query}) TO '{path}' (FORMAT PARQUET)")
        exported.append(str(path))
    return exported
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_export.py -v`
Expected: All passed

- [ ] **Step 5: Commit**

```bash
git add src/export.py tests/test_export.py
git commit -m "feat: add Parquet export for dashboard data"
```

---

## Phase 4: Data Ingestion

### Task 10: CSV Import

**Files:**
- Create: `src/import_csv.py`
- Create: `tests/test_import_csv.py`

- [ ] **Step 1: Write failing tests for CSV import**

```python
# tests/test_import_csv.py
import pytest
import tempfile
from pathlib import Path
from src import crud
from src.import_csv import import_csv


def _write_csv(rows, headers=None):
    """Write CSV rows to a temp file and return the path."""
    if headers is None:
        headers = ["Name", "Company", "Title", "Email", "Stage"]
    path = Path(tempfile.mktemp(suffix=".csv"))
    with open(path, "w") as f:
        f.write(",".join(headers) + "\n")
        for row in rows:
            f.write(",".join(row) + "\n")
    return path


class TestImportCsv:
    def test_imports_contacts_and_deals(self, db):
        csv_path = _write_csv([
            ["Jane Doe", "Acme Corp", "VP Eng", "jane@acme.com", "Responded"],
            ["Bob Smith", "Beta Inc", "CTO", "bob@beta.com", "Call Scheduled"],
        ])
        result = import_csv(db, csv_path)
        assert result["success"] is True
        assert result["imported"]["contacts"] == 2
        assert result["imported"]["deals"] == 2
        assert result["imported"]["contact_emails"] == 2

    def test_creates_primary_email(self, db):
        csv_path = _write_csv([
            ["Jane Doe", "Acme", "", "jane@acme.com", "Responded"],
        ])
        import_csv(db, csv_path)
        contact = crud.get_all_contacts(db)[0]
        emails = crud.get_contact_emails(db, contact["id"])
        assert len(emails) == 1
        assert emails[0]["is_primary"] is True

    def test_contact_without_stage_skips_deal(self, db):
        csv_path = _write_csv([
            ["Jane Doe", "Acme", "", "jane@acme.com", ""],
        ])
        result = import_csv(db, csv_path)
        assert result["imported"]["contacts"] == 1
        assert result["imported"]["deals"] == 0

    def test_invalid_stage_rolls_back(self, db):
        csv_path = _write_csv([
            ["Jane Doe", "Acme", "", "jane@acme.com", "Fake Stage"],
        ])
        result = import_csv(db, csv_path)
        assert result["success"] is False
        assert any("Invalid stage" in e or "invalid stage" in e.lower()
                    for e in result["errors"])
        # Nothing should have been committed
        assert len(crud.get_all_contacts(db)) == 0

    def test_missing_name_reports_error(self, db):
        csv_path = _write_csv([
            ["", "Acme", "", "jane@acme.com", "Responded"],
        ])
        result = import_csv(db, csv_path)
        assert result["success"] is False
        assert any("Name" in e for e in result["errors"])

    def test_duplicate_email_reports_error(self, db):
        csv_path = _write_csv([
            ["Jane Doe", "Acme", "", "jane@acme.com", "Responded"],
            ["Jane Copy", "Acme", "", "jane@acme.com", "Responded"],
        ])
        result = import_csv(db, csv_path)
        assert result["success"] is False
        assert any("duplicate" in e.lower() for e in result["errors"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_import_csv.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.import_csv'`

- [ ] **Step 3: Implement CSV import**

```python
# src/import_csv.py
import csv
from pathlib import Path
from src import crud

COLUMN_MAP = {
    "Name": "name",
    "Company": "company",
    "Title": "title",
    "LinkedIn": "linkedin_url",
    "Email": "email",
    "Stage": "stage",
    "Deal Name": "deal_name",
    "Deal Value": "deal_value",
    "Expected Close": "expected_close",
}


def import_csv(conn, csv_path, column_map=None):
    """Import contacts and deals from a CSV file. Transactional — all or nothing."""
    column_map = column_map or COLUMN_MAP
    csv_path = Path(csv_path)

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Phase 1: Validate all rows before writing
    errors = []
    parsed_rows = []

    valid_stages = {
        r[0]
        for r in conn.execute("SELECT name FROM pipeline_stages").fetchall()
    }

    for i, row in enumerate(rows, start=2):
        mapped = {}
        for csv_col, field in column_map.items():
            if csv_col in row and row[csv_col].strip():
                mapped[field] = row[csv_col].strip()

        if "name" not in mapped:
            errors.append(f"Row {i}: missing required field 'Name'")
            continue

        if "stage" in mapped and mapped["stage"] not in valid_stages:
            errors.append(
                f"Row {i}: Invalid stage '{mapped['stage']}'. "
                f"Valid: {sorted(valid_stages)}"
            )

        if "deal_value" in mapped:
            try:
                float(mapped["deal_value"].replace(",", ""))
            except ValueError:
                errors.append(f"Row {i}: invalid deal value '{mapped['deal_value']}'")

        parsed_rows.append((i, mapped))

    if errors:
        return {"success": False, "errors": errors, "imported": None}

    # Phase 2: Check for duplicate emails within the CSV
    emails_seen = set()
    for i, mapped in parsed_rows:
        email = mapped.get("email")
        if email:
            if email in emails_seen:
                errors.append(f"Row {i}: duplicate email '{email}'")
            emails_seen.add(email)

    if errors:
        return {"success": False, "errors": errors, "imported": None}

    # Phase 3: Import in a transaction
    imported = {"contacts": 0, "deals": 0, "contact_emails": 0}

    conn.execute("BEGIN TRANSACTION")
    try:
        for i, mapped in parsed_rows:
            contact = crud.create_contact(
                conn,
                name=mapped["name"],
                company=mapped.get("company"),
                title=mapped.get("title"),
                linkedin_url=mapped.get("linkedin_url"),
            )
            imported["contacts"] += 1

            if "email" in mapped:
                crud.add_contact_email(
                    conn, contact["id"], mapped["email"], is_primary=True
                )
                imported["contact_emails"] += 1

            if "stage" in mapped:
                deal_name = mapped.get(
                    "deal_name", f"{mapped['name']} - Opportunity"
                )
                value = None
                if "deal_value" in mapped:
                    value = float(mapped["deal_value"].replace(",", ""))
                crud.create_deal(
                    conn,
                    contact_id=contact["id"],
                    name=deal_name,
                    stage=mapped["stage"],
                    value=value,
                    expected_close=mapped.get("expected_close"),
                )
                imported["deals"] += 1

        conn.execute("COMMIT")
        return {"success": True, "errors": [], "imported": imported}
    except Exception as e:
        conn.execute("ROLLBACK")
        return {"success": False, "errors": [str(e)], "imported": None}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_import_csv.py -v`
Expected: All passed

- [ ] **Step 5: Commit**

```bash
git add src/import_csv.py tests/test_import_csv.py
git commit -m "feat: add transactional CSV import with validation"
```

---

### Task 11: Integration Helpers

**Files:**
- Create: `src/integrations.py`
- Create: `tests/test_integrations.py`

- [ ] **Step 1: Write failing tests for integration helpers**

```python
# tests/test_integrations.py
import pytest
from datetime import datetime, date
from src import crud, integrations


@pytest.fixture
def contact(db):
    c = crud.create_contact(db, name="Jane Doe", company="Acme")
    crud.add_contact_email(db, c["id"], "jane@acme.com", is_primary=True)
    return c


class TestLogGranolaMeeting:
    def test_creates_meeting_interaction(self, db, contact):
        result = integrations.log_granola_meeting(
            db,
            contact_id=contact["id"],
            summary="Discussed product roadmap",
            occurred_at=datetime(2026, 3, 20, 14, 0, 0),
        )
        assert result["type"] == "meeting"
        assert result["source"] == "granola"
        assert result["summary"] == "Discussed product roadmap"


class TestLogGmailThread:
    def test_creates_email_interaction(self, db, contact):
        result = integrations.log_gmail_thread(
            db,
            contact_id=contact["id"],
            summary="Re: Follow-up on partnership",
        )
        assert result["type"] == "email"
        assert result["source"] == "gmail"


class TestLogCalendarEvent:
    def test_creates_calendar_interaction(self, db, contact):
        result = integrations.log_calendar_event(
            db,
            contact_id=contact["id"],
            summary="Weekly sync",
            event_date=date(2026, 4, 1),
        )
        assert result["type"] == "meeting"
        assert result["source"] == "calendar"
        assert result["next_connect_date"] == date(2026, 4, 1)


class TestMatchContactByEmail:
    def test_finds_by_email(self, db, contact):
        match = integrations.match_contact_by_email(db, "jane@acme.com")
        assert match is not None
        assert match["name"] == "Jane Doe"

    def test_returns_none_for_unknown(self, db):
        assert integrations.match_contact_by_email(db, "nobody@x.com") is None


class TestMatchContactByName:
    def test_finds_case_insensitive(self, db, contact):
        match = integrations.match_contact_by_name(db, "jane doe")
        assert match is not None
        assert match["name"] == "Jane Doe"

    def test_returns_none_for_unknown(self, db):
        assert integrations.match_contact_by_name(db, "Nobody") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_integrations.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.integrations'`

- [ ] **Step 3: Implement integration helpers**

```python
# src/integrations.py
from src import crud
from src.models import to_dict


def log_granola_meeting(conn, *, contact_id, summary, occurred_at=None,
                        deal_id=None, next_connect_date=None):
    """Log a Granola meeting as an interaction."""
    return crud.create_interaction(
        conn,
        contact_id=contact_id,
        type="meeting",
        summary=summary,
        source="granola",
        deal_id=deal_id,
        occurred_at=occurred_at,
        next_connect_date=next_connect_date,
    )


def log_gmail_thread(conn, *, contact_id, summary, occurred_at=None,
                     deal_id=None):
    """Log a Gmail thread as an interaction."""
    return crud.create_interaction(
        conn,
        contact_id=contact_id,
        type="email",
        summary=summary,
        source="gmail",
        deal_id=deal_id,
        occurred_at=occurred_at,
    )


def log_calendar_event(conn, *, contact_id, summary, event_date,
                       deal_id=None):
    """Log a calendar event as a future interaction."""
    return crud.create_interaction(
        conn,
        contact_id=contact_id,
        type="meeting",
        summary=summary,
        source="calendar",
        deal_id=deal_id,
        next_connect_date=event_date,
    )


def match_contact_by_email(conn, email):
    """Find a contact by email address (exact match)."""
    result = conn.execute(
        """SELECT c.* FROM contacts c
           JOIN contact_emails ce ON c.id = ce.contact_id
           WHERE ce.email = ?""",
        [email],
    )
    return to_dict(result)


def match_contact_by_name(conn, name):
    """Find a contact by name (case-insensitive)."""
    result = conn.execute(
        "SELECT * FROM contacts WHERE LOWER(name) = LOWER(?)",
        [name],
    )
    return to_dict(result)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_integrations.py -v`
Expected: All passed

- [ ] **Step 5: Run full test suite**

Run: `pytest -v`
Expected: All tests pass across all modules

- [ ] **Step 6: Commit**

```bash
git add src/integrations.py tests/test_integrations.py
git commit -m "feat: add integration helpers for Granola, Gmail, Calendar"
```

---

## Phase 5: Dashboard

### Task 12: Streamlit Dashboard — Setup & Core Views

**Files:**
- Create: `dashboard/app.py`

No automated tests for this task — Streamlit UI is tested manually.

- [ ] **Step 1: Create the dashboard app with auth and all views**

```python
# dashboard/app.py
import streamlit as st
import duckdb
import pandas as pd
from pathlib import Path

EXPORTS_DIR = Path(__file__).parent.parent / "data" / "exports"


def check_password():
    """Password gate — blocks all content until correct password entered."""
    if st.session_state.get("authenticated"):
        return True
    password = st.text_input("Password", type="password")
    if password and password == st.secrets.get("dashboard_password", ""):
        st.session_state.authenticated = True
        st.rerun()
    elif password:
        st.error("Incorrect password")
    return False


def load_table(name):
    """Load a Parquet file as a DataFrame using DuckDB."""
    path = EXPORTS_DIR / f"{name}.parquet"
    if not path.exists():
        return pd.DataFrame()
    return duckdb.query(f"SELECT * FROM '{path}'").df()


# --- Views ---


def pipeline_snapshot():
    st.header("Pipeline Snapshot")
    deals = load_table("deals")
    stages = load_table("pipeline_stages")
    contacts = load_table("contacts")

    if deals.empty or stages.empty:
        st.info("No deal data available yet.")
        return

    active_stages = stages[stages["category"] == "active"].sort_values("sort_order")
    paused_stages = stages[stages["category"] == "paused"]
    closed_stages = stages[stages["category"] == "closed"]

    # Summary cards
    col1, col2, col3 = st.columns(3)
    col1.metric("Active", len(deals[deals["stage"].isin(active_stages["name"])]))
    col2.metric("Paused", len(deals[deals["stage"].isin(paused_stages["name"])]))
    col3.metric("Closed", len(deals[deals["stage"].isin(closed_stages["name"])]))

    # Bar chart of deals per active stage
    stage_order = active_stages["name"].tolist()
    active_deals = deals[deals["stage"].isin(stage_order)]
    if not active_deals.empty:
        counts = (
            active_deals.groupby("stage").size().reindex(stage_order, fill_value=0)
        )
        st.bar_chart(counts)

    # Detail table
    if not contacts.empty and not deals.empty:
        merged = deals.merge(
            contacts[["id", "name", "company", "last_contact_date"]],
            left_on="contact_id", right_on="id", suffixes=("_deal", "_contact"),
        )
        st.dataframe(
            merged[["name_contact", "company", "stage", "last_contact_date"]]
            .rename(columns={"name_contact": "Contact", "last_contact_date": "Last Contact"})
            .sort_values("stage"),
            use_container_width=True,
        )


def conversion_rates():
    st.header("Conversion Rates")
    history = load_table("stage_history")
    stages = load_table("pipeline_stages")

    if history.empty:
        st.info("No stage transition data yet.")
        return

    active = stages[stages["category"] == "active"].sort_values("sort_order")

    # Compute sequential transitions
    merged = history.merge(
        active[["name", "sort_order"]], left_on="from_stage", right_on="name",
        how="inner",
    ).rename(columns={"sort_order": "from_order"})
    merged = merged.merge(
        active[["name", "sort_order"]], left_on="to_stage", right_on="name",
        how="inner", suffixes=("", "_to"),
    ).rename(columns={"sort_order": "to_order"})

    sequential = merged[merged["to_order"] == merged["from_order"] + 1]

    if sequential.empty:
        st.info("No sequential stage transitions recorded yet.")
        return

    entries = history.groupby("to_stage")["deal_id"].nunique().rename("entries")
    trans = sequential.groupby(["from_stage", "to_stage"]).size().reset_index(name="transitions")
    trans = trans.merge(entries, left_on="from_stage", right_index=True, how="left")
    trans["conversion_pct"] = (trans["transitions"] / trans["entries"] * 100).round(1)

    st.dataframe(
        trans[["from_stage", "to_stage", "transitions", "entries", "conversion_pct"]]
        .rename(columns={
            "from_stage": "From", "to_stage": "To",
            "transitions": "Transitions", "entries": "Entered From",
            "conversion_pct": "Conversion %",
        }),
        use_container_width=True,
    )


def time_in_stage_view():
    st.header("Time in Stage")
    history = load_table("stage_history")
    stages = load_table("pipeline_stages")

    if history.empty:
        st.info("No stage transition data yet.")
        return

    active_names = stages[stages["category"] == "active"]["name"].tolist()

    # Calculate durations using DuckDB on the Parquet file directly
    path = EXPORTS_DIR / "stage_history.parquet"
    result = duckdb.query(f"""
        WITH durations AS (
            SELECT to_stage AS stage, changed_at AS entered_at,
                   LEAD(changed_at) OVER (PARTITION BY deal_id ORDER BY changed_at) AS exited_at
            FROM '{path}'
        )
        SELECT stage,
               ROUND(AVG(DATEDIFF('second', entered_at,
                   COALESCE(exited_at, CURRENT_TIMESTAMP)) / 86400.0), 1) AS avg_days,
               COUNT(*) AS deals
        FROM durations
        WHERE stage IN ({','.join(f"'{s}'" for s in active_names)})
        GROUP BY stage
        ORDER BY stage
    """).df()

    if not result.empty:
        st.bar_chart(result.set_index("stage")["avg_days"])
        st.dataframe(result, use_container_width=True)


def activity_tracking():
    st.header("Activity Tracking")
    interactions = load_table("interactions")
    contacts = load_table("contacts")

    if interactions.empty:
        st.info("No interaction data yet.")
        return

    # Interactions by type
    by_type = interactions.groupby("type").size().reset_index(name="count")
    st.subheader("Interactions by Type")
    st.bar_chart(by_type.set_index("type")["count"])

    # Contacts going cold
    st.subheader("Contacts Going Cold")
    if not contacts.empty:
        contacts["last_contact_date"] = pd.to_datetime(contacts["last_contact_date"])
        contacts["days_silent"] = (
            pd.Timestamp.now() - contacts["last_contact_date"]
        ).dt.days

        cold_14 = contacts[
            (contacts["days_silent"] >= 14) | contacts["last_contact_date"].isna()
        ].sort_values("days_silent", ascending=False, na_position="first")

        if not cold_14.empty:
            st.dataframe(
                cold_14[["name", "company", "last_contact_date", "days_silent"]],
                use_container_width=True,
            )
        else:
            st.success("All contacts have been reached in the last 14 days.")


def contact_aging():
    st.header("Contact Aging")
    contacts = load_table("contacts")
    deals = load_table("deals")

    if contacts.empty:
        st.info("No contact data yet.")
        return

    contacts["last_contact_date"] = pd.to_datetime(contacts["last_contact_date"])
    contacts["days_since_contact"] = (
        pd.Timestamp.now() - contacts["last_contact_date"]
    ).dt.days

    def status_color(days):
        if pd.isna(days):
            return "red"
        if days < 14:
            return "green"
        if days <= 30:
            return "yellow"
        return "red"

    contacts["status"] = contacts["days_since_contact"].apply(status_color)

    # Stage filter
    if not deals.empty:
        all_stages = ["All"] + sorted(deals["stage"].unique().tolist())
        selected = st.selectbox("Filter by deal stage", all_stages)
        if selected != "All":
            deal_contacts = deals[deals["stage"] == selected]["contact_id"]
            contacts = contacts[contacts["id"].isin(deal_contacts)]

    st.dataframe(
        contacts[["name", "company", "last_contact_date", "days_since_contact", "status"]]
        .sort_values("days_since_contact", ascending=False, na_position="first"),
        use_container_width=True,
    )


def upcoming_engagements():
    st.header("Upcoming Engagements (14 days)")
    interactions = load_table("interactions")
    contacts = load_table("contacts")

    if interactions.empty:
        st.info("No interaction data yet.")
        return

    interactions["next_connect_date"] = pd.to_datetime(interactions["next_connect_date"])
    now = pd.Timestamp.now()
    upcoming = interactions[
        (interactions["next_connect_date"] >= now)
        & (interactions["next_connect_date"] <= now + pd.Timedelta(days=14))
    ]

    if upcoming.empty:
        st.info("No upcoming engagements in the next 14 days.")
        return

    if not contacts.empty:
        upcoming = upcoming.merge(
            contacts[["id", "name", "company"]],
            left_on="contact_id", right_on="id", suffixes=("", "_contact"),
        )
        st.dataframe(
            upcoming[["name", "company", "next_connect_date", "type", "summary"]]
            .rename(columns={"name": "Contact", "next_connect_date": "Date"})
            .sort_values("Date"),
            use_container_width=True,
        )


# --- Main ---


def main():
    st.set_page_config(page_title="CRM Dashboard", layout="wide")

    if not check_password():
        st.stop()

    st.title("Lightweight CRM Dashboard")

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "Pipeline", "Conversions", "Time in Stage",
        "Activity", "Contact Aging", "Upcoming",
    ])

    with tab1:
        pipeline_snapshot()
    with tab2:
        conversion_rates()
    with tab3:
        time_in_stage_view()
    with tab4:
        activity_tracking()
    with tab5:
        contact_aging()
    with tab6:
        upcoming_engagements()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Manual test — run locally**

Run: `streamlit run dashboard/app.py`
Expected: App opens in browser, shows password prompt. (To test views, first run `python scripts/init_db.py`, add some data via Python, then run `python -c "from src.models import get_connection; from src.export import export_parquet; export_parquet(get_connection())"`)

- [ ] **Step 3: Commit**

```bash
git add dashboard/app.py
git commit -m "feat: add Streamlit dashboard with all six views"
```

---

## Phase 6: Configuration

### Task 13: CLAUDE.md

**Files:**
- Create: `CLAUDE.md`

- [ ] **Step 1: Write CLAUDE.md**

```markdown
# Lightweight CRM

Local-first CRM built on DuckDB + Python, operated via Claude Code.

## Quick Reference

- **Database:** `db/crm.duckdb` (local, gitignored)
- **Initialize DB:** `python scripts/init_db.py`
- **Run tests:** `pytest -v`
- **Export data:** `python -c "from src.models import get_connection; from src.export import export_parquet; export_parquet(get_connection())"`
- **Dashboard (local):** `streamlit run dashboard/app.py`

## Data Flow

1. CRUD operations write to local DuckDB via `src/crud.py`
2. `src/export.py` exports Parquet files to `data/exports/`
3. Commit and push Parquet files
4. Streamlit Cloud reads Parquet on next page load

## After Any Data Change

Always run export + commit after modifying CRM data:
```
python -c "from src.models import get_connection; from src.export import export_parquet; export_parquet(get_connection())"
git add data/exports/ && git commit -m "data: update exports"
```

## Commit Message Rules

- Never include PII in commit messages — use contact ID or first name only
- Prefix: `feat:`, `fix:`, `data:`, `chore:`

## Key Modules

| Module | Purpose |
|--------|---------|
| `src/crud.py` | All CRUD operations — contacts, deals, interactions, action_items, notes |
| `src/queries.py` | Reporting queries — pipeline, stale contacts, conversions, activity |
| `src/integrations.py` | Helpers for structuring Granola/Gmail/Calendar data |
| `src/import_csv.py` | One-time Coda CSV importer |
| `src/export.py` | Parquet export for dashboard |
| `src/models.py` | Connection management, migration runner, result helpers |

## Pipeline Stages

Active: Responded → Call Scheduled → Discovery & Demo → Evaluation → Committed → Referral Partner
Paused: Reconnect later, Interest/Blocked (Org), Interest/Blocked (Eng)
Closed: Went Dark, No Show, Not a Fit (ICP Mismatch, Tire Kicker, No Need)
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add CLAUDE.md with project reference"
```

- [ ] **Step 3: Run full test suite one final time**

Run: `pytest -v`
Expected: All tests pass

- [ ] **Step 4: Update plan.md with completed status**

Update `plan.md` to reflect that implementation is complete.
