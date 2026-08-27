import pytest
from src import crud


class TestCreateContact:
    def test_creates_with_required_fields(self, db):
        contact = crud.create_contact(db, name="Jane Doe")
        assert contact["name"] == "Jane Doe"
        assert contact["id"] is not None
        assert contact["company"] is None

    def test_creates_with_all_fields(self, db):
        contact = crud.create_contact(
            db,
            name="Jane Doe",
            company="Acme Corp",
            title="VP Engineering",
            linkedin_url="https://linkedin.com/in/janedoe",
        )
        assert contact["company"] == "Acme Corp"
        assert contact["title"] == "VP Engineering"


class TestGetContact:
    def test_returns_existing_contact(self, db):
        created = crud.create_contact(db, name="Jane Doe")
        fetched = crud.get_contact(db, created["id"])
        assert fetched["name"] == "Jane Doe"

    def test_raises_for_missing_contact(self, db):
        with pytest.raises(ValueError, match="not found"):
            crud.get_contact(db, 9999)


class TestGetAllContacts:
    def test_returns_all_contacts_sorted(self, db):
        crud.create_contact(db, name="Zara")
        crud.create_contact(db, name="Alice")
        contacts = crud.get_all_contacts(db)
        assert len(contacts) == 2
        assert contacts[0]["name"] == "Alice"


class TestUpdateContact:
    def test_updates_specified_fields(self, db):
        contact = crud.create_contact(db, name="Jane Doe")
        updated = crud.update_contact(db, contact["id"], company="New Corp")
        assert updated["company"] == "New Corp"
        assert updated["name"] == "Jane Doe"

    def test_rejects_invalid_fields(self, db):
        contact = crud.create_contact(db, name="Jane Doe")
        with pytest.raises(ValueError, match="No valid fields"):
            crud.update_contact(db, contact["id"], fake_field="bad")


class TestDeleteContact:
    def test_deletes_contact_and_related(self, db):
        contact = crud.create_contact(db, name="Jane Doe")
        crud.add_contact_email(db, contact["id"], "jane@acme.com")
        crud.delete_contact(db, contact["id"])
        with pytest.raises(ValueError, match="not found"):
            crud.get_contact(db, contact["id"])

    def test_raises_for_missing_contact(self, db):
        with pytest.raises(ValueError, match="not found"):
            crud.delete_contact(db, 9999)


class TestContactEmails:
    def test_add_email(self, db):
        contact = crud.create_contact(db, name="Jane Doe")
        email = crud.add_contact_email(db, contact["id"], "jane@acme.com")
        assert email["email"] == "jane@acme.com"
        assert email["is_primary"] is False

    def test_add_primary_email(self, db):
        contact = crud.create_contact(db, name="Jane Doe")
        email = crud.add_contact_email(
            db, contact["id"], "jane@acme.com", is_primary=True
        )
        assert email["is_primary"] is True

    def test_set_primary_clears_others(self, db):
        contact = crud.create_contact(db, name="Jane Doe")
        e1 = crud.add_contact_email(
            db, contact["id"], "jane@acme.com", is_primary=True
        )
        e2 = crud.add_contact_email(
            db, contact["id"], "jane@gmail.com", is_primary=True
        )
        emails = crud.get_contact_emails(db, contact["id"])
        primary = [e for e in emails if e["is_primary"]]
        assert len(primary) == 1
        assert primary[0]["email"] == "jane@gmail.com"

    def test_set_primary_email_by_id(self, db):
        contact = crud.create_contact(db, name="Jane Doe")
        e1 = crud.add_contact_email(
            db, contact["id"], "jane@acme.com", is_primary=True
        )
        e2 = crud.add_contact_email(db, contact["id"], "jane@gmail.com")
        crud.set_primary_email(db, contact["id"], e2["id"])
        emails = crud.get_contact_emails(db, contact["id"])
        primary = [e for e in emails if e["is_primary"]]
        assert len(primary) == 1
        assert primary[0]["id"] == e2["id"]

    def test_get_emails_primary_first(self, db):
        contact = crud.create_contact(db, name="Jane Doe")
        crud.add_contact_email(db, contact["id"], "secondary@acme.com")
        crud.add_contact_email(
            db, contact["id"], "primary@acme.com", is_primary=True
        )
        emails = crud.get_contact_emails(db, contact["id"])
        assert emails[0]["email"] == "primary@acme.com"
