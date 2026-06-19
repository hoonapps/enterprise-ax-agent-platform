create extension if not exists "uuid-ossp";

create table tenants (
  id uuid primary key default uuid_generate_v4(),
  slug text not null unique,
  name text not null,
  created_at timestamptz not null default now()
);

create table users (
  id uuid primary key default uuid_generate_v4(),
  tenant_id uuid not null references tenants(id),
  external_ref text not null,
  display_name text not null,
  role text not null default 'member',
  created_at timestamptz not null default now(),
  unique (tenant_id, external_ref)
);

create table documents (
  id uuid primary key default uuid_generate_v4(),
  tenant_id uuid not null references tenants(id),
  source_type text not null,
  source_uri text not null,
  title text not null,
  content_hash text not null,
  classification text not null default 'internal',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create unique index ux_documents_tenant_hash
  on documents (tenant_id, content_hash);

create index ix_documents_tenant_source
  on documents (tenant_id, source_type);

create index ix_documents_metadata_gin
  on documents using gin (metadata);

create table document_chunks (
  id uuid primary key default uuid_generate_v4(),
  tenant_id uuid not null references tenants(id),
  document_id uuid not null references documents(id) on delete cascade,
  chunk_index int not null,
  content text not null,
  token_count int not null default 0,
  metadata jsonb not null default '{}'::jsonb,
  embedding_ref text not null,
  created_at timestamptz not null default now(),
  unique (tenant_id, document_id, chunk_index)
);

create index ix_document_chunks_embedding
  on document_chunks (tenant_id, embedding_ref);

create table ontology_nodes (
  tenant_id uuid not null references tenants(id),
  node_key text not null,
  label text not null,
  node_type text not null,
  source_document_id uuid references documents(id) on delete set null,
  evidence_count int not null default 1,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (tenant_id, node_key)
);

create index ix_ontology_nodes_type
  on ontology_nodes (tenant_id, node_type, evidence_count desc);

create table ontology_edges (
  tenant_id uuid not null references tenants(id),
  source_key text not null,
  target_key text not null,
  relation text not null,
  evidence_count int not null default 1,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (tenant_id, source_key, target_key, relation)
);

create index ix_ontology_edges_relation
  on ontology_edges (tenant_id, relation, evidence_count desc);

create table agent_runs (
  id uuid primary key default uuid_generate_v4(),
  tenant_id uuid not null references tenants(id),
  user_id uuid references users(id),
  scenario text not null,
  query text not null,
  redacted_query text not null,
  query_type text not null,
  status text not null,
  confidence numeric(4, 3) not null default 0,
  latency_ms int,
  created_at timestamptz not null default now(),
  completed_at timestamptz
);

create index ix_agent_runs_tenant_created
  on agent_runs (tenant_id, created_at desc);

create index ix_agent_runs_tenant_scenario_created
  on agent_runs (tenant_id, scenario, created_at desc);

create index ix_agent_runs_tenant_status
  on agent_runs (tenant_id, status);

create table retrieval_events (
  id uuid primary key default uuid_generate_v4(),
  tenant_id uuid not null references tenants(id),
  agent_run_id uuid not null references agent_runs(id) on delete cascade,
  strategy text not null,
  query text not null,
  top_k int not null,
  selected_chunk_ids uuid[] not null default '{}',
  scores jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table tool_calls (
  id uuid primary key default uuid_generate_v4(),
  tenant_id uuid not null references tenants(id),
  agent_run_id uuid not null references agent_runs(id) on delete cascade,
  tool_name text not null,
  action_type text not null,
  input_payload jsonb not null default '{}'::jsonb,
  output_payload jsonb not null default '{}'::jsonb,
  policy_decision text not null,
  status text not null,
  latency_ms int,
  created_at timestamptz not null default now()
);

create index ix_tool_calls_run
  on tool_calls (tenant_id, agent_run_id);

create index ix_tool_calls_tool_created
  on tool_calls (tenant_id, tool_name, created_at desc);

create index ix_tool_calls_policy
  on tool_calls (tenant_id, policy_decision);

create table approval_requests (
  id uuid primary key default uuid_generate_v4(),
  tenant_id uuid not null references tenants(id),
  agent_run_id uuid not null references agent_runs(id) on delete cascade,
  tool_execution_id uuid not null,
  tool_name text not null,
  action_type text not null,
  input_payload jsonb not null default '{}'::jsonb,
  reason text not null,
  status text not null,
  requested_by text,
  approved_by text,
  replay_result jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index ix_approval_requests_pending
  on approval_requests (tenant_id, status, created_at desc);

create index ix_approval_requests_agent_run
  on approval_requests (tenant_id, agent_run_id);

create table agent_messages (
  id uuid primary key default uuid_generate_v4(),
  tenant_id uuid not null references tenants(id),
  agent_run_id uuid not null references agent_runs(id) on delete cascade,
  role text not null,
  content text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table evaluation_runs (
  id uuid primary key default uuid_generate_v4(),
  tenant_id uuid not null references tenants(id),
  name text not null,
  scenario text not null,
  status text not null,
  metrics jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  completed_at timestamptz
);

create table evaluation_cases (
  id uuid primary key default uuid_generate_v4(),
  tenant_id uuid not null references tenants(id),
  evaluation_run_id uuid not null references evaluation_runs(id) on delete cascade,
  input_query text not null,
  expected_facts jsonb not null default '[]'::jsonb,
  actual_answer text,
  score numeric(4, 3),
  failure_reason text,
  created_at timestamptz not null default now()
);

create table audit_events (
  id uuid primary key default uuid_generate_v4(),
  tenant_id uuid not null references tenants(id),
  actor_type text not null,
  actor_id text not null,
  event_type text not null,
  resource_type text not null,
  resource_id uuid,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index ix_audit_events_created
  on audit_events (tenant_id, created_at desc);

create index ix_audit_events_type_created
  on audit_events (tenant_id, event_type, created_at desc);

create index ix_audit_events_resource
  on audit_events (tenant_id, resource_type, resource_id);

create table webhook_subscriptions (
  id uuid primary key default uuid_generate_v4(),
  tenant_id uuid not null references tenants(id),
  name text not null,
  target_url text not null,
  event_types text[] not null default '{}',
  secret text,
  enabled boolean not null default true,
  created_at timestamptz not null default now()
);

create index ix_webhook_subscriptions_tenant_enabled
  on webhook_subscriptions (tenant_id, enabled);

create table webhook_deliveries (
  id uuid primary key default uuid_generate_v4(),
  tenant_id uuid not null references tenants(id),
  subscription_id uuid not null references webhook_subscriptions(id) on delete cascade,
  event_id uuid not null references audit_events(id) on delete cascade,
  event_type text not null,
  target_url text not null,
  payload jsonb not null default '{}'::jsonb,
  status text not null,
  attempt_count int not null default 0,
  next_attempt_at timestamptz,
  last_error text,
  created_at timestamptz not null default now(),
  delivered_at timestamptz
);

create index ix_webhook_deliveries_status
  on webhook_deliveries (tenant_id, status, created_at desc);

create index ix_webhook_deliveries_subscription
  on webhook_deliveries (tenant_id, subscription_id, created_at desc);

create table idempotency_keys (
  tenant_id uuid not null references tenants(id),
  key text not null,
  request_hash text not null,
  response_payload jsonb,
  created_at timestamptz not null default now(),
  primary key (tenant_id, key)
);
