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
