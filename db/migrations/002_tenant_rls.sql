create or replace function app_current_tenant_id()
returns uuid
language sql
stable
as $$
  select nullif(current_setting('app.tenant_id', true), '')::uuid;
$$;

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'ax_agent_app') then
    create role ax_agent_app login password 'ax_agent_app';
  end if;
end;
$$;

create or replace function enable_tenant_rls(table_name regclass)
returns void
language plpgsql
as $$
begin
  execute format('alter table %s enable row level security', table_name);
  execute format('alter table %s force row level security', table_name);
  execute format('drop policy if exists tenant_isolation on %s', table_name);
  execute format(
    'create policy tenant_isolation on %s
       for all
       using (tenant_id = app_current_tenant_id())
       with check (tenant_id = app_current_tenant_id())',
    table_name
  );
end;
$$;

select enable_tenant_rls('users');
select enable_tenant_rls('documents');
select enable_tenant_rls('document_chunks');
select enable_tenant_rls('ontology_nodes');
select enable_tenant_rls('ontology_edges');
select enable_tenant_rls('agent_runs');
select enable_tenant_rls('retrieval_events');
select enable_tenant_rls('tool_calls');
select enable_tenant_rls('approval_requests');
select enable_tenant_rls('agent_messages');
select enable_tenant_rls('evaluation_runs');
select enable_tenant_rls('evaluation_cases');
select enable_tenant_rls('audit_events');
select enable_tenant_rls('webhook_subscriptions');
select enable_tenant_rls('webhook_deliveries');
select enable_tenant_rls('idempotency_keys');

grant usage on schema public to ax_agent_app;
grant select, insert, update, delete on all tables in schema public to ax_agent_app;
grant execute on function app_current_tenant_id() to ax_agent_app;
alter default privileges in schema public
  grant select, insert, update, delete on tables to ax_agent_app;

drop function enable_tenant_rls(regclass);
