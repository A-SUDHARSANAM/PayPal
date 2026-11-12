-- AgentPay Supabase PostgreSQL schema. Apply with the Supabase CLI or SQL Editor.
create extension if not exists pgcrypto;

create table public.users (
  id uuid primary key references auth.users(id) on delete cascade,
  display_name text,
  default_currency char(3) not null default 'USD' check (default_currency ~ '^[A-Z]{3}$'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.user_budgets (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null unique references public.users(id) on delete cascade,
  monthly_budget_minor bigint not null check (monthly_budget_minor >= 0),
  max_transaction_minor bigint not null check (max_transaction_minor >= 0),
  currency char(3) not null default 'USD' check (currency ~ '^[A-Z]{3}$'),
  created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);

create table public.products (
  id uuid primary key default gen_random_uuid(),
  sku text not null unique,
  name text not null,
  category text not null,
  merchant text not null,
  price_minor bigint not null check (price_minor >= 0),
  currency char(3) not null check (currency ~ '^[A-Z]{3}$'),
  features jsonb not null default '[]'::jsonb,
  recurring_cost_minor bigint not null default 0 check (recurring_cost_minor >= 0),
  is_eligible boolean not null default true,
  is_demo boolean not null default true check (is_demo),
  created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);

create table public.purchase_requests (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  request_text text not null check (char_length(request_text) between 3 and 1000),
  budget_minor bigint not null check (budget_minor >= 0),
  max_transaction_minor bigint not null check (max_transaction_minor >= 0),
  currency char(3) not null check (currency ~ '^[A-Z]{3}$'),
  selected_product_id uuid references public.products(id),
  status text not null default 'submitted' check (status in ('draft','submitted','researching','validating','recommended','blocked','awaiting_approval','approved','cancelled','expired')),
  risk_score smallint check (risk_score between 0 and 100),
  created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);

create table public.agent_executions (
  id uuid primary key default gen_random_uuid(),
  purchase_request_id uuid not null references public.purchase_requests(id) on delete cascade,
  agent_name text not null check (agent_name in ('research','finance','risk','recommendation','payment','orchestrator')),
  status text not null check (status in ('running','completed','failed','blocked','timed_out')),
  input_digest text,
  output jsonb not null default '{}'::jsonb,
  error_code text,
  error_message text,
  duration_ms integer check (duration_ms >= 0),
  started_at timestamptz not null default now(), completed_at timestamptz
);

create table public.recommendations (
  id uuid primary key default gen_random_uuid(),
  purchase_request_id uuid not null unique references public.purchase_requests(id) on delete cascade,
  product_id uuid references public.products(id),
  ranked_products jsonb not null default '[]'::jsonb,
  score smallint check (score between 0 and 100),
  explanation text not null,
  status text not null check (status in ('eligible','blocked','superseded')),
  created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);

create table public.payment_approvals (
  id uuid primary key default gen_random_uuid(),
  purchase_request_id uuid not null references public.purchase_requests(id) on delete cascade,
  user_id uuid not null references public.users(id) on delete cascade,
  product_id uuid not null references public.products(id),
  amount_minor bigint not null check (amount_minor >= 0),
  currency char(3) not null check (currency ~ '^[A-Z]{3}$'),
  status text not null default 'pending' check (status in ('pending','approved','rejected','expired','cancelled')),
  decision_at timestamptz,
  approval_token_hash text,
  created_at timestamptz not null default now(),
  constraint payment_approval_decision check ((status in ('approved','rejected') and decision_at is not null) or (status not in ('approved','rejected')))
);

create table public.transactions (
  id uuid primary key default gen_random_uuid(),
  approval_id uuid not null unique references public.payment_approvals(id),
  user_id uuid not null references public.users(id),
  product_id uuid not null references public.products(id),
  amount_minor bigint not null check (amount_minor >= 0),
  currency char(3) not null check (currency ~ '^[A-Z]{3}$'),
  paypal_order_id text unique,
  paypal_capture_id text unique,
  idempotency_key uuid not null unique,
  status text not null check (status in ('created','approved','capture_pending','captured','cancelled','declined','failed','pending')),
  created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);

create table public.audit_logs (
  id uuid primary key default gen_random_uuid(),
  actor_user_id uuid references public.users(id),
  entity_type text not null,
  entity_id uuid not null,
  action text not null,
  before_state jsonb,
  after_state jsonb,
  request_id uuid,
  created_at timestamptz not null default now()
);

create table public.paypal_webhook_events (
  paypal_event_id text primary key,
  event_type text not null,
  paypal_order_id text,
  payload jsonb not null,
  verified_at timestamptz not null default now(), processed_at timestamptz
);

create index purchase_requests_user_created_idx on public.purchase_requests(user_id, created_at desc);
create index purchase_requests_status_idx on public.purchase_requests(status);
create index agent_executions_request_idx on public.agent_executions(purchase_request_id, started_at desc);
create index payment_approvals_user_status_idx on public.payment_approvals(user_id, status, created_at desc);
create index transactions_user_created_idx on public.transactions(user_id, created_at desc);
create index transactions_paypal_order_idx on public.transactions(paypal_order_id) where paypal_order_id is not null;
create index audit_logs_entity_idx on public.audit_logs(entity_type, entity_id, created_at desc);

create or replace function public.set_updated_at() returns trigger language plpgsql security invoker as $$ begin new.updated_at = now(); return new; end; $$;
create trigger users_updated_at before update on public.users for each row execute function public.set_updated_at();
create trigger budgets_updated_at before update on public.user_budgets for each row execute function public.set_updated_at();
create trigger products_updated_at before update on public.products for each row execute function public.set_updated_at();
create trigger requests_updated_at before update on public.purchase_requests for each row execute function public.set_updated_at();
create trigger recommendations_updated_at before update on public.recommendations for each row execute function public.set_updated_at();
create trigger transactions_updated_at before update on public.transactions for each row execute function public.set_updated_at();

-- Creates the app profile only from an authenticated Supabase Auth signup.
create or replace function public.handle_new_auth_user() returns trigger language plpgsql security definer set search_path = public as $$
begin insert into public.users (id, display_name) values (new.id, coalesce(new.raw_user_meta_data->>'display_name', new.email)) on conflict (id) do nothing; return new; end; $$;
create trigger on_auth_user_created after insert on auth.users for each row execute procedure public.handle_new_auth_user();

-- Payment audit history is append-only, even for privileged application code.
create or replace function public.prevent_audit_mutation() returns trigger language plpgsql as $$ begin raise exception 'audit_logs is immutable'; end; $$;
create trigger audit_immutable before update or delete on public.audit_logs for each row execute function public.prevent_audit_mutation();

alter table public.users enable row level security;
alter table public.user_budgets enable row level security;
alter table public.products enable row level security;
alter table public.purchase_requests enable row level security;
alter table public.agent_executions enable row level security;
alter table public.recommendations enable row level security;
alter table public.payment_approvals enable row level security;
alter table public.transactions enable row level security;
alter table public.audit_logs enable row level security;
alter table public.paypal_webhook_events enable row level security;

create policy "users_read_own" on public.users for select using (id = auth.uid());
create policy "users_update_own" on public.users for update using (id = auth.uid()) with check (id = auth.uid());
create policy "budgets_own" on public.user_budgets for all using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy "products_public_read" on public.products for select using (true);
create policy "requests_own" on public.purchase_requests for all using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy "executions_own_request" on public.agent_executions for select using (exists (select 1 from public.purchase_requests r where r.id = purchase_request_id and r.user_id = auth.uid()));
create policy "recommendations_own_request" on public.recommendations for select using (exists (select 1 from public.purchase_requests r where r.id = purchase_request_id and r.user_id = auth.uid()));
create policy "approvals_own" on public.payment_approvals for select using (user_id = auth.uid());
create policy "transactions_own" on public.transactions for select using (user_id = auth.uid());
create policy "audit_own_entities" on public.audit_logs for select using (actor_user_id = auth.uid());
