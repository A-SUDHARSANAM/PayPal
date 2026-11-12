# AgentPay security and quality audit

Audited: 2026-11-12. This is a code-level audit; no real PayPal Sandbox buyer transaction was run because no credentials are stored in the workspace.

## Findings and remediation

| Area | Result | Evidence / action |
| --- | --- | --- |
| PayPal credentials | Pass | Read only from backend settings; no frontend variables or literals. Sandbox host is hard-locked. Rotate credentials previously shared outside a secret manager. |
| Frontend amount manipulation | Pass | `CreateOrderRequest` accepts only an approval ID. Payment Agent derives product, price, and currency from canonical server records. |
| Unauthorized order capture | Pass | Protected route verifies JWT, payment ownership, matching approved approval, and live PayPal `APPROVED` state. |
| Duplicate capture | Mitigated | Stored `PayPal-Request-Id`, terminal-state return, per-order async lock, unique database order/capture IDs. A multi-instance production deployment should add a DB row/advisory lock. |
| Approval validation | Pass | An order cannot be created or captured unless the matching approval is `approved`. |
| Invalid product ID | Pass | Selection is constrained to IDs in the server-owned recommendation results and controlled catalog. |
| Prompt injection | Mitigated | Gemini receives bounded intent context and returns schema-validated extraction only; it has no catalog write, approval, or payment tool. Treat user text as untrusted. |
| Malformed Gemini output | Pass | `model_validate_json` / Pydantic validation rejects invalid structured output; BaseAgent logs failure and does not continue the workflow. |
| Supabase RLS | Pass in migration | RLS covers all requested app tables. Service role stays backend-only; deployment must apply the migration. |
| API authz | Fixed | `current_user` requires a Supabase JWT and routes use its `sub`; client body identity is ignored. |
| Webhook verification | Pass | Event signature is verified with PayPal before deduplication/reconciliation. |
| Capture race condition | Mitigated | In-process lock plus provider idempotency. Add a database lock before horizontal scaling. |

## Test coverage

Executed locally:

- Agent unit tests: research/mock Gemini, finance limit violation, duplicate risk, recommendation eligibility, explicit selection, payment approval/price guard.
- API integration tests: missing bearer token rejected; client-supplied identity ignored after dependency-provided identity.
- Build checks: ESLint, TypeScript typecheck, Next production build, Python compile/test suite.

Required before release (requires separate credentials/infrastructure):

- **PayPal Sandbox:** buyer approval, cancellation, denial/failure, pending capture, duplicate capture from concurrent clients, timeout/retry, and verified real webhook event.
- **Database:** run migration in a disposable Supabase project; test RLS as two distinct JWT users and audit trigger immutability.
- **Frontend:** add Vitest/React Testing Library tests for API loading/error/retry/approval states and Playwright end-to-end tests against a dedicated backend/Sandbox environment.

## Release blockers

1. Configure Supabase Auth JWT issuer/audience and wire the frontend Supabase session token to the API client; protected routes intentionally return `401` without it.
2. Apply the Supabase migration and replace in-memory workflow reads with durable repository queries before multi-instance deployment.
3. Run the real Sandbox and webhook tests above; do not treat mocked HTTP responses as payment confirmation.
4. Implement a database-level capture lock for multi-instance Render deployment.
