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
