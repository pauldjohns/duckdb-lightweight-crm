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
