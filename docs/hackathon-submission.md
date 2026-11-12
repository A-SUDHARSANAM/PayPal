# Hackathon submission materials

## Concise project description

AgentPay is a human-approved multi-agent purchase workflow for safer AI-assisted commerce. It turns a natural-language request into controlled demo-catalog research, deterministic budget and risk checks, an explainable recommendation, and—only after explicit user approval—a PayPal Sandbox checkout order. AI recommends; users and verified payment state remain in control.

## Technical architecture for judges

The Next.js frontend authenticates with Supabase and calls a FastAPI backend with the user’s bearer token. FastAPI coordinates five narrow agents and validates all structured output with Pydantic. Gemini is limited to structured intent/reasoning; server code remains authoritative for catalog IDs, prices, budgets, policy, approval state, and payment actions. Supabase stores workflow records, RLS-protected user data, transactions, and immutable audit events. The Payment Agent uses PayPal Orders v2 Sandbox: it creates an order from the server quote, checks the PayPal order before capture, applies idempotency/locking, and reconciles only verified webhooks.

## Differentiating features

- Human approval binds a specific product, amount, and currency before checkout.
- AI has no direct spending tool or payment-authority path.
- Finance and risk agents are deterministic policy gates, not prompt-only advice.
- Product research is constrained to an honest, controlled demo catalog.
- Payment completion is verified from PayPal state or a verified webhook; browser redirects never count as success.
- Every material decision has an audit trail designed for review.

## 2 minute 45 second video script

**0:00–0:15 — Hook**

“AI can already help us decide what to buy. The harder question is: how can it help without quietly taking control of our money? AgentPay is our answer: a multi-agent purchase workflow where AI recommends, but people approve.”

**0:15–0:35 — Problem**

“Shopping requests involve research, price comparison, budget impact, fraud and duplicate checks, and finally payment. A single chat response is not an auditable or safe way to handle that sequence—especially when money is involved.”

**0:35–0:58 — Request and orchestration**

“Here I enter a natural-language request for noise-cancelling headphones under a set budget. FastAPI sends it through the Research, Finance, Risk, and Recommendation agents. The dashboard shows their backend workflow state. Our catalog is explicitly demo data for this hackathon.”

**0:58–1:22 — Explainable recommendation**

“Research returns controlled catalog matches. Finance checks the canonical price against budget and transaction limit. Risk checks duplicates, unusual amounts, and eligibility. Only products that pass those deterministic checks reach the recommendation step, where I can compare the rationale.”

**1:22–1:48 — Human approval**

“I select one eligible product. Now AgentPay presents its server-calculated price, budget result, risk score, and explanation. This is the key design choice: no agent can approve a purchase. I must explicitly approve this exact quote, or reject it. Rejecting creates no PayPal order.”

**1:48–2:14 — PayPal Sandbox**

“After approval, the backend—not the browser—creates a PayPal Sandbox Orders v2 order. PayPal handles buyer approval. Back in AgentPay, capture is permitted only after the backend re-checks the order, product reference, amount, currency, and PayPal’s `APPROVED` state.”

**2:14–2:33 — Trust and security**

“We use minor-unit amounts, Supabase JWTs and RLS, server-only credentials, structured Gemini output validation, idempotency, capture locking, and verified PayPal webhooks. A browser redirect is never treated as a successful payment.”

**2:33–2:45 — Close**

“AgentPay makes AI commerce useful without giving up human control: explainable agents, deterministic guardrails, and PayPal-powered checkout. That’s what responsible agentic commerce looks like.”

## Recording notes

- Replace only the Sandbox workflow portion with a real, verified capture if it is available.
- If a live Sandbox capture is not verified, say so in the video and demonstrate order creation/cancellation instead.
- Blur test emails, access tokens, IDs, and all credentials.
