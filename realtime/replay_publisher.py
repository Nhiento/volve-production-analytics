"""Replay Volve daily well data as a live MQTT sensor feed.

Think of this script as the "edge": the box on the platform that reads the
instruments and pushes their values to the data platform. Volve only has daily
averages, so we replay history fast (default: 1 field day per real second).

Every tag is published to its own topic:
    volve/<well>/<template>      e.g. volve/F-12/downhole_pressure
with a small JSON payload:
    {"ts": 1199145600, "value": 251.3, "unit": "bar", "quality": "good",
     "sent_at": 1760380000.12, "interval_s": 1.0}

Fault injection (for demos): break the feed on purpose and watch the quality
monitor catch it. Faults start after --fault-after-days of replay.
    --drop F-14.downhole_pressure        stop sending one tag
    --freeze F-11.wellhead_pressure      keep repeating the last value
    --wrong-unit F-12.wellhead_pressure  send psi instead of bar
    --crash-after-days 60                die without saying goodbye

Usage (from the realtime/ folder):
    python replay_publisher.py --start 2014-01-01 --speed 5
"""
import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

import pandas as pd
import paho.mqtt.client as mqtt

from registry import load_assets, load_templates

RAW_FILE = Path(__file__).resolve().parents[1] / "data" / "raw" / "Volve production data.xlsx"
STATUS_TOPIC = "status/publisher"

# What a misconfigured vendor might send instead of the standard unit
UNIT_CONVERSIONS = {
    "bar": ("psi", lambda v: v * 14.5038),
    "degC": ("degF", lambda v: v * 9 / 5 + 32),
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--broker", default=os.getenv("MQTT_HOST", "localhost"))
    p.add_argument("--port", type=int, default=int(os.getenv("MQTT_PORT", "1883")))
    p.add_argument("--speed", type=float, default=1.0, help="field days replayed per real second")
    p.add_argument("--start", default=None, help="first field date, e.g. 2014-01-01")
    p.add_argument("--end", default=None, help="last field date")
    p.add_argument("--wells", default=None, help="comma-separated asset ids, e.g. F-12,F-14")
    p.add_argument("--fault-after-days", type=int, default=30)
    p.add_argument("--drop", action="append", default=[], metavar="WELL.TEMPLATE")
    p.add_argument("--freeze", action="append", default=[], metavar="WELL.TEMPLATE")
    p.add_argument("--wrong-unit", action="append", default=[], metavar="WELL.TEMPLATE")
    p.add_argument("--crash-after-days", type=int, default=None)
    return p.parse_args()


def load_source_rows(start, end, wells) -> pd.DataFrame:
    """Read the raw Excel file and keep producer rows, same filter as the notebook."""
    raw = pd.read_excel(RAW_FILE, sheet_name="Daily Production Data")
    rows = raw[(raw["WELL_TYPE"] == "OP") & (raw["FLOW_KIND"] == "production")].copy()

    # Map the source wellbore name ("15/9-F-12") to our asset id ("F-12")
    by_wellbore = {a.source_wellbore: a.asset_id for a in load_assets()}
    rows["asset_id"] = rows["NPD_WELL_BORE_NAME"].map(by_wellbore)
    rows = rows.dropna(subset=["asset_id"])

    if start:
        rows = rows[rows["DATEPRD"] >= pd.Timestamp(start)]
    if end:
        rows = rows[rows["DATEPRD"] <= pd.Timestamp(end)]
    if wells:
        rows = rows[rows["asset_id"].isin(wells.split(","))]
    return rows.sort_values(["DATEPRD", "asset_id"])


def connect(args) -> mqtt.Client:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="volve-replay-publisher")
    # Last Will: if this process dies without disconnecting, the broker itself
    # publishes "offline" on our behalf. That is how the platform knows the edge is down.
    client.will_set(STATUS_TOPIC, "offline", qos=1, retain=True)
    client.connect(args.broker, args.port, keepalive=5)
    client.loop_start()
    client.publish(STATUS_TOPIC, "online", qos=1, retain=True)
    return client


def main() -> None:
    args = parse_args()
    templates = load_templates()
    rows = load_source_rows(args.start, args.end, args.wells)
    days = rows["DATEPRD"].drop_duplicates().tolist()
    interval_s = 1.0 / args.speed

    print(f"Replaying {len(rows):,} well-days ({len(days):,} field days) "
          f"from {days[0]:%Y-%m-%d} to {days[-1]:%Y-%m-%d} at {args.speed:g} day/s "
          f"-> about {len(days) * interval_s / 60:.1f} min")

    client = connect(args)
    frozen_values: dict[str, float] = {}
    sent = 0

    for day_number, (day, day_rows) in enumerate(rows.groupby("DATEPRD", sort=True)):
        tick = time.monotonic()
        faults_on = day_number >= args.fault_after_days

        if args.crash_after_days is not None and day_number >= args.crash_after_days:
            print(f"Simulated crash on {day:%Y-%m-%d}: exiting without disconnecting")
            os._exit(1)  # skip the clean disconnect so the broker fires the Last Will

        ts = int(day.tz_localize("UTC").timestamp())
        for _, row in day_rows.iterrows():
            well = row["asset_id"]
            for t in templates:
                key = f"{well}.{t.name}"
                if faults_on and key in args.drop:
                    continue

                value = row[t.source_column]
                value = None if pd.isna(value) else float(value)
                unit = t.unit

                if faults_on and key in args.freeze:
                    frozen_values.setdefault(key, value)
                    value = frozen_values[key]
                if faults_on and key in args.wrong_unit and value is not None and t.unit in UNIT_CONVERSIONS:
                    unit, convert = UNIT_CONVERSIONS[t.unit]
                    value = convert(value)

                payload = {"ts": ts, "unit": unit, "sent_at": time.time(), "interval_s": interval_s}
                if value is None or math.isnan(value):
                    payload["quality"] = "no_data"   # the source had nothing for this tag today
                else:
                    payload["quality"] = "good"
                    payload["value"] = round(value, 4)

                client.publish(f"volve/{well}/{t.name}", json.dumps(payload), qos=1)
                sent += 1

        if day_number % 100 == 0:
            print(f"  {day:%Y-%m-%d}  {sent:,} messages sent")
        time.sleep(max(0.0, interval_s - (time.monotonic() - tick)))

    print(f"Done: {sent:,} messages")
    client.publish(STATUS_TOPIC, "finished", qos=1, retain=True).wait_for_publish()
    client.loop_stop()
    client.disconnect()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
