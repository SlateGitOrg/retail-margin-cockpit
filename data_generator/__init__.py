"""Synthetic retail data generator for retail-margin-cockpit.

Produces a coherent, multi-year, multi-channel retail dataset (products,
channels, daily sales, weekly inventory snapshots) that is written out as
CSV seed files for the dbt project. Everything here is deterministic given
a fixed random seed so the generated dataset -- and every downstream dbt
build/test run -- is fully reproducible offline, with no network calls.
"""
