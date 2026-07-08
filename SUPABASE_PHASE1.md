# Supabase Phase 1

Supabase is optional in this version. The RAG answer path still uses the local SQLite knowledge base. Supabase is the product data layer for real usage signals.

## Tables

- `interaction_events`: each `/api/ask` request, question, category, depth, latency, and source summary.
- `feedback_events`: thumbs-up / thumbs-down feedback for answers.
- `client_due_diligence`: high-risk client intake, score, risk level, evidence, gaps, and next actions.

## Schema

Apply:

```text
supabase_phase1_schema.sql
```

The production Supabase migration name is:

```text
northstar_phase1_events_feedback_due_diligence
```

## Render Environment

```text
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<server-only service role key>
SUPABASE_EVENT_TIMEOUT_SECONDS=2.5
```

Keep `SUPABASE_SERVICE_ROLE_KEY` server-side only. If these variables are not configured, the app keeps working and writes only the local JSONL event log.
