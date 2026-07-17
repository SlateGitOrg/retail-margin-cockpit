"""Build the synthetic retail-margin-cockpit dataset.

Public entry points:
    build_dim_channel()  -> pandas.DataFrame
    build_dim_product()  -> pandas.DataFrame
    build_fact_sales(dim_product, dim_channel)     -> pandas.DataFrame
    build_fact_inventory(dim_product, dim_channel, fact_sales) -> pandas.DataFrame
    main(out_dir)  -> writes the four CSVs dbt expects as seeds

Everything is driven off `data_generator.config` and a single numpy
Generator seeded with config.RANDOM_SEED, so repeated runs are
byte-for-byte identical -- important both for the "no network / fully
offline" requirement and for making dbt test failures reproducible.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import os
from pathlib import Path

import numpy as np
import pandas as pd

from data_generator import config as cfg

CATEGORY_PREFIX = {
    "Apparel": "APP",
    "Footwear": "FTW",
    "Accessories": "ACC",
    "Home": "HOM",
}


def _rng() -> np.random.Generator:
    return np.random.default_rng(cfg.RANDOM_SEED)


def build_dim_channel() -> pd.DataFrame:
    df = pd.DataFrame(cfg.CHANNELS)
    df["opened_date"] = pd.to_datetime(df["opened_date"])
    return df


def build_dim_product() -> pd.DataFrame:
    rng = _rng()
    rows = []
    pid = 1
    for category, subcategory, count, cost_range, margin_range in cfg.CATEGORY_SPEC:
        prefix = CATEGORY_PREFIX[category]
        for i in range(count):
            unit_cost = round(float(rng.uniform(*cost_range)), 2)
            target_margin = float(rng.uniform(*margin_range))
            list_price = round(unit_cost / (1 - target_margin), 2)

            # Stagger launch dates so the catalog grows over time, and let a
            # handful of early products be discontinued mid-window -- this is
            # what makes sell-through / turns / YoY comparisons interesting
            # rather than every product having a perfectly flat lifecycle.
            days_span = (cfg.END_DATE - cfg.START_DATE).days
            launch_offset = int(rng.integers(0, max(days_span - 60, 1)))
            launch_date = cfg.START_DATE + _dt.timedelta(days=launch_offset)
            if launch_offset < days_span * 0.35 and rng.random() < 0.18:
                discontinued_offset = launch_offset + int(
                    rng.integers(180, max(days_span - launch_offset, 181))
                )
                discontinued_offset = min(discontinued_offset, days_span)
                discontinued_date = cfg.START_DATE + _dt.timedelta(days=discontinued_offset)
            else:
                discontinued_date = None

            rows.append(
                {
                    "product_id": f"{prefix}-{pid:04d}",
                    "sku": f"{prefix}{pid:05d}",
                    "product_name": f"{subcategory} {category} Item {i + 1:02d}",
                    "category": category,
                    "subcategory": subcategory,
                    "unit_cost": unit_cost,
                    "list_price": list_price,
                    "launch_date": launch_date,
                    "discontinued_date": discontinued_date,
                    "reorder_point": int(rng.integers(15, 45)),
                    "target_stock_level": int(rng.integers(60, 160)),
                }
            )
            pid += 1
    df = pd.DataFrame(rows)
    df["launch_date"] = pd.to_datetime(df["launch_date"])
    df["discontinued_date"] = pd.to_datetime(df["discontinued_date"])
    df["is_active"] = df["discontinued_date"].isna()
    return df


def _promo_discount(day: _dt.date, category: str) -> float:
    best = 0.0
    for month, start_day, end_day, discount, promo_category in cfg.PROMO_WINDOWS:
        if day.month == month and start_day <= day.day <= end_day:
            if promo_category is None or promo_category == category:
                best = max(best, discount)
    return best


def build_fact_sales(dim_product: pd.DataFrame, dim_channel: pd.DataFrame) -> pd.DataFrame:
    """Daily grain, one row per (date, product, channel) with activity.

    This mirrors how most POS/Shopify exports land in a warehouse: an
    order-line rollup by day, not a full clickstream. Quantity and pricing
    incorporate seasonality, per-channel demand, product lifecycle, and
    promo/clearance windows so the resulting margin and turns numbers are
    not flat noise.
    """
    rng = _rng()
    rows = []
    all_days = pd.date_range(cfg.START_DATE, cfg.END_DATE, freq="D")

    channels = dim_channel.to_dict("records")
    products = dim_product.to_dict("records")

    for day_ts in all_days:
        day = day_ts.date()
        seasonality = cfg.MONTH_SEASONALITY[day.month]
        dow_boost = 1.25 if day.weekday() in (4, 5) else 1.0  # Fri/Sat lift

        for ch in channels:
            if pd.Timestamp(ch["opened_date"]) > day_ts:
                continue
            activity_rate = ch["base_daily_activity_rate"]

            for p in products:
                if pd.Timestamp(p["launch_date"]) > day_ts:
                    continue
                if pd.notna(p["discontinued_date"]) and pd.Timestamp(p["discontinued_date"]) < day_ts:
                    continue

                fires = rng.random() < activity_rate * 0.55
                if not fires:
                    continue

                expected_qty = 2.4 * seasonality * dow_boost * ch["demand_index"]
                qty = int(rng.poisson(lam=max(expected_qty, 0.1)))
                if qty <= 0:
                    continue

                discount_pct = _promo_discount(day, p["category"])
                unit_price = round(p["list_price"] * (1 - discount_pct), 2)
                # small +/-4% freight/handling noise on landed cost
                unit_cost = round(p["unit_cost"] * float(rng.uniform(0.97, 1.04)), 2)

                rows.append(
                    {
                        "order_date": day,
                        "product_id": p["product_id"],
                        "channel_id": ch["channel_id"],
                        "quantity": qty,
                        "unit_price": unit_price,
                        "unit_cost": unit_cost,
                        "discount_pct": discount_pct,
                        "gross_revenue": round(qty * unit_price, 2),
                        "gross_cost": round(qty * unit_cost, 2),
                    }
                )
    df = pd.DataFrame(rows)
    df["order_date"] = pd.to_datetime(df["order_date"])
    df.insert(0, "sale_id", [f"SL-{i:07d}" for i in range(1, len(df) + 1)])
    return df


def build_fact_inventory(
    dim_product: pd.DataFrame, dim_channel: pd.DataFrame, fact_sales: pd.DataFrame
) -> pd.DataFrame:
    """Weekly on-hand snapshots per (product, channel), driven by actual
    sales drawn from fact_sales plus a simple reorder-point restock policy.
    """
    rng = _rng()
    snapshot_days = [
        d.date()
        for d in pd.date_range(cfg.START_DATE, cfg.END_DATE, freq="D")
        if d.weekday() == cfg.INVENTORY_SNAPSHOT_WEEKDAY
    ]

    weekly_sales = (
        fact_sales.assign(week_start=fact_sales["order_date"] - pd.to_timedelta(
            fact_sales["order_date"].dt.weekday, unit="D"
        ))
        .groupby(["week_start", "product_id", "channel_id"])["quantity"]
        .sum()
        .to_dict()
    )

    rows = []
    state: dict[tuple[str, str], dict] = {}

    for p in dim_product.to_dict("records"):
        for ch in dim_channel.to_dict("records"):
            state[(p["product_id"], ch["channel_id"])] = {
                "on_hand": p["target_stock_level"],
                "on_order": 0,
            }

    for day in snapshot_days:
        week_start = pd.Timestamp(day)
        for p in dim_product.to_dict("records"):
            if pd.Timestamp(p["launch_date"]).date() > day:
                continue
            if pd.notna(p["discontinued_date"]) and pd.Timestamp(p["discontinued_date"]).date() < day:
                continue
            for ch in dim_channel.to_dict("records"):
                if pd.Timestamp(ch["opened_date"]).date() > day:
                    continue
                key = (p["product_id"], ch["channel_id"])
                sold = int(weekly_sales.get((week_start, p["product_id"], ch["channel_id"]), 0))

                s = state[key]
                # receive any pending order
                s["on_hand"] += s["on_order"]
                s["on_order"] = 0

                s["on_hand"] -= sold
                stockout = s["on_hand"] <= 0
                s["on_hand"] = max(s["on_hand"], 0)

                if s["on_hand"] <= p["reorder_point"]:
                    lead_time_units = int(
                        rng.integers(
                            p["target_stock_level"] // 2, p["target_stock_level"] + 1
                        )
                    )
                    s["on_order"] = lead_time_units

                rows.append(
                    {
                        "snapshot_date": day,
                        "product_id": p["product_id"],
                        "channel_id": ch["channel_id"],
                        "on_hand_qty": s["on_hand"],
                        "on_order_qty": s["on_order"],
                        "units_sold_in_week": sold,
                        "reorder_point": p["reorder_point"],
                        "is_stockout": stockout,
                    }
                )

    df = pd.DataFrame(rows)
    df["snapshot_date"] = pd.to_datetime(df["snapshot_date"])
    df.insert(0, "inventory_snapshot_id", [f"INV-{i:07d}" for i in range(1, len(df) + 1)])
    return df


def main(out_dir: str | os.PathLike) -> dict[str, int]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    dim_channel = build_dim_channel()
    dim_product = build_dim_product()
    fact_sales = build_fact_sales(dim_product, dim_channel)
    fact_inventory = build_fact_inventory(dim_product, dim_channel, fact_sales)

    dim_channel.to_csv(out / "raw_channels.csv", index=False)
    dim_product.to_csv(out / "raw_products.csv", index=False)
    fact_sales.to_csv(out / "raw_sales.csv", index=False)
    fact_inventory.to_csv(out / "raw_inventory.csv", index=False)

    return {
        "channels": len(dim_channel),
        "products": len(dim_product),
        "sales": len(fact_sales),
        "inventory_snapshots": len(fact_inventory),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default=str(Path(__file__).resolve().parents[1] / "dbt" / "retail_margin_cockpit" / "seeds"),
        help="Directory to write raw_*.csv seed files into.",
    )
    args = parser.parse_args()
    counts = main(args.out)
    print(f"Wrote synthetic retail dataset to {args.out}: {counts}")
