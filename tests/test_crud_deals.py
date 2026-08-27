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
