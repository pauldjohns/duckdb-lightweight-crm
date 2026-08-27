from datetime import date, datetime

from src.models import to_dict, to_dicts


# --- Contacts ---


def create_contact(conn, *, name, company=None, title=None, linkedin_url=None,
                   company_url=None, country=None):
    result = conn.execute(
        """INSERT INTO contacts (name, company, title, linkedin_url, company_url, country)
           VALUES (?, ?, ?, ?, ?, ?) RETURNING *""",
        [name, company, title, linkedin_url, company_url, country],
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
    allowed = {"name", "company", "title", "linkedin_url", "company_url", "country"}
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
    # DuckDB triggers FK checks on any UPDATE to a referenced row, even when the PK
    # doesn't change. Temporarily null out interactions.deal_id to allow the update.
    interaction_ids = [
        r[0] for r in conn.execute(
            "SELECT id FROM interactions WHERE deal_id = ?", [deal_id]
        ).fetchall()
    ]
    if interaction_ids:
        conn.execute("UPDATE interactions SET deal_id = NULL WHERE deal_id = ?", [deal_id])
    conn.execute(
        "UPDATE deals SET stage = ?, updated_at = now() WHERE id = ?",
        [new_stage, deal_id],
    )
    if interaction_ids:
        placeholders = ", ".join("?" * len(interaction_ids))
        conn.execute(
            f"UPDATE interactions SET deal_id = ? WHERE id IN ({placeholders})",
            [deal_id] + interaction_ids,
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
    # Update contact's last_contact_date
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
