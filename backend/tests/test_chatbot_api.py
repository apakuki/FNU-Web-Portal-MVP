"""Integration-ish tests for the chatbot API.

Mocks the database session, the Banner client, and the persistence helpers
(audit + notification) so the API layer can be exercised without a real
Postgres or Banner instance.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.backend.api import chatbot as chatbot_api
from src.backend.db.models import ChatbotKnowledge
from src.backend.db.session import get_session
from src.backend.main import app
from src.backend.services import chatbot_service


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _knowledge(title: str, content: str, tags: list[str]) -> ChatbotKnowledge:
    return ChatbotKnowledge(
        id=uuid.uuid4(),
        kind="faq",
        title=title,
        content=content,
        tags=tags,
        is_active=True,
    )


def _override_session(db):
    async def _override():
        yield db

    return _override


def _build_chat_db(faq_rows: list[ChatbotKnowledge]):
    """Mock async session that supports the chat endpoint code paths."""
    db = AsyncMock()
    # retrieve_knowledge -> db.scalars(...).all() returns FAQ rows
    scalars_result = MagicMock()
    scalars_result.all.return_value = faq_rows
    db.scalars.return_value = scalars_result
    # _persist_conversation -> db.scalar(select(ChatbotConversation)) returns None on first call
    db.scalar.return_value = None
    db.commit.return_value = None
    db.refresh.return_value = None

    # db.add is synchronous in SQLAlchemy; replace the AsyncMock attribute
    # with a plain MagicMock so it doesn't create a stray coroutine warning.
    def _add(obj):
        if not getattr(obj, "id", None):
            obj.id = uuid.uuid4()

    db.add = MagicMock(side_effect=_add)
    return db


async def test_chat_returns_faq_answer_in_stub_mode(client: AsyncClient, monkeypatch):
    # Chatbot service must be in stub mode for deterministic response.
    monkeypatch.setattr(chatbot_service.settings, "chatbot_mode", "stub")

    faqs = [
        _knowledge(
            "Bachelor of Nursing entry requirements",
            "BNUR requires biology and chemistry at grade C.",
            ["nursing", "admissions"],
        )
    ]
    db = _build_chat_db(faqs)
    app.dependency_overrides[get_session] = _override_session(db)

    # Avoid creating an enquiry row even if escalation logic triggers.
    monkeypatch.setattr(
        chatbot_api, "_create_enquiry_from_conversation", AsyncMock(return_value=None)
    )

    try:
        response = await client.post(
            "/api/chat",
            json={"message": "What are the entry requirements for nursing?"},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert "biology" in data["reply"].lower()
        assert data["session_key"]
        assert data["sources"][0]["title"].startswith("Bachelor of Nursing")
        assert data["escalated"] is False
    finally:
        app.dependency_overrides.clear()


async def test_chat_health_query_two_plus_two(client: AsyncClient, monkeypatch):
    """The TOR acceptance test set includes a '2+2' sanity check.

    With CHATBOT_MODE=stub and no matching FAQ this returns the no-info /
    escalation message — but the endpoint must still return 200 and a non-empty
    reply for any well-formed input.
    """
    monkeypatch.setattr(chatbot_service.settings, "chatbot_mode", "stub")
    db = _build_chat_db([])
    app.dependency_overrides[get_session] = _override_session(db)
    monkeypatch.setattr(
        chatbot_api, "_create_enquiry_from_conversation", AsyncMock(return_value=None)
    )
    try:
        response = await client.post("/api/chat", json={"message": "2+2"})
        assert response.status_code == 200
        body = response.json()
        assert isinstance(body["reply"], str) and len(body["reply"]) > 0
    finally:
        app.dependency_overrides.clear()


async def test_chat_escalates_on_human_request(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(chatbot_service.settings, "chatbot_mode", "stub")
    faqs = [_knowledge("Fees", "FJ$3,780 per semester", ["fees"])]
    db = _build_chat_db(faqs)
    app.dependency_overrides[get_session] = _override_session(db)

    enquiry_spy = AsyncMock(return_value=None)
    monkeypatch.setattr(chatbot_api, "_create_enquiry_from_conversation", enquiry_spy)

    try:
        response = await client.post(
            "/api/chat",
            json={"message": "I want to speak to a human about my fees"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["escalated"] is True
        assert data["escalation_reason"] == "user_requested_human"
        enquiry_spy.assert_awaited_once()
    finally:
        app.dependency_overrides.clear()


async def test_chat_rejects_empty_message(client: AsyncClient):
    response = await client.post("/api/chat", json={"message": "   "})
    # Pydantic enforces min_length=1; whitespace-only passes Pydantic but
    # the sanitiser empties it, so the endpoint returns 400.
    assert response.status_code in (400, 422)


async def test_chat_rejects_message_too_long(client: AsyncClient):
    response = await client.post("/api/chat", json={"message": "x" * 5000})
    assert response.status_code == 422


async def test_admin_knowledge_requires_auth(client: AsyncClient):
    response = await client.get("/api/admin/chatbot/knowledge")
    assert response.status_code in (401, 403)

    response = await client.post(
        "/api/admin/chatbot/knowledge",
        json={"title": "X", "content": "Y", "tags": []},
    )
    assert response.status_code in (401, 403)


async def test_admin_conversations_requires_auth(client: AsyncClient):
    response = await client.get("/api/admin/chatbot/conversations")
    assert response.status_code in (401, 403)


async def test_admin_analytics_requires_auth(client: AsyncClient):
    response = await client.get("/api/admin/chatbot/analytics")
    assert response.status_code in (401, 403)


async def test_chat_session_key_short_rejected(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(chatbot_service.settings, "chatbot_mode", "stub")
    db = _build_chat_db([])
    app.dependency_overrides[get_session] = _override_session(db)
    monkeypatch.setattr(
        chatbot_api, "_create_enquiry_from_conversation", AsyncMock(return_value=None)
    )
    try:
        response = await client.post(
            "/api/chat",
            json={"message": "hello", "session_key": "short"},
        )
        assert response.status_code == 400
    finally:
        app.dependency_overrides.clear()
