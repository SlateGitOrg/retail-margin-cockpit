import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DBT_PROJECT_DIR = ROOT / "dbt" / "retail_margin_cockpit"

# Make `data_generator` and `scripts.build_model_bim` importable without
# installing the project as a package.
for p in (str(ROOT),):
    if p not in sys.path:
        sys.path.insert(0, p)
