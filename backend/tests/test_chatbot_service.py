"""Unit tests for the chatbot service helpers — sanitisation, retrieval, prompt
composition, escalation, PII masking, and the stub reply generator."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.backend.db.models import ChatbotKnowledge
from src.backend.services.chatbot_service import (
    RetrievedFaq,
    StudentContext,
    compose_messages,
    decide_escalation,
    mask_pii,
    retrieve_knowledge,
    sanitize_message,
    stub_reply,
)

# ---------- sanitisation ----------


def test_sanitize_message_strips_control_characters():
    raw = "Hello\x00\x01world\nnext\tline"
    cleaned = sanitize_message(raw)
    assert "\x00" not in cleaned
    assert "\x01" not in cleaned
    assert "\n" in cleaned
    assert "\t" in cleaned


def test_sanitize_message_clamps_length():
    text = "a" * 5000
    cleaned = sanitize_message(text, max_chars=100)
    assert len(cleaned) == 100


def test_sanitize_message_trims_whitespace():
    assert sanitize_message("   hello   ") == "hello"


# ---------- retrieval ----------


def _knowledge(title: str, content: str, tags: list[str] | None = None):
    return ChatbotKnowledge(
        id=uuid.uuid4(),
        kind="faq",
        title=title,
        content=content,
        tags=tags or [],
        is_active=True,
    )


def _mock_db_with_rows(rows):
    db = AsyncMock()
    scalars_result = MagicMock()
    scalars_result.all.return_value = rows
    db.scalars.return_value = scalars_result
    return db


async def test_retrieve_knowledge_returns_best_match_first():
    rows = [
        _knowledge("Graduation requirements", "Need GPA 2.0 to graduate", ["graduation"]),
        _knowledge(
            "Bachelor of Nursing entry requirements",
            "BNUR requires biology and chemistry",
            ["nursing", "admissions"],
        ),
    ]
    db = _mock_db_with_rows(rows)
    results = await retrieve_knowledge(db, "What are the entry requirements for nursing?")
    assert results[0].title == "Bachelor of Nursing entry requirements"


async def test_retrieve_knowledge_filters_zero_score():
    rows = [_knowledge("Graduation", "GPA requirements", ["graduation"])]
    db = _mock_db_with_rows(rows)
    results = await retrieve_knowledge(db, "How do I cook pasta?")
    assert results == []


async def test_retrieve_knowledge_handles_empty_query():
    db = _mock_db_with_rows([])
    assert await retrieve_knowledge(db, "   ") == []


async def test_retrieve_knowledge_respects_limit():
    rows = [_knowledge(f"Entry {i}", "fees fees fees fees", ["fees"]) for i in range(5)]
    db = _mock_db_with_rows(rows)
    results = await retrieve_knowledge(db, "tell me about fees", limit=2)
    assert len(results) == 2


# ---------- prompt composition ----------


def _faq(title: str, content: str = "body") -> RetrievedFaq:
    return RetrievedFaq(id=uuid.uuid4(), title=title, content=content, score=10)


def test_compose_messages_includes_system_and_user_blocks():
    messages = compose_messages(
        user_message="What is the fee?",
        history=[],
        faqs=[_faq("Fees")],
        student=None,
    )
    assert messages[0]["role"] == "system"
    assert "FNU" in messages[0]["content"]
    assert "FAQ 1" in messages[0]["content"]
    assert messages[-1]["role"] == "user"
    assert "<student_message>" in messages[-1]["content"]


def test_compose_messages_includes_student_context_when_authenticated():
    student = StudentContext(
        full_name="Apisai Delana",
        banner_id="S00012345",
        programme_code="BCOM",
        balance_cents=189000,
        registered_courses=("ACC201", "MGT101"),
    )
    messages = compose_messages(
        user_message="What is my balance?",
        history=[],
        faqs=[],
        student=student,
    )
    system = messages[0]["content"]
    assert "S00012345" in system
    assert "FJ$1890.00" in system
    assert "ACC201" in system


def test_compose_messages_trims_history_to_max_turns():
    long_history = []
    for i in range(200):
        long_history.append({"role": "user", "content": f"q{i}"})
        long_history.append({"role": "assistant", "content": f"a{i}"})
    messages = compose_messages(
        user_message="hi", history=long_history, faqs=[], student=None
    )
    # 1 system + N history messages + 1 final user
    history_count = len(messages) - 2
    assert history_count <= 100  # default max_history_turns(50) * 2


def test_compose_messages_skips_unknown_roles():
    history = [{"role": "tool", "content": "ignored"}, {"role": "user", "content": "kept"}]
    messages = compose_messages(
        user_message="hi", history=history, faqs=[], student=None
    )
    assert all(m["content"] != "ignored" for m in messages)
    assert any(m["content"] == "kept" for m in messages)


# ---------- escalation ----------


def test_escalate_on_explicit_human_request():
    decision = decide_escalation("Please let me speak to a human", "ok", retrieved_count=2)
    assert decision.escalate is True
    assert decision.reason == "user_requested_human"


def test_escalate_on_low_confidence_reply():
    decision = decide_escalation(
        "What is the policy?", "I'm not sure about that policy.", retrieved_count=1
    )
    assert decision.escalate is True
    assert decision.reason == "low_confidence_reply"


def test_escalate_on_no_matching_faq_for_substantive_question():
    decision = decide_escalation("What does my plan look like?", "answer", retrieved_count=0)
    assert decision.escalate is True
    assert decision.reason == "no_matching_faq"


def test_no_escalation_for_short_question_with_no_faq():
    decision = decide_escalation("hi", "hello", retrieved_count=0)
    assert decision.escalate is False


def test_no_escalation_when_faq_matched_and_reply_confident():
    decision = decide_escalation(
        "What are the fees?", "Fees are FJ$3,780.", retrieved_count=2
    )
    assert decision.escalate is False


# ---------- PII masking ----------


def test_mask_pii_redacts_banner_id():
    masked = mask_pii("Student S00012345 has paid")
    assert "S00012345" not in masked
    assert "S******" in masked


def test_mask_pii_redacts_email():
    masked = mask_pii("Contact apisai@fnu.ac.fj for help")
    assert "apisai@fnu.ac.fj" not in masked
    assert "@fnu.ac.fj" in masked


def test_mask_pii_handles_short_email_local():
    masked = mask_pii("Contact ab@x.com")
    assert masked == "Contact **@x.com"


# ---------- stub reply ----------


def test_stub_reply_returns_top_faq_content():
    faqs = [_faq("Fees", "FJ$3,780 per semester"), _faq("Other")]
    reply = stub_reply("How much are fees?", faqs)
    assert "FJ$3,780 per semester" in reply
    assert "Related topics" in reply


def test_stub_reply_offers_escalation_when_no_faq():
    reply = stub_reply("random unrelated question?", [])
    assert "speak to a human" in reply.lower()


# ---------- input contracts ----------


def test_sanitize_message_default_max_from_settings():
    # Just ensure the call without max_chars uses the configured default.
    from src.backend.config import settings

    text = "x" * (settings.chatbot_max_message_chars + 50)
    cleaned = sanitize_message(text)
    assert len(cleaned) <= settings.chatbot_max_message_chars


def test_retrieved_faq_is_immutable():
    faq = _faq("X")
    with pytest.raises(Exception):
        faq.title = "changed"  # type: ignore[misc]
