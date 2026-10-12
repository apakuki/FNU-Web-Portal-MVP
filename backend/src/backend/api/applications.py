import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.auth import require_role
from src.backend.db.models import Application, ApplicationDocument, Offer, User
from src.backend.db.session import get_session
from src.backend.rate_limit import limiter
from src.backend.services.audit_service import write_audit_log
from src.backend.services.notification_service import send_notification

router = APIRouter(tags=["applications"])

ALLOWED_MIME_TYPES = {"application/pdf", "image/jpeg", "image/png"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
MAGIC_BYTES = {
    b"%PDF": "application/pdf",
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG": "image/png",
}
VALID_STATUSES = {
    "submitted",
    "under_review",
    "awaiting_documents",
    "approved",
    "conditionally_approved",
    "rejected",
}
REASON_REQUIRED_STATUSES = {"rejected", "awaiting_documents"}

OFFER_TOKEN_EXPIRY_DAYS = 7


# --- Schemas ---


class PersonalDetails(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    date_of_birth: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    gender: str = Field(min_length=1, max_length=20)
    nationality: str = Field(min_length=1, max_length=60)
    address: str = Field(min_length=1, max_length=500)


class PriorQualification(BaseModel):
    institution: str = Field(min_length=1, max_length=200)
    qualification: str = Field(min_length=1, max_length=200)
    year_completed: int = Field(ge=1950, le=2030)
    grade: str = Field(max_length=20)


class ApplicationCreateRequest(BaseModel):
    applicant_email: EmailStr
    applicant_phone: str | None = Field(default=None, max_length=20)
    personal_details: PersonalDetails
    prior_qualifications: list[PriorQualification] = Field(min_length=1)
    programme_preference: str = Field(min_length=1, max_length=20)
    campus_preference: str = Field(min_length=1, max_length=50)
    documents: list[uuid.UUID] = []


class ApplicationCreateResponse(BaseModel):
    id: uuid.UUID
    application_number: str
    status: str
    submitted_at: datetime


class DocumentUploadResponse(BaseModel):
    id: uuid.UUID
    filename: str
    document_type: str
    size_bytes: int


class ApplicationListItem(BaseModel):
    id: uuid.UUID
    application_number: str
    applicant_email: str
    status: str
    programme: str | None = None
    campus: str | None = None
    submitted_at: datetime
    decided_at: datetime | None = None

    model_config = {"from_attributes": True}


class ApplicationListResponse(BaseModel):
    items: list[ApplicationListItem]
    total: int
    page: int
    per_page: int


class ApplicationDetailResponse(BaseModel):
    id: uuid.UUID
    application_number: str
    applicant_email: str
    applicant_phone: str | None
    payload: dict[str, Any]
    status: str
    status_reason: str | None
    is_conditional: bool
    submitted_at: datetime
    decided_at: datetime | None
    documents: list[DocumentUploadResponse]

    model_config = {"from_attributes": True}


class StatusUpdateRequest(BaseModel):
    status: str
    reason: str | None = None
    is_conditional: bool = False


class BulkActionRequest(BaseModel):
    application_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)
    action: str = Field(pattern=r"^(approve|reject|under_review)$")
    reason: str | None = None


class BulkActionResponse(BaseModel):
    updated: int
    failed: int


class OfferDetailResponse(BaseModel):
    programme: str
    campus: str
    applicant_name: str
    is_conditional: bool
    conditions: str | None = None
    issued_at: datetime
    accepted_at: datetime | None = None
    declined_at: datetime | None = None


class OfferActionResponse(BaseModel):
    detail: str
    login_url: str | None = None


# --- Helpers ---


async def _generate_application_number(db: AsyncSession) -> str:
    year = datetime.now(UTC).year
    result = await db.execute(
        select(func.count())
        .select_from(Application)
        .where(Application.application_number.like(f"APP-{year}-%"))
    )
    count = result.scalar_one()
    return f"APP-{year}-{count + 1:06d}"


def _verify_magic_bytes(data: bytes) -> str | None:
    for magic, mime in MAGIC_BYTES.items():
        if data[: len(magic)] == magic:
            return mime
    return None


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# --- Public endpoints ---


@router.post("/applications", response_model=ApplicationCreateResponse, status_code=201)
@limiter.limit("5/hour")
async def create_application(
    body: ApplicationCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_session),
) -> ApplicationCreateResponse:
    app_number = await _generate_application_number(db)

    payload = {
        "personal_details": body.personal_details.model_dump(),
        "prior_qualifications": [q.model_dump() for q in body.prior_qualifications],
        "programme_preference": body.programme_preference,
        "campus_preference": body.campus_preference,
    }

    application = Application(
        application_number=app_number,
        applicant_email=body.applicant_email,
        applicant_phone=body.applicant_phone,
        payload=payload,
        status="submitted",
    )
    db.add(application)
    await db.flush()

    if body.documents:
        await db.execute(
            update(ApplicationDocument)
            .where(ApplicationDocument.id.in_(body.documents))
            .where(ApplicationDocument.application_id.is_(None))
            .values(application_id=application.id)
        )

    await db.commit()
    await db.refresh(application)

    await send_notification(
        channel="email",
        recipient_email=body.applicant_email,
        subject="Application Received",
        body=f"Your application {app_number} has been received and is under review.",
    )

    return ApplicationCreateResponse(
        id=application.id,
        application_number=application.application_number,
        status=application.status,
        submitted_at=application.submitted_at,
    )


@router.post(
    "/applications/documents",
    response_model=DocumentUploadResponse,
    status_code=201,
)
@limiter.limit("20/hour")
async def upload_document(
    request: Request,
    file: UploadFile,
    document_type: str = "other",
    db: AsyncSession = Depends(get_session),
) -> DocumentUploadResponse:
    if document_type not in ("birth_certificate", "transcript", "reference", "other"):
        raise HTTPException(status_code=400, detail="Invalid document_type")

    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail="File type not allowed. Accepted: PDF, JPG, PNG",
        )

    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File exceeds 5MB limit")

    detected_mime = _verify_magic_bytes(data)
    if detected_mime is None or detected_mime != file.content_type:
        raise HTTPException(
            status_code=400,
            detail="File content does not match declared type",
        )

    random_name = f"{uuid.uuid4().hex}_{file.filename or 'upload'}"
    storage_path = f"uploads/applications/{random_name}"

    doc = ApplicationDocument(
        document_type=document_type,
        filename=file.filename or "upload",
        storage_path=storage_path,
        mime_type=detected_mime,
        size_bytes=len(data),
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    return DocumentUploadResponse(
        id=doc.id,
        filename=doc.filename,
        document_type=doc.document_type,
        size_bytes=doc.size_bytes,
    )


# --- Staff endpoints ---


@router.get("/admin/applications", response_model=ApplicationListResponse)
async def list_applications(
    status: str | None = None,
    campus: str | None = None,
    programme: str | None = None,
    page: int = 1,
    per_page: int = 20,
    user: User = Depends(require_role("staff", "admin")),
    db: AsyncSession = Depends(get_session),
) -> ApplicationListResponse:
    query = select(Application)
    count_query = select(func.count()).select_from(Application)

    if status:
        query = query.where(Application.status == status)
        count_query = count_query.where(Application.status == status)

    if campus:
        query = query.where(Application.payload["campus_preference"].astext == campus)
        count_query = count_query.where(
            Application.payload["campus_preference"].astext == campus
        )

    if programme:
        query = query.where(Application.payload["programme_preference"].astext == programme)
        count_query = count_query.where(
            Application.payload["programme_preference"].astext == programme
        )

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    query = (
        query.order_by(Application.submitted_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    result = await db.execute(query)
    apps = result.scalars().all()

    items = [
        ApplicationListItem(
            id=a.id,
            application_number=a.application_number,
            applicant_email=a.applicant_email,
            status=a.status,
            programme=a.payload.get("programme_preference") if a.payload else None,
            campus=a.payload.get("campus_preference") if a.payload else None,
            submitted_at=a.submitted_at,
            decided_at=a.decided_at,
        )
        for a in apps
    ]

    return ApplicationListResponse(items=items, total=total, page=page, per_page=per_page)


@router.get("/admin/applications/{application_id}", response_model=ApplicationDetailResponse)
async def get_application(
    application_id: uuid.UUID,
    user: User = Depends(require_role("staff", "admin")),
    db: AsyncSession = Depends(get_session),
) -> ApplicationDetailResponse:
    result = await db.execute(
        select(Application).where(Application.id == application_id)
    )
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    doc_result = await db.execute(
        select(ApplicationDocument).where(
            ApplicationDocument.application_id == application_id
        )
    )
    docs = doc_result.scalars().all()

    return ApplicationDetailResponse(
        id=app.id,
        application_number=app.application_number,
        applicant_email=app.applicant_email,
        applicant_phone=app.applicant_phone,
        payload=app.payload,
        status=app.status,
        status_reason=app.status_reason,
        is_conditional=app.is_conditional,
        submitted_at=app.submitted_at,
        decided_at=app.decided_at,
        documents=[
            DocumentUploadResponse(
                id=d.id,
                filename=d.filename,
                document_type=d.document_type,
                size_bytes=d.size_bytes,
            )
            for d in docs
        ],
    )


@router.put("/admin/applications/{application_id}/status")
async def update_application_status(
    application_id: uuid.UUID,
    body: StatusUpdateRequest,
    request: Request,
    user: User = Depends(require_role("staff", "admin")),
    db: AsyncSession = Depends(get_session),
) -> ApplicationDetailResponse:
    if body.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status: {body.status}")

    if body.status in REASON_REQUIRED_STATUSES and not body.reason:
        raise HTTPException(
            status_code=400,
            detail=f"Reason is required when status is {body.status}",
        )

    result = await db.execute(
        select(Application).where(Application.id == application_id)
    )
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    old_status = app.status
    app.status = body.status
    app.status_reason = body.reason
    app.is_conditional = body.is_conditional

    if body.status in ("approved", "conditionally_approved", "rejected"):
        app.decided_at = datetime.now(UTC)

    offer = None
    if body.status in ("approved", "conditionally_approved"):
        token = secrets.token_urlsafe(48)
        offer = Offer(
            application_id=app.id,
            pdf_storage_path=f"offers/{app.application_number}.pdf",
            acceptance_token=_hash_token(token),
        )
        db.add(offer)

    await db.commit()
    await db.refresh(app)

    await write_audit_log(
        actor_user_id=user.id,
        action=f"application.{body.status}",
        target_type="application",
        target_id=str(app.id),
        before={"status": old_status},
        after={"status": body.status, "reason": body.reason},
        ip_address=request.client.host if request.client else None,
    )

    await send_notification(
        channel="email",
        recipient_email=app.applicant_email,
        subject=f"Application {app.application_number} — Status Update",
        body=f"Your application status has been updated to: {body.status}."
        + (f" Reason: {body.reason}" if body.reason else ""),
    )

    doc_result = await db.execute(
        select(ApplicationDocument).where(
            ApplicationDocument.application_id == application_id
        )
    )
    docs = doc_result.scalars().all()

    return ApplicationDetailResponse(
        id=app.id,
        application_number=app.application_number,
        applicant_email=app.applicant_email,
        applicant_phone=app.applicant_phone,
        payload=app.payload,
        status=app.status,
        status_reason=app.status_reason,
        is_conditional=app.is_conditional,
        submitted_at=app.submitted_at,
        decided_at=app.decided_at,
        documents=[
            DocumentUploadResponse(
                id=d.id,
                filename=d.filename,
                document_type=d.document_type,
                size_bytes=d.size_bytes,
            )
            for d in docs
        ],
    )


@router.post("/admin/applications/bulk-action", response_model=BulkActionResponse)
async def bulk_action(
    body: BulkActionRequest,
    request: Request,
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_session),
) -> BulkActionResponse:
    status_map = {
        "approve": "approved",
        "reject": "rejected",
        "under_review": "under_review",
    }
    new_status = status_map[body.action]

    if body.action == "reject" and not body.reason:
        raise HTTPException(status_code=400, detail="Reason required for rejection")

    result = await db.execute(
        select(Application).where(Application.id.in_(body.application_ids))
    )
    apps = result.scalars().all()

    updated = 0
    failed = 0
    for app in apps:
        old_status = app.status
        app.status = new_status
        app.status_reason = body.reason
        if new_status in ("approved", "rejected"):
            app.decided_at = datetime.now(UTC)

        if new_status == "approved":
            token = secrets.token_urlsafe(48)
            offer = Offer(
                application_id=app.id,
                pdf_storage_path=f"offers/{app.application_number}.pdf",
                acceptance_token=_hash_token(token),
            )
            db.add(offer)

        await write_audit_log(
            actor_user_id=user.id,
            action=f"application.bulk_{body.action}",
            target_type="application",
            target_id=str(app.id),
            before={"status": old_status},
            after={"status": new_status, "reason": body.reason},
            ip_address=request.client.host if request.client else None,
        )
        updated += 1

    await db.commit()

    return BulkActionResponse(updated=updated, failed=failed)


# --- Offer endpoints ---


@router.get("/offers/{token}", response_model=OfferDetailResponse)
async def get_offer(
    token: str,
    db: AsyncSession = Depends(get_session),
) -> OfferDetailResponse:
    token_hash = _hash_token(token)
    result = await db.execute(
        select(Offer).where(Offer.acceptance_token == token_hash)
    )
    offer = result.scalar_one_or_none()
    if not offer:
        raise HTTPException(status_code=404, detail="Invalid or expired offer link")

    if offer.issued_at.replace(tzinfo=UTC) + timedelta(days=OFFER_TOKEN_EXPIRY_DAYS) < datetime.now(
        UTC
    ):
        raise HTTPException(status_code=410, detail="Offer has expired")

    app_result = await db.execute(
        select(Application).where(Application.id == offer.application_id)
    )
    app = app_result.scalar_one()
    pd = app.payload.get("personal_details", {})

    return OfferDetailResponse(
        programme=app.payload.get("programme_preference", ""),
        campus=app.payload.get("campus_preference", ""),
        applicant_name=f"{pd.get('first_name', '')} {pd.get('last_name', '')}".strip(),
        is_conditional=app.is_conditional,
        conditions=app.status_reason if app.is_conditional else None,
        issued_at=offer.issued_at,
        accepted_at=offer.accepted_at,
        declined_at=offer.declined_at,
    )


@router.post("/offers/{token}/accept", response_model=OfferActionResponse)
async def accept_offer(
    token: str,
    db: AsyncSession = Depends(get_session),
) -> OfferActionResponse:
    token_hash = _hash_token(token)
    result = await db.execute(
        select(Offer).where(Offer.acceptance_token == token_hash)
    )
    offer = result.scalar_one_or_none()
    if not offer:
        raise HTTPException(status_code=404, detail="Invalid or expired offer link")

    if offer.accepted_at or offer.declined_at:
        raise HTTPException(status_code=400, detail="Offer has already been responded to")

    if offer.issued_at.replace(tzinfo=UTC) + timedelta(days=OFFER_TOKEN_EXPIRY_DAYS) < datetime.now(
        UTC
    ):
        raise HTTPException(status_code=410, detail="Offer has expired")

    offer.accepted_at = datetime.now(UTC)
    await db.commit()

    app_result = await db.execute(
        select(Application).where(Application.id == offer.application_id)
    )
    app = app_result.scalar_one()

    await send_notification(
        channel="email",
        recipient_email=app.applicant_email,
        subject=f"Offer Accepted — {app.application_number}",
        body="Congratulations! Your offer has been accepted. "
        "You will receive enrolment details shortly.",
    )

    return OfferActionResponse(detail="Offer accepted", login_url="/login")


@router.post("/offers/{token}/decline", response_model=OfferActionResponse)
async def decline_offer(
    token: str,
    db: AsyncSession = Depends(get_session),
) -> OfferActionResponse:
    token_hash = _hash_token(token)
    result = await db.execute(
        select(Offer).where(Offer.acceptance_token == token_hash)
    )
    offer = result.scalar_one_or_none()
    if not offer:
        raise HTTPException(status_code=404, detail="Invalid or expired offer link")

    if offer.accepted_at or offer.declined_at:
        raise HTTPException(status_code=400, detail="Offer has already been responded to")

    offer.declined_at = datetime.now(UTC)
    await db.commit()

    return OfferActionResponse(detail="Offer declined")
