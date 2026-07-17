"""Unit tests for the synthetic data generator.

These run in-process against the pandas DataFrames the generator builds
-- no dbt, no database, no network -- so they're fast and pin down the
data-quality invariants the whole rest of the pipeline (dbt tests, DAX
measures) depends on.
"""
from __future__ import annotations


import pandas as pd
import pytest

from data_generator import config as cfg
from data_generator.generate import (
    build_dim_channel,
    build_dim_product,
    build_fact_inventory,
    build_fact_sales,
)


@pytest.fixture(scope="module")
def dims():
    return build_dim_channel(), build_dim_product()


@pytest.fixture(scope="module")
def sales(dims):
    dim_channel, dim_product = dims
    return build_fact_sales(dim_product, dim_channel)


@pytest.fixture(scope="module")
def inventory(dims, sales):
    dim_channel, dim_product = dims
    return build_fact_inventory(dim_product, dim_channel, sales)


class TestDimChannel:
    def test_row_count_matches_config(self, dims):
        dim_channel, _ = dims
        assert len(dim_channel) == len(cfg.CHANNELS)

    def test_channel_ids_unique(self, dims):
        dim_channel, _ = dims
        assert dim_channel["channel_id"].is_unique

    def test_regions_are_known_values(self, dims):
        dim_channel, _ = dims
        assert set(dim_channel["region"]) <= {"Northeast", "Midwest", "West", "National"}


class TestDimProduct:
    def test_product_ids_unique(self, dims):
        _, dim_product = dims
        assert dim_product["product_id"].is_unique

    def test_list_price_exceeds_cost(self, dims):
        _, dim_product = dims
        assert (dim_product["list_price"] > dim_product["unit_cost"]).all()

    def test_margin_within_configured_bounds(self, dims):
        # list_price_margin_pct itself is computed downstream in dbt
        # (stg_products.sql); here we just check the raw cost/price pair
        # the generator emits implies a margin inside the configured band.
        _, dim_product = dims
        lo = min(m[0] for *_, m in cfg.CATEGORY_SPEC) - 0.01
        hi = max(m[1] for *_, m in cfg.CATEGORY_SPEC) + 0.01
        implied_margin = (dim_product["list_price"] - dim_product["unit_cost"]) / dim_product["list_price"]
        assert (implied_margin >= lo).all()
        assert (implied_margin <= hi).all()

    def test_some_products_discontinued_and_some_active(self, dims):
        # A believable multi-year catalog isn't 100% flat lifecycles.
        _, dim_product = dims
        assert dim_product["is_active"].sum() > 0
        assert (~dim_product["is_active"]).sum() > 0

    def test_launch_dates_within_history_window(self, dims):
        _, dim_product = dims
        assert (dim_product["launch_date"] >= pd.Timestamp(cfg.START_DATE)).all()
        assert (dim_product["launch_date"] <= pd.Timestamp(cfg.END_DATE)).all()


class TestFactSales:
    def test_nonempty(self, sales):
        assert len(sales) > 1000

    def test_sale_ids_unique(self, sales):
        assert sales["sale_id"].is_unique

    def test_no_negative_or_zero_quantity(self, sales):
        assert (sales["quantity"] > 0).all()

    def test_gross_revenue_equals_qty_times_price(self, sales):
        expected = (sales["quantity"] * sales["unit_price"]).round(2)
        assert (sales["gross_revenue"].round(2) == expected).all()

    def test_gross_cost_equals_qty_times_cost(self, sales):
        expected = (sales["quantity"] * sales["unit_cost"]).round(2)
        assert (sales["gross_cost"].round(2) == expected).all()

    def test_discount_within_bounds(self, sales):
        assert (sales["discount_pct"] >= 0).all()
        assert (sales["discount_pct"] <= 0.31).all()

    def test_referential_integrity_to_product_and_channel(self, sales, dims):
        dim_channel, dim_product = dims
        assert set(sales["product_id"]) <= set(dim_product["product_id"])
        assert set(sales["channel_id"]) <= set(dim_channel["channel_id"])

    def test_no_sales_before_channel_open_or_product_launch(self, sales, dims):
        dim_channel, dim_product = dims
        merged = sales.merge(dim_product[["product_id", "launch_date", "discontinued_date"]], on="product_id")
        merged = merged.merge(dim_channel[["channel_id", "opened_date"]], on="channel_id")
        assert (merged["order_date"] >= merged["launch_date"]).all()
        assert (merged["order_date"] >= merged["opened_date"]).all()
        still_active_or_before_discontinue = merged["discontinued_date"].isna() | (
            merged["order_date"] <= merged["discontinued_date"]
        )
        assert still_active_or_before_discontinue.all()

    def test_november_december_outsell_january_february(self, sales):
        # Sanity check that the seasonality curve actually bites: holiday
        # months should materially outsell the post-holiday slump months.
        by_month = sales.groupby(sales["order_date"].dt.month)["quantity"].sum()
        holiday = by_month[[11, 12]].sum()
        slump = by_month[[1, 2]].sum()
        assert holiday > slump


class TestFactInventory:
    def test_nonempty(self, inventory):
        assert len(inventory) > 100

    def test_snapshot_ids_unique(self, inventory):
        assert inventory["inventory_snapshot_id"].is_unique

    def test_snapshots_fall_on_configured_weekday(self, inventory):
        assert (inventory["snapshot_date"].dt.weekday == cfg.INVENTORY_SNAPSHOT_WEEKDAY).all()

    def test_on_hand_never_negative(self, inventory):
        assert (inventory["on_hand_qty"] >= 0).all()

    def test_referential_integrity_to_product_and_channel(self, inventory, dims):
        dim_channel, dim_product = dims
        assert set(inventory["product_id"]) <= set(dim_product["product_id"])
        assert set(inventory["channel_id"]) <= set(dim_channel["channel_id"])

    def test_some_stockouts_occur(self, inventory):
        # A dataset with zero stockouts ever would make the Stockout Rate %
        # DAX measure meaningless to demo -- assert the simulation actually
        # produces some.
        assert inventory["is_stockout"].sum() > 0
        assert inventory["is_stockout"].mean() < 0.5  # but not chronically broken


class TestDeterminism:
    def test_regenerating_products_is_byte_identical(self):
        first = build_dim_product()
        second = build_dim_product()
        pd.testing.assert_frame_equal(first, second)

    def test_regenerating_sales_is_byte_identical(self, dims):
        dim_channel, dim_product = dims
        first = build_fact_sales(dim_product, dim_channel)
        second = build_fact_sales(dim_product, dim_channel)
        pd.testing.assert_frame_equal(first, second)
