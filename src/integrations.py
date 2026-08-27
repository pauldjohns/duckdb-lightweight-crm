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
