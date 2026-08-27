# tests/test_crud_misc.py
import pytest
from datetime import date
from src import crud


@pytest.fixture
def contact(db):
    return crud.create_contact(db, name="Jane Doe")


@pytest.fixture
def interaction(db, contact):
    return crud.create_interaction(db, contact_id=contact["id"], type="meeting")


class TestActionItems:
    def test_create_action_item(self, db, interaction):
        item = crud.create_action_item(
            db,
            interaction_id=interaction["id"],
            description="Send proposal",
            owner="operator",
            due_date=date(2026, 4, 1),
        )
        assert item["description"] == "Send proposal"
        assert item["completed"] is False

    def test_get_open_action_items(self, db, interaction):
        crud.create_action_item(
            db, interaction_id=interaction["id"], description="Task 1"
        )
        crud.create_action_item(
            db, interaction_id=interaction["id"], description="Task 2"
        )
        items = crud.get_action_items(db, completed=False)
        assert len(items) == 2

    def test_complete_action_item(self, db, interaction):
        item = crud.create_action_item(
            db, interaction_id=interaction["id"], description="Task 1"
        )
        completed = crud.complete_action_item(db, item["id"])
        assert completed["completed"] is True

    def test_get_filters_by_completed(self, db, interaction):
        item = crud.create_action_item(
            db, interaction_id=interaction["id"], description="Task 1"
        )
        crud.create_action_item(
            db, interaction_id=interaction["id"], description="Task 2"
        )
        crud.complete_action_item(db, item["id"])
        open_items = crud.get_action_items(db, completed=False)
        assert len(open_items) == 1
        assert open_items[0]["description"] == "Task 2"

    def test_complete_nonexistent_raises(self, db):
        with pytest.raises(ValueError, match="not found"):
            crud.complete_action_item(db, 9999)


class TestNotes:
    def test_create_note(self, db, contact):
        note = crud.create_note(
            db, contact_id=contact["id"], content="Prefers async communication"
        )
        assert note["content"] == "Prefers async communication"

    def test_get_notes_for_contact(self, db, contact):
        crud.create_note(db, contact_id=contact["id"], content="Note 1")
        crud.create_note(db, contact_id=contact["id"], content="Note 2")
        notes = crud.get_notes(db, contact["id"])
        assert len(notes) == 2

    def test_delete_note(self, db, contact):
        note = crud.create_note(db, contact_id=contact["id"], content="Temp")
        crud.delete_note(db, note["id"])
        notes = crud.get_notes(db, contact["id"])
        assert len(notes) == 0

    def test_delete_nonexistent_raises(self, db):
        with pytest.raises(ValueError, match="not found"):
            crud.delete_note(db, 9999)

    def test_create_for_invalid_contact_raises(self, db):
        with pytest.raises(ValueError, match="not found"):
            crud.create_note(db, contact_id=9999, content="Bad")
