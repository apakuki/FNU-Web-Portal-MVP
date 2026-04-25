# system_flows.md

# FNU Web Portal MVP — System Flows

This document defines the major application workflows across the full stack.

Purpose:

* Help reviewers understand trust boundaries
* Clarify frontend → backend → database ownership
* Make authorization paths visible
* Identify persistence and integration layers
* Support LLM-assisted code review

---

# System Actors

## Public User

Unauthenticated visitor.

Capabilities:

* View public pages
* Submit application
* Access login
* Browse programme information

---

## Student

Authenticated portal user.

Capabilities:

* Login
* View profile
* Register for courses
* Pay invoices
* Upload documents
* Chat with AI assistant
* View enrolments and academic records

---

## Staff

Authenticated internal user.

Capabilities:

* Review applications
* Update records
* Access student administration features
* Respond to enquiries
* Access reporting

---

## Admin

Privileged internal role.

Capabilities:

* Manage users
* Manage permissions
* View audit logs
* Configure portal settings
* Access KPI dashboards
* Override workflows where permitted

---

## External Systems

### Banner (Oracle)

System of record.

Stores:

* Students
* Courses
* Programmes
* Fees
* Grades
* Enrolments

---

### Payment Gateway

External payment provider.

Examples:

* M-PAiSA
* MyCash

---

### OpenRouter LLM

External AI inference provider.

Used for:

* Student chatbot
* FAQ retrieval
* Escalation routing

---

# System Trust Boundaries

```text
Browser
   ↓
Next.js Frontend
   ↓
Reverse Proxy
   ↓
FastAPI Backend
   ↓
PostgreSQL / Banner / Payment Gateway / OpenRouter
```

Rules:

* Browser is untrusted
* Frontend cannot enforce security alone
* Backend owns validation and authorization
* Database is never accessed directly by frontend
* Banner access only occurs through backend adapter

---

# Flow 1 — Authentication Flow

## Objective

Authenticate a user and establish secure session state.

## Flow

```text
Browser
  → Next.js login page
  → POST /api/auth/login
  → Reverse proxy routes request
  → FastAPI validates credentials
  → Query users table
  → Password verified (bcrypt)
  → JWT created
  → JWT returned to next-auth
  → next-auth creates session cookie
  → Cookie stored in browser
```

## Backend Ownership

* Credential verification
* JWT issuance
* Session persistence
* Failed login handling
* Account lockout

## Database Tables

* users
* sessions
* login_attempts

## Security Controls

* bcrypt password hashing
* httpOnly cookie
* Secure cookie
* SameSite=Lax
* JWT expiration
* Session revocation
* Lockout after repeated failures

---

# Flow 2 — Authenticated API Request Lifecycle

## Objective

Allow authenticated requests to access protected resources.

## Flow

```text
Browser
  → User action
  → Frontend apiFetch helper
  → next-auth retrieves session JWT
  → Bearer token attached
  → Request hits backend
  → JWT middleware validates token
  → Session lookup
  → Role verification
  → Route executes
  → Response returned
```

## Backend Ownership

* JWT validation
* Session validation
* Role authorization
* Request tracing

## Security Controls

* Shared require_role() dependency
* JWT verification
* Session revocation check
* Middleware auth enforcement

---

# Flow 3 — Public Application Submission

## Objective

Allow prospective students to submit applications.

## Flow

```text
Browser
  → Next.js SSR landing page
  → User completes application form
  → Frontend validates via Zod
  → POST /api/applications
  → FastAPI validates request
  → Insert application into Postgres
  → Queue confirmation notification
  → Return success response
```

## Database Tables

* applications
* notifications

## Backend Ownership

* Validation
* Duplicate prevention
* Input sanitization
* Persistence

## Security Controls

* Public endpoint rate limiting
* Schema validation
* Spam prevention
* Request logging

---

# Flow 4 — Student Dashboard Load

## Objective

Load authenticated student dashboard data.

## Flow

```text
Browser
  → Navigate to dashboard
  → Next.js Server Component request
  → Backend API call
  → JWT validation
  → Backend fetches student data
  → Query Postgres + Banner
  → Return aggregated response
  → SSR page rendered
```

## Data Sources

* Banner
* Postgres

## Backend Ownership

* Student ownership validation
* Data aggregation
* Cache retrieval

## Security Controls

* Student ID ownership validation
* Role enforcement
* Data filtering

---

# Flow 5 — Course Registration

## Objective

Allow authenticated students to register for courses.

## Flow

```text
Browser
  → Student selects programme
  → Frontend requests available courses
  → Backend retrieves cached Banner data
  → Student selects classes
  → Frontend validates clashes/prerequisites
  → POST /api/registration/confirm
  → Backend validates again
  → Atomic transaction begins
  → Register course in Banner
  → Create invoice
  → Update roster
  → Commit transaction
  → Return confirmation
```

## Data Sources

* Banner
* Postgres

## Database Tables

* registrations
* invoices
* audit_log

## Backend Ownership

* Validation
* Transaction safety
* Duplicate prevention
* Banner synchronization

## Critical Review Areas

* Race conditions
* Partial transaction failure
* Duplicate registration
* Authorization gaps

---

# Flow 6 — Payment Lifecycle

## Objective

Process tuition or fee payments.

## Flow

```text
Browser
  → Student clicks Pay
  → POST /api/payments/initiate
  → Backend creates payment_attempt
  → Backend calls gateway API
  → Redirect URL returned
  → Browser redirects to gateway
  → User completes payment
  → Gateway calls callback endpoint
  → Signature validated
  → Payment status updated
  → Invoice updated in Banner
  → Student balance refreshed
```

## Database Tables

* payment_attempts
* invoices
* audit_log

## Security Controls

* Signature validation
* Callback verification
* Idempotency protection
* Duplicate callback handling

## Critical Review Areas

* Replay attack protection
* Payment tampering
* Callback authorization
* Transaction rollback

---

# Flow 7 — File Upload Flow

## Objective

Allow users to upload supporting documents.

## Flow

```text
Browser
  → Select file
  → Upload request
  → Backend validates auth
  → Validate MIME type
  → Validate file size
  → Rename file
  → Store outside web root
  → Create metadata record
  → Return upload reference
```

## Database Tables

* documents
* audit_log

## Security Controls

* MIME allowlist
* Size limits
* Randomized filenames
* Virus scan hook (recommended)
* Storage isolation

## Critical Review Areas

* Path traversal
* Arbitrary file execution
* Missing ownership validation
* Unrestricted upload types

---

# Flow 8 — Role-Based Authorization

## Objective

Restrict access by role.

## Flow

```text
Request
  → JWT middleware
  → Extract role
  → require_role() dependency
  → Compare required role
  → Permit or deny request
```

## Role Hierarchy

```text
Admin
  → Staff
    → Student
```

## Backend Ownership

* Central role enforcement
* Endpoint-level protection
* Object ownership checks

## Critical Review Areas

* Missing decorators
* Frontend-only protection
* Horizontal privilege escalation
* Role mismatch between frontend/backend

---

# Flow 9 — Chatbot Interaction

## Objective

Allow users to interact with AI assistant.

## Flow

```text
Browser
  → Floating chatbot widget
  → POST /api/chat
  → Backend validates request
  → Retrieve FAQ context
  → Retrieve student context (optional)
  → Compose prompt
  → Call OpenRouter
  → Store chat log
  → Return response
```

## Database Tables

* chatbot_logs
* chatbot_knowledge
* enquiries

## Security Controls

* Prompt sanitization
* Rate limiting
* PII filtering
* Token limits

## Critical Review Areas

* Prompt injection
* Data leakage
* Sensitive context exposure
* Escalation abuse

---

# Flow 10 — Admin Action Flow

## Objective

Allow privileged users to perform sensitive actions.

## Flow

```text
Admin UI
  → Protected route
  → Backend authorization
  → Admin action executes
  → Audit log written
  → Response returned
```

## Database Tables

* audit_log
* admin_actions

## Security Controls

* Strict RBAC
* Audit trail
* Request attribution
* Change logging

## Critical Review Areas

* Missing audit logging
* Over-privileged routes
* Missing ownership checks

---

# Flow 11 — Banner Integration Flow

## Objective

Keep portal synchronized with institutional data.

## Flow

```text
Backend service
  → banner_client module
  → Query Banner
  → Cache result
  → Return normalized payload
```

## Rules

* Banner never accessed directly from frontend
* Banner isolated behind adapter
* Cache reduces repeated queries

## Critical Review Areas

* Timeout handling
* Cache invalidation
* Data mismatch
* Retry behavior

---

# Flow 12 — Error Handling Flow

## Objective

Prevent internal details leaking to clients.

## Flow

```text
Request failure
  → Exception handler
  → Structured error response
  → Log written server-side
  → Client receives safe message
```

## Security Controls

* No stack traces exposed
* Request correlation ID
* Structured logging

## Critical Review Areas

* Exception swallowing
* Sensitive data leakage
* Missing logging

---

# Flow 13 — Audit Logging Flow

## Objective

Track sensitive system actions.

## Trigger Events

* Login
* Logout
* Payment changes
* Admin actions
* File uploads
* Permission updates
* Registration changes

## Flow

```text
Action occurs
  → Audit service invoked
  → Record persisted
  → Immutable log entry created
```

## Database Tables

* audit_log

## Required Fields

* actor_id
* action_type
* timestamp
* entity_type
* entity_id
* previous_value
* new_value
* request_id

---

# Flow 14 — Deployment Runtime Flow

## Objective

Define runtime request path.

## Flow

```text
Browser
  → HTTPS
  → Reverse Proxy
      → /api/* routed to FastAPI
      → /* routed to Next.js
  → Backend accesses Postgres
  → Backend accesses Banner
```

## Infrastructure Components

* Reverse proxy
* Next.js container
* FastAPI container
* PostgreSQL container
* Background scheduler

---

# High-Risk Review Areas

These should receive first-pass review.

## Critical

1. Authentication lifecycle
2. Session invalidation
3. RBAC enforcement
4. Payment callbacks
5. File uploads
6. Banner synchronization
7. Ownership validation
8. Admin route protection
9. JWT storage
10. Chatbot data exposure

---

# Recommended First Review Order

```text
1. Auth middleware
2. Session lifecycle
3. Role enforcement
4. API validation
5. Course registration transaction
6. Payment callback security
7. File upload validation
8. Banner adapter
9. Admin routes
10. Chatbot context filtering
```
