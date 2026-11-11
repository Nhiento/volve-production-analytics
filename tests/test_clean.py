"""Unit tests for python/clean.py. Uses a few hand-made rows, not the real file.

Run from the project folder:
    python -m pytest -q tests
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))
from clean import clean_injection, clean_production, monthly_production  # noqa: E402


def raw_rows(rows):
    base = {
        "DATEPRD": pd.Timestamp("2010-01-01"), "NPD_WELL_BORE_NAME": "15/9-F-12",
        "WELL_TYPE": "OP", "FLOW_KIND": "production", "ON_STREAM_HRS": 24.0,
        "BORE_OIL_VOL": 100.0, "BORE_GAS_VOL": 1000.0, "BORE_WAT_VOL": 100.0, "BORE_WI_VOL": np.nan,
    }
    return pd.DataFrame([{**base, **r} for r in rows])


def test_splits_on_well_type_and_flow_kind():
    raw = raw_rows([
        {},                                                         # producer
        {"WELL_TYPE": "WI", "FLOW_KIND": "injection", "BORE_WI_VOL": 500.0},
        {"WELL_TYPE": "OP", "FLOW_KIND": "injection"},              # mismatched: neither
    ])
    assert len(clean_production(raw)) == 1
    assert len(clean_injection(raw)) == 1


def test_negative_water_becomes_missing():
    prod = clean_production(raw_rows([{"BORE_WAT_VOL": -5.0}]))
    assert prod["BORE_WAT_VOL"].isna().all()
    assert prod["WATER_CUT_PCT"].isna().all()


def test_uptime_capped_at_100_on_25_hour_days():
    prod = clean_production(raw_rows([{"ON_STREAM_HRS": 25.0}]))
    assert prod["UPTIME_PCT"].iloc[0] == 100


def test_rates_scale_to_24_hours():
    prod = clean_production(raw_rows([{"ON_STREAM_HRS": 12.0, "BORE_OIL_VOL": 50.0}]))
    assert prod["OIL_RATE_24H"].iloc[0] == pytest.approx(100.0)


def test_rate_is_missing_when_well_was_offline():
    prod = clean_production(raw_rows([{"ON_STREAM_HRS": 0.0, "BORE_OIL_VOL": 0.0}]))
    assert np.isnan(prod["OIL_RATE_24H"].iloc[0])


def test_water_cut():
    prod = clean_production(raw_rows([{"BORE_OIL_VOL": 25.0, "BORE_WAT_VOL": 75.0}]))
    assert prod["WATER_CUT_PCT"].iloc[0] == pytest.approx(75.0)


def test_monthly_rollup_sums_volumes_and_weights_water_cut_by_volume():
    prod = clean_production(raw_rows([
        {"DATEPRD": pd.Timestamp("2010-01-01"), "BORE_OIL_VOL": 90.0, "BORE_WAT_VOL": 10.0},
        {"DATEPRD": pd.Timestamp("2010-01-15"), "BORE_OIL_VOL": 10.0, "BORE_WAT_VOL": 90.0},
        {"DATEPRD": pd.Timestamp("2010-02-01")},
    ]))
    m = monthly_production(prod)
    jan = m[m["MONTH"] == pd.Timestamp("2010-01-01")].iloc[0]
    assert len(m) == 2
    assert jan["oil_volume"] == 100.0
    assert jan["WATER_CUT_PCT"] == pytest.approx(50.0)
