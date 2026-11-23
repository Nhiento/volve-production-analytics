"""Roll the cleaned daily records up to monthly totals per well.

This is a summary (mart) step, so it reads only the cleaned layer and writes to
data/marts/, never back into data/processed/:

    python python/monthly_totals.py

Reads   data/processed/production_daily_clean.csv
        data/processed/injection_daily_clean.csv
Writes  data/marts/monthly_production.csv   producer totals per well-month
        data/marts/monthly_injection.csv    injector totals per well-month
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
OUT = ROOT / "data" / "marts"


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
    prod = pd.read_csv(PROCESSED / "production_daily_clean.csv", parse_dates=["DATEPRD"])
    inj = pd.read_csv(PROCESSED / "injection_daily_clean.csv", parse_dates=["DATEPRD"])

    outputs = {
        "monthly_production.csv": monthly_production(prod),
        "monthly_injection.csv": monthly_injection(inj),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    for name, df in outputs.items():
        df.to_csv(OUT / name, index=False, date_format="%Y-%m-%d")
        print(f"  {name:<30} {len(df):>6} rows")


if __name__ == "__main__":
    print(f"Building monthly totals from {PROCESSED.relative_to(ROOT)}")
    main()
