"""Build data/volve.db: load producer and injector records, run checks, create views.

Run from the project folder:
    python python/load_sqlite.py
"""
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "Volve production data.xlsx"
DAILY_PROD = ROOT / "data" / "processed" / "production_daily_clean.csv"
DB = ROOT / "data" / "volve.db"
SQL = ROOT / "sql"


def load_production() -> pd.DataFrame:
    """Producer records already cleaned in the notebook."""
    df = pd.read_csv(DAILY_PROD, parse_dates=["DATEPRD"])
    return pd.DataFrame({
        "prod_date": df["DATEPRD"].dt.strftime("%Y-%m-%d"),
        "well_name": df["NPD_WELL_BORE_NAME"],
        "on_stream_hrs": df["ON_STREAM_HRS"],
        "oil_vol": df["BORE_OIL_VOL"],
        "gas_vol": df["BORE_GAS_VOL"],
        "water_vol": df["BORE_WAT_VOL"],
        "uptime_pct": df["UPTIME_PCT"],
        "water_cut_pct": df["WATER_CUT_PCT"],
        "oil_rate_24h": df["OIL_RATE_24H"],
        "gas_rate_24h": df["GAS_RATE_24H"],
    })


def load_injection() -> pd.DataFrame:
    """Injector records, filtered from the raw file with the notebook's rules."""
    raw = pd.read_excel(RAW, sheet_name="Daily Production Data")
    inj = raw[(raw["WELL_TYPE"] == "WI") & (raw["FLOW_KIND"] == "injection")].copy()
    hrs = inj["ON_STREAM_HRS"]
    return pd.DataFrame({
        "inj_date": inj["DATEPRD"].dt.strftime("%Y-%m-%d"),
        "well_name": inj["NPD_WELL_BORE_NAME"],
        "on_stream_hrs": hrs,
        "water_injected": inj["BORE_WI_VOL"],
        "uptime_pct": (hrs / 24 * 100).clip(upper=100),
        "injection_rate_24h": np.where(hrs > 0, inj["BORE_WI_VOL"] / hrs * 24, np.nan),
    })


def build_wells(prod: pd.DataFrame, inj: pd.DataFrame) -> pd.DataFrame:
    p = prod.groupby("well_name")["prod_date"].agg(["min", "max", "count"]).assign(role="producer")
    i = inj.groupby("well_name")["inj_date"].agg(["min", "max", "count"]).assign(role="injector")
    wells = pd.concat([p, i]).reset_index()
    return wells.rename(columns={"min": "first_date", "max": "last_date", "count": "record_days"})[
        ["well_name", "role", "first_date", "last_date", "record_days"]
    ]


def main() -> None:
    prod = load_production()
    inj = load_injection()
    wells = build_wells(prod, inj)

    con = sqlite3.connect(DB)
    con.executescript((SQL / "01_schema.sql").read_text())
    wells.to_sql("wells", con, if_exists="append", index=False)
    prod.to_sql("daily_production", con, if_exists="append", index=False)
    inj.to_sql("daily_injection", con, if_exists="append", index=False)
    con.executescript((SQL / "02_checks.sql").read_text())
    con.executescript((SQL / "03_views.sql").read_text())
    con.commit()

    print(f"Built {DB.relative_to(ROOT)}")
    print(f"  wells: {len(wells)}  daily_production: {len(prod)}  daily_injection: {len(inj)}\n")
    print("Data-quality log:")
    print(pd.read_sql("SELECT check_name, table_name, issue_count, severity FROM data_quality_log", con)
          .to_string(index=False))
    print("\nInjection correlation:")
    print(pd.read_sql("SELECT * FROM vw_injection_correlation", con).to_string(index=False))
    con.close()


if __name__ == "__main__":
    main()
