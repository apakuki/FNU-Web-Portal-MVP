# LLM-Driven End-to-End Code Review Workflow for a NextJS + Python Student Portal Project

You are not looking for a shallow "scan the code and give comments" review.

You want a structured engineering-grade audit pipeline where:

An LLM reviews your codebase in stages.
Findings are organized into categories.
Results are validated.
Recommendations become implementation tasks.
Another LLM agent applies fixes safely.
Changes are verified before merge.

This workflow is how you turn an LLM into a real software review partner instead of a random suggestion engine.

## High-Level Architecture

Your workflow should look like this:

Project Codebase
        ↓
Repository Preparation
        ↓
Context Packaging
        ↓
Multi-Pass LLM Code Review
        ↓
Structured Findings Report
        ↓
Human Validation
        ↓
Task Breakdown
        ↓
Implementation LLM Agent
        ↓
Automated Testing + Security Validation
        ↓
Merge Approved Changes
## Step 1 — Freeze The Current State

Before reviewing anything:

### Create a Review Branch
git checkout -b review/student-portal-audit

You never want the LLM changing your production branch directly.

## Step 2 — Create a Clean Repository Structure

LLMs fail when repositories are messy.

You want a predictable structure.

Example:

student-portal/
├── frontend/
│   ├── app/
│   ├── components/
│   ├── hooks/
│   ├── services/
│   ├── utils/
│   └── tests/
│
├── backend/
│   ├── api/
│   ├── services/
│   ├── models/
│   ├── db/
│   ├── auth/
│   ├── middleware/
│   └── tests/
│
├── database/
│   ├── migrations/
│   └── schema/
│
├── docs/
├── docker/
├── .env.example
├── docker-compose.yml
├── README.md
└── architecture.md

If the repo is chaotic, review quality drops dramatically.

## Step 3 — Generate Architecture Context

The biggest weakness of LLM code review is lack of system-level understanding.

You must give the model context.

Create:

### architecture.md

Include:

Application purpose
User roles
Authentication flow
Database relationships
API structure
Frontend routing
Security assumptions
Third-party integrations
Docker architecture
Deployment flow

Without this file, the LLM reviews fragments instead of systems.

## Step 4 — Generate Repository Inventory

Create a machine-readable project map.

Run:

tree -L 4 > repo-structure.txt

Also create:

find . -type f > file-index.txt

This allows the LLM to understand:

Project scale
Layer separation
Folder ownership
Dependency placement

## Step 5 — Create Review Domains

Never ask:

“Review my whole project.”

That produces weak output.

You must review in domains.

### Domain 1 — Architecture Review

Ask:

Review this repository structure and architecture.


Focus on:
- Layer separation
- API boundaries
- Dependency coupling
- Scalability
- State management
- Backend ownership boundaries
- Technical debt patterns
- Anti-patterns

Expected output:

Structural weaknesses
Tight coupling
Missing abstraction layers
Scaling risks
### Domain 2 — NextJS Frontend Review

Ask:

Review this NextJS frontend.


Focus on:
- Component architecture
- Server/client component separation
- State management
- API fetching patterns
- Hydration risks
- Render inefficiencies
- Accessibility
- Form handling
- Route protection
- Error boundaries
- Security issues

Expected output:

Rendering inefficiencies
Missing loading states
Memory leaks
Bad component composition
Auth weaknesses
### Domain 3 — Python Backend Review

Ask:

Review this Python backend.


Focus on:
- Service layer design
- API validation
- Async handling
- Exception management
- Dependency injection
- Auth handling
- SQL safety
- Business logic duplication
- Transaction safety
- Performance bottlenecks

Expected output:

Missing validation
Unsafe queries
Weak service isolation
Retry failures
Blocking calls
### Domain 4 — Database Review

Ask:

Review this database schema.


Focus on:
- Table normalization
- Indexing
- Foreign keys
- Constraints
- Query efficiency
- Data integrity
- Missing relations
- Cascade rules

Expected output:

Missing indexes
Bad relationships
Over-normalization
Under-normalization
### Domain 5 — Security Review

Ask:

Review this full stack application for security vulnerabilities.


Focus on:
- Authentication
- Authorization
- Session handling
- JWT usage
- CSRF
- XSS
- SQL injection
- Rate limiting
- Input validation
- Secrets management
- File upload security
- Docker exposure

Expected output:

Critical vulnerabilities
Misconfigurations
Unsafe auth flows
### Domain 6 — Performance Review

Ask:

Review this application for performance bottlenecks.


Focus on:
- Query performance
- Rendering performance
- Bundle size
- Duplicate API calls
- N+1 query problems
- Cache opportunities
- Pagination
- Slow endpoints

Expected output:

Expensive queries
Render loops
Over-fetching
Cache gaps
### Step 6 — Feed Code To The LLM Correctly

Do NOT paste entire repo at once.

That destroys context quality.

Use chunking.

Recommended chunk size:

1000–2500 lines per review segment

Provide:

1. Architecture file
2. Repo tree
3. Relevant code files
4. Review prompt

Sequence matters.

Bad:

Review this folder.

Good:

This is a student portal.


Architecture:
[paste architecture.md]


Repo structure:
[paste repo tree]


Now review the auth service and related middleware.


Focus on:
- JWT validation
- Session persistence
- Permission leakage
- Security risks
### Step 7 — Force Structured Output

You want deterministic review output.

Use this format:

For every issue found provide:


1. Severity
   - Critical
   - High
   - Medium
   - Low


2. File affected


3. Problem description


4. Why it matters


5. Suggested fix


6. Example code


7. Estimated impact

This prevents vague answers.

### Step 8 — Create A Master Findings Document

Build:

review-report.md

Structure:

- Architecture Findings
- Frontend Findings
- Backend Findings
- Database Findings
- Security Findings
- Performance Findings

You now have a real audit document.

### Step 9 — Validate Findings

Never trust raw LLM output.

Run:

Unit tests
Static analysis
Linters
Dependency audit
Security scanners

Recommended stack:

Frontend:

npm run lint
npm run build
npm audit

Backend:

ruff .
bandit -r .
pytest

Database:

EXPLAIN ANALYZE
### Step 10 — Convert Findings Into Implementation Tasks

You do NOT give raw review text to another LLM.

That produces chaos.

Convert findings into tickets.

Example:

TASK-001


Problem:
JWT tokens never expire.


Files:
backend/auth/jwt_handler.py


Required fix:
Implement token expiration validation.


Acceptance Criteria:
- Tokens expire after 60 minutes
- Refresh token supported
- Invalid token rejected
- Unit tests added
### Step 11 — Feed Tasks To Implementation Agent

Now the builder LLM becomes highly effective.

Prompt:

Implement TASK-001.


Do not modify unrelated code.


Requirements:
- Preserve current architecture
- Add tests
- Explain changes
- Output changed files only

This prevents codebase drift.

### Step 12 — Review The Fixes Again

You now run:

Second-pass review

Ask:

Review only the changed files.


Focus on:
- Regression risk
- Security
- Maintainability
- Coding standards
Step 13 — Add Continuous Review Pipeline

Once the project matures, automate.

Add:

GitHub Actions

Pipeline:

Push → Tests → Security Scan → LLM Review → PR Comment
Recommended Tool Stack
Repository Understanding
GitHub
Cursor
VS Code
Claude
ChatGPT
Gemini
Security
Bandit
Semgrep
OWASP ZAP
Trivy
npm audit
Static Analysis

Frontend:

ESLint
TypeScript strict mode
Prettier

Backend:

Ruff
mypy
pylint
Database
pgAdmin
EXPLAIN ANALYZE
DB schema visualization
Best Prompt For Full Review
You are a senior staff engineer performing a full-stack audit.


Application:
Student Portal


Stack:
- NextJS frontend
- Python backend
- PostgreSQL database
- Docker deployment


Your task:
Review this codebase as if preparing it for enterprise production.


Evaluate:
- Architecture
- Maintainability
- Security
- Performance
- Scalability
- Technical debt
- Code duplication
- Data integrity
- API design
- Authentication
- Deployment safety


For every finding output:
- Severity
- File
- Explanation
- Risk
- Suggested fix
- Refactor example
The Biggest Mistake People Make

Most people ask:

“Review my app.”

That is garbage input.

You must:

Provide architecture context.
Review by domain.
Force structured output.
Convert findings into tickets.
Feed tickets to implementation agent.

That creates a professional engineering loop.

Recommended Execution Order
1. Architecture Review
2. Backend Review
3. Frontend Review
4. Database Review
5. Security Review
6. Performance Review
7. Findings Consolidation
8. Ticket Creation
9. Fix Implementation
10. Regression Review
What You Should Do Next

For your student portal specifically:

Build architecture.md
Export repo tree
Start with backend auth review
Review DB schema next
Then frontend routing/auth
Finish with security audit

The auth layer and database design usually hide the biggest failures in student portal projects.

Those are normally where permissions, session handling, and data leakage problems live.