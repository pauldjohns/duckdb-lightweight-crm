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
