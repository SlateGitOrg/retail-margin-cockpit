"""Static checks on the DAX measure library.

Power BI itself isn't installable in this environment, so we can't
literally evaluate DAX here. What we *can* verify offline: every measure
we claim to ship actually exists with a plausible, syntactically sound
expression, that the file has no leftover placeholders, and that the
measure-to-table parser (also used to build model.bim) agrees on what's
in the file.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.build_model_bim import MEASURE_TABLE, parse_measures

ROOT = Path(__file__).resolve().parents[1]
DAX_PATH = ROOT / "powerbi" / "measures.dax"


@pytest.fixture(scope="module")
def dax_text():
    return DAX_PATH.read_text()


@pytest.fixture(scope="module")
def measures(dax_text):
    return dict(parse_measures(dax_text))


REQUIRED_MEASURES = {
    "Gross Margin %": ["DIVIDE"],
    "Sell-Through %": ["DIVIDE"],
    "Inventory Turns (Annualized)": ["DIVIDE"],
    "Gross Revenue YoY %": [],
    "Gross Revenue MoM %": [],
    "Stockout Rate %": ["DIVIDE", "fact_inventory"],
}


class TestMeasuresExist:
    def test_no_todo_or_placeholder_text(self, dax_text):
        lowered = dax_text.lower()
        for marker in ("todo", "fixme", "placeholder", "not implemented", "xxx"):
            assert marker not in lowered, f"found '{marker}' in measures.dax"

    def test_parser_finds_a_healthy_number_of_measures(self, measures):
        assert len(measures) >= 20

    @pytest.mark.parametrize("name", sorted(REQUIRED_MEASURES))
    def test_required_measure_present(self, measures, name):
        assert name in measures

    @pytest.mark.parametrize("name,must_contain", sorted(REQUIRED_MEASURES.items()))
    def test_required_measure_expression_mentions_expected_tokens(self, measures, name, must_contain):
        expr = measures[name]
        for token in must_contain:
            assert token in expr, f"expected '{token}' in expression for measure '{name}'"

    def test_every_measure_has_balanced_parentheses(self, measures):
        for name, expr in measures.items():
            assert expr.count("(") == expr.count(")"), f"unbalanced parens in measure '{name}'"

    def test_time_intelligence_measures_reference_dim_date(self, measures):
        for name in (
            "Gross Revenue PY",
            "Gross Revenue Prior Month",
            "Gross Revenue YTD",
        ):
            assert "dim_date" in measures[name]

    def test_rls_helper_measure_uses_userprincipalname(self, measures):
        assert "USERPRINCIPALNAME" in measures["Current User Region"]


class TestParserAgreesWithModelAssignment:
    def test_every_parsed_measure_has_a_table_assignment(self, measures):
        assert set(measures) == set(MEASURE_TABLE), (
            "measures.dax and scripts/build_model_bim.py:MEASURE_TABLE have "
            "drifted -- every measure must be assigned to exactly one table."
        )
