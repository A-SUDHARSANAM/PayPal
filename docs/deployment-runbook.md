# AgentPay deployment runbook

Status: **prepared; no deployment, external URL, webhook ID, or Sandbox transaction has been verified from this workspace.** Use placeholders below only as formats, never as real values.

## 0. Preflight

Run locally:

```text
npm ci
npm run lint
npm run typecheck
npm run build
python -m pytest backend/tests -q -p no:cacheprovider
```

Rotate any credential that has been shared outside a secret manager. Keep PayPal/Gemini/database/Supabase service-role secrets out of Vercel, source control, browser DevTools, and logs.

## 1. Supabase

The migration at [001_initial_schema.sql](../backend/supabase/migrations/001_initial_schema.sql) creates UUID keys, foreign keys, status constraints, indexes, timestamp triggers, RLS, immutable `audit_logs`, and payment/webhook records. [seed.sql](../backend/supabase/seed.sql) adds only demo products.

1. Supabase Dashboard → **SQL Editor** → **New query** → run the migration, then the seed file.
2. Dashboard → **Table Editor**: confirm `users`, `user_budgets`, `products`, `purchase_requests`, `agent_executions`, `recommendations`, `payment_approvals`, `transactions`, and `audit_logs` exist.
3. Dashboard → **Authentication** → **Providers**: enable the selected sign-in provider and create two test users.
4. Sign into each through the application. Confirm each sees only its own request/approval/transaction records; demo products remain readable. Attempt audit-log update/delete and confirm the immutable trigger rejects it.

Set these in Render → service → **Environment**:

| Name | Required value format | Secret |
| --- | --- | --- |
| `SUPABASE_URL` | `https://<project-ref>.supabase.co` | No |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase backend service-role key | Yes |
| `SUPABASE_JWT_ISSUER` | `https://<project-ref>.supabase.co/auth/v1` | No |
| `SUPABASE_JWT_AUDIENCE` | `authenticated` | No |

## 2. Render backend

The committed [render.yaml](../render.yaml) uses root directory `backend`, `pip install -r requirements.txt`, `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, and `/healthz`.

1. Render Dashboard → **New +** → **Blueprint** → choose this repository; alternatively create a Web Service and use those same root/build/start values.
2. Render → service → **Environment** → add:

| Name | Required value format | Secret |
| --- | --- | --- |
| `GEMINI_API_KEY` | Google AI API key | Yes |
| `GEMINI_MODEL` | approved Gemini model name, e.g. `gemini-2.0-flash` | No |
| `PAYPAL_CLIENT_ID` / `PAYPAL_CLIENT_SECRET` | PayPal Sandbox REST app credentials | Yes |
| `PAYPAL_BASE_URL` | exactly `https://api-m.sandbox.paypal.com` | No |
| `PAYPAL_WEBHOOK_ID` | Sandbox REST-app webhook ID | Yes |
| `PAYPAL_RETURN_URL` | `https://<vercel-domain>/checkout/return` | No |
| `PAYPAL_CANCEL_URL` | `https://<vercel-domain>/checkout/cancel` | No |
| `ALLOWED_ORIGINS` | exact HTTPS Vercel origin(s), comma-separated; never `*` | No |
| `REQUEST_TIMEOUT_SECONDS` | positive number, e.g. `15` | No |
| `RATE_LIMIT_PER_MINUTE` | positive integer, e.g. `30` | No |

3. Deploy. Render → **Logs** must show a clean Uvicorn startup.
4. Visit `https://<render-service>/healthz`: expect `200` / `{"status":"ok"}`.
5. Visit `/readyz`: expect `200` / `{"status":"ready"}` only after all backend configuration is present. `503` is expected if configuration is missing and must not reveal secrets.
6. Check JSON logs include request ID/method/path/status/duration, but no Authorization header, bearer token, or secrets.

## 3. Vercel frontend

[vercel.json](../vercel.json) builds Next.js using `npm ci` and `npm run build`. The browser client now obtains the Supabase session access token and sends `Authorization: Bearer <token>` on API requests.

1. Vercel Dashboard → **Add New** → **Project** → import this repository. Keep root directory as repository root.
2. Project → **Settings** → **Environment Variables** → add for Production (and Preview if testing):

| Name | Required value format |
| --- | --- |
| `NEXT_PUBLIC_AGENTPAY_API_URL` | `https://<render-service>` with no trailing slash |
| `NEXT_PUBLIC_SUPABASE_URL` | `https://<project-ref>.supabase.co` |
| `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | Supabase publishable/anon browser key |

3. Do not add any backend secret to Vercel.
4. Deploy a preview. Sign in and use DevTools → **Network** to confirm a purchase request targets the Render HTTPS URL with a bearer token. Do not copy or expose the token.
5. Test at 360px, 768px, and desktop; DevTools → **Console** must have no uncaught errors. Promote/deploy production only after Phase 5 passes.

## 4. PayPal Sandbox

1. PayPal Developer Dashboard → **Apps & Credentials** → **Sandbox** → select the REST app.
2. Add webhook URL `https://<render-service>/api/payments/webhook`; place its generated ID only in Render as `PAYPAL_WEBHOOK_ID`.
3. Subscribe to `CHECKOUT.ORDER.APPROVED`, `PAYMENT.CAPTURE.COMPLETED`, `PAYMENT.CAPTURE.PENDING`, `PAYMENT.CAPTURE.DENIED`, and `PAYMENT.CAPTURE.DECLINED`.
4. Developer Dashboard → **Testing Tools** → **Sandbox Accounts**: use a Business seller and Personal buyer.

The backend verifies webhook signatures, deduplicates events, validates the canonical approval/reference/product/amount/currency, requires PayPal order state `APPROVED`, and uses idempotency plus a capture lock. A return redirect alone is not a payment success.

## 5. Verification checklist

- [ ] Authenticated request succeeds; missing/different user token gets `401`/`403`.
- [ ] Agent orchestration and product recommendations are persisted.
- [ ] Budget violation blocks approval/order.
- [ ] User rejection produces no PayPal order.
- [ ] Approved request produces exactly one Sandbox order with canonical amount/currency.
- [ ] Personal Sandbox buyer approval followed by backend capture reports verified completion.
- [ ] Checkout cancellation, declined/failed/pending payment are never marked captured.
- [ ] Repeated capture returns existing state; no second capture ID/charge.
- [ ] Verified webhook is processed once and updates transaction/audit persistence.
- [ ] RLS isolation, browser responsiveness/console, and Render logs are clean.

Record actual service URLs, webhook IDs, order IDs, and capture IDs only in your secure deployment record—not in source control or this runbook.
