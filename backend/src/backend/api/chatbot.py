"""Chatbot API — public chat endpoint plus admin knowledge / conversation tools."""

from __future__ import annotations

import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.auth import get_optional_user, require_role
from src.backend.banner import get_banner_client
from src.backend.config import settings
from src.backend.db.models import (
    ChatbotConversation,
    ChatbotKnowledge,
    Enquiry,
    User,
)
from src.backend.db.session import get_session
from src.backend.rate_limit import limiter
from src.backend.services.audit_service import write_audit_log
from src.backend.services.chatbot_service import (
    ChatbotError,
    StudentContext,
    call_openrouter,
    compose_messages,
    decide_escalation,
    mask_pii,
    retrieve_knowledge,
    sanitize_message,
    stub_reply,
)
from src.backend.services.notification_service import send_notification

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chatbot"])


# --- Schemas ---


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_key: str | None = Field(default=None, max_length=80)


class ChatSourceOut(BaseModel):
    title: str


class ChatResponse(BaseModel):
    session_key: str
    reply: str
    escalated: bool
    escalation_reason: str | None = None
    sources: list[ChatSourceOut] = []


class KnowledgeRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=20000)
    kind: str = Field(default="faq", min_length=1, max_length=40)
    tags: list[str] = Field(default_factory=list, max_length=20)
    is_active: bool = True


class KnowledgeOut(BaseModel):
    id: uuid.UUID
    kind: str
    title: str
    content: str
    tags: list[str]
    is_active: bool
    updated_at: datetime


class ConversationOut(BaseModel):
    id: uuid.UUID
    session_key: str
    user_id: uuid.UUID | None
    escalated: bool
    resolved: bool
    category: str | None
    message_count: int
    last_message_preview: str
    created_at: datetime
    updated_at: datetime


class ConversationsList(BaseModel):
    total: int
    conversations: list[ConversationOut]


class ConversationDetailMessage(BaseModel):
    role: str
    content: str
    timestamp: str | None = None


class ConversationDetail(BaseModel):
    id: uuid.UUID
    session_key: str
    user_id: uuid.UUID | None
    escalated: bool
    resolved: bool
    category: str | None
    messages: list[ConversationDetailMessage]
    created_at: datetime
    updated_at: datetime


class AnalyticsOut(BaseModel):
    total_conversations: int
    escalated_conversations: int
    resolved_conversations: int
    escalation_rate: float
    resolution_rate: float
    active_knowledge_entries: int
    top_categories: list[dict]


# --- Helpers ---


_SCRIPT_BLOCK_RE = (
    "<script",
    "javascript:",
    "onerror=",
    "onload=",
)


def _sanitise_knowledge_field(text: str) -> str:
    lowered = text.lower()
    if any(token in lowered for token in _SCRIPT_BLOCK_RE):
        raise HTTPException(
            status_code=400, detail="FAQ content may not contain script markup"
        )
    return text.strip()


async def _build_student_context(user: User, db: AsyncSession) -> StudentContext | None:
    """Fetch the student's balance and registered courses; tolerate Banner failures."""
    if user.role != "student" or not user.banner_id:
        return None

    balance_cents: int | None = None
    courses: tuple[str, ...] = ()
    programme: str | None = None

    try:
        banner = get_banner_client()
        invoices = await banner.get_invoices(user.banner_id)
        balance_cents = sum((i.total_cents - i.paid_cents) for i in invoices)
        registrations = await banner.get_student_registrations(
            user.banner_id, semester="S1", year=2026
        )
        courses = tuple(getattr(r, "course_code", str(r)) for r in registrations)
        student = await banner.get_student(user.banner_id)
        programme = getattr(student, "programme_code", None)
    except Exception:  # noqa: BLE001 — Banner outage must not break the chat
        logger.warning("Banner lookup failed for student context; continuing without it")

    return StudentContext(
        full_name=user.full_name,
        banner_id=user.banner_id,
        programme_code=programme,
        balance_cents=balance_cents,
        registered_courses=courses,
    )


async def _persist_conversation(
    db: AsyncSession,
    *,
    session_key: str,
    user_id: uuid.UUID | None,
    user_message: str,
    reply: str,
    escalated: bool,
    escalation_reason: str | None,
) -> ChatbotConversation:
    convo = await db.scalar(
        select(ChatbotConversation).where(ChatbotConversation.session_key == session_key)
    )
    now_iso = datetime.now(UTC).isoformat()
    new_messages: list[dict[str, Any]] = [
        {"role": "user", "content": user_message, "timestamp": now_iso},
        {"role": "assistant", "content": reply, "timestamp": now_iso},
    ]
    if convo is None:
        convo = ChatbotConversation(
            user_id=user_id,
            session_key=session_key,
            messages=new_messages,
            escalated=escalated,
            category=escalation_reason if escalated else None,
        )
        db.add(convo)
    else:
        existing = list(convo.messages or [])
        existing.extend(new_messages)
        # Cap stored history to prevent unbounded JSONB growth.
        max_stored = settings.chatbot_max_history_turns * 2
        if len(existing) > max_stored:
            existing = existing[-max_stored:]
        convo.messages = existing
        if escalated and not convo.escalated:
            convo.escalated = True
            convo.category = escalation_reason

    await db.commit()
    await db.refresh(convo)
    return convo


async def _create_enquiry_from_conversation(
    db: AsyncSession,
    convo: ChatbotConversation,
    user: User | None,
    user_message: str,
) -> None:
    enquiry = Enquiry(
        source="chatbot",
        student_user_id=user.id if user else None,
        student_identifier=user.banner_id if user else None,
        subject=f"Chatbot escalation: {user_message[:80]}",
        body=user_message,
        status="open",
    )
    db.add(enquiry)
    await db.commit()

    # Best-effort staff alert; never block the user response on the notification.
    try:
        await send_notification(
            channel="email",
            recipient_email="enquiries@fnu.ac.fj",
            subject="Chatbot escalation",
            body=f"A chatbot conversation was escalated. Session {convo.session_key}.",
            template_code="chatbot_escalation",
        )
    except Exception:  # noqa: BLE001
        logger.warning("Failed to send escalation notification")


# --- Public chat endpoint ---


@router.post("/api/chat", response_model=ChatResponse)
@limiter.limit("30/minute")
async def chat(
    request: Request,
    body: ChatRequest,
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_session),
) -> ChatResponse:
    cleaned = sanitize_message(body.message)
    if not cleaned:
        raise HTTPException(status_code=400, detail="Empty message")

    session_key = body.session_key or secrets.token_urlsafe(16)
    if len(session_key) > 80 or len(session_key) < 8:
        raise HTTPException(status_code=400, detail="Invalid session_key")

    faqs = await retrieve_knowledge(db, cleaned, limit=3)

    # Load prior history for this session (if any) so multi-turn conversations work.
    convo_existing = await db.scalar(
        select(ChatbotConversation).where(ChatbotConversation.session_key == session_key)
    )
    history = list(convo_existing.messages or []) if convo_existing else []

    student_ctx = await _build_student_context(user, db) if user else None

    if settings.chatbot_mode == "live":
        messages = compose_messages(
            user_message=cleaned, history=history, faqs=faqs, student=student_ctx
        )
        try:
            reply = await call_openrouter(messages)
        except ChatbotError as exc:
            logger.warning("Chatbot LLM call failed: %s", exc)
            reply = stub_reply(cleaned, faqs)
    else:
        reply = stub_reply(cleaned, faqs)

    decision = decide_escalation(cleaned, reply, len(faqs))

    convo = await _persist_conversation(
        db,
        session_key=session_key,
        user_id=user.id if user else None,
        user_message=cleaned,
        reply=reply,
        escalated=decision.escalate,
        escalation_reason=decision.reason,
    )

    if decision.escalate and (convo_existing is None or not convo_existing.escalated):
        await _create_enquiry_from_conversation(db, convo, user, cleaned)

    return ChatResponse(
        session_key=session_key,
        reply=reply,
        escalated=decision.escalate,
        escalation_reason=decision.reason,
        sources=[ChatSourceOut(title=f.title) for f in faqs],
    )


# --- Admin knowledge CRUD ---


@router.get("/api/admin/chatbot/knowledge", response_model=list[KnowledgeOut])
async def list_knowledge(
    include_inactive: bool = False,
    _user: User = Depends(require_role("admin", "staff")),
    db: AsyncSession = Depends(get_session),
) -> list[KnowledgeOut]:
    stmt = select(ChatbotKnowledge).order_by(ChatbotKnowledge.title)
    if not include_inactive:
        stmt = stmt.where(ChatbotKnowledge.is_active.is_(True))
    rows = (await db.scalars(stmt)).all()
    return [
        KnowledgeOut(
            id=r.id,
            kind=r.kind,
            title=r.title,
            content=r.content,
            tags=list(r.tags or []),
            is_active=r.is_active,
            updated_at=r.updated_at,
        )
        for r in rows
    ]


@router.post("/api/admin/chatbot/knowledge", response_model=KnowledgeOut, status_code=201)
async def create_knowledge(
    request: Request,
    body: KnowledgeRequest,
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_session),
) -> KnowledgeOut:
    title = _sanitise_knowledge_field(body.title)
    content = _sanitise_knowledge_field(body.content)
    entry = ChatbotKnowledge(
        kind=body.kind,
        title=title,
        content=content,
        tags=body.tags,
        is_active=body.is_active,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)

    await write_audit_log(
        actor_user_id=user.id,
        action="chatbot.knowledge.create",
        target_type="chatbot_knowledge",
        target_id=str(entry.id),
        after={"title": title, "tags": body.tags},
        ip_address=request.client.host if request.client else None,
    )
    return KnowledgeOut(
        id=entry.id,
        kind=entry.kind,
        title=entry.title,
        content=entry.content,
        tags=list(entry.tags or []),
        is_active=entry.is_active,
        updated_at=entry.updated_at,
    )


@router.put("/api/admin/chatbot/knowledge/{entry_id}", response_model=KnowledgeOut)
async def update_knowledge(
    entry_id: uuid.UUID,
    body: KnowledgeRequest,
    request: Request,
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_session),
) -> KnowledgeOut:
    entry = await db.scalar(
        select(ChatbotKnowledge).where(ChatbotKnowledge.id == entry_id)
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Knowledge entry not found")

    before = {"title": entry.title, "is_active": entry.is_active}
    entry.title = _sanitise_knowledge_field(body.title)
    entry.content = _sanitise_knowledge_field(body.content)
    entry.kind = body.kind
    entry.tags = body.tags
    entry.is_active = body.is_active
    await db.commit()
    await db.refresh(entry)

    await write_audit_log(
        actor_user_id=user.id,
        action="chatbot.knowledge.update",
        target_type="chatbot_knowledge",
        target_id=str(entry.id),
        before=before,
        after={"title": entry.title, "is_active": entry.is_active},
        ip_address=request.client.host if request.client else None,
    )
    return KnowledgeOut(
        id=entry.id,
        kind=entry.kind,
        title=entry.title,
        content=entry.content,
        tags=list(entry.tags or []),
        is_active=entry.is_active,
        updated_at=entry.updated_at,
    )


@router.delete("/api/admin/chatbot/knowledge/{entry_id}", status_code=204)
async def delete_knowledge(
    entry_id: uuid.UUID,
    request: Request,
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_session),
) -> None:
    entry = await db.scalar(
        select(ChatbotKnowledge).where(ChatbotKnowledge.id == entry_id)
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Knowledge entry not found")
    entry.is_active = False
    await db.commit()
    await write_audit_log(
        actor_user_id=user.id,
        action="chatbot.knowledge.delete",
        target_type="chatbot_knowledge",
        target_id=str(entry.id),
        before={"is_active": True},
        after={"is_active": False},
        ip_address=request.client.host if request.client else None,
    )


# --- Admin conversations log ---


@router.get("/api/admin/chatbot/conversations", response_model=ConversationsList)
async def list_conversations(
    q: str | None = None,
    escalated: bool | None = None,
    limit: int = 50,
    offset: int = 0,
    _user: User = Depends(require_role("admin", "staff")),
    db: AsyncSession = Depends(get_session),
) -> ConversationsList:
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=400, detail="limit must be 1..200")
    if offset < 0:
        raise HTTPException(status_code=400, detail="offset must be >= 0")

    conditions = []
    if escalated is not None:
        conditions.append(ChatbotConversation.escalated.is_(escalated))
    if q:
        like = f"%{q.lower()}%"
        conditions.append(
            or_(
                func.lower(ChatbotConversation.session_key).like(like),
                func.lower(func.coalesce(ChatbotConversation.category, "")).like(like),
            )
        )

    base_stmt = select(ChatbotConversation)
    if conditions:
        base_stmt = base_stmt.where(and_(*conditions))

    total = await db.scalar(
        select(func.count()).select_from(base_stmt.subquery())
    ) or 0

    rows = (
        await db.scalars(
            base_stmt.order_by(ChatbotConversation.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()

    out: list[ConversationOut] = []
    for r in rows:
        messages = list(r.messages or [])
        last = messages[-1]["content"] if messages else ""
        preview = mask_pii(last)[:160]
        out.append(
            ConversationOut(
                id=r.id,
                session_key=r.session_key,
                user_id=r.user_id,
                escalated=r.escalated,
                resolved=r.resolved,
                category=r.category,
                message_count=len(messages),
                last_message_preview=preview,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
        )

    return ConversationsList(total=total, conversations=out)


@router.get(
    "/api/admin/chatbot/conversations/{convo_id}", response_model=ConversationDetail
)
async def get_conversation(
    convo_id: uuid.UUID,
    _user: User = Depends(require_role("admin", "staff")),
    db: AsyncSession = Depends(get_session),
) -> ConversationDetail:
    convo = await db.scalar(
        select(ChatbotConversation).where(ChatbotConversation.id == convo_id)
    )
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages_out = [
        ConversationDetailMessage(
            role=m.get("role", "user"),
            content=mask_pii(str(m.get("content", ""))),
            timestamp=m.get("timestamp"),
        )
        for m in (convo.messages or [])
    ]
    return ConversationDetail(
        id=convo.id,
        session_key=convo.session_key,
        user_id=convo.user_id,
        escalated=convo.escalated,
        resolved=convo.resolved,
        category=convo.category,
        messages=messages_out,
        created_at=convo.created_at,
        updated_at=convo.updated_at,
    )


# --- Admin analytics ---


@router.get("/api/admin/chatbot/analytics", response_model=AnalyticsOut)
async def chatbot_analytics(
    days: int = 30,
    _user: User = Depends(require_role("admin", "manager", "staff")),
    db: AsyncSession = Depends(get_session),
) -> AnalyticsOut:
    if days < 1 or days > 365:
        raise HTTPException(status_code=400, detail="days must be 1..365")
    since = datetime.now(UTC) - timedelta(days=days)

    total = (
        await db.scalar(
            select(func.count()).select_from(ChatbotConversation).where(
                ChatbotConversation.created_at >= since
            )
        )
    ) or 0
    escalated = (
        await db.scalar(
            select(func.count())
            .select_from(ChatbotConversation)
            .where(
                and_(
                    ChatbotConversation.created_at >= since,
                    ChatbotConversation.escalated.is_(True),
                )
            )
        )
    ) or 0
    resolved = (
        await db.scalar(
            select(func.count())
            .select_from(ChatbotConversation)
            .where(
                and_(
                    ChatbotConversation.created_at >= since,
                    ChatbotConversation.resolved.is_(True),
                )
            )
        )
    ) or 0
    active_knowledge = (
        await db.scalar(
            select(func.count())
            .select_from(ChatbotKnowledge)
            .where(ChatbotKnowledge.is_active.is_(True))
        )
    ) or 0

    category_rows = (
        await db.execute(
            select(
                ChatbotConversation.category,
                func.count().label("n"),
            )
            .where(
                and_(
                    ChatbotConversation.created_at >= since,
                    ChatbotConversation.category.isnot(None),
                )
            )
            .group_by(ChatbotConversation.category)
            .order_by(func.count().desc())
            .limit(5)
        )
    ).all()
    top_categories = [{"category": cat, "count": n} for cat, n in category_rows]

    return AnalyticsOut(
        total_conversations=total,
        escalated_conversations=escalated,
        resolved_conversations=resolved,
        escalation_rate=round(escalated / total, 3) if total else 0.0,
        resolution_rate=round(resolved / total, 3) if total else 0.0,
        active_knowledge_entries=active_knowledge,
        top_categories=top_categories,
    )
