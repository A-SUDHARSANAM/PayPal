# AgentPay implementation plan

## 1. Repository assessment and scope

**Assessment (2026-11-12):** the repository is empty. There is no existing Next.js application, FastAPI service, database migration history, environment template, test suite, or repository-specific instruction file.

This plan therefore defines a greenfield, hackathon-grade build. It uses a **controlled demo catalog** only; its products, merchant labels, prices, availability, and images are clearly presented as demo data. It does not scrape or represent live merchant inventory. PayPal is limited to its Sandbox environment, and no payment is captured without an explicit human confirmation in the UI.

## 2. Proposed architecture

### Deployment topology

```text
Browser
  │
  ▼
Next.js web app (Vercel)
  ├─ Authentication/session UI
  ├─ Request and approval experience
  └─ PayPal JS SDK button (Sandbox client ID only)
  │ HTTPS + user access token
  ▼
FastAPI API (Render)
  ├─ API/auth boundary and rate limits
  ├─ Orchestrator and specialized-agent services
  ├─ Server-side catalog, pricing, policy, and order validation
  ├─ Gemini adapter (structured outputs)
  ├─ PayPal REST adapter (Sandbox server credentials)
  └─ Webhook verification/processing
  │                         │
  ▼                         ▼
Supabase PostgreSQL       PayPal Sandbox REST + webhook events
```

### Frontend: Next.js + TypeScript + Tailwind + shadcn/ui

Use the App Router. The frontend should be a presentation and interaction layer, never a source of truth for products, prices, approvals, transaction state, or payment capture.

Key routes:

| Route | Purpose |
| --- | --- |
| `/` | Product explanation and authenticated entry point. |
| `/requests/new` | Natural-language purchase request form, budget, and optional delivery/preferences fields. |
| `/requests/[id]` | Live workflow timeline, research options, validations, recommendation, and explanations. |
| `/requests/[id]/approve` | Explicit final review: selected item, canonical total, policy findings, and irreversible approval action. |
| `/checkout/[paymentId]` | Renders PayPal Sandbox checkout only after backend approval/order creation. |
| `/transactions` | User transaction history and receipt/status detail. |
| `/admin/catalog` (optional demo admin) | Restricted catalog management; omit for the first demo if time is tight. |

Use React Query or server actions only for UI-friendly data fetching; all state-changing operations go to FastAPI. Store the Supabase auth session in secure cookies using the supported Supabase SSR pattern. Configure the PayPal JS SDK with a *Sandbox client ID* exposed as `NEXT_PUBLIC_PAYPAL_CLIENT_ID`; its secret stays exclusively in FastAPI.

### Backend: FastAPI

Organize around clear domain boundaries:

```text
backend/app/
  api/             # versioned routers and request/response schemas
  core/            # configuration, security, logging, error handling
  db/              # SQLAlchemy models, repositories, Alembic migrations
  domain/          # state machines and business rules
  services/        # catalog, workflow, finance, risk, recommendation
  agents/          # orchestrator and Gemini-backed agent adapters
  integrations/    # Supabase auth verifier, PayPal, Gemini
  workers/         # optional durable/background processing
  tests/
```

The API validates the Supabase JWT, derives the user identity from it, and applies authorization checks on every request. Product lookup and final price calculation always happen on the server from the catalog. Monetary values are integer minor units (`amount_minor`) plus an ISO 4217 currency code, never floating point.

### Agent architecture

Agents are services called by the orchestrator, not autonomous actors with direct payment access. Gemini is used for interpreting requests, product narrative comparison, and natural-language explanations. Deterministic code remains authoritative for prices, budgets, risk thresholds, IDs, policies, state transitions, and PayPal calls.

| Component | Input | Output | Authority |
| --- | --- | --- | --- |
| Orchestrator | purchase request | persisted workflow and stage transitions | selects the next allowed agent; cannot capture funds |
| Research agent | structured intent + demo catalog | matching catalog product IDs and comparison notes | can only reference catalog IDs returned by server search |
| Finance agent | canonical candidates, budget and user limits | pass/warn/fail findings and totals | deterministic checks first; Gemini may explain findings |
| Risk agent | request context and transaction history | pass/review/fail findings | deterministic duplicate/limit/policy rules first |
| Recommendation agent | eligible candidates and findings | ranked product IDs plus concise rationale | only ranks options that passed required validations |
| Payment agent | approved selected product and canonical quote | PayPal order / capture status | only server service with PayPal secret; capture requires approved state |

Each Gemini call has a strict JSON schema, low temperature, bounded input from server-curated records, timeout/retry rules, and stored model/version/request metadata. Treat model output as untrusted: validate it with Pydantic and reject unknown product IDs, arbitrary prices, invalid enums, or malformed fields. A deterministic fallback should return simple catalog ordering/reason text when Gemini is unavailable, so no money workflow fails open.

### Workflow state machine

```text
draft → submitted → researching → validating → recommended
                                      │             │
                                      └→ blocked ←──┘
recommended → awaiting_approval → approved → order_created → checkout_started
                                                              │
                                     cancelled ←──────────────┼─→ capture_pending
                                                              │        │
                                                              └────────┴→ captured
                                                                        └→ failed / expired
```

`approved` requires a user interaction that displays the selected product, server-calculated amount/currency, and disclosures. Approval records the user, timestamp, quote/version, and an idempotency key. Any selected-product, catalog-price, currency, or material request change invalidates prior approval and returns the request to `awaiting_approval`.

Only one transition may be applied at a time (row lock and/or optimistic `version` column). Payment capture is additionally serialized by a unique PayPal order constraint and a database transaction. Webhooks reconcile asynchronous PayPal state; the UI never declares a payment successful merely because the browser returned from checkout.

## 3. API contract (v1)

All non-webhook endpoints require `Authorization: Bearer <Supabase access token>`. Response models must avoid returning provider secrets, raw tokens, or sensitive prompts. Mutations require a generated/requested `Idempotency-Key` header and write an audit event.

### User workflow

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/purchase-requests` | Create a draft from natural-language intent, budget, currency, and optional preferences. |
| `GET` | `/api/v1/purchase-requests` | List the authenticated user’s requests. |
| `GET` | `/api/v1/purchase-requests/{request_id}` | Return workflow status, safe agent findings, candidates, recommendation, and approval eligibility. |
| `POST` | `/api/v1/purchase-requests/{request_id}/submit` | Validate request and start/retry orchestration; returns workflow status. |
| `POST` | `/api/v1/purchase-requests/{request_id}/select` | Select a recommended eligible catalog product by ID; server derives the quote. |
| `POST` | `/api/v1/purchase-requests/{request_id}/approve` | Explicitly approve current selected quote; requires confirmation payload and idempotency key. |
| `POST` | `/api/v1/purchase-requests/{request_id}/cancel` | Cancel an un-captured workflow. |
| `GET` | `/api/v1/purchase-requests/{request_id}/events` | Fetch audit-friendly workflow timeline; SSE can be added later for live updates. |

### Catalog and payments

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/catalog/products` | Return clearly labeled demo products; supports bounded search/filtering. |
| `GET` | `/api/v1/catalog/products/{product_id}` | Return a demo product and current display price. |
| `POST` | `/api/v1/payments/orders` | Create a PayPal Sandbox order for an already approved, current quote. The body references request ID only—not price. |
| `GET` | `/api/v1/payments/{payment_id}` | Return canonical payment/order status for the owner. |
| `POST` | `/api/v1/payments/{payment_id}/capture` | Server captures the associated order after PayPal approval. It is idempotent and valid only once. |
| `GET` | `/api/v1/transactions` | List authenticated user’s transaction records. |
| `GET` | `/api/v1/transactions/{transaction_id}` | Return authenticated user’s transaction record and reconciliation status. |
| `POST` | `/api/v1/webhooks/paypal` | Public endpoint validating PayPal webhook signature before recording/reconciling events. |
| `GET` | `/healthz` | Liveness endpoint with no secrets or dependency detail. |
| `GET` | `/readyz` | Internal/controlled readiness check for DB/config availability. |

For a hackathon MVP, `POST /submit` may run the bounded agent pipeline synchronously and return the completed recommendation. A production-shaped iteration should enqueue it and expose polling/SSE. Do not expose arbitrary "run agent" endpoints that could bypass the state machine.

## 4. Database schema

Use Supabase Postgres for durable application data. Use Alembic migrations owned by FastAPI; Supabase Auth owns `auth.users`. UUID primary keys, UTC `timestamptz`, and an append-only audit trail are the defaults.

| Table | Core columns | Notes / constraints |
| --- | --- | --- |
| `profiles` | `id` (FK `auth.users`), `display_name`, `default_currency`, `monthly_limit_minor`, timestamps | User preferences; no raw payment credentials. |
| `catalog_products` | `id`, `sku` (unique), `name`, `description`, `category`, `price_minor`, `currency`, `image_url`, `merchant_label`, `is_demo`, `is_active`, `catalog_version`, timestamps | Mark every record `is_demo=true` for MVP. Price is server authoritative. |
| `purchase_requests` | `id`, `user_id`, `natural_language_request`, `budget_minor`, `currency`, `preferences` JSONB, `status`, `selected_product_id`, `quote_minor`, `quote_currency`, `quote_catalog_version`, `approval_invalidated_at`, `version`, timestamps | Check nonnegative budget; selected product must be valid for request state. |
| `workflow_runs` | `id`, `purchase_request_id`, `status`, `started_at`, `finished_at`, `failure_code`, `attempt` | One or more retryable orchestration runs. |
| `agent_runs` | `id`, `workflow_run_id`, `agent_type`, `status`, `input_digest`, `output` JSONB, `model_name`, `model_version`, `prompt_version`, `started_at`, `finished_at`, `error_code` | Never persist secrets; redact PII as appropriate. |
| `product_candidates` | `id`, `purchase_request_id`, `product_id`, `rank`, `match_score`, `research_notes`, `eligible`, timestamps | Unique `(purchase_request_id, product_id)`. Product price is joined from catalog/quote, not trusted from notes. |
| `validation_findings` | `id`, `purchase_request_id`, `agent_type`, `severity`, `code`, `message`, `details` JSONB, `is_blocking`, timestamps | Finance/risk outputs; deterministic codes enable UI and tests. |
| `recommendations` | `id`, `purchase_request_id` (unique/current), `product_id`, `ranked_products` JSONB, `rationale`, `status`, timestamps | Product reference must be among eligible candidates. |
| `approvals` | `id`, `purchase_request_id`, `user_id`, `product_id`, `amount_minor`, `currency`, `quote_catalog_version`, `approved_at`, `approval_token_hash`, `idempotency_key` | Unique `(purchase_request_id, quote_catalog_version)` and idempotency key per user/action. Immutable proof of explicit approval. |
| `payments` | `id`, `purchase_request_id` (unique), `approval_id` (unique), `user_id`, `provider`, `environment`, `paypal_order_id` (unique nullable), `paypal_capture_id` (unique nullable), `amount_minor`, `currency`, `status`, `capture_attempted_at`, `captured_at`, timestamps | `provider='paypal'`, `environment='sandbox'` enforced in MVP. Amount must equal approval quote. |
| `payment_events` | `id`, `payment_id`, `provider_event_id` (unique), `event_type`, `payload` JSONB, `verified_at`, `processed_at`, `processing_result` | Store verified webhook payloads for reconciliation; restrict access. |
| `transactions` | `id`, `payment_id` (unique), `user_id`, `product_id`, `amount_minor`, `currency`, `status`, `provider_capture_id`, `completed_at`, timestamps | Created/updated only from canonical payment outcomes. |
| `audit_events` | `id`, `actor_user_id` nullable, `entity_type`, `entity_id`, `action`, `before_state` JSONB, `after_state` JSONB, `request_id`, `ip_hash`, timestamps | Append-only event trail for approvals, state changes, and payment actions. |

Recommended indexes: request `(user_id, created_at DESC)`, candidate `(purchase_request_id, rank)`, finding `(purchase_request_id, is_blocking)`, payment `(user_id, status)`, and a partial duplicate-detection index/query over recent pending/captured requests with normalized intent and amount. Apply row-level security as defense in depth for user-owned tables (user can only select their own records); backend service access uses a server-only Supabase service role key and remains subject to application authorization.

## 5. Configuration and secrets

Provide `.env.example`, never `.env` with real values. Required server-side variables:

```dotenv
ENVIRONMENT=development
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_JWT_ISSUER=
GEMINI_API_KEY=
GEMINI_MODEL=
PAYPAL_CLIENT_ID=
PAYPAL_CLIENT_SECRET=
PAYPAL_BASE_URL=https://api-m.sandbox.paypal.com
PAYPAL_WEBHOOK_ID=
ALLOWED_ORIGINS=http://localhost:3000
```

Frontend variables are limited to public values such as `NEXT_PUBLIC_API_BASE_URL`, `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, and `NEXT_PUBLIC_PAYPAL_CLIENT_ID`. Environment validation must reject production/live PayPal hostnames for the MVP. Vercel and Render hold their own secret stores; no secrets are committed or sent to Gemini.

## 6. Development roadmap

| Phase | Deliverable | Acceptance criteria |
| --- | --- | --- |
| 0. Foundation | Monorepo scaffold (`apps/web`, `apps/api`, shared contract package optional), formatting/linting, CI, `.env.example`, deployment docs | Local web/API boot; CI runs typecheck, lint, and tests. |
| 1. Data/auth/catalog | Supabase project, migrations, auth integration, seeded demo catalog, RLS, catalog endpoints/UI | A signed-in user sees only demo-labelled catalog records and their own data. |
| 2. Request/workflow core | Purchase request CRUD, state machine, audit events, deterministic product search and finance/risk rules | Invalid transitions, arbitrary prices, and foreign-user IDs are rejected. |
| 3. AI assistance | Gemini adapter, JSON schemas, agent-run persistence, orchestrator, deterministic fallback | Model output cannot select nonexistent product, change a price, or advance to payment. |
| 4. Decision UI | Workflow timeline, comparison cards, findings, recommendation, explicit approval review | Approval is impossible with blocking findings or stale quote; changing selection invalidates approval. |
| 5. PayPal Sandbox | Order creation, JS checkout, server capture, webhook validation/reconciliation, transaction screens | One explicit approval produces at most one capture; UI reflects verified canonical status. |
| 6. Hardening/demo | Observability, error states, accessibility, seed/demo script, deployment validation and demo runbook | Fresh deployment completes a safe happy path and representative failures. |

Recommended MVP cut line: do Phases 0–5 with fixed catalog inventory, a small deterministic ruleset, polling rather than real-time streams, and no admin UI. Do not cut server-side quote validation, approval records, idempotency, webhook verification, or capture reconciliation.

## 7. Security and reliability requirements

| Risk | Required mitigation |
| --- | --- |
| Client-side amount/product tampering | Accept only IDs; fetch active product and price server-side; recompute quote before order creation/capture. |
| Unauthorized data access | Verify Supabase JWT on API; ownership checks; RLS; scoped service-role use only in backend. |
| Payment without consent | Require state `approved`, fresh immutable approval record, visible confirmation, and user ownership before order creation/capture. |
| Duplicate capture/retries | Idempotency keys, unique order/capture IDs, transactional locks, provider status fetch before retry, webhook deduplication. |
| Fake success states | Never set `captured` from browser data; verify PayPal capture API response and verified webhooks. |
| Live-payment accident | Hard-code no credentials; config guard requires Sandbox base URL/environment; test asserts live endpoints are rejected. |
| Prompt injection / unsafe model output | Keep catalog and policy context server curated; structured schema validation; no tool access to payment; logs/redaction; deterministic policy precedence. |
| Budget/risk bypass | Deterministic server rules are blocking gates; user-facing explanations never alter the decision. |
| Webhook forgery/replay | Verify PayPal headers/signature via PayPal API; unique provider event ID; retain raw event separately; reject unverified events. |
| Secret exposure | Secret manager, least privilege, no client secret, no secret logs, repo scanning, key rotation procedure. |
| XSS/CSRF/CORS | React escaping and content security policy, origin allowlist, secure cookies, CSRF protection for cookie-auth mutations, input validation. |
| Abuse/cost exhaustion | Per-user/IP rate limits, request size limits, Gemini timeouts/quotas, bounded retries, circuit breaker/fallback. |
| Sensitive audit data | Minimize stored PII, hash IPs, redact prompts/logs, retention policy, restricted audit/event access. |

Do not store card details, PayPal credentials belonging to users, or PayPal approval URLs beyond what is operationally necessary. Use PayPal-provided checkout rather than handling payment instrument data.

## 8. Testing and verification plan

### Automated tests

- **Unit tests:** money/currency formatting, catalog quote calculation, budget and recurring-cost rules, risk thresholds, state-transition guard, approval invalidation, redaction, Gemini JSON validation, and PayPal response mapping.
- **API/integration tests:** authentication/ownership, RLS policies, request lifecycle, blocked validation, stale approval, server-side price recomputation, idempotency collisions, concurrent capture attempts, provider timeout/retry, and webhook replay/signature failures.
- **Contract tests:** OpenAPI schema checked by frontend generated types/client; PayPal Sandbox adapter fixtures from official response shapes.
- **Frontend component tests:** clear demo-data labels, disabled/blocked approval actions, final amount disclosure, error/retry states, and accessible form feedback.
- **End-to-end tests:** Playwright with mocked Gemini and PayPal for deterministic flows: recommended purchase → explicit approval → checkout handoff → verified capture display; plus cancelled checkout, rejected risk, and stale-price scenarios.
- **Sandbox smoke test:** controlled PayPal Sandbox buyer completes a small demo order in a non-production environment; verify server capture and webhook reconciliation, then record no fictional transaction in tests.
- **Security checks:** dependency audit, secret scan, static typing/linting, authz regression suite, OWASP-oriented API tests, and manual webhook-signature verification exercise.

### Definition of done for payments

1. The final amount is derived solely from the active server catalog quote.
2. The user has performed a recorded explicit approval for that exact quote.
3. The backend creates a Sandbox order exactly once or returns its existing idempotent result.
4. Capture is guarded, idempotent, provider-verified, and transaction records are written atomically/reconciled by verified webhook.
5. A duplicate or failed capture never appears as a success in the UI.

## 9. Initial implementation decisions

- Start in USD-only Sandbox for the hackathon unless multi-currency is a required demo scenario; keep the schema currency-safe from day one.
- Seed a small curated catalog (for example, 20–40 items across 3–4 categories) with copyright-safe mock images and explicit `Demo catalog` badges.
- Use Pydantic v2, SQLAlchemy 2, Alembic, `httpx`, and pytest for the API; use Zod, React Hook Form, TanStack Query, Vitest, and Playwright for the web application.
- Generate and publish FastAPI OpenAPI types/client for the frontend to reduce API drift.
- Treat Gemini as augmentation, not authorization. If it is unavailable, users can still receive a deterministic catalog-based outcome or a safe retry state.

## 10. Questions deferred until implementation

No decisions are currently blocking the planning phase. Before the payment-integration phase, confirm the PayPal Sandbox app/client credentials and webhook endpoint setup. Before the authentication phase, confirm whether email/password, magic link, or a demo-only sign-in experience is preferred. The plan assumes Supabase Auth with email/password or magic link and a single user role for the MVP.
