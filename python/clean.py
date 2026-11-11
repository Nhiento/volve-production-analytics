"""Clean the raw Volve file into the processed CSVs the rest of the project uses.

This is the cleaning logic from notebooks/01_data_cleaning_eda.ipynb as a script,
so the batch pipeline runs end to end without opening a notebook:

    python python/clean.py

Reads   data/raw/Volve production data.xlsx  (sheet "Daily Production Data")
Writes  data/processed/production_daily_clean.csv   one row per producer well-day
        data/processed/injection_daily_clean.csv    one row per injector well-day
        data/processed/monthly_production.csv       producer totals per well-month
        data/processed/monthly_injection.csv        injector totals per well-month

The notebook stays as the place to explore and explain; this script is what runs.
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "Volve production data.xlsx"
OUT = ROOT / "data" / "processed"

PROD_COLS = [
    "DATEPRD", "NPD_WELL_BORE_NAME", "WELL_TYPE", "FLOW_KIND", "ON_STREAM_HRS",
    "BORE_OIL_VOL", "BORE_GAS_VOL", "BORE_WAT_VOL",
]
INJ_COLS = ["DATEPRD", "NPD_WELL_BORE_NAME", "WELL_TYPE", "FLOW_KIND", "ON_STREAM_HRS", "BORE_WI_VOL"]


def read_raw(path: Path = RAW) -> pd.DataFrame:
    return pd.read_excel(path, sheet_name="Daily Production Data")


def per_24h(volume: pd.Series, hours: pd.Series) -> np.ndarray:
    """Normalize a volume to a 24-hour rate; undefined when the well never ran."""
    return np.where(hours > 0, volume / hours * 24, np.nan)


def clean_production(raw: pd.DataFrame) -> pd.DataFrame:
    """Oil producer records with KPI columns.

    F-5 and F-1 C appear as both producer and injector, so rows are split on
    WELL_TYPE and FLOW_KIND together rather than on well name.
    """
    df = raw[(raw["WELL_TYPE"] == "OP") & (raw["FLOW_KIND"] == "production")][PROD_COLS].copy()
    hrs = df["ON_STREAM_HRS"]

    df["UPTIME_PCT"] = (hrs / 24 * 100).clip(upper=100)          # a few raw days are 25 h (clock changes)
    df.loc[df["BORE_WAT_VOL"] < 0, "BORE_WAT_VOL"] = np.nan       # negative water is physically invalid
    df["WATER_CUT_PCT"] = df["BORE_WAT_VOL"] / (df["BORE_OIL_VOL"] + df["BORE_WAT_VOL"]) * 100
    df["OIL_RATE_24H"] = per_24h(df["BORE_OIL_VOL"], hrs)
    df["GAS_RATE_24H"] = per_24h(df["BORE_GAS_VOL"], hrs)
    return df


def clean_injection(raw: pd.DataFrame) -> pd.DataFrame:
    """Water injector records with uptime and a 24-hour injection rate."""
    df = raw[(raw["WELL_TYPE"] == "WI") & (raw["FLOW_KIND"] == "injection")][INJ_COLS].copy()
    hrs = df["ON_STREAM_HRS"]
    df["UPTIME_PCT"] = (hrs / 24 * 100).clip(upper=100)
    df["INJECTION_RATE_24H"] = per_24h(df["BORE_WI_VOL"], hrs)
    return df


def month_start(dates: pd.Series) -> pd.Series:
    return dates.dt.to_period("M").dt.to_timestamp()


def monthly_production(prod: pd.DataFrame) -> pd.DataFrame:
    m = (
        prod.assign(MONTH=month_start(prod["DATEPRD"]))
        .groupby(["MONTH", "NPD_WELL_BORE_NAME"], as_index=False)
        .agg(
            oil_volume=("BORE_OIL_VOL", "sum"),
            gas_volume=("BORE_GAS_VOL", "sum"),
            water_volume=("BORE_WAT_VOL", "sum"),
            avg_uptime_pct=("UPTIME_PCT", "mean"),
        )
    )
    m["WATER_CUT_PCT"] = m["water_volume"] / (m["oil_volume"] + m["water_volume"]) * 100
    return m


def monthly_injection(inj: pd.DataFrame) -> pd.DataFrame:
    return (
        inj.assign(MONTH=month_start(inj["DATEPRD"]))
        .groupby(["MONTH", "NPD_WELL_BORE_NAME"], as_index=False)
        .agg(
            water_injected=("BORE_WI_VOL", "sum"),
            avg_uptime_pct=("UPTIME_PCT", "mean"),
        )
    )


def main() -> None:
    raw = read_raw()
    prod = clean_production(raw)
    inj = clean_injection(raw)

    outputs = {
        "production_daily_clean.csv": prod,
        "injection_daily_clean.csv": inj,
        "monthly_production.csv": monthly_production(prod),
        "monthly_injection.csv": monthly_injection(inj),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    for name, df in outputs.items():
        df.to_csv(OUT / name, index=False, date_format="%Y-%m-%d")
        print(f"  {name:<30} {len(df):>6} rows")


if __name__ == "__main__":
    print(f"Cleaning {RAW.relative_to(ROOT)}")
    main()
