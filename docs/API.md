# API Endpoint Contracts

All endpoints are served under `/api/` via the reverse proxy. Request and response bodies are JSON unless noted. Every endpoint has a corresponding Pydantic model in the backend.

Authentication: endpoints marked **(auth)** require a valid JWT in the `Authorization: Bearer <token>` header. Endpoints marked **(role: X)** additionally require the specified role. Endpoints marked **(public)** require no authentication.

---

## Auth

### POST /api/auth/login (public)

**Request**
```json
{
  "email": "student@fnu.ac.fj",
  "password": "string"
}
```

**Response 200**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "email": "student@fnu.ac.fj",
    "full_name": "Jane Doe",
    "role": "student",
    "banner_id": "S00012345"
  }
}
```

**Response 401** — invalid credentials

### POST /api/auth/logout (auth)

**Response 200**
```json
{ "detail": "Logged out" }
```

### GET /api/auth/me (auth)

**Response 200** — same `user` object as login response

### POST /api/auth/reset-password (public)

**Request**
```json
{ "email": "student@fnu.ac.fj" }
```

**Response 200** — always returns success (no email enumeration)

### POST /api/auth/reset-password/confirm (public)

**Request**
```json
{
  "token": "string",
  "new_password": "string"
}
```

**Response 200**
```json
{ "detail": "Password reset" }
```

**Response 400** — invalid or expired token

---

## Health

### GET /api/health (public)

**Response 200**
```json
{
  "status": "ok",
  "postgres": "ok",
  "banner": "ok"
}
```

### GET /api/banner/health (public)

**Response 200**
```json
{
  "status": "ok",
  "latency_ms": 42
}
```

---

## Applications

### POST /api/applications (public)

**Request**
```json
{
  "applicant_email": "jane@email.com",
  "applicant_phone": "+6799991234",
  "personal_details": {
    "first_name": "Jane",
    "last_name": "Doe",
    "date_of_birth": "2000-01-15",
    "gender": "female",
    "nationality": "Fijian",
    "address": "123 Main St, Suva"
  },
  "prior_qualifications": [
    {
      "institution": "Suva Grammar School",
      "qualification": "Year 13",
      "year_completed": 2023,
      "grade": "A"
    }
  ],
  "programme_preference": "BCOM",
  "campus_preference": "Nasinu",
  "documents": ["uuid-of-uploaded-doc"]
}
```

**Response 201**
```json
{
  "id": "uuid",
  "application_number": "APP-2026-000001",
  "status": "submitted",
  "submitted_at": "2026-04-19T10:00:00Z"
}
```

**Response 422** — validation errors

### POST /api/applications/documents (public)

Upload a document (multipart/form-data).

**Request**: `file` (PDF/JPG/PNG, max 5MB), `document_type` (birth_certificate | transcript | reference | other)

**Response 201**
```json
{
  "id": "uuid",
  "filename": "transcript.pdf",
  "document_type": "transcript",
  "size_bytes": 204800
}
```

**Response 400** — invalid MIME type or exceeds 5MB

### GET /api/applications/{id} (auth, role: staff | admin)

**Response 200** — full application object with documents array

### GET /api/admin/applications (auth, role: staff | admin)

**Query params**: `status`, `campus`, `programme`, `page`, `per_page`

**Response 200**
```json
{
  "items": [{ "id": "uuid", "application_number": "APP-2026-000001", "applicant_email": "...", "status": "submitted", "submitted_at": "...", "decided_at": null }],
  "total": 42,
  "page": 1,
  "per_page": 20
}
```

### PUT /api/admin/applications/{id}/status (auth, role: staff | admin)

**Request**
```json
{
  "status": "approved",
  "reason": "All documents verified"
}
```

`reason` is mandatory when status is `rejected` or `awaiting_documents`.

**Response 200** — updated application object

### POST /api/admin/applications/bulk-action (auth, role: staff | admin)

**Request**
```json
{
  "application_ids": ["uuid1", "uuid2"],
  "action": "approve",
  "reason": "Batch approval"
}
```

**Response 200**
```json
{ "updated": 2, "failed": 0 }
```

---

## Offers

### GET /api/offers/{token} (public)

**Response 200** — offer details (programme, campus, conditions if conditional)

**Response 404** — invalid token

### POST /api/offers/{token}/accept (public)

**Response 200**
```json
{ "detail": "Offer accepted", "login_url": "/login" }
```

### POST /api/offers/{token}/decline (public)

**Response 200**
```json
{ "detail": "Offer declined" }
```

---

## Programme and Courses

### GET /api/programme (auth, role: student)

Returns the student's approved programme structure.

**Response 200**
```json
{
  "programme_code": "BCOM",
  "programme_name": "Bachelor of Commerce",
  "total_credits_required": 240,
  "credits_completed": 80,
  "semesters": [
    {
      "year": 2,
      "semester": 1,
      "core_courses": [
        { "code": "ACC201", "name": "Intermediate Accounting", "credits": 15, "prereqs": ["ACC101"], "prereqs_met": true }
      ],
      "elective_courses": [
        { "code": "MGT210", "name": "Organisational Behaviour", "credits": 15, "prereqs": [], "prereqs_met": true }
      ]
    }
  ]
}
```

### GET /api/courses (auth, role: student)

Selectable courses for the current registration period.

**Query params**: `semester`, `programme`

**Response 200**
```json
{
  "courses": [
    {
      "code": "ACC201",
      "name": "Intermediate Accounting",
      "credits": 15,
      "fee_cents": 75000,
      "prereqs": ["ACC101"],
      "prereqs_met": true,
      "prereq_reason": null,
      "offerings": [
        {
          "id": "offering-uuid",
          "day": "Monday",
          "start_time": "09:00",
          "end_time": "11:00",
          "room": "A201",
          "lecturer": "Dr. Smith",
          "campus": "Nasinu",
          "seats_available": 15
        }
      ]
    }
  ]
}
```

---

## Registration

### POST /api/registration/confirm (auth, role: student)

**Request**
```json
{
  "offerings": ["offering-uuid-1", "offering-uuid-2"]
}
```

**Response 200**
```json
{
  "registration_id": "uuid",
  "courses_registered": 2,
  "invoice_id": "INV-2026-000001",
  "total_fee_cents": 150000,
  "timetable_url": "/portal/timetable"
}
```

**Response 400** — prereq not met, timetable clash, or credit overload (with reason)

**Response 409** — already registered for this semester

---

## Invoices

### GET /api/invoices (auth, role: student)

**Response 200**
```json
{
  "invoices": [
    {
      "id": "INV-2026-000001",
      "semester": "2026-S2",
      "total_cents": 150000,
      "paid_cents": 75000,
      "balance_cents": 75000,
      "status": "partially_paid",
      "items": [
        { "course_code": "ACC201", "description": "Intermediate Accounting", "amount_cents": 75000 }
      ],
      "created_at": "2026-04-19T10:00:00Z"
    }
  ]
}
```

### GET /api/invoices/{id}.pdf (auth, role: student)

**Response 200** — `application/pdf` binary

---

## Payments

### POST /api/payments/initiate (auth, role: student)

**Request**
```json
{
  "invoice_id": "INV-2026-000001",
  "method": "mpaisa",
  "amount_cents": 75000
}
```

**Response 200**
```json
{
  "payment_id": "uuid",
  "redirect_url": "https://sandbox.mpaisa.vodafone.com.fj/...",
  "status": "initiated"
}
```

### POST /api/payments/callback/mpaisa (public, signature-verified)

Gateway-initiated callback. Request body is provider-specific. Response: `200 OK`.

### POST /api/payments/callback/mycash (public, signature-verified)

Same pattern as M-PAiSA.

### POST /api/payments/bank-confirm (auth, role: finance)

**Request**
```json
{
  "payment_id": "uuid",
  "bank_reference": "REF123456"
}
```

**Response 200** — updated payment object

### GET /api/payments/reconciliation (auth, role: finance)

**Query params**: `date_from`, `date_to`, `method`, `format` (json | csv | xlsx)

**Response 200** — reconciliation report

---

## Timetable

### GET /api/timetable (auth, role: student)

**Response 200**
```json
{
  "semester": "2026-S2",
  "entries": [
    {
      "course_code": "ACC201",
      "course_name": "Intermediate Accounting",
      "day": "Monday",
      "start_time": "09:00",
      "end_time": "11:00",
      "room": "A201",
      "lecturer": "Dr. Smith",
      "campus": "Nasinu"
    }
  ]
}
```

### GET /api/timetable.ics (auth, role: student)

**Response 200** — `text/calendar` iCalendar file

---

## Grades

### GET /api/grades (auth, role: student)

**Response 200**
```json
{
  "cumulative_gpa": 3.45,
  "semesters": [
    {
      "semester": "2026-S1",
      "gpa": 3.60,
      "courses": [
        { "code": "ACC101", "name": "Intro to Accounting", "credits": 15, "grade": "A", "points": 4.0 }
      ]
    }
  ]
}
```

---

## Profile

### GET /api/profile (auth)

**Response 200**
```json
{
  "id": "uuid",
  "email": "student@fnu.ac.fj",
  "full_name": "Jane Doe",
  "phone": "+6799991234",
  "address": "123 Main St, Suva",
  "emergency_contact": { "name": "John Doe", "phone": "+6799995678", "relationship": "Father" },
  "photo_url": "/api/profile/photo",
  "banner_id": "S00012345"
}
```

### PUT /api/profile (auth)

**Request** — partial update of editable fields (phone, address, emergency_contact)

**Response 200** — updated profile

### POST /api/profile/photo (auth)

Multipart upload, max 2MB. Backend resizes to 400x400.

**Response 200**
```json
{ "photo_url": "/api/profile/photo" }
```

---

## Student ID

### GET /api/id-card (auth, role: student)

**Response 200**
```json
{
  "full_name": "Jane Doe",
  "banner_id": "S00012345",
  "programme": "Bachelor of Commerce",
  "campus": "Nasinu",
  "photo_url": "/api/profile/photo",
  "qr_payload": "signed-qr-string",
  "valid_until": "2026-12-31"
}
```

### GET /verify/{qr_payload} (public)

Server-rendered verification page.

**Response 200** — HTML page showing student name, photo, programme, validity

---

## Account

### GET /api/account (auth, role: student)

**Response 200**
```json
{
  "balance_cents": 75000,
  "currency": "FJD",
  "payment_history": [
    { "id": "uuid", "date": "2026-04-10", "method": "mpaisa", "amount_cents": 75000, "status": "confirmed" }
  ],
  "instalment_schedule": [
    { "due_date": "2026-05-15", "amount_cents": 37500, "status": "upcoming" },
    { "due_date": "2026-06-15", "amount_cents": 37500, "status": "upcoming" }
  ]
}
```

---

## Chatbot

### POST /api/chat (auth or public)

**Request**
```json
{
  "message": "What are the entry requirements for nursing?",
  "session_key": "browser-session-id"
}
```

**Response 200**
```json
{
  "reply": "The Bachelor of Nursing requires...",
  "conversation_id": "uuid",
  "escalated": false
}
```

### GET /api/chat/history (auth)

**Response 200** — list of conversation objects for the authenticated user

---

## Admin: Chatbot Management

### GET /api/admin/chatbot/knowledge (auth, role: staff | admin)

**Response 200** — paginated list of FAQ/document entries

### POST /api/admin/chatbot/knowledge (auth, role: staff | admin)

**Request**
```json
{
  "kind": "faq",
  "title": "Entry requirements for Nursing",
  "content": "The Bachelor of Nursing requires...",
  "tags": ["admissions", "nursing"]
}
```

### PUT /api/admin/chatbot/knowledge/{id} (auth, role: staff | admin)

### DELETE /api/admin/chatbot/knowledge/{id} (auth, role: staff | admin)

### GET /api/admin/chatbot/conversations (auth, role: staff | admin)

**Query params**: `status`, `category`, `date_from`, `date_to`, `page`, `per_page`

### GET /api/admin/chatbot/analytics (auth, role: staff | admin)

**Response 200**
```json
{
  "total_conversations": 1200,
  "resolution_rate": 0.85,
  "escalation_rate": 0.08,
  "top_categories": [
    { "category": "fees", "count": 320 },
    { "category": "enrolment", "count": 280 }
  ],
  "period": { "from": "2026-04-01", "to": "2026-04-19" }
}
```

---

## Admin: Students

### GET /api/admin/students (auth, role: staff | admin)

**Query params**: `q` (search by ID, name, email), `programme`, `campus`, `status`, `page`, `per_page`

### GET /api/admin/students/{id} (auth, role: staff | admin)

**Response 200** — full student record (personal, programme, courses, payments, grades, notes)

### POST /api/admin/students/{id}/override (auth, role: staff | admin)

**Request**
```json
{
  "type": "prereq_waiver",
  "course_code": "ACC201",
  "reason": "Mature student with equivalent work experience"
}
```

`reason` is mandatory. Types: `prereq_waiver`, `late_registration`, `credit_overload`.

**Response 200** — updated record + audit log entry ID

---

## Admin: Enquiries

### GET /api/admin/enquiries (auth, role: staff | admin)

**Query params**: `status`, `source`, `assigned_to`, `page`, `per_page`

### PUT /api/admin/enquiries/{id} (auth, role: staff | admin)

**Request**
```json
{
  "status": "in_progress",
  "assigned_staff_id": "uuid"
}
```

### PUT /api/admin/enquiries/{id}/resolve (auth, role: staff | admin)

**Request**
```json
{
  "resolution_note": "Explained fee structure and payment plan options."
}
```

---

## Admin: Communications

### POST /api/admin/communications/send (auth, role: staff | admin)

**Request**
```json
{
  "channel": "email",
  "filter": { "programme": "BCOM", "campus": "Nasinu" },
  "subject": "Important deadline reminder",
  "body": "Dear student, ..."
}
```

**Response 200**
```json
{ "recipients": 145, "queued": 145 }
```

### GET /api/admin/communications/preview-count (auth, role: staff | admin)

**Query params**: same filter as send

**Response 200**
```json
{ "count": 145 }
```

---

## Lecturer

### GET /api/lecturer/rosters (auth, role: lecturer)

**Response 200**
```json
{
  "courses": [
    {
      "code": "ACC201",
      "name": "Intermediate Accounting",
      "semester": "2026-S2",
      "roster": [
        { "student_id": "S00012345", "full_name": "Jane Doe", "programme": "BCOM", "status": "registered" }
      ]
    }
  ]
}
```

### GET /api/lecturer/rosters/{course_code}/export (auth, role: lecturer)

**Query params**: `format` (csv | xlsx | pdf)

**Response 200** — file download

### POST /api/lecturer/grades (auth, role: lecturer)

**Request**
```json
{
  "course_code": "ACC201",
  "semester": "2026-S2",
  "action": "submit",
  "grades": [
    { "student_id": "S00012345", "grade": "A", "marks": 85 }
  ]
}
```

`action`: `draft` (save without submitting), `submit` (submit for review), `finalise` (lock and write to Banner).

**Response 200**
```json
{ "status": "submitted", "updated": 25 }
```

---

## KPI

### GET /api/kpi/dashboard (auth, role: manager | dean | vc | finance | staff)

**Query params**: `view` (vc | dean | section_head | me | finance), `period` (current | previous | ytd | custom), `date_from`, `date_to`, `college`, `function`

**Response 200**
```json
{
  "kpis": [
    {
      "code": "application_turnaround_hours",
      "name": "Application Turnaround",
      "value": 18.5,
      "target": 24,
      "unit": "hours",
      "status": "green",
      "trend": [12, 15, 18, 22, 18]
    }
  ],
  "drill_down_available": true
}
```

### GET /api/kpi/dashboard/drill-down (auth, role: manager | dean | vc)

**Query params**: `kpi_code`, `level` (institution | college | function | individual), `parent_id`

### POST /api/kpi/values (auth, role: staff | manager)

Manual KPI entry.

**Request**
```json
{
  "kpi_code": "enquiries_resolved",
  "value": 15,
  "period_start": "2026-04-14",
  "period_end": "2026-04-18"
}
```

### GET /api/kpi/targets (auth, role: admin)

### PUT /api/kpi/targets/{kpi_code} (auth, role: admin)

**Request**
```json
{ "target_default": 24 }
```

---

## Notifications (internal)

### GET /api/notifications (auth)

User's notification history.

### PUT /api/notifications/{id}/read (auth)

Mark as read.
