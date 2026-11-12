# AgentPay

> A human-approved, multi-agent purchase workflow for safer AI-assisted commerce.

AgentPay turns a natural-language purchase request into a controlled decision workflow: it searches a **demo catalog**, validates budget and risk rules, ranks eligible products, requires explicit human approval, then prepares a PayPal **Sandbox** checkout order. AI agents can recommend; they cannot authorize or capture a payment.

## Hackathon summary

| Item | Detail |
| --- | --- |
| Track | What's Next with PayPal and AI |
| Demo URL | _Not deployed yet — add verified Vercel URL here_ |
| Video URL | _Add published YouTube URL here_ |
| Payment environment | PayPal Sandbox only |
| Catalog | Controlled demo products, not live merchant inventory |

## The problem

AI can reduce the effort of researching purchases, but an autonomous agent that spends money creates obvious trust, security, and accountability problems. People need an understandable recommendation, deterministic policy checks, and a clear moment to approve before any payment workflow begins.

## Proposed solution

AgentPay separates AI reasoning from payment authority. A FastAPI orchestrator coordinates specialized agents; deterministic backend checks own prices, product IDs, budgets, risk policy, workflow state, and PayPal calls. The user must explicitly approve the selected server-calculated quote. Only then can the backend create a PayPal Sandbox order; capture additionally requires PayPal to report buyer approval.

## What is implemented

- Premium Next.js dashboard with request, monitoring, approval, transaction, and settings views.
- FastAPI Research, Finance, Risk, Recommendation, and Payment agents plus a central orchestrator.
- Controlled demo catalog; the UI labels it as demo data.
- Gemini structured JSON adapter with Pydantic validation and deterministic catalog/policy gates.
- Explicit product selection and immutable pending approval workflow.
- PayPal Orders v2 Sandbox OAuth, order creation, retrieval, guarded capture, status mapping, idempotency key, webhook signature verification, and webhook deduplication.
- Supabase schema/migration, RLS policies, demo seed data, transaction/audit records, and server-only repository adapter.
- JWT-protected backend routes; browser API client attaches the active Supabase access token.
- Structured request logging, basic in-process rate limiting, `/healthz`, and secret-safe `/readyz`.

## Deployment-dependent / planned items

- A live Vercel URL, Render URL, registered webhook ID, and real Sandbox capture are not yet verified.
- Supabase Auth UI/sign-in screens are not yet implemented; the API client is ready to use an existing Supabase browser session.
- Cross-instance database locking and durable workflow reads should replace in-memory workflow state before a multi-instance production deployment.
- The dashboard’s aggregate analytics tiles are UI placeholders until reporting endpoints are added.

## Key innovations

- **AI advises, deterministic code authorizes:** LLM output cannot create orders, set prices, choose arbitrary products, approve a request, or capture money.
- **Human approval is an explicit cryptographic/business boundary:** approval records bind user, product, currency, and server-calculated minor-unit amount.
- **Defense-in-depth payment checks:** canonical quote validation, PayPal order re-fetch, provider status verification, idempotency, capture locking, unique IDs, and verified webhooks.
- **Explainable multi-agent routing:** research, finance, risk, and recommendation findings are separate structured artifacts rather than one opaque response.
- **Demo-data honesty:** product catalog and merchant labels are explicitly marked as simulated.

## Features

- Natural-language purchase request intake
- Product comparison cards and recommendation rationale
- Budget/max-transaction and recurring-cost evaluation
- Duplicate-request, unusual-amount, and eligibility risk checks
- Human approval/rejection center
- PayPal Sandbox checkout handoff and capture flow
- Payment state/transaction result display
- Agent activity status and structured execution logging

## System architecture

```text
┌──────────────────────────┐       HTTPS + Supabase JWT       ┌───────────────────────────┐
│ Next.js / Vercel         │ ───────────────────────────────▶ │ FastAPI / Render          │
│ • dashboard              │                                  │ • auth + orchestration    │
│ • approvals              │ ◀─────────────────────────────── │ • deterministic policies  │
│ • PayPal redirect UI     │         typed workflow state      │ • Gemini / PayPal adapters│
└───────────┬──────────────┘                                  └───────┬───────────┬───────┘
            │                                                         │           │
            ▼                                                         ▼           ▼
   Supabase Auth session                                    Supabase Postgres  PayPal Sandbox
   (browser publishable key)                                RLS + audit logs  Orders v2 + webhooks
```

## Multi-agent workflow

```text
User request
    │
    ▼
Research Agent ──▶ controlled catalog matches + comparison
    │
    ├──────────────▶ Finance Agent ──▶ budget / limit / recurring-cost result
    ├──────────────▶ Risk Agent ─────▶ duplicate / amount / eligibility result
    │                              │
    └──── blocking policy? ─────────┴──▶ blocked (no approval, no order)
                                           │
                                           ▼
Recommendation Agent ──▶ eligible ranked product IDs + explanation
    │
    ▼
User selects + explicitly approves canonical quote
    │
    ▼
Payment Agent ──▶ PayPal Sandbox order ─▶ buyer approval ─▶ guarded capture
    │                                                           │
    └───────── verified webhook / API status ◀─────────────────┘
```

## PayPal integration

The Payment Agent uses the official PayPal Orders v2 Sandbox endpoints. It obtains an OAuth token server-side, creates an order from a stored approved quote, returns PayPal’s approval link if present, retrieves the order before capture, and captures only if PayPal reports `APPROVED`.

The frontend never submits an amount or PayPal secret. The backend validates the stored approval, product ID, minor-unit amount, currency, PayPal reference ID, and provider order state. Webhook payloads are verified through PayPal’s signature-verification API before reconciliation. A redirect to the return URL alone is never considered payment success.

## AI and agents

Gemini is used only for structured product-intent extraction and explanatory assistance. Every response is constrained by a Pydantic JSON schema. The server, not Gemini, searches the catalog and enforces price, budget, risk, approval, and payment decisions.

| Agent | Implemented responsibility |
| --- | --- |
| Research | Extract intent; match controlled catalog products; return comparisons. |
| Finance | Evaluate canonical product total against budget/transaction limit and recurring cost. |
| Risk | Check duplicate requests, unusual amounts, product eligibility, and policy flags. |
| Recommendation | Rank only eligible catalog results and explain the selection. |
| Payment | Create/retrieve/capture PayPal Sandbox orders after verified approval. |
| Orchestrator | Sequence agents, validate outputs, block policies, and create pending approvals. |

## Technology stack

- Frontend: Next.js, TypeScript, Tailwind CSS, shadcn-style primitives
- Backend: Python, FastAPI, Pydantic, httpx
- AI: Google Gemini structured JSON output
- Data/auth: Supabase PostgreSQL and Supabase Auth
- Payments: PayPal Orders API v2 Sandbox
- Hosting target: Vercel (frontend), Render (backend)

## Database schema

See [migration](backend/supabase/migrations/001_initial_schema.sql) for the authoritative schema and [Supabase setup guide](backend/docs/supabase-setup.md) for RLS details.

| Table | Purpose |
| --- | --- |
| `users`, `user_budgets` | User profile and limits. |
| `products` | Controlled demo catalog. |
| `purchase_requests`, `agent_executions` | Workflow input and agent audit trail/duration. |
| `recommendations`, `payment_approvals` | Server recommendation and human decision proof. |
| `transactions`, `paypal_webhook_events` | Canonical provider IDs/status and webhook dedupe. |
| `audit_logs` | Append-only payment-related history. |

## Local setup

### Prerequisites

- Node.js 20+ and npm
- Python 3.13+ (or a compatible Python runtime)
- Supabase project, Gemini API key, and PayPal Sandbox REST app for a complete integration test

### Frontend

```bash
npm ci
copy .env.example .env.local
npm run dev
```

Set only these browser-visible variables in `.env.local`:

```dotenv
NEXT_PUBLIC_AGENTPAY_API_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=https://<project-ref>.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=sb_publishable_<public-key>
```

### Backend

```bash
cd backend
python -m pip install -r requirements.txt
copy .env.example .env
python -m uvicorn app.main:app --reload
```

Set backend-only variables in `backend/.env`. Use [backend/.env.example](backend/.env.example) as the variable-name reference; never commit it with values.

## Supabase and Sandbox setup

1. Apply [the schema migration](backend/supabase/migrations/001_initial_schema.sql), then [seed demo products](backend/supabase/seed.sql) in Supabase SQL Editor.
2. Configure Supabase Auth, then set the backend JWT issuer/audience and browser URL/publishable key.
3. In PayPal Developer Dashboard → **Apps & Credentials** → **Sandbox**, create/select the REST app.
4. In **Testing Tools** → **Sandbox Accounts**, use a Business seller and Personal buyer. Sign in to Sandbox checkout only with the Personal buyer.
5. Register the backend webhook and subscribe to `CHECKOUT.ORDER.APPROVED`, `PAYMENT.CAPTURE.COMPLETED`, `PAYMENT.CAPTURE.PENDING`, `PAYMENT.CAPTURE.DENIED`, and `PAYMENT.CAPTURE.DECLINED`.

Full click-by-click instructions: [deployment runbook](docs/deployment-runbook.md) and [PayPal Sandbox guide](backend/docs/paypal-sandbox.md).

## Environment variables

| Variable | Location | Notes |
| --- | --- | --- |
| `NEXT_PUBLIC_AGENTPAY_API_URL` | Vercel/browser | Public Render HTTPS API base URL. |
| `NEXT_PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | Vercel/browser | Public Supabase browser config only. |
| `GEMINI_API_KEY` | Render/backend | Secret; never browser-visible. |
| `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, `PAYPAL_WEBHOOK_ID` | Render/backend | Sandbox secrets. |
| `PAYPAL_BASE_URL` | Render/backend | Must be `https://api-m.sandbox.paypal.com`. |
| `PAYPAL_RETURN_URL`, `PAYPAL_CANCEL_URL` | Render/backend | HTTPS Vercel callback URLs. |
| `SUPABASE_SERVICE_ROLE_KEY` | Render/backend | Secret; bypasses RLS and must remain server-only. |
| `SUPABASE_JWT_ISSUER`, `SUPABASE_JWT_AUDIENCE` | Render/backend | JWT verification configuration. |
| `ALLOWED_ORIGINS` | Render/backend | Exact Vercel origin(s), never `*`. |

## Deployment

Follow the [deployment runbook](docs/deployment-runbook.md). It covers migration application, Render/ Vercel dashboard steps, variable formats, PayPal webhook registration, readiness checks, responsive testing, console/log review, and Sandbox verification. Do not mark the project deployed until every checklist item has evidence.

## Security and human approval

- All money values use integer minor units; frontend-supplied price/product data is ignored.
- User identity is derived from a verified Supabase JWT, not request-body identity.
- Human approval is mandatory before order creation; PayPal buyer approval is mandatory before capture.
- Gemini is never a payment-authority component.
- Sandbox-only PayPal host guard, idempotency key, capture lock, unique provider IDs, and verified webhooks reduce duplicate-capture risk.
- RLS limits user data access; audit logs are immutable at the database layer.

See [security audit](docs/security-audit.md) for findings and deployment blockers.

## Screenshots

_Add verified screenshots before submission. Suggested captures:_

1. Dashboard overview with its demo-data labels.
2. Natural-language request and agent workflow.
3. Product comparison and finance/risk findings.
4. Explicit human approval screen.
5. PayPal Sandbox checkout / return or cancellation state.
6. Transaction state shown from backend response.

Do not use screenshots that imply a successful payment unless the displayed status was verified by PayPal Sandbox.

## License

This project is available under the [MIT License](LICENSE).
