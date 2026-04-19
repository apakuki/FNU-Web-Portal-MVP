# Frontend (Next.js App Router)

## Stack

- Next.js 15+ (App Router), React 19+, TypeScript strict mode
- Tailwind CSS with FNU brand tokens defined in `tailwind.config.ts`
- TanStack Query for server state management
- Zod for client-side form validation
- `next-auth` (Auth.js) with Credentials provider wrapping FastAPI-issued JWT
- Playwright for E2E tests, Vitest for unit tests

## Route Structure

```
app/
  (public)/           # Unauthenticated pages
    page.tsx          # Landing page (Server Component, SSR)
    apply/            # Application form
    offer/[token]/    # Offer acceptance
    verify/[qr]/      # QR verification (Server Component)
    login/            # Login page (Client Component)
  (portal)/           # Authenticated student pages
    layout.tsx        # Portal shell: top nav, side nav, fees banner
    dashboard/        # Dashboard with widget cards
    register/         # Course selection and registration
    timetable/        # Timetable view + .ics export
    courses/          # My courses
    grades/           # My grades
    invoices/         # Invoice list and PDF download
    pay/              # Payment initiation
    id-card/          # Digital student ID with QR
    profile/          # Profile view/edit, photo upload
  (admin)/            # Staff/admin pages
    applications/     # Application review queue
    students/         # Student record search and detail
    enquiries/        # Enquiry management
    communications/   # Batch SMS/email
    finance/          # Reconciliation, bank-confirm
    chatbot/
      knowledge/      # FAQ CRUD
      conversations/  # Query log
      analytics/      # Chatbot analytics
    dashboard/
      vc/             # VC/SLT KPI dashboard
      dean/           # Dean view
      section-head/   # Section head view
      me/             # Individual staff view
      finance/        # Finance KPI view
  (lecturer)/         # Lecturer pages
    rosters/          # Class rosters
    grades/           # Grade entry
```

## Conventions

- Server Components are the default. Use Client Components (`"use client"`) only when the component needs interactivity (event handlers, useState, useEffect, browser APIs).
- API types are generated from the backend OpenAPI schema. Run `npm run generate:types` after backend schema changes. Never hand-write API types.
- All user-visible strings live in a single i18n file (English only for MVP, structured for future Fijian / Hindi).
- Use the shared `apiFetch` helper (`lib/api-client.ts`) for all backend calls. It attaches the session JWT automatically.
- No secrets in `NEXT_PUBLIC_*` environment variables.
- Mobile-first responsive design. Minimum 44px tap targets. WCAG 2.1 AA.
- Standalone output mode (`output: "standalone"` in `next.config.ts`) for small Docker images.

## FNU Brand Tokens

Defined in `tailwind.config.ts`. Colors are provisional until FNU provides updated brand assets:

- `fnu-blue`: `#003A70` (headers, primary buttons)
- `fnu-gold`: `#FFB81C` (accents, highlights)
- `success`: `#2E7D32` (confirmations, KPI green)
- `warning`: `#F9A825` (overdue warnings, KPI amber)
- `danger`: `#C62828` (errors, rejections, KPI red)
- `dark`: `#0A1F33` (headings, body text)
- `gray`: `#6B7280` (supporting text, labels)
- `surface`: `#F4F6F9` (page backgrounds, panels)

## Testing

- Vitest for unit tests. Minimum 80% coverage.
- Playwright for E2E tests across Chromium, Firefox, WebKit.
- axe-core for accessibility checks.
- Lighthouse (simulated 3G) for performance on public pages.

## Key Files

- `lib/api-client.ts` — `apiFetch` wrapper with JWT attachment
- `lib/api-types.ts` — generated TypeScript types (do not edit manually)
- `middleware.ts` — next-auth route protection
- `tailwind.config.ts` — FNU brand tokens
