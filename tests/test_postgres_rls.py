"""OPTIONAL integration test for sql/postgres_rls_demo.sql.

This is the one part of the project that genuinely cannot be verified
offline: real Postgres row-level security requires a real Postgres
server. Per the project's offline-verifiability requirement, this test
is skipped by default and only runs if you explicitly point it at a
reachable Postgres via RMC_TEST_PG_DSN, e.g.:

    createdb rmc_rls_test
    dbt build --target postgres --profiles-dir dbt/retail_margin_cockpit \\
        --project-dir dbt/retail_margin_cockpit
    RMC_TEST_PG_DSN="dbname=rmc_rls_test" python -m pytest tests/test_postgres_rls.py

`python -m pytest` with no extra configuration (the command CI and this
repo's main verification path both use) skips this file entirely and
exits non-error.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

PG_DSN = os.environ.get("RMC_TEST_PG_DSN")

pytestmark = pytest.mark.skipif(
    not PG_DSN,
    reason=(
        "RMC_TEST_PG_DSN not set -- Postgres RLS is an optional integration "
        "test that requires a real, already-seeded Postgres instance. See "
        "this file's module docstring."
    ),
)

ROOT = Path(__file__).resolve().parents[1]
RLS_SQL_PATH = ROOT / "sql" / "postgres_rls_demo.sql"


def _connect(dsn: str):
    psycopg = pytest.importorskip("psycopg2", reason="psycopg2 not installed; RLS integration test skipped")
    return psycopg.connect(dsn)


def test_rls_scopes_regional_manager_to_one_region():
    conn = _connect(PG_DSN)
    try:
        with conn.cursor() as cur:
            cur.execute(RLS_SQL_PATH.read_text())
        conn.commit()

        ne_dsn = PG_DSN + " user=regional_manager_northeast password=demo_only_change_me"
        ne_conn = _connect(ne_dsn)
        try:
            with ne_conn.cursor() as cur:
                cur.execute("select distinct region from marts.dim_channel")
                regions = {row[0] for row in cur.fetchall()}
            assert regions == {"Northeast"}
        finally:
            ne_conn.close()

        hq_dsn = PG_DSN + " user=hq_analyst password=demo_only_change_me"
        hq_conn = _connect(hq_dsn)
        try:
            with hq_conn.cursor() as cur:
                cur.execute("select distinct region from marts.dim_channel")
                regions = {row[0] for row in cur.fetchall()}
            assert regions >= {"Northeast", "Midwest", "West", "National"}
        finally:
            hq_conn.close()
    finally:
        conn.close()
