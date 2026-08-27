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
