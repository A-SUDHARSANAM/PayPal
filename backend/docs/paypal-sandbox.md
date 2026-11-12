# PayPal Sandbox integration

AgentPay uses the official PayPal Orders API v2, restricted in code to `https://api-m.sandbox.paypal.com`. Credentials are server-only environment variables; do not set them in Next.js public variables or commit them to the repository.

## Environment

```dotenv
PAYPAL_CLIENT_ID=Sandbox REST app client ID
PAYPAL_CLIENT_SECRET=Sandbox REST app secret
PAYPAL_BASE_URL=https://api-m.sandbox.paypal.com
PAYPAL_WEBHOOK_ID=ID of the webhook registered for this REST app
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=server-only key
```

Apply [the payment migration](../supabase/migrations/001_payments.sql) before enabling the integration. If Supabase variables are configured, payment lifecycle data is persisted through Supabase PostgREST; development without those variables uses the in-memory repository only.

## API behavior

| AgentPay endpoint | PayPal call | Guardrail |
| --- | --- | --- |
| `POST /api/payments/create-order` | `POST /v2/checkout/orders` | Body contains only `approval_id`; canonical product, amount, and currency come from server records. A verified approved record is required. |
| `GET /api/payments/{order_id}` | `GET /v2/checkout/orders/{id}` | Rejects orders absent from AgentPay storage and checks order ID, reference ID, currency, and amount against the canonical payment record. |
| `POST /api/payments/{order_id}/capture` | `POST /v2/checkout/orders/{id}/capture` | Re-fetches the order and requires PayPal status `APPROVED` plus the matching verified approval. A persisted request ID provides idempotency. |
| `POST /api/payments/webhook` | `POST /v1/notifications/verify-webhook-signature` | Verifies PayPal headers/event before deduplicating and reconciling any state. |

`PayPal-Request-Id` is a stored UUID used for create/capture idempotency. `PaymentRecord` stores PayPal order and capture IDs uniquely. Captured orders return their existing canonical result without issuing another capture request. The order creation response exposes its `approve`/`payer-action` URL if PayPal returns one.

The webhook state mapping covers buyer approval, completed and pending captures, denied/declined captures, and cancelled/voided order state returned by the Orders API. The UI must consider a payment successful only when the server records an Orders v2 `COMPLETED` capture or a verified `PAYMENT.CAPTURE.COMPLETED` webhook.

## Sandbox accounts and credentials

1. Sign in to the [PayPal Developer Dashboard](https://developer.paypal.com/).
2. In **Apps & Credentials**, switch to **Sandbox**, create/select a REST app, and assign its business sandbox account as the merchant. Copy the app client ID and secret to the backend secret store.
3. Under **Testing Tools → Sandbox Accounts**, create a **Business** account for the seller/merchant and a **Personal** account for the buyer. PayPal normally creates default accounts; create additional Personal buyers for test cases.
4. Use the buyer email and password shown by the dashboard at `https://sandbox.paypal.com/signin` to approve checkout. Never use production PayPal accounts or credentials.
5. Configure an HTTPS webhook URL in the REST app settings and record its webhook ID as `PAYPAL_WEBHOOK_ID`. Subscribe at least to `CHECKOUT.ORDER.APPROVED`, `PAYMENT.CAPTURE.COMPLETED`, `PAYMENT.CAPTURE.PENDING`, `PAYMENT.CAPTURE.DENIED`, and `PAYMENT.CAPTURE.DECLINED`.

PayPal’s current docs: [Orders API v2](https://developer.paypal.com/docs/api/orders/v2/), [orders integration overview](https://developer.paypal.com/whats-an-order/), [webhook integration and verification](https://developer.paypal.com/api/rest/webhooks/rest/), and [Sandbox accounts](https://developer.paypal.com/sandbox-testing/accounts).

## Integration-test strategy

Keep live sandbox testing separate from unit tests and never run it in an untrusted PR environment.

1. Apply Supabase migration to a dedicated test project and configure only Sandbox credentials.
2. Create a valid AgentPay workflow and explicitly approve it through the API; verify create-order rejects pending/rejected approval, tampered amount, and mismatched product records.
3. Call create-order twice and assert the same stored PayPal order ID is returned. Confirm the purchase unit reference ID is the AgentPay approval ID and the amount/currency match storage.
4. Open the returned approval URL and sign in with the Personal Sandbox buyer; then retrieve until it reports `APPROVED`.
5. Capture once, assert `COMPLETED`, capture ID persistence, and a repeated capture returns the existing result rather than creating a second capture.
6. Use alternate buyer funding/negative scenarios where available to exercise declined, cancelled, pending, and failed behavior. Assert AgentPay never marks them captured.
7. Trigger real sandbox events to the registered webhook endpoint and assert signature verification and event-ID deduplication. Do not use the webhook simulator as proof of postback verification: PayPal documents that the postback method is unavailable for mock events.

For automated contract tests, mock HTTP only at the PayPal boundary and use recorded official response fixtures. Do not place real Sandbox credentials in source control or CI logs.
