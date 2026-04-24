# Staff User Guide — FNU Web Portal

This guide covers the staff-facing interfaces of the FNU web portal: application review, student records, enquiries, communications, finance reconciliation, the lecturer interface, and the KPI dashboards.

Portal URL: **https://portal.fnu.ac.fj**

Your role determines which screens you see:

| Role | Access |
|---|---|
| `admin` | Everything below |
| `staff` | Application review, student records, enquiries, communications |
| `finance` | Finance reconciliation, Finance KPI dashboard |
| `manager` | Dean / Section Head dashboards |
| `vc` | VC/SLT dashboard |
| `lecturer` | Rosters + grade entry only |

If you need additional access, contact the registry admin.

---

## 1. Logging in

1. Go to **https://portal.fnu.ac.fj/login**.
2. Use the FNU email and password issued by IT.
3. After 5 wrong passwords your account locks for 15 minutes.

## 2. The staff dashboard

Lands at `/admin`. Cards include:

- **Pending applications** (live count)
- **Open enquiries** (live count)
- **Processing-time metrics** (median days from submission to decision)
- **Quick links** to each section below

## 3. Application review

Path: **Admin → Applications**.

### The queue

- Filter by status (Received / Under Review / Documents Requested / Offer Made / Declined) and by programme.
- Sort by age to triage oldest-first.
- Click a row to open the detail view.

### The detail view

- **Applicant info** — personal details, prior qualifications, programme preferences.
- **Documents** — view uploaded files (virus-scanned on upload, served via auth-gated endpoint).
- **History** — every status change, with the staff member who made it.

### Actions

- **Approve** → Issues an offer automatically; the system emails the applicant with a link to `https://portal.fnu.ac.fj/offer/<token>`. Offers expire after 7 days.
- **Request documents** → Select the missing documents; the applicant gets an email.
- **Decline** → Must include a reason (shown to the applicant in the email).

All actions are audit-logged. Use the **Bulk action** button (admin only) to approve or update many records at once — each row still lands in the audit log individually.

### Conditional offers

Mark an applicant as a **school leaver** on the first review. When approved, the offer becomes conditional on meeting the stated grade threshold. You receive an alert when final results are uploaded so you can finalise or decline.

## 4. Student records

Path: **Admin → Students**.

- Search by ID, name, programme, campus, or enrolment status.
- Click a student to see: personal, programme, registered courses (live from Banner), payments, grades, offer history, and internal notes.
- **Edit profile** fields: contact info, emergency contact.
- **Manual overrides** (require a reason ≥10 chars; audit-logged):
  - **Prereq waiver** — allow a student to register for a course they don't strictly meet prereqs for.
  - **Late registration** — admit after the registration deadline.
  - **Overload** — allow more than the normal per-semester credit cap.

Overrides write to `audit_log` with before/after state, you, timestamp, and IP.

## 5. Enquiries

Path: **Admin → Enquiries**.

- Queue view with filters (status, category, assignee, age).
- Open an enquiry to see the full message, student details, and any chatbot conversation that escalated it.
- **Assign to me** (or to another staff member).
- **Status transitions**: Open → In Progress → Resolved. Assignment changes and status transitions are audit-logged.
- **Resolution note** — written when you mark as Resolved. **The note cannot be edited after submission.** Be concise and accurate.
- On resolution, the student receives an email prompt to rate the support 1–5 stars. Ratings feed into the Section Head KPI dashboard.

## 6. Communications

Path: **Admin → Communications**.

### Templates

Every automated notification (payment reminder, registration confirmation, offer issued, etc.) uses a template from `notification_templates`. Edit the text; variables are of the form `{name}` — you can see which variables a given template supports in the editor.

- Subject and body support `{variable}` interpolation.
- Control characters (CR/LF) are stripped automatically; values are clamped to 500 chars; unknown variables raise an error on render.

### Batch send

1. Filter the recipient group (by programme, campus, outstanding balance, etc.).
2. Preview the recipient count.
3. Pick a template or write a one-off.
4. Send.

Every batch send logs: who sent it, recipient count, and a content hash (for dispute resolution). You can see the per-recipient status under **Recent notifications**.

## 7. Finance reconciliation

Path: **Admin → Finance** (finance / admin roles only).

### Daily workflow

1. **Payments received today** — card shows count and total by method.
2. **Bank transfer confirmations queue** — students who uploaded a bank deposit slip. For each:
   - Verify against the bank statement.
   - Click **Confirm** → marks the invoice paid, updates the payment plan, audit-logs.
   - **Reject** with a reason if the slip is invalid.
3. **Reconciliation report** — daily totals by method; download CSV for import into the finance system.

### Disputed payments

If a gateway callback looks suspicious, mark the row **Disputed** and notify the gateway's support. See [INCIDENT_RESPONSE.md](INCIDENT_RESPONSE.md) for the fraud runbook.

### Payment plans

Students set up instalment plans themselves. From the finance UI you can:

- **View** any student's plan and status.
- **Mark overdue manually** (usually automatic).
- **Waive late fees** (admin only; requires reason; audit-logged).

## 8. Lecturer interface

Path: **Lecturer → (dashboard)**.

### Rosters

- The dashboard shows each course you teach this semester with student count and grading progress.
- Click a course → full roster with student names, IDs, programme, and status.
- **Export** as CSV, Excel (.xlsx), or PDF.

### Grade entry

From a course roster page:

1. Select the assessment period (midterm, final, overall).
2. Enter grades in the grid — autosaves as **draft** every few seconds.
3. When complete, click **Submit for review** — draft → submitted. You can't edit after this unless you revert to draft (state transitions are audit-logged).
4. When reviewed, click **Finalise** — submitted → finalised. **This is irreversible without admin override.** Grades write through to Banner at this point, and students see them in "My Grades" immediately.

Grade validation:

- Grades must be within the allowed range.
- Every change is audit-logged with before/after values.

## 9. KPI dashboards

Path: **Admin → KPI**.

Five role-specific views, each with period filters (current semester / YTD / custom, max 366 days) and traffic-light styling (green/amber/red against targets).

### VC / SLT — `/admin/kpi/vc`
High-level institutional KPIs: enrolment growth, application throughput, revenue, chatbot resolution.

### Dean / Manager — `/admin/kpi/dean`
Processing times, service KPIs, academic KPIs, scoped to your college/function.

### Section Head — `/admin/kpi/section-head`
Manual KPI entry form + the shared dashboard. Target: <5 minutes per person per day to update manual inputs.

### Individual Staff — `/admin/kpi/me`
Your own assigned-enquiry count, resolution time, student rating.

### Finance — `/admin/kpi/finance`
Revenue, receivables, method breakdown. **Export CSV** for the finance team (audit-logged).

### Targets (admin only)

Path: `/admin/kpi/targets`. Update the target value for any KPI. Changes are audit-logged. Auto KPIs recompute against the new target within the next scheduler tick (default every 60 minutes; trigger a recompute from the top-right menu).

## 10. Audit trail

Every significant action writes to `audit_log`:

- Login / logout / password reset
- Application review decisions
- Manual overrides and bulk actions
- Payment confirmations and waivers
- Grade drafts / submits / finalises
- KPI target changes
- Communications sent
- Banner writes (register_course, submit_grade, create_invoice, create_student)

Access the audit log from **Admin → Audit** (admin only) for investigations. You can filter by actor, target, action, and date range.

## 11. Browser and accessibility

- Supported browsers: **Chrome, Firefox, Safari, Edge** (current versions).
- Tablet-friendly; the admin interface is optimised for desktop but degrades gracefully to mobile.
- WCAG 2.1 AA throughout; report accessibility issues to it-helpdesk@fnu.ac.fj.

## 12. Security expectations

- Do **not** share your password. IT will never ask for it.
- Log out on shared devices.
- Use the portal-provided workflows (overrides with reasons, resolution notes) rather than direct database edits — the audit trail depends on it.
- Report anything suspicious (unexpected login notifications, data that looks wrong, etc.) to ops@fnu.ac.fj. See [INCIDENT_RESPONSE.md](INCIDENT_RESPONSE.md) for how we handle incidents.

---

*Last updated: 2026-04. Feedback: it-helpdesk@fnu.ac.fj.*
