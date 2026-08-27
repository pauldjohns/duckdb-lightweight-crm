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
