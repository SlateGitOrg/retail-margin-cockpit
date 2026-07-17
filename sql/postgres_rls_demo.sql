-- =========================================================================
-- Postgres row-level-security demo: "Regional Manager" role
-- =========================================================================
-- Companion to the Power BI RLS role of the same name (powerbi/model.bim).
-- Where the Power BI role filters what a report shows, this demonstrates
-- the same access boundary enforced one layer down, directly in the
-- warehouse -- useful when other tools (a BI tool without RLS, an ad-hoc
-- SQL client, a reverse ETL job) read the same Postgres tables.
--
-- Requires a real Postgres instance (this repo's automated tests run
-- against DuckDB and do not exercise this file -- see
-- tests/test_postgres_rls.py, which is skipped unless RMC_TEST_PG_DSN is
-- set to a real, reachable Postgres). Apply with:
--
--   psql "$RMC_PG_DSN" -f sql/postgres_rls_demo.sql
--
-- Prerequisite: the marts schema already built by `dbt build --target postgres`.
-- =========================================================================

begin;

-- 1. A small security-mapping table, mirroring dbt's marts.dim_user_region_map.
--    (In production this is the dbt-built table; recreated here so the demo
--    is runnable standalone against a bare marts schema too.)
create table if not exists marts.rls_session_region_map (
    db_role      text primary key,
    region       text not null
);

insert into marts.rls_session_region_map (db_role, region) values
    ('regional_manager_northeast', 'Northeast'),
    ('regional_manager_midwest',   'Midwest'),
    ('regional_manager_west',      'West'),
    ('hq_analyst',                 'ALL')
on conflict (db_role) do update set region = excluded.region;

-- 2. Database roles a BI tool / analyst connects as. NOLOGIN parents plus
--    NOINHERIT login roles keep this demo self-contained; wire these to
--    your real IdP-backed roles in production instead of literal CREATE
--    ROLE statements.
do $$
begin
    if not exists (select 1 from pg_roles where rolname = 'regional_manager') then
        create role regional_manager nologin;
    end if;
    if not exists (select 1 from pg_roles where rolname = 'regional_manager_northeast') then
        create role regional_manager_northeast login password 'demo_only_change_me' in role regional_manager;
    end if;
    if not exists (select 1 from pg_roles where rolname = 'regional_manager_midwest') then
        create role regional_manager_midwest login password 'demo_only_change_me' in role regional_manager;
    end if;
    if not exists (select 1 from pg_roles where rolname = 'regional_manager_west') then
        create role regional_manager_west login password 'demo_only_change_me' in role regional_manager;
    end if;
    if not exists (select 1 from pg_roles where rolname = 'hq_analyst') then
        create role hq_analyst login password 'demo_only_change_me' in role regional_manager;
    end if;
end
$$;

grant usage on schema marts to regional_manager;
grant select on marts.dim_channel, marts.dim_product, marts.dim_date,
    marts.fact_sales, marts.fact_inventory, marts.rls_session_region_map
    to regional_manager;

-- 3. Enable RLS on the two tables that carry channel_id (and therefore
--    region) directly or via dim_channel. Postgres RLS policies apply per
--    row of the table they're attached to, so fact tables get a policy
--    that joins back to dim_channel; dim_channel gets a direct policy.

alter table marts.dim_channel enable row level security;
alter table marts.dim_channel force row level security;

drop policy if exists regional_manager_channel_scope on marts.dim_channel;
create policy regional_manager_channel_scope
    on marts.dim_channel
    for select
    to regional_manager
    using (
        region = (
            select region from marts.rls_session_region_map
            where db_role = current_user
        )
        or (
            select region from marts.rls_session_region_map
            where db_role = current_user
        ) = 'ALL'
    );

alter table marts.fact_sales enable row level security;
alter table marts.fact_sales force row level security;

drop policy if exists regional_manager_fact_sales_scope on marts.fact_sales;
create policy regional_manager_fact_sales_scope
    on marts.fact_sales
    for select
    to regional_manager
    using (
        channel_id in (
            select ch.channel_id
            from marts.dim_channel ch, marts.rls_session_region_map m
            where m.db_role = current_user
              and (ch.region = m.region or m.region = 'ALL')
        )
    );

alter table marts.fact_inventory enable row level security;
alter table marts.fact_inventory force row level security;

drop policy if exists regional_manager_fact_inventory_scope on marts.fact_inventory;
create policy regional_manager_fact_inventory_scope
    on marts.fact_inventory
    for select
    to regional_manager
    using (
        channel_id in (
            select ch.channel_id
            from marts.dim_channel ch, marts.rls_session_region_map m
            where m.db_role = current_user
              and (ch.region = m.region or m.region = 'ALL')
        )
    );

commit;

-- =========================================================================
-- Manual verification (run these as psql -U <role> after applying above):
--
--   -- as regional_manager_northeast: only Northeast channel rows visible
--   select distinct region from marts.dim_channel;                 -- Northeast
--   select count(*) from marts.fact_sales;                          -- < full count
--
--   -- as hq_analyst: everything visible
--   select distinct region from marts.dim_channel;  -- Northeast, Midwest, West, National
-- =========================================================================
