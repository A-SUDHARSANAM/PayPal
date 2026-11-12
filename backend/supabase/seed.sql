-- Demo-only catalog seed. Run after 001_initial_schema.sql.
insert into public.products (id, sku, name, category, merchant, price_minor, currency, features, recurring_cost_minor, is_eligible, is_demo) values
  ('00000000-0000-0000-0000-000000000101', 'demo-headphones-1', 'Sony WH-1000XM5', 'headphones', 'Audio Gallery', 34800, 'USD', '["noise cancellation","30-hour battery","multipoint"]', 0, true, true),
  ('00000000-0000-0000-0000-000000000102', 'demo-headphones-2', 'Bose QuietComfort', 'headphones', 'Audio Gallery', 29900, 'USD', '["noise cancellation","comfortable","24-hour battery"]', 0, true, true),
  ('00000000-0000-0000-0000-000000000103', 'demo-laptop-1', 'MacBook Pro 14-inch', 'laptop', 'DemoTech Store', 219900, 'USD', '["M-series chip","14-inch display","18-hour battery"]', 0, true, true),
  ('00000000-0000-0000-0000-000000000104', 'demo-chair-1', 'Ergonomic office chair', 'chair', 'Workspace Lab', 69900, 'USD', '["lumbar support","adjustable arms","mesh back"]', 0, true, true)
on conflict (sku) do update set name = excluded.name, price_minor = excluded.price_minor, features = excluded.features, updated_at = now();
