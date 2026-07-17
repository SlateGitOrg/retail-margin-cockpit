"""End-to-end test of the dbt project against the DuckDB target.

This is the closest thing to an integration test that still satisfies
"no network, no Docker, no running cluster": DuckDB is an embedded,
in-process database, so `dbt build` here only ever touches a local file.
It genuinely runs the full pipeline -- seed load, staging views, mart
tables, and all 56+ generic tests (not_null/unique/relationships/
accepted_values) -- exactly as CI does.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import duckdb
import pytest

DBT_PROJECT_DIR = Path(__file__).resolve().parents[1] / "dbt" / "retail_margin_cockpit"


def _dbt_command() -> list[str]:
    """The `dbt` console script (dbt-core has no runnable `dbt.__main__`,
    so `python -m dbt` doesn't work -- invoke the installed entry point
    script directly, resolved relative to the current interpreter so this
    works both in a venv and in CI without assuming `dbt` is on PATH).
    """
    candidate = Path(sys.executable).parent / "dbt"
    if candidate.exists():
        return [str(candidate)]
    return ["dbt"]  # fall back to PATH lookup


def _run_dbt(*args: str, duckdb_path) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["DBT_PROFILES_DIR"] = str(DBT_PROJECT_DIR)
    env["RMC_DUCKDB_PATH"] = str(duckdb_path)
    return subprocess.run(
        [*_dbt_command(), *args],
        cwd=str(DBT_PROJECT_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )


@pytest.fixture(scope="module")
def built_duckdb(tmp_path_factory):
    """Runs `dbt build` once into a throwaway duckdb file, shared by the
    tests in this module (avoids re-running the whole pipeline per test).
    """
    db_path = tmp_path_factory.mktemp("rmc_dbt") / "test_run.duckdb"
    result = _run_dbt("build", "--target", "duckdb", duckdb_path=db_path)
    assert result.returncode == 0, (
        f"dbt build failed.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    # Note: dbt's own summary line legitimately contains the substring
    # "ERROR=0" (e.g. "Done. PASS=72 WARN=0 ERROR=0 ..."), so a blanket
    # "ERROR" not in stdout check is a false positive. Look for actual
    # failure/error markers dbt emits instead.
    assert "ERROR=0" in result.stdout or "ERROR" not in result.stdout.replace(
        "ERROR=0", ""
    )
    return db_path


def test_dbt_build_succeeds(built_duckdb):
    assert built_duckdb.exists()


def test_dbt_build_reports_all_tests_passing(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("rmc_dbt_report") / "report_run.duckdb"
    result = _run_dbt("build", "--target", "duckdb", duckdb_path=db_path)
    assert result.returncode == 0
    # dbt's summary line, e.g.
    # "03:52:52  Done. PASS=72 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=72"
    # -- dbt always prefixes log lines with a wall-clock timestamp, so we
    # search for "Done." anywhere in the line rather than at the start.
    summary_lines = [ln for ln in result.stdout.splitlines() if "Done." in ln]
    assert summary_lines, f"no dbt summary line found in output:\n{result.stdout}"
    summary = summary_lines[-1].split("Done.", 1)[1]
    assert "ERROR=0" in summary
    assert "PASS=" in summary
    # sanity: make sure a meaningful number of tests actually ran, not zero.
    pass_count = int(summary.split("PASS=")[1].split()[0])
    assert pass_count >= 50


EXPECTED_TABLES = {
    "dim_channel",
    "dim_product",
    "dim_date",
    "dim_user_region_map",
    "fact_sales",
    "fact_inventory",
}


def test_star_schema_tables_exist(built_duckdb):
    con = duckdb.connect(str(built_duckdb), read_only=True)
    try:
        tables = {
            row[0]
            for row in con.execute(
                "select table_name from information_schema.tables where table_schema = 'marts'"
            ).fetchall()
        }
    finally:
        con.close()
    assert EXPECTED_TABLES <= tables


def test_fact_sales_has_positive_margin_on_average(built_duckdb):
    con = duckdb.connect(str(built_duckdb), read_only=True)
    try:
        avg_margin_pct = con.execute(
            "select avg(gross_margin_pct) from marts.fact_sales"
        ).fetchone()[0]
    finally:
        con.close()
    assert 0.2 < avg_margin_pct < 0.8


def test_fact_tables_join_cleanly_to_dims(built_duckdb):
    """A second line of defense beyond the dbt `relationships` tests:
    confirm there are zero orphaned fact rows directly via SQL.
    """
    con = duckdb.connect(str(built_duckdb), read_only=True)
    try:
        orphans_sales = con.execute(
            """
            select count(*) from marts.fact_sales fs
            left join marts.dim_product p on fs.product_id = p.product_id
            left join marts.dim_channel c on fs.channel_id = c.channel_id
            where p.product_id is null or c.channel_id is null
            """
        ).fetchone()[0]
        orphans_inventory = con.execute(
            """
            select count(*) from marts.fact_inventory fi
            left join marts.dim_product p on fi.product_id = p.product_id
            left join marts.dim_channel c on fi.channel_id = c.channel_id
            where p.product_id is null or c.channel_id is null
            """
        ).fetchone()[0]
    finally:
        con.close()
    assert orphans_sales == 0
    assert orphans_inventory == 0
