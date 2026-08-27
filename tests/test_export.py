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
