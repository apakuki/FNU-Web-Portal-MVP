# Database Schema Design

## Overview

The FNU Web Portal uses two database systems:

- **PostgreSQL** — portal-specific data (sessions, applications in flight, chatbot logs, KPI inputs, notifications, audit trail). This is the operational store for data the portal owns.
- **Oracle (Ellucian Banner)** — single source of truth for student records, programmes, courses, enrolments, fees, grades, staff. The portal reads from and writes to Banner via Ethos APIs (preferred) or direct SQL where Ethos does not yet expose a required field.

Banner remains the system of record. The portal never keeps a divergent parallel copy of Banner-owned data; it caches selectively (e.g. programme structure) with a 15-minute TTL.

## Design Principles

- **Banner is source of truth**: no duplicate mastering of student, course, or fee data
- **Portal owns workflow state**: application drafts, chatbot conversations, KPI manual inputs, audit logs live in Postgres
- **Role-based access**: every table with user-scoped data carries a `user_id` and RLS-style query filtering in the repository layer
- **Auditable**: every admin-initiated write to Banner is mirrored into a local `audit_log` row before the Banner call
- **JSON where flexibility matters**: application form payloads, KPI snapshot blobs, and chatbot message turns use `jsonb` so schema can evolve without migrations
- **Simple schema first**: MVP tables are minimal; future-proofing is done via `jsonb` columns and nullable foreign keys rather than speculative tables

## Data Requirements Analysis

Extracted from the TOR, the portal needs to persist:

### Owned by the portal (PostgreSQL)
- **Users and sessions**: local auth users (student, staff, lecturer, finance, manager, VC, admin), JWT sessions, password reset tokens
- **Applications in flight**: new-student online applications before they become Banner student records (personal details, prior qualifications, programme preference, uploaded documents, status)
- **Offer letters**: generated PDFs, acceptance tokens, conditional offer flags
- **Payments**: mobile-money and bank-transfer payment attempts, gateway callbacks, reconciliation state (the canonical invoice lives in Banner, but payment attempts and gateway lifecycle are portal-owned)
- **Payment plans**: configurable instalment schedules per student per semester
- **Chatbot**: conversation turns, escalated queries, training-data FAQ entries
- **KPI inputs**: manual KPI entries from section heads, KPI target configuration
- **Notifications**: outbound SMS/email queue, send status, templates
- **Enquiries**: multi-channel enquiry log (chatbot, email, phone, walk-in) with assignment and resolution tracking
- **Audit trail**: every admin action (who, what, when, which record)
- **File uploads**: uploaded document metadata (the file bytes live on disk / S3)

### Read from Banner (Oracle, not modelled here)
- Students (once registered), programmes, courses, course offerings, timetables, enrolments, grades, fee schedules, invoices, staff records, class rosters

## PostgreSQL Table Structure

### `users`

Local authentication. Students are mirrored here on application approval; staff / lecturers / admins are seeded or provisioned by the admin panel.

| Column | Type | Constraints | Purpose |
|--------|------|-------------|---------|
| `id` | UUID | PRIMARY KEY | Portal user id |
| `banner_id` | TEXT | UNIQUE, NULL | Banner student/staff id once linked |
| `email` | TEXT | NOT NULL, UNIQUE | Login / notifications |
| `phone` | TEXT | NULL | For SMS |
| `password_hash` | TEXT | NOT NULL | bcrypt |
| `role` | TEXT | NOT NULL | student, staff, finance, manager, lecturer, vc, admin |
| `full_name` | TEXT | NOT NULL | Display name |
| `is_active` | BOOLEAN | DEFAULT TRUE | Soft-disable accounts |
| `created_at` | TIMESTAMPTZ | DEFAULT now() | |
| `updated_at` | TIMESTAMPTZ | DEFAULT now() | |

### `sessions`

| Column | Type | Constraints | Purpose |
|--------|------|-------------|---------|
| `id` | UUID | PRIMARY KEY | |
| `user_id` | UUID | FK → users.id, NOT NULL | |
| `token_hash` | TEXT | NOT NULL, UNIQUE | SHA-256 of JWT jti |
| `expires_at` | TIMESTAMPTZ | NOT NULL | Auto-timeout |
| `revoked_at` | TIMESTAMPTZ | NULL | Logout / admin revoke |
| `created_at` | TIMESTAMPTZ | DEFAULT now() | |

### `applications`

New-student applications, before they become Banner students.

| Column | Type | Constraints | Purpose |
|--------|------|-------------|---------|
| `id` | UUID | PRIMARY KEY | |
| `application_number` | TEXT | NOT NULL, UNIQUE | Human-readable, auto-assigned |
| `applicant_email` | TEXT | NOT NULL | |
| `applicant_phone` | TEXT | NULL | |
| `payload` | JSONB | NOT NULL | Form data: personal, prior qualifications, programme preference, campus preference |
| `status` | TEXT | NOT NULL | submitted, under_review, awaiting_documents, approved, offer_issued, accepted, declined, rejected |
| `status_reason` | TEXT | NULL | Mandatory on reject / request-documents |
| `assigned_staff_id` | UUID | FK → users.id, NULL | Staff reviewer |
| `is_conditional` | BOOLEAN | DEFAULT FALSE | School leaver awaiting exam results |
| `linked_user_id` | UUID | FK → users.id, NULL | Set once applicant is promoted to a user |
| `submitted_at` | TIMESTAMPTZ | DEFAULT now() | |
| `decided_at` | TIMESTAMPTZ | NULL | For processing-time KPI |
| `updated_at` | TIMESTAMPTZ | DEFAULT now() | |

### `application_documents`

| Column | Type | Constraints | Purpose |
|--------|------|-------------|---------|
| `id` | UUID | PRIMARY KEY | |
| `application_id` | UUID | FK → applications.id, NOT NULL | |
| `document_type` | TEXT | NOT NULL | birth_certificate, transcript, reference, other |
| `filename` | TEXT | NOT NULL | Original upload name |
| `storage_path` | TEXT | NOT NULL | Local disk path or S3 key |
| `mime_type` | TEXT | NOT NULL | PDF / JPG / PNG only |
| `size_bytes` | INTEGER | NOT NULL | Max 5 MB |
| `uploaded_at` | TIMESTAMPTZ | DEFAULT now() | |

### `offers`

| Column | Type | Constraints | Purpose |
|--------|------|-------------|---------|
| `id` | UUID | PRIMARY KEY | |
| `application_id` | UUID | FK → applications.id, NOT NULL | |
| `pdf_storage_path` | TEXT | NOT NULL | Generated PDF location |
| `acceptance_token` | TEXT | NOT NULL, UNIQUE | Embedded in offer letter URL |
| `accepted_at` | TIMESTAMPTZ | NULL | |
| `declined_at` | TIMESTAMPTZ | NULL | |
| `issued_at` | TIMESTAMPTZ | DEFAULT now() | |

### `payment_attempts`

One row per attempt against a Banner invoice. Banner holds the invoice record; the portal holds the attempt lifecycle.

| Column | Type | Constraints | Purpose |
|--------|------|-------------|---------|
| `id` | UUID | PRIMARY KEY | |
| `user_id` | UUID | FK → users.id, NOT NULL | Paying student |
| `banner_invoice_id` | TEXT | NOT NULL | Foreign id into Banner |
| `method` | TEXT | NOT NULL | mpaisa, mycash, bank_transfer |
| `amount_cents` | INTEGER | NOT NULL | Stored in cents to avoid FP |
| `currency` | TEXT | NOT NULL, DEFAULT 'FJD' | |
| `gateway_reference` | TEXT | NULL | Provider transaction id |
| `status` | TEXT | NOT NULL | initiated, pending, confirmed, failed, timeout, manual_confirmed |
| `callback_payload` | JSONB | NULL | Raw gateway callback |
| `confirmed_by_staff_id` | UUID | FK → users.id, NULL | For bank-transfer manual confirmation |
| `created_at` | TIMESTAMPTZ | DEFAULT now() | |
| `updated_at` | TIMESTAMPTZ | DEFAULT now() | |

### `payment_plans`

| Column | Type | Constraints | Purpose |
|--------|------|-------------|---------|
| `id` | UUID | PRIMARY KEY | |
| `user_id` | UUID | FK → users.id, NOT NULL | |
| `banner_invoice_id` | TEXT | NOT NULL | |
| `schedule` | JSONB | NOT NULL | `[{due_date, amount_cents, status}]` |
| `deregistration_warning_week` | INTEGER | DEFAULT 4 | Configurable per plan |
| `created_at` | TIMESTAMPTZ | DEFAULT now() | |
| `updated_at` | TIMESTAMPTZ | DEFAULT now() | |

### `chatbot_conversations`

| Column | Type | Constraints | Purpose |
|--------|------|-------------|---------|
| `id` | UUID | PRIMARY KEY | |
| `user_id` | UUID | FK → users.id, NULL | Anonymous allowed |
| `session_key` | TEXT | NOT NULL | Browser session for anonymous |
| `messages` | JSONB | NOT NULL | `[{role, content, timestamp}]` |
| `escalated` | BOOLEAN | DEFAULT FALSE | Routed to staff |
| `escalated_to_staff_id` | UUID | FK → users.id, NULL | |
| `resolved` | BOOLEAN | DEFAULT FALSE | |
| `category` | TEXT | NULL | Auto-classified: fees, enrolment, graduation, etc |
| `created_at` | TIMESTAMPTZ | DEFAULT now() | |
| `updated_at` | TIMESTAMPTZ | DEFAULT now() | |

### `chatbot_knowledge`

Training data for the chatbot — FAQ entries and uploaded documents.

| Column | Type | Constraints | Purpose |
|--------|------|-------------|---------|
| `id` | UUID | PRIMARY KEY | |
| `kind` | TEXT | NOT NULL | faq, document |
| `title` | TEXT | NOT NULL | |
| `content` | TEXT | NOT NULL | FAQ answer or extracted document text |
| `source_file` | TEXT | NULL | For uploaded documents |
| `tags` | TEXT[] | DEFAULT '{}' | Category tags |
| `is_active` | BOOLEAN | DEFAULT TRUE | Soft-delete |
| `created_at` | TIMESTAMPTZ | DEFAULT now() | |
| `updated_at` | TIMESTAMPTZ | DEFAULT now() | |

### `enquiries`

Multi-channel enquiry log (chatbot escalations, email, phone, walk-in).

| Column | Type | Constraints | Purpose |
|--------|------|-------------|---------|
| `id` | UUID | PRIMARY KEY | |
| `source` | TEXT | NOT NULL | chatbot, email, phone, walk_in |
| `student_user_id` | UUID | FK → users.id, NULL | Null for anonymous walk-ins |
| `student_identifier` | TEXT | NULL | Email/phone/name if not a user |
| `subject` | TEXT | NOT NULL | |
| `body` | TEXT | NOT NULL | |
| `status` | TEXT | NOT NULL | open, in_progress, resolved |
| `assigned_staff_id` | UUID | FK → users.id, NULL | |
| `resolution_note` | TEXT | NULL | |
| `student_feedback` | INTEGER | NULL | 1–5 rating |
| `opened_at` | TIMESTAMPTZ | DEFAULT now() | |
| `resolved_at` | TIMESTAMPTZ | NULL | |

### `kpi_definitions`

System-administrator-configurable KPI definitions. Not hardcoded.

| Column | Type | Constraints | Purpose |
|--------|------|-------------|---------|
| `id` | UUID | PRIMARY KEY | |
| `code` | TEXT | NOT NULL, UNIQUE | e.g. `application_turnaround_hours` |
| `name` | TEXT | NOT NULL | Human label |
| `category` | TEXT | NOT NULL | auto, manual |
| `unit` | TEXT | NOT NULL | count, hours, percent, fjd |
| `applies_to_role` | TEXT | NOT NULL | staff, section_head, dean, finance, etc |
| `target_default` | NUMERIC | NULL | Default target; overridable per-staff |
| `is_active` | BOOLEAN | DEFAULT TRUE | |

### `kpi_values`

Every KPI measurement — auto-computed or manually entered.

| Column | Type | Constraints | Purpose |
|--------|------|-------------|---------|
| `id` | UUID | PRIMARY KEY | |
| `kpi_code` | TEXT | FK → kpi_definitions.code, NOT NULL | |
| `staff_user_id` | UUID | FK → users.id, NULL | Null for org-level KPIs |
| `function` | TEXT | NULL | e.g. admissions, finance, records |
| `college` | TEXT | NULL | CAFF, CBHTS, etc |
| `period_start` | DATE | NOT NULL | |
| `period_end` | DATE | NOT NULL | |
| `value` | NUMERIC | NOT NULL | |
| `target` | NUMERIC | NULL | Resolved at recording time |
| `source` | TEXT | NOT NULL | auto, manual |
| `recorded_at` | TIMESTAMPTZ | DEFAULT now() | |

### `notifications`

Outbound SMS / email queue.

| Column | Type | Constraints | Purpose |
|--------|------|-------------|---------|
| `id` | UUID | PRIMARY KEY | |
| `recipient_user_id` | UUID | FK → users.id, NULL | |
| `recipient_email` | TEXT | NULL | For non-user recipients |
| `recipient_phone` | TEXT | NULL | |
| `channel` | TEXT | NOT NULL | email, sms |
| `template_code` | TEXT | NULL | Template used, if any |
| `subject` | TEXT | NULL | Email only |
| `body` | TEXT | NOT NULL | |
| `status` | TEXT | NOT NULL | queued, sent, failed |
| `provider_reference` | TEXT | NULL | Provider message id |
| `error_message` | TEXT | NULL | |
| `queued_at` | TIMESTAMPTZ | DEFAULT now() | |
| `sent_at` | TIMESTAMPTZ | NULL | |

### `audit_log`

Append-only. Every admin-initiated write — portal or Banner — lands here.

| Column | Type | Constraints | Purpose |
|--------|------|-------------|---------|
| `id` | BIGSERIAL | PRIMARY KEY | |
| `actor_user_id` | UUID | FK → users.id, NULL | Null for system actions |
| `action` | TEXT | NOT NULL | e.g. application.approve, payment.manual_confirm, banner.write.course_registration |
| `target_type` | TEXT | NOT NULL | application, payment, course_registration, etc |
| `target_id` | TEXT | NOT NULL | |
| `before` | JSONB | NULL | Pre-state snapshot |
| `after` | JSONB | NULL | Post-state snapshot |
| `reason` | TEXT | NULL | Mandatory for manual overrides |
| `ip_address` | TEXT | NULL | |
| `occurred_at` | TIMESTAMPTZ | DEFAULT now() | |

## Banner (Oracle) — Read/Write Surface

The portal does not own Banner tables; it interacts via a dedicated `banner_client` module. Documented here for reference only — these are Banner fields the portal depends on, not tables we create.

| Banner entity | Read | Write | Via |
|---|---|---|---|
| Student (SPRIDEN, SGBSTDN) | yes | yes (create on approval) | Ethos Persons + Students API |
| Programme structure | yes | no | Ethos Programs API |
| Course catalogue | yes | no | Ethos Courses API |
| Course offerings (sections) | yes | no | Ethos Sections API |
| Enrolments (SFRSTCR) | yes | yes | Ethos Student Registrations API |
| Fee schedule | yes | no | Direct SQL (not on Ethos) |
| Invoices | yes | yes (create on confirm) | Direct SQL |
| Grades | yes | yes (lecturer submission) | Ethos Student Grades API |
| Class rosters | yes | no | Ethos Sections + Registrations |

## Database Initialization

The backend on startup will:

1. Check Postgres connection; fail fast if unavailable
2. Run migrations (Alembic) — create any missing tables, apply pending schema changes
3. Seed `kpi_definitions` from `seed/kpi_definitions.json` (idempotent upsert)
4. Seed default admin user from environment variables if no admin exists
5. Verify Banner connectivity with a health-check read; log (don't crash) if Banner is down

## Sample Data

See `seed/` directory:
- `seed/kpi_definitions.json` — canonical KPI list
- `seed/notification_templates.json` — email/SMS templates
- `seed/synthetic_students.json` — anonymised test student records
- `seed/chatbot_faq.json` — initial FAQ training set

## API Endpoints (Planned)

Grouped by bounded context. Full specification lives in `docs/API.md` once drafted in Part 2.

- **Auth**: `POST /api/auth/login`, `POST /api/auth/logout`, `POST /api/auth/reset-password`
- **Applications**: `POST /api/applications`, `GET /api/applications/{id}`, `PUT /api/applications/{id}/status` (staff)
- **Offers**: `GET /api/offers/{token}`, `POST /api/offers/{token}/accept`, `POST /api/offers/{token}/decline`
- **Registration**: `GET /api/programme`, `GET /api/courses`, `POST /api/registration/confirm`
- **Invoicing**: `GET /api/invoices`, `GET /api/invoices/{id}.pdf`
- **Payments**: `POST /api/payments/initiate`, `POST /api/payments/callback/{provider}`, `POST /api/payments/bank-confirm` (finance)
- **Timetable**: `GET /api/timetable`, `GET /api/timetable.ics`
- **Grades**: `GET /api/grades`, `POST /api/grades` (lecturer)
- **Profile**: `GET /api/profile`, `PUT /api/profile`, `POST /api/profile/photo`
- **Chatbot**: `POST /api/chat`, `GET /api/chat/history`, `POST /api/chat/escalate`
- **Admin — applications / students / enquiries / communications**: `/api/admin/...`
- **KPI**: `GET /api/kpi/dashboard`, `POST /api/kpi/values` (section head)
- **Lecturer**: `GET /api/lecturer/rosters`, `POST /api/lecturer/grades`

## Future Enhancements

- Row-level security policies in Postgres (currently enforced in repository layer)
- Partition `audit_log` by month once volume exceeds ~10M rows
- Read replica for dashboard queries
- Materialised views for KPI dashboard roll-ups
- Full-text search on `chatbot_knowledge` via `tsvector`
- Move file uploads from local disk to S3 / FNU object storage
- Cache layer (Redis) for programme structure and fee schedules
- Event sourcing for payment lifecycle (currently last-write-wins on status)
