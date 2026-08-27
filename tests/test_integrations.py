# tests/test_integrations.py
import pytest
from datetime import datetime, date
from src import crud, integrations


@pytest.fixture
def contact(db):
    c = crud.create_contact(db, name="Jane Doe", company="Acme")
    crud.add_contact_email(db, c["id"], "jane@acme.com", is_primary=True)
    return c


class TestLogGranolaMeeting:
    def test_creates_meeting_interaction(self, db, contact):
        result = integrations.log_granola_meeting(
            db,
            contact_id=contact["id"],
            summary="Discussed product roadmap",
            occurred_at=datetime(2026, 3, 20, 14, 0, 0),
        )
        assert result["type"] == "meeting"
        assert result["source"] == "granola"
        assert result["summary"] == "Discussed product roadmap"


class TestLogGmailThread:
    def test_creates_email_interaction(self, db, contact):
        result = integrations.log_gmail_thread(
            db,
            contact_id=contact["id"],
            summary="Re: Follow-up on partnership",
        )
        assert result["type"] == "email"
        assert result["source"] == "gmail"


class TestLogCalendarEvent:
    def test_creates_calendar_interaction(self, db, contact):
        result = integrations.log_calendar_event(
            db,
            contact_id=contact["id"],
            summary="Weekly sync",
            event_date=date(2026, 4, 1),
        )
        assert result["type"] == "meeting"
        assert result["source"] == "calendar"
        assert result["next_connect_date"] == date(2026, 4, 1)


class TestMatchContactByEmail:
    def test_finds_by_email(self, db, contact):
        match = integrations.match_contact_by_email(db, "jane@acme.com")
        assert match is not None
        assert match["name"] == "Jane Doe"

    def test_returns_none_for_unknown(self, db):
        assert integrations.match_contact_by_email(db, "nobody@x.com") is None


class TestMatchContactByName:
    def test_finds_case_insensitive(self, db, contact):
        match = integrations.match_contact_by_name(db, "jane doe")
        assert match is not None
        assert match["name"] == "Jane Doe"

    def test_returns_none_for_unknown(self, db):
        assert integrations.match_contact_by_name(db, "Nobody") is None
