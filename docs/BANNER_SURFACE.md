# Banner Integration Surface

This document catalogues every field the FNU Student Portal reads from or writes to Ellucian Banner, organised by entity. This is the definitive reference for mapping portal data to Banner API fields.

---

## Configuration

| Setting | Env Variable | Default | Description |
|---|---|---|---|
| Mode | `BANNER_MODE` | `mock` | `mock` for development, `live` for production |
| API URL | `BANNER_API_URL` | (empty) | Base URL of Banner REST API |
| API Key | `BANNER_API_KEY` | (empty) | Bearer token for authentication |
| Timeout | `BANNER_TIMEOUT_SECONDS` | `10` | Per-request timeout in seconds |
| Cache TTL | `BANNER_CACHE_TTL_SECONDS` | `900` | TTL for cached read data (15 min) |

---

## Read Operations

### Programmes (`get_programmes`)

Returns all active academic programmes.

| Field | Type | Description | Example |
|---|---|---|---|
| `code` | string | Programme code | `BCOM` |
| `name` | string | Full programme name | `Bachelor of Commerce` |
| `level` | string | Certificate / Diploma / Degree / Postgrad | `Degree` |
| `college` | string | College code | `CBHTS` |
| `campus_codes` | string[] | Available campuses | `["Nasinu", "Lautoka"]` |
| `duration_years` | int | Normal duration | `3` |
| `total_credits` | int | Total credit points | `360` |
| `is_active` | bool | Whether programme accepts enrolments | `true` |

**Cached**: Yes (15-min TTL, key: `programmes`)

### Courses (`get_courses`)

Returns courses, optionally filtered by programme.

| Field | Type | Description | Example |
|---|---|---|---|
| `code` | string | Course code | `ACC101` |
| `name` | string | Course name | `Introduction to Accounting` |
| `credits` | int | Credit points | `15` |
| `programme_codes` | string[] | Parent programmes | `["BCOM"]` |
| `year_level` | int | Recommended year | `1` |
| `semester` | string | S1 / S2 / Summer | `S1` |
| `prerequisites` | object[] | Required prior courses | `[{"course_code": "ACC101", "min_grade": "C"}]` |
| `is_active` | bool | Whether course is offered | `true` |

**Cached**: Yes (15-min TTL, key: `courses:{programme_code}`)

### Offerings (`get_offerings`)

Returns class schedule offerings (timetable data).

| Field | Type | Description | Example |
|---|---|---|---|
| `id` | string | Offering identifier | `OFF-2026-S1-ACC101-NAS` |
| `course_code` | string | Parent course | `ACC101` |
| `semester` | string | S1 / S2 / Summer | `S1` |
| `year` | int | Academic year | `2026` |
| `campus` | string | Campus name | `Nasinu` |
| `lecturer_name` | string? | Assigned lecturer | `Dr. Mere Tuisawau` |
| `lecturer_banner_id` | string? | Lecturer Banner ID | `L00010001` |
| `day_of_week` | string | Day of class | `Monday` |
| `start_time` | string | Start time (HH:MM) | `09:00` |
| `end_time` | string | End time (HH:MM) | `11:00` |
| `room` | string | Room/venue | `CBHTS-LT1` |
| `capacity` | int | Max enrolment | `60` |
| `enrolled` | int | Current enrolment count | `42` |

**Cached**: No (real-time enrolment counts needed)

### Fee Schedule (`get_fee_schedule`)

Returns fee items for a given year and semester.

| Field | Type | Description | Example |
|---|---|---|---|
| `year` | int | Academic year | `2026` |
| `semester` | string | S1 / S2 / Summer | `S1` |
| `items[].code` | string | Fee code | `TUI-BCOM` |
| `items[].description` | string | Fee description | `Tuition Fee — Bachelor of Commerce` |
| `items[].amount_cents` | int | Amount in cents (FJD) | `350000` |
| `items[].currency` | string | Currency code | `FJD` |
| `items[].applies_to` | string | Programme code or `ALL` | `BCOM` |
| `items[].fee_type` | string | tuition / lab / library / registration / exam | `tuition` |

**Cached**: Yes (15-min TTL, key: `fees:{year}:{semester}`)

### Student (`get_student`)

Returns a single student record by Banner ID.

| Field | Type | Description | Example |
|---|---|---|---|
| `banner_id` | string | Student Banner ID | `S00012345` |
| `first_name` | string | First name | `Apisai` |
| `last_name` | string | Last name | `Delana` |
| `email` | string | Email address | `student@fnu.ac.fj` |
| `phone` | string? | Phone number | `+6799991001` |
| `programme_code` | string? | Enrolled programme | `BCOM` |
| `campus` | string? | Home campus | `Nasinu` |
| `enrolment_status` | string | active / suspended / graduated / withdrawn | `active` |
| `gpa` | float? | Current GPA | `3.2` |

**Cached**: No (student data may change frequently)

### Invoices (`get_invoices`)

Returns all invoices for a student.

| Field | Type | Description | Example |
|---|---|---|---|
| `invoice_id` | string | Invoice identifier | `INV-2026-S1-00001` |
| `banner_student_id` | string | Student Banner ID | `S00012345` |
| `semester` | string | S1 / S2 / Summer | `S1` |
| `year` | int | Academic year | `2026` |
| `items[]` | FeeItem[] | Line items (same fields as fee schedule) | — |
| `total_cents` | int | Total amount in cents | `378000` |
| `paid_cents` | int | Amount paid in cents | `100000` |
| `due_date` | date? | Payment due date | `2026-03-15` |
| `status` | string | unpaid / partial / paid / overdue | `partial` |

**Cached**: No

### Class Roster (`get_class_roster`)

Returns enrolled students for an offering (lecturer view).

| Field | Type | Description | Example |
|---|---|---|---|
| `offering_id` | string | Offering identifier | `OFF-2026-S1-ACC101-NAS` |
| `course_code` | string | Course code | `ACC101` |
| `course_name` | string | Course name | `Introduction to Accounting` |
| `semester` | string | S1 / S2 / Summer | `S1` |
| `year` | int | Academic year | `2026` |
| `campus` | string | Campus | `Nasinu` |
| `entries[].banner_student_id` | string | Student Banner ID | `S00012345` |
| `entries[].student_name` | string | Student full name | `Apisai Delana` |
| `entries[].email` | string | Student email | `student@fnu.ac.fj` |
| `entries[].grade` | string? | Assigned grade | `null` |
| `entries[].attendance_pct` | float? | Attendance percentage | `92.5` |

**Cached**: No

---

## Write Operations

### Create Student (`create_student`)

Creates a new student record in Banner (used after application approval).

| Field | Direction | Type | Description |
|---|---|---|---|
| `first_name` | Request | string | Student first name |
| `last_name` | Request | string | Student last name |
| `email` | Request | string | Student email |
| `phone` | Request | string? | Phone number |
| `programme_code` | Request | string | Programme to enrol in |
| `campus` | Request | string | Home campus |
| `banner_id` | Response | string | Assigned Banner ID (e.g. `S00012347`) |
| `success` | Response | bool | Whether creation succeeded |

### Register Course (`register_course`)

Registers a student for a specific course offering.

| Field | Direction | Type | Description |
|---|---|---|---|
| `banner_student_id` | Request | string | Student Banner ID |
| `offering_id` | Request | string | Offering to register for |
| `success` | Response | bool | Whether registration succeeded |
| `message` | Response | string | Success/error message |

### Submit Grade (`submit_grade`)

Submits a final grade for a student in an offering (lecturer action).

| Field | Direction | Type | Description |
|---|---|---|---|
| `offering_id` | Request | string | Offering identifier |
| `banner_student_id` | Request | string | Student Banner ID |
| `grade` | Request | string | Grade value (A+, A, A-, B+, B, B-, C+, C, C-, D, E, F, WD) |
| `success` | Response | bool | Whether submission succeeded |
| `message` | Response | string | Success/error message |

### Create Invoice (`create_invoice`)

Creates a fee invoice for a student in Banner.

| Field | Direction | Type | Description |
|---|---|---|---|
| `banner_student_id` | Request | string | Student Banner ID |
| `semester` | Request | string | Semester (S1 / S2 / Summer) |
| `year` | Request | int | Academic year |
| `items` | Request | FeeItem[] | Fee line items |
| `invoice_id` | Response | string | Generated invoice ID |
| `total_cents` | Response | int | Total amount in cents |
| `success` | Response | bool | Whether creation succeeded |

---

## Health Check

### `GET /api/banner/health`

| Field | Type | Description |
|---|---|---|
| `status` | string | `ok` or `unavailable` |
| `latency_ms` | float | Round-trip latency in milliseconds |

---

## Architecture Notes

- **Mock vs Live**: Controlled by `BANNER_MODE` env variable. Mock is blocked in production at startup.
- **Caching**: Programmes, courses, and fee schedules are cached with 15-minute TTL. Student data, invoices, offerings, and rosters are never cached.
- **Circuit Breaker**: After 5 consecutive failures, the live client opens the circuit for 60 seconds. During this window, all calls fail fast with `CircuitOpenError`.
- **TLS**: The live client verifies SSL certificates by default. This can be overridden for development but must not be disabled in production.
- **Sanitisation**: All string data received from Banner is HTML-escaped before storage or rendering to prevent stored XSS.
- **Audit Logging**: All write operations (create_student, register_course, submit_grade, create_invoice) should be logged to the audit_log table by the calling API endpoint.

---

## Portal Consumers

| Consumer (Part) | Banner Functions Used |
|---|---|
| Part 6: Applications | `create_student` (after approval) |
| Part 7: Registration | `get_programmes`, `get_courses`, `get_offerings`, `register_course`, `get_fee_schedule`, `create_invoice` |
| Part 7: Timetable | `get_offerings` (student's registered offerings) |
| Part 7: Grades | `get_class_roster`, `submit_grade` |
| Part 8: Payments | `get_invoices`, `get_student` |
| Part 9: Chatbot | `get_student`, `get_invoices`, `get_programmes` (FAQ lookups) |
| Part 13: Student ID | `get_student` (photo, programme, campus) |
| Part 14: KPI Dashboard | `get_programmes` (programme counts), `get_invoices` (revenue) |
