create table if not exists public.interaction_events (
  id uuid primary key default gen_random_uuid(),
  request_id text not null,
  question text not null,
  category_key text,
  depth text,
  retrieval_limit integer,
  use_llm boolean,
  elapsed_ms integer,
  answer_length integer,
  source_count integer,
  source_titles jsonb not null default '[]'::jsonb,
  source_categories jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default timezone('utc', now())
);

create index if not exists interaction_events_created_at_idx
  on public.interaction_events (created_at desc);

create index if not exists interaction_events_request_id_idx
  on public.interaction_events (request_id);

create index if not exists interaction_events_category_depth_idx
  on public.interaction_events (category_key, depth);

alter table public.interaction_events enable row level security;

create table if not exists public.feedback_events (
  id uuid primary key default gen_random_uuid(),
  request_id text not null,
  feedback text not null check (feedback in ('up', 'down')),
  answer_preview text,
  created_at timestamptz not null default timezone('utc', now())
);

create index if not exists feedback_events_created_at_idx
  on public.feedback_events (created_at desc);

create index if not exists feedback_events_request_id_idx
  on public.feedback_events (request_id);

alter table public.feedback_events enable row level security;

create table if not exists public.client_due_diligence (
  id uuid primary key default gen_random_uuid(),
  client_name text,
  industry text,
  risk_level text,
  score integer,
  status text,
  evidence jsonb not null default '{}'::jsonb,
  gaps jsonb not null default '[]'::jsonb,
  next_actions jsonb not null default '[]'::jsonb,
  notes text,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create index if not exists client_due_diligence_created_at_idx
  on public.client_due_diligence (created_at desc);

create index if not exists client_due_diligence_risk_status_idx
  on public.client_due_diligence (risk_level, status);

alter table public.client_due_diligence enable row level security;

do $$
begin
  if not exists (
    select 1 from pg_policies
    where schemaname = 'public'
      and tablename = 'interaction_events'
      and policyname = 'anon can insert interaction events'
  ) then
    create policy "anon can insert interaction events"
      on public.interaction_events
      for insert
      to anon
      with check (true);
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public'
      and tablename = 'feedback_events'
      and policyname = 'anon can insert feedback events'
  ) then
    create policy "anon can insert feedback events"
      on public.feedback_events
      for insert
      to anon
      with check (true);
  end if;
end $$;

create or replace function public.northstar_admin_analytics(p_limit integer default 20)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  result jsonb;
  safe_limit integer := greatest(1, least(coalesce(p_limit, 20), 50));
begin
  select jsonb_build_object(
    'totals', jsonb_build_object(
      'questions', (select count(*) from public.interaction_events),
      'feedback_up', (select count(*) from public.feedback_events where feedback = 'up'),
      'feedback_down', (select count(*) from public.feedback_events where feedback = 'down'),
      'avg_elapsed_ms', (select coalesce(round(avg(elapsed_ms))::int, 0) from public.interaction_events where elapsed_ms is not null),
      'avg_source_count', (select coalesce(round(avg(source_count), 1), 0) from public.interaction_events where source_count is not null)
    ),
    'by_category', coalesce((
      select jsonb_agg(row_to_json(t) order by t.count desc)
      from (
        select coalesce(category_key, 'unknown') as category_key, count(*)::int as count
        from public.interaction_events
        group by coalesce(category_key, 'unknown')
        order by count desc
        limit 12
      ) t
    ), '[]'::jsonb),
    'by_depth', coalesce((
      select jsonb_agg(row_to_json(t) order by t.count desc)
      from (
        select coalesce(depth, 'unknown') as depth, count(*)::int as count
        from public.interaction_events
        group by coalesce(depth, 'unknown')
        order by count desc
        limit 8
      ) t
    ), '[]'::jsonb),
    'recent_questions', coalesce((
      select jsonb_agg(row_to_json(t) order by t.created_at desc)
      from (
        select request_id, left(question, 260) as question, category_key, depth, retrieval_limit, source_count, elapsed_ms, created_at
        from public.interaction_events
        order by created_at desc
        limit safe_limit
      ) t
    ), '[]'::jsonb),
    'low_source_questions', coalesce((
      select jsonb_agg(row_to_json(t) order by t.created_at desc)
      from (
        select request_id, left(question, 260) as question, category_key, source_count, created_at
        from public.interaction_events
        where coalesce(source_count, 0) <= 1
        order by created_at desc
        limit 20
      ) t
    ), '[]'::jsonb),
    'negative_feedback', coalesce((
      select jsonb_agg(row_to_json(t) order by t.created_at desc)
      from (
        select request_id, answer_preview, created_at
        from public.feedback_events
        where feedback = 'down'
        order by created_at desc
        limit 20
      ) t
    ), '[]'::jsonb),
    'generated_at', timezone('utc', now())
  ) into result;

  return result;
end;
$$;

grant execute on function public.northstar_admin_analytics(integer) to anon;
