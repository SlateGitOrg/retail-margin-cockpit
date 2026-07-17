"""Structural validation of powerbi/model.bim (the TMSL semantic model).

Checks the JSON is well-formed TMSL with the star schema's tables,
relationships, and RLS roles all present and internally consistent, and
that its measures are exactly the ones generated from measures.dax (i.e.
scripts/build_model_bim.py has been run since the last edit to either
file -- this test fails loudly if someone edits one and forgets to
regenerate the other).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_model_bim import BIM_PATH, DAX_PATH, MEASURE_TABLE, parse_measures

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def bim():
    return json.loads(BIM_PATH.read_text())


@pytest.fixture(scope="module")
def model(bim):
    return bim["model"]


@pytest.fixture(scope="module")
def tables_by_name(model):
    return {t["name"]: t for t in model["tables"]}


EXPECTED_TABLES = {
    "dim_date",
    "dim_product",
    "dim_channel",
    "dim_user_region_map",
    "fact_sales",
    "fact_inventory",
}


class TestStructure:
    def test_bim_is_valid_json_with_model_key(self, bim):
        assert "model" in bim
        assert "tables" in bim["model"]

    def test_expected_tables_present(self, tables_by_name):
        assert EXPECTED_TABLES <= set(tables_by_name)

    def test_dim_date_is_marked_as_time_table(self, tables_by_name):
        assert tables_by_name["dim_date"].get("dataCategory") == "Time"

    def test_every_table_has_a_key_column(self, tables_by_name):
        for name, table in tables_by_name.items():
            keys = [c for c in table["columns"] if c.get("isKey")]
            assert len(keys) == 1, f"table {name} should have exactly one key column"

    def test_fact_tables_have_partitions_with_m_expressions(self, tables_by_name):
        for fact in ("fact_sales", "fact_inventory"):
            partitions = tables_by_name[fact]["partitions"]
            assert partitions
            expr = partitions[0]["source"]["expression"]
            assert isinstance(expr, list) and len(expr) > 0


class TestRelationships:
    def test_six_relationships_present(self, model):
        assert len(model["relationships"]) == 6

    def test_each_fact_relates_to_each_dim_it_should(self, model):
        pairs = {(r["fromTable"], r["toTable"]) for r in model["relationships"]}
        expected = {
            ("fact_sales", "dim_product"),
            ("fact_sales", "dim_channel"),
            ("fact_sales", "dim_date"),
            ("fact_inventory", "dim_product"),
            ("fact_inventory", "dim_channel"),
            ("fact_inventory", "dim_date"),
        }
        assert pairs == expected

    def test_relationship_columns_exist_on_their_tables(self, model, tables_by_name):
        for rel in model["relationships"]:
            from_cols = {c["name"] for c in tables_by_name[rel["fromTable"]]["columns"]}
            to_cols = {c["name"] for c in tables_by_name[rel["toTable"]]["columns"]}
            assert rel["fromColumn"] in from_cols
            assert rel["toColumn"] in to_cols


class TestRowLevelSecurity:
    def test_regional_manager_role_exists(self, model):
        roles = {r["name"] for r in model["roles"]}
        assert "Regional Manager" in roles

    def test_regional_manager_filters_dim_channel(self, model):
        role = next(r for r in model["roles"] if r["name"] == "Regional Manager")
        perms = {p["name"]: p for p in role["tablePermissions"]}
        assert "dim_channel" in perms
        filter_expr = perms["dim_channel"]["filterExpression"]
        assert "dim_user_region_map" in filter_expr
        assert "USERPRINCIPALNAME" in filter_expr
        assert "region" in filter_expr

    def test_hq_analyst_role_is_unrestricted(self, model):
        role = next(r for r in model["roles"] if r["name"] == "HQ Analyst")
        assert role["tablePermissions"] == []


class TestMeasuresMatchDaxFile:
    def test_model_bim_measures_are_exactly_the_generated_set(self, tables_by_name):
        dax_measures = dict(parse_measures(DAX_PATH.read_text()))

        bim_measures: dict[str, dict] = {}
        for table_name, expected_names in _measures_grouped_by_table().items():
            table_measures = {m["name"]: m for m in tables_by_name[table_name].get("measures", [])}
            assert set(table_measures) == expected_names, (
                f"model.bim table '{table_name}' measures do not match "
                f"MEASURE_TABLE assignment. Run scripts/build_model_bim.py."
            )
            bim_measures.update(table_measures)

        assert set(bim_measures) == set(dax_measures)

        for name, dax_expr in dax_measures.items():
            bim_expr = "\n".join(bim_measures[name]["expression"])
            assert bim_expr == dax_expr, f"expression drift for measure '{name}'"


def _measures_grouped_by_table() -> dict[str, set[str]]:
    grouped: dict[str, set[str]] = {}
    for name, table in MEASURE_TABLE.items():
        grouped.setdefault(table, set()).add(name)
    return grouped
