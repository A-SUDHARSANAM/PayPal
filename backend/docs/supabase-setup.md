# Supabase database setup

## Security first

Keep `SUPABASE_SERVICE_ROLE_KEY` only in the Render/FastAPI environment. It bypasses Row Level Security and must never be placed in a frontend `.env`, committed to source control, or returned from an API. The frontend may use only the Supabase project URL and publishable/anon key through `NEXT_PUBLIC_*` configuration.

If any service-role key or database password has been shared outside a secure secret manager, rotate it in the Supabase dashboard before deployment.

## Apply schema and demo data

1. Create or select the Supabase project.
2. In **SQL Editor**, run [001_initial_schema.sql](../supabase/migrations/001_initial_schema.sql).
3. Run [seed.sql](../supabase/seed.sql) to create the clearly labeled demo catalog.
4. Configure Supabase Auth. The `on_auth_user_created` trigger creates a matching `public.users` profile.
5. Add `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` only to the backend environment. Use the backend [`.env.example`](../.env.example) as the variable-name reference.
6. Configure the frontend separately with the project URL and publishable key; never use the service-role key or database password there.

## RLS model

All required application tables have RLS enabled. Authenticated users can access only their own budgets, purchase requests, approvals, and transactions. Product data is readable because it is public demo catalog data. Agent execution/recommendation visibility is derived from ownership of the source request. Writes made by FastAPI use the server-only service role after it has authenticated and authorized the caller.

`audit_logs` is append-only: a database trigger rejects updates and deletes. Payment actions should insert an audit record for approval decisions, PayPal order creation, capture requests, capture outcome, and verified webhook reconciliation.

## FastAPI repository layer

`SupabaseRepository` uses the Supabase REST endpoint with the service-role key and persists purchase requests, agent executions (including duration), payment approvals, transactions, and webhook deduplication. It activates only when both Supabase environment variables are configured; `MemoryRepository` remains available for local unit tests.

Before enabling a multi-instance deployment, replace in-memory workflow reads with the corresponding durable query methods and use an authenticated Supabase JWT dependency to derive `user_id` rather than accepting it from a request body.
