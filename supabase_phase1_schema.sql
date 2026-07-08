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
