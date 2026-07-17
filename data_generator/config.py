"""Static configuration for the synthetic retail dataset.

Kept in one place so the generator, the tests, and documentation all agree
on what the "world" looks like (date range, categories, channels, seed).
"""
from __future__ import annotations

import datetime as _dt

# Reproducibility: every run with this seed produces byte-identical CSVs.
RANDOM_SEED = 20240115

# Two full fiscal years -> enough history for YoY / MoM DAX time intelligence.
START_DATE = _dt.date(2023, 1, 1)
END_DATE = _dt.date(2024, 12, 31)

# Weekly cadence for inventory snapshots keeps the fact table at a sensible,
# BI-realistic grain (most retail inventory ledgers snapshot daily-to-weekly,
# not per-transaction) while keeping the CSV seed a manageable size.
INVENTORY_SNAPSHOT_WEEKDAY = 0  # Monday

# --- Channels -----------------------------------------------------------
# region drives the row-level-security demo: a "regional manager" role is
# scoped to exactly one physical region; national channels (Online,
# Wholesale) are visible only to the HQ / unrestricted role.
CHANNELS = [
    {
        "channel_id": "CH-NE-01",
        "channel_name": "Retail Store - Northeast",
        "channel_type": "Retail Store",
        "region": "Northeast",
        "opened_date": _dt.date(2019, 3, 1),
        "base_daily_activity_rate": 0.86,
        "demand_index": 1.05,
    },
    {
        "channel_id": "CH-MW-01",
        "channel_name": "Retail Store - Midwest",
        "channel_type": "Retail Store",
        "region": "Midwest",
        "opened_date": _dt.date(2020, 6, 15),
        "base_daily_activity_rate": 0.78,
        "demand_index": 0.9,
    },
    {
        "channel_id": "CH-WE-01",
        "channel_name": "Retail Store - West",
        "channel_type": "Retail Store",
        "region": "West",
        "opened_date": _dt.date(2018, 11, 1),
        "base_daily_activity_rate": 0.9,
        "demand_index": 1.15,
    },
    {
        "channel_id": "CH-ON-01",
        "channel_name": "Shopify Online",
        "channel_type": "Ecommerce",
        "region": "National",
        "opened_date": _dt.date(2017, 1, 1),
        "base_daily_activity_rate": 0.97,
        "demand_index": 1.35,
    },
    {
        "channel_id": "CH-WS-01",
        "channel_name": "Wholesale B2B",
        "channel_type": "Wholesale",
        "region": "National",
        "opened_date": _dt.date(2021, 2, 1),
        "base_daily_activity_rate": 0.35,
        "demand_index": 0.7,
    },
]

# --- Categories & products ------------------------------------------------
# (category, subcategory, unit_count, base_cost_range, margin_range)
CATEGORY_SPEC = [
    ("Apparel", "Outerwear", 5, (28.0, 62.0), (0.42, 0.55)),
    ("Apparel", "Basics", 6, (6.0, 14.0), (0.55, 0.68)),
    ("Footwear", "Sneakers", 5, (22.0, 48.0), (0.38, 0.50)),
    ("Accessories", "Bags", 4, (14.0, 40.0), (0.45, 0.60)),
    ("Accessories", "Small Leather Goods", 4, (5.0, 16.0), (0.5, 0.65)),
    ("Home", "Kitchen", 4, (8.0, 26.0), (0.40, 0.52)),
    ("Home", "Decor", 4, (6.0, 20.0), (0.48, 0.62)),
]

# Seasonality multipliers applied to expected daily demand, keyed by month.
MONTH_SEASONALITY = {
    1: 0.80,  # post-holiday slump
    2: 0.82,
    3: 0.92,
    4: 0.95,
    5: 0.98,
    6: 1.00,
    7: 0.97,
    8: 1.08,  # back to school
    9: 1.00,
    10: 1.05,
    11: 1.35,  # Black Friday / early holiday
    12: 1.55,  # peak holiday
}

# Clearance / promo events: (month, day-of-month window, discount_pct, applies to category)
PROMO_WINDOWS = [
    (11, 24, 30, 0.30, None),  # Black Friday week, all categories
    (7, 1, 14, 0.20, "Apparel"),  # summer apparel clearance
    (1, 2, 15, 0.25, None),  # post-holiday markdown, all categories
]
