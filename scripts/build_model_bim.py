"""Generate powerbi/model.bim (TMSL) from powerbi/measures.dax.

Why this exists: the DAX measure library (powerbi/measures.dax, meant to
be pasted into Power BI Desktop / read by a human) and the Tabular Model
Definition (powerbi/model.bim, the machine-readable semantic model
Power BI / Tabular Editor would actually load) need to define the exact
same measures with the exact same expressions. Hand-maintaining both
invites drift, so model.bim's measure list is generated straight out of
measures.dax -- run this after editing measures.dax and commit the
regenerated model.bim.

Usage:
    python scripts/build_model_bim.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DAX_PATH = ROOT / "powerbi" / "measures.dax"
BIM_PATH = ROOT / "powerbi" / "model.bim"

# Which table each measure is organized under in the model. Purely
# organizational (Power BI doesn't care which table hosts a measure) --
# keeps the "Sales" vs "Inventory" vs "RLS" folders sensible in the field
# list.
MEASURE_TABLE = {
    "Total Units Sold": "fact_sales",
    "Total Gross Revenue": "fact_sales",
    "Total Gross Cost": "fact_sales",
    "Avg Selling Price": "fact_sales",
    "Distinct Products Sold": "fact_sales",
    "Distinct Orders": "fact_sales",
    "Gross Margin $": "fact_sales",
    "Gross Margin %": "fact_sales",
    "Effective Discount %": "fact_sales",
    "Revenue Below Margin Floor": "fact_sales",
    "Gross Revenue PY": "fact_sales",
    "Gross Revenue YoY %": "fact_sales",
    "Gross Margin $ PY": "fact_sales",
    "Gross Margin % PY": "fact_sales",
    "Gross Margin % YoY pts": "fact_sales",
    "Gross Revenue Prior Month": "fact_sales",
    "Gross Revenue MoM %": "fact_sales",
    "Gross Revenue YTD": "fact_sales",
    "Gross Revenue YTD PY": "fact_sales",
    "Gross Revenue YTD YoY %": "fact_sales",
    "Ending On Hand Units": "fact_inventory",
    "Ending Inventory Value (Cost)": "fact_inventory",
    "Average Inventory Value (Cost)": "fact_inventory",
    "Sell-Through %": "fact_inventory",
    "Inventory Turns (Annualized)": "fact_inventory",
    "Stockout Rate %": "fact_inventory",
    "Weeks of Supply": "fact_inventory",
    "Current User Region": "dim_user_region_map",
}

DISPLAY_FOLDER = {
    "fact_sales": "Sales & Margin",
    "fact_inventory": "Inventory Health",
    "dim_user_region_map": "RLS",
}

FORMAT_STRING = {
    "Gross Margin %": "0.0%",
    "Effective Discount %": "0.0%",
    "Sell-Through %": "0.0%",
    "Stockout Rate %": "0.0%",
    "Gross Revenue YoY %": "+0.0%;-0.0%",
    "Gross Margin % PY": "0.0%",
    "Gross Margin % YoY pts": "+0.0%;-0.0%",
    "Gross Revenue MoM %": "+0.0%;-0.0%",
    "Gross Revenue YTD YoY %": "+0.0%;-0.0%",
    "Inventory Turns (Annualized)": "0.0",
    "Weeks of Supply": "0.0",
    "Total Gross Revenue": "$#,##0",
    "Total Gross Cost": "$#,##0",
    "Gross Margin $": "$#,##0",
    "Avg Selling Price": "$#,##0.00",
    "Ending Inventory Value (Cost)": "$#,##0",
    "Average Inventory Value (Cost)": "$#,##0",
    "Revenue Below Margin Floor": "$#,##0",
}


def parse_measures(dax_text: str) -> list[tuple[str, str]]:
    """Parse `Name =\\n<expr...>` blocks separated by blank lines.

    Lines starting with `//` are treated as comments and dropped before
    grouping, so section-header comment blocks disappear entirely rather
    than being (mis)parsed as measures.
    """
    lines = [ln for ln in dax_text.splitlines() if not ln.strip().startswith("//")]

    groups: list[list[str]] = []
    current: list[str] = []
    for ln in lines:
        if ln.strip() == "":
            if current:
                groups.append(current)
                current = []
            continue
        current.append(ln)
    if current:
        groups.append(current)

    measures = []
    name_pattern = re.compile(r"^(.+?)\s*=\s*$")
    for group in groups:
        m = name_pattern.match(group[0])
        if not m:
            continue
        name = m.group(1).strip()
        expr = "\n".join(group[1:]).strip()
        if not expr:
            continue
        measures.append((name, expr))
    return measures


def build_measure_tmsl(name: str, expr: str) -> dict:
    tmsl = {
        "name": name,
        "expression": expr.split("\n"),
    }
    if name in FORMAT_STRING:
        tmsl["formatString"] = FORMAT_STRING[name]
    folder = DISPLAY_FOLDER.get(MEASURE_TABLE.get(name))
    if folder:
        tmsl["displayFolder"] = folder
    return tmsl


def main() -> None:
    dax_text = DAX_PATH.read_text()
    measures = parse_measures(dax_text)

    found_names = {n for n, _ in measures}
    expected_names = set(MEASURE_TABLE)
    missing = expected_names - found_names
    unexpected = found_names - expected_names
    if missing:
        raise SystemExit(f"measures.dax is missing expected measures: {sorted(missing)}")
    if unexpected:
        raise SystemExit(
            f"measures.dax defines measures not assigned to a table in "
            f"MEASURE_TABLE: {sorted(unexpected)}"
        )

    measures_by_table: dict[str, list[dict]] = {"fact_sales": [], "fact_inventory": [], "dim_user_region_map": []}
    for name, expr in measures:
        table = MEASURE_TABLE[name]
        measures_by_table[table].append(build_measure_tmsl(name, expr))

    bim = json.loads(BIM_PATH.read_text())
    tables = bim["model"]["tables"]
    for table in tables:
        if table["name"] in measures_by_table:
            table["measures"] = measures_by_table[table["name"]]

    BIM_PATH.write_text(json.dumps(bim, indent=2) + "\n")
    print(f"Wrote {sum(len(v) for v in measures_by_table.values())} measures into {BIM_PATH}")


if __name__ == "__main__":
    main()
