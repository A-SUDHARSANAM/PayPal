# Agent schemas

All agents receive the canonical `PurchaseRequest` (`id`, `user_id`, `text`, `budget_minor`, `currency`, `max_transaction_minor`). Amounts are integer minor units. Catalog products are server-owned records and always carry `is_demo: true` in this MVP.

| Agent | Input | Validated output | Authority |
| --- | --- | --- | --- |
| Research | Purchase request; controlled catalog | `ResearchResult`: `ProductRequirement`, catalog `products`, comparisons | Gemini may extract requirements only. The server searches catalog and provides products/prices. |
| Finance | Request; research products | `FinanceResult`: status, total, budget remaining, recurring cost, violations | Deterministically applies budgets and max transaction amount. |
| Risk | Request; research products; user request history | `RiskResult`: 0–100 score, duplicate/unusual flags, policy violations | Deterministically identifies duplicate, eligibility, and amount signals. |
| Recommendation | Request; products; finance; risk | `RecommendationResult`: ranked known product IDs, selected ID, explanation | Cannot recommend a product outside research results. Blocking finance/risk results stop it. |
| Payment | Approved `PendingApproval`; canonical product | `PayPalOrder` / `PayPalCapture` | No LLM. Refuses unapproved, mismatched product, or mismatched amount. Sandbox host enforced. |

## Gemini structured output

`GeminiClient.generate(prompt, schema)` configures `application/json` and the Pydantic model JSON Schema as `response_json_schema`. It then calls `schema.model_validate_json`; malformed or unknown fields do not cross the agent boundary. Gemini is deliberately not called for budget, risk policy, payment order validation, authorization, or capture.

## Orchestrator protocol

`research → finance + risk → recommendation → pending approval`

Finance/risk failures produce a `WorkflowResponse` with `status: blocked`; they never create an approval. Successful recommendations create `PendingApproval(status=pending)`. A separate explicit approval action is required before the deterministic Payment Agent may request a PayPal Sandbox order.
