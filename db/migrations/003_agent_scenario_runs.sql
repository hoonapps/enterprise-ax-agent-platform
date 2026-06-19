create table agent_scenario_runs (
  id uuid primary key default uuid_generate_v4(),
  tenant_id uuid not null references tenants(id),
  scenario_id text not null,
  name text not null,
  status text not null,
  metrics jsonb not null default '{}'::jsonb,
  step_results jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now()
);

create index ix_agent_scenario_runs_tenant_created
  on agent_scenario_runs (tenant_id, created_at desc);

create index ix_agent_scenario_runs_tenant_scenario_created
  on agent_scenario_runs (tenant_id, scenario_id, created_at desc);

create index ix_agent_scenario_runs_tenant_status
  on agent_scenario_runs (tenant_id, status, created_at desc);

alter table agent_scenario_runs enable row level security;
alter table agent_scenario_runs force row level security;

create policy tenant_isolation on agent_scenario_runs
  for all
  using (tenant_id = app_current_tenant_id())
  with check (tenant_id = app_current_tenant_id());

do $$
begin
  if exists (select 1 from pg_roles where rolname = 'ax_agent_app') then
    grant select, insert, update, delete on agent_scenario_runs to ax_agent_app;
  end if;
end;
$$;
