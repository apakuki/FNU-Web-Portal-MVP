"""Tests for the application flow API endpoints.

Focuses on input validation (no DB needed) and document upload security.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from src.backend.api.applications import (
    ALLOWED_MIME_TYPES,
    MAX_FILE_SIZE,
    REASON_REQUIRED_STATUSES,
    VALID_STATUSES,
    ApplicationCreateRequest,
    PersonalDetails,
    PriorQualification,
    StatusUpdateRequest,
    _hash_token,
    _verify_magic_bytes,
)
from src.backend.main import app


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _valid_payload(**overrides):
    base = {
        "applicant_email": "jane@email.com",
        "applicant_phone": "+6799991234",
        "personal_details": {
            "first_name": "Jane",
            "last_name": "Doe",
            "date_of_birth": "2000-01-15",
            "gender": "female",
            "nationality": "Fijian",
            "address": "123 Main St, Suva",
        },
        "prior_qualifications": [
            {
                "institution": "Suva Grammar School",
                "qualification": "Year 13",
                "year_completed": 2023,
                "grade": "A",
            }
        ],
        "programme_preference": "BCOM",
        "campus_preference": "Nasinu",
    }
    base.update(overrides)
    return base


# --- Schema validation tests (no DB) ---


def test_valid_application_schema():
    data = _valid_payload()
    req = ApplicationCreateRequest(**data)
    assert req.applicant_email == "jane@email.com"
    assert req.personal_details.first_name == "Jane"
    assert len(req.prior_qualifications) == 1


def test_application_missing_email():
    data = _valid_payload()
    del data["applicant_email"]
    with pytest.raises(Exception):
        ApplicationCreateRequest(**data)


def test_application_invalid_email():
    data = _valid_payload(applicant_email="not-an-email")
    with pytest.raises(Exception):
        ApplicationCreateRequest(**data)


def test_application_no_qualifications():
    data = _valid_payload(prior_qualifications=[])
    with pytest.raises(Exception):
        ApplicationCreateRequest(**data)


def test_application_invalid_dob():
    data = _valid_payload()
    data["personal_details"]["date_of_birth"] = "not-a-date"
    with pytest.raises(Exception):
        ApplicationCreateRequest(**data)


def test_application_name_too_long():
    data = _valid_payload()
    data["personal_details"]["first_name"] = "A" * 101
    with pytest.raises(Exception):
        ApplicationCreateRequest(**data)


def test_application_valid_phone_optional():
    data = _valid_payload()
    del data["applicant_phone"]
    req = ApplicationCreateRequest(**data)
    assert req.applicant_phone is None


def test_personal_details_validation():
    pd = PersonalDetails(
        first_name="Jane",
        last_name="Doe",
        date_of_birth="2000-01-15",
        gender="female",
        nationality="Fijian",
        address="123 Main St",
    )
    assert pd.first_name == "Jane"


def test_personal_details_empty_name():
    with pytest.raises(Exception):
        PersonalDetails(
            first_name="",
            last_name="Doe",
            date_of_birth="2000-01-15",
            gender="female",
            nationality="Fijian",
            address="123 Main St",
        )


def test_qualification_year_bounds():
    PriorQualification(
        institution="School",
        qualification="Year 13",
        year_completed=2023,
        grade="A",
    )
    with pytest.raises(Exception):
        PriorQualification(
            institution="School",
            qualification="Year 13",
            year_completed=1900,
            grade="A",
        )


# --- Status update validation ---


def test_status_update_schema_accepts_all():
    req = StatusUpdateRequest(status="rejected", reason="Incomplete docs")
    assert req.reason == "Incomplete docs"
    req2 = StatusUpdateRequest(status="approved")
    assert req2.reason is None


def test_status_update_valid_statuses():
    for status in VALID_STATUSES:
        if status not in REASON_REQUIRED_STATUSES:
            req = StatusUpdateRequest(status=status)
            assert req.status == status


# --- Magic byte verification ---


def test_magic_bytes_pdf():
    assert _verify_magic_bytes(b"%PDF-1.4 content") == "application/pdf"


def test_magic_bytes_jpeg():
    assert _verify_magic_bytes(b"\xff\xd8\xff\xe0 content") == "image/jpeg"


def test_magic_bytes_png():
    assert _verify_magic_bytes(b"\x89PNG\r\n content") == "image/png"


def test_magic_bytes_unknown():
    assert _verify_magic_bytes(b"unknown format") is None


def test_magic_bytes_empty():
    assert _verify_magic_bytes(b"") is None


# --- Token hashing ---


def test_hash_token_deterministic():
    token = "test-token-12345"
    assert _hash_token(token) == _hash_token(token)


def test_hash_token_different_inputs():
    assert _hash_token("token-a") != _hash_token("token-b")


# --- API validation tests (422 responses, no DB needed) ---


async def test_api_missing_email(client: AsyncClient):
    payload = _valid_payload()
    del payload["applicant_email"]
    response = await client.post("/api/applications", json=payload)
    assert response.status_code == 422


async def test_api_invalid_email(client: AsyncClient):
    payload = _valid_payload(applicant_email="bad")
    response = await client.post("/api/applications", json=payload)
    assert response.status_code == 422


async def test_api_empty_qualifications(client: AsyncClient):
    payload = _valid_payload(prior_qualifications=[])
    response = await client.post("/api/applications", json=payload)
    assert response.status_code == 422


async def test_api_missing_personal_details(client: AsyncClient):
    payload = _valid_payload()
    del payload["personal_details"]
    response = await client.post("/api/applications", json=payload)
    assert response.status_code == 422


async def test_api_document_wrong_mime(client: AsyncClient):
    response = await client.post(
        "/api/applications/documents",
        files={"file": ("test.exe", b"MZ\x00\x00", "application/x-msdownload")},
        data={"document_type": "transcript"},
    )
    assert response.status_code == 400
    assert "not allowed" in response.json()["detail"]


async def test_api_document_invalid_type(client: AsyncClient):
    response = await client.post(
        "/api/applications/documents",
        files={"file": ("test.txt", b"just text", "text/plain")},
        data={"document_type": "malicious_type"},
    )
    assert response.status_code == 400


async def test_api_document_magic_mismatch(client: AsyncClient):
    response = await client.post(
        "/api/applications/documents",
        files={"file": ("fake.pdf", b"NOT_A_PDF_CONTENT", "application/pdf")},
        data={"document_type": "transcript"},
    )
    assert response.status_code == 400
    assert "does not match" in response.json()["detail"]


async def test_api_document_too_large(client: AsyncClient):
    large_pdf = b"%PDF" + b"\x00" * (6 * 1024 * 1024)
    response = await client.post(
        "/api/applications/documents",
        files={"file": ("big.pdf", large_pdf, "application/pdf")},
        data={"document_type": "transcript"},
    )
    assert response.status_code == 400
    assert "5MB" in response.json()["detail"]


# --- Constants verification ---


def test_allowed_mime_types():
    assert "application/pdf" in ALLOWED_MIME_TYPES
    assert "image/jpeg" in ALLOWED_MIME_TYPES
    assert "image/png" in ALLOWED_MIME_TYPES
    assert len(ALLOWED_MIME_TYPES) == 3


def test_max_file_size():
    assert MAX_FILE_SIZE == 5 * 1024 * 1024
