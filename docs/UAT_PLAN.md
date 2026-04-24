# UAT Plan — FNU Web Portal MVP

User Acceptance Testing plan for handover to FNU registry, finance, academic, and IT staff. Delivers **TOR D11**. Runs in Week 7 of the build plan (early May 2026), ahead of go-live on **15 June 2026**.

---

## 1. Scope

Every TOR 2.x feature and the cross-cutting non-functional targets from TOR 2.7 / 5.2. Organised as **13 scenarios** covering the student journey, staff workflows, lecturer workflows, finance operations, KPI dashboards, the chatbot, and non-functional checks.

Not in scope for UAT (deferred to post-launch):

- Load test at 500 users — run by the build team against staging and signed off separately (see [TESTING.md §15.8](TESTING.md)).
- OWASP ZAP scan — run by the build team against staging.

## 2. Environment

- **URL**: `https://staging.portal.fnu.ac.fj` (UAT environment, mirrors production).
- **Banner**: live sandbox connection.
- **Payments**: live sandbox for M-PAiSA and MyCash.
- **Chatbot**: live OpenRouter connection with the production FAQ corpus.
- **Notifications**: live SMTP/SMS but routed to a `+uat@` alias and a dedicated sandbox SMS number to avoid emailing real students.

## 3. Test accounts

IT provisions one account per role using real FNU email addresses (not seed accounts). Confirm roster with FNU PM before UAT start.

| Role | Purpose | Count |
|---|---|---|
| student | Full student journey tests | 3 (one BCOM, one BNUR, one conditional offer) |
| staff | Application review, enquiries | 2 |
| finance | Reconciliation, bank-confirm | 1 |
| lecturer | Grade entry | 2 |
| manager (Dean) | KPI dashboard | 1 |
| section head | Manual KPI entry | 1 |
| vc | VC dashboard | 1 |
| admin | Overrides, targets, templates | 1 |

## 4. Schedule (5 working days)

| Day | Focus | Participants |
|---|---|---|
| **Day 1** | Onboarding + orientation; scenarios A–C (new-student journey) | All |
| **Day 2** | Scenarios D–F (registration, timetable, fees) + H (chatbot) | Students + staff |
| **Day 3** | Scenarios G (payments, live sandbox) + I (lecturer) | Finance + lecturers |
| **Day 4** | Scenarios J (admin) + K (KPI) + L (comms) | Admin + managers + VC |
| **Day 5** | Scenario M (non-functional); triage + sign-off | All |

Daily standup at 09:00, bug triage at 16:00. Each scenario has a named **facilitator** (build team) and **participant** (FNU staff).

## 5. Scenarios

Each scenario references the TOR requirement and the detailed manual steps in [TESTING.md](TESTING.md).

### Scenario A — Application submission (TOR 2.1.2) [TESTING.md Part 6]
Prospective student completes the online application, uploads documents, receives confirmation email with application number.

### Scenario B — Application review & offer (TOR 2.1.3) [TESTING.md Part 6]
Staff reviews, requests additional documents, approves, offer letter PDF issued with FNU letterhead. Conditional offer variant for school leaver.

### Scenario C — Offer acceptance [TESTING.md Part 6]
Prospective student opens `/offer/<token>`, reads letter, accepts. Student credentials issued by email.

### Scenario D — First login + portal tour [TESTING.md Part 4]
Student logs in, changes password, views dashboard, navigates all six cards.

### Scenario E — Course registration (TOR 2.1.4) [TESTING.md Part 7]
Student picks courses including one that should clash (warning shown), one with unmet prereqs (blocked with reason), registers the clean set, sees confirmation + invoice + updated timetable.

### Scenario F — Timetable + grades + my-courses (TOR 2.1.5, 2.1.8, 2.1.9) [TESTING.md Part 7]
Student views timetable, exports .ics and imports into Google Calendar, views grades (from seeded history) and current GPA, views "My Courses" with lecturer contact.

### Scenario G — Payments (TOR 2.2) [TESTING.md Part 8]
Student initiates payment via M-PAiSA sandbox (full success), via MyCash sandbox (failure then retry), via bank transfer (finance confirms). Payment plan created and an overdue reminder fires on a short test schedule.

### Scenario H — AI chatbot (TOR 2.3) [TESTING.md Part 9, 10]
Student asks 20 predefined queries (see Appendix A) including the authenticated "what's my balance" query. Escalates one to human support — enquiry row created. Admin adds a new FAQ and students see it reflected in subsequent answers.

### Scenario I — Lecturer workflow (TOR 2.6) [TESTING.md Part 13]
Lecturer views rosters, exports to CSV and PDF, enters grades (draft → submitted → finalised). Grades appear on the student's "My Grades" view. Banner sandbox shows the write.

### Scenario J — Staff admin (TOR 2.4) [TESTING.md Part 12]
Staff searches for a student, records a manual override (prereq waiver) with reason, logs a walk-in enquiry, assigns, resolves. Student rates resolution.

### Scenario K — KPI dashboards (TOR 2.5) [TESTING.md Part 14]
VC/SLT, Dean, Section Head, Finance views all load and show accurate data for the seeded UAT dataset. Section head enters a manual KPI; VC sees it. Admin changes a target; traffic lights update on next recompute.

### Scenario L — Communications (TOR 2.4.3, D9) [TESTING.md Part 11]
Staff edits a template, previews it, sends a batch to the filtered group, verifies recipients received it (Mailtrap inbox + SMS dashboard). Outstanding-fees banner appears correctly for an overdue student.

### Scenario M — Non-functional (TOR 2.7) [TESTING.md Part 15]
- Public landing page loads in <3 s on a 3G throttle.
- Axe-core shows no critical/serious violations on the core student pages.
- Portal works on Chrome, Firefox, Safari, Edge (latest).
- Works on an iPhone and an Android phone.
- Security headers present (`curl -I`).
- `/api/health` returns all subsystems `ok`.

## 6. Bug log

Every observed defect goes into the [test report template](TEST_REPORT.md). Fields:

- **ID** — `UAT-YYYYMMDD-NNN`
- **Severity** — Blocker / Major / Minor / Cosmetic
- **Reproducer** — numbered steps
- **Expected** — what should happen
- **Actual** — what happened
- **Environment** — browser/OS/device
- **Screenshot or log excerpt**
- **Scenario** — which of A–M
- **Status** — Open / In Fix / Fixed / Deferred / Closed

Daily triage sorts by severity; blockers must be fixed before go-live. Majors are evaluated for fix-vs-defer with FNU PM sign-off on any deferral.

## 7. Exit criteria

All of the following must be true for UAT sign-off:

- [ ] All 13 scenarios executed end-to-end.
- [ ] Zero **Blocker** bugs open.
- [ ] All **Major** bugs have a signed-off resolution (fix shipped or deferral approved by FNU PM).
- [ ] 20/20 predefined chatbot queries return acceptable answers.
- [ ] At least **one confirmed sandbox transaction** per payment gateway.
- [ ] Grade submission verified end-to-end (draft → finalised → visible to student → Banner write confirmed).
- [ ] Accessibility, cross-browser, and mobile checks all pass (scenario M).
- [ ] FNU PM and FNU IT lead sign the UAT sign-off sheet (see [TEST_REPORT.md](TEST_REPORT.md)).

## 8. Participants and contacts

| Role | Name | Email |
|---|---|---|
| FNU PM | *TBA* | pm@fnu.ac.fj |
| FNU IT lead | *TBA* | it-director@fnu.ac.fj |
| Build team lead | *TBA* | *TBA* |
| UAT facilitator | *TBA* | *TBA* |

## Appendix A — 20 chatbot acceptance queries

These 20 predefined queries must all return sensible answers (TOR 2.3 acceptance). Drawn from the seeded FAQ set plus authenticated-mode scenarios.

1. "What are the entry requirements for the Bachelor of Nursing?"
2. "When does Semester 2 2026 start?"
3. "How much is tuition for the Bachelor of Commerce?"
4. "How do I apply to FNU?"
5. "What documents do I need for my application?"
6. "I'm a school leaver — can I get a conditional offer?"
7. "How long does it take to review my application?"
8. "How do I accept an offer?"
9. "Where are FNU campuses located?"
10. "How do I pay my fees?"
11. "What payment methods does FNU accept?"
12. "Can I pay in instalments?"
13. "What happens if I miss a payment?"
14. "How do I check my timetable?"
15. "How do I add or drop a course?"
16. "What is my current balance?" *(authenticated)*
17. "What courses am I registered for?" *(authenticated)*
18. "When can I graduate?"
19. "I want to speak to a human." *(must escalate)*
20. "Can I defer my admission?"

---

*Last updated: 2026-04 (Part 16). Owner: build team + FNU PM.*
