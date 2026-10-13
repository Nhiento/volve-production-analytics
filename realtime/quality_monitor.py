"""Real-time data-quality monitor for the Volve feed.

It subscribes to every tag, compares each message against the tag registry, and
publishes what it finds back to MQTT so Telegraf can store it next to the data.

Checks on every message:
  unit_mismatch   unit is not the registry's standard unit (e.g. psi instead of bar)
  missing_value   the source sent the tag but with no value
  out_of_range    value outside the registry's min/max
  bad_zero        exactly 0 on a gauge that cannot read 0 while the well is flowing
  frozen          the same non-zero value 3 readings in a row while flowing
  latency         seconds between the edge sending and us receiving

Checks on a timer:
  stale_tag       a tag stopped arriving while the rest of its well keeps reporting
  well_gap        a whole well skipped one or more days
  feed_stale      nothing at all arriving (publisher crashed or network down)
  publisher       online/offline status from the publisher's MQTT Last Will

Output topics:
  dq/<well>/<template>   one event per problem   (Telegraf -> measurement dq_event)
  dq_summary/<well>      rolling scorecard        (Telegraf -> measurement dq_summary)

On exit it writes reports/dq_report.csv and reports/dq_summary.md.

Usage (from the realtime/ folder):
    python quality_monitor.py               # Ctrl-C to stop
    python quality_monitor.py --exit-when-done
"""
import argparse
import csv
import json
import os
import signal
import statistics
import threading
import time
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

import paho.mqtt.client as mqtt

from registry import load_assets, load_templates

REPORTS = Path(__file__).resolve().parent / "reports"
DAY = 86_400
FROZEN_READINGS = 3     # identical readings in a row before we call a sensor frozen
STALE_DAYS = 3          # a tag missing this many field days while its well reports = stale
SUMMARY_EVERY_S = 2.0   # how often the scorecard is recomputed and published


def iso(ts: int | None) -> str:
    return "-" if ts is None else datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")


class QualityMonitor:
    def __init__(self, client: mqtt.Client):
        self.client = client
        self.templates = {t.name: t for t in load_templates()}
        self.assets = [a.asset_id for a in load_assets()]
        self.lock = threading.Lock()

        # Per-tag state
        self.last_value: dict[tuple, float] = {}
        self.repeat_run: Counter = Counter()
        self.tag_last_ts: dict[tuple, int] = {}
        self.stale: set[tuple] = set()

        # Per-well state
        self.well_last_ts: dict[str, int] = {}
        self.well_first_ts: dict[str, int] = {}
        self.flowing: dict[tuple, bool] = {}          # (well, ts) -> on stream?
        self.good_values: Counter = Counter()          # well -> readings that had a value
        self.valid_values: Counter = Counter()         # well -> readings that had a value AND passed every check
        self.well_days: Counter = Counter()            # well -> distinct days seen

        # Feed state
        self.latencies: deque = deque(maxlen=2000)
        self.last_msg_wall: float | None = None
        self.interval_s = 1.0
        self.publisher_status = "unknown"
        self.feed_alarm = False

        # Findings
        self.counts: Counter = Counter()               # (well, template, check) -> count
        self.first_seen: dict[tuple, int] = {}
        self.last_seen: dict[tuple, int] = {}
        self.examples: dict[tuple, str] = {}
        self.total_flags = 0

    # ---------- recording ----------
    def flag(self, well: str, template: str, check: str, ts: int, detail: str, value=None) -> None:
        key = (well, template, check)
        if key not in self.counts:
            print(f"  NEW ISSUE  {iso(ts)}  {well:<6} {template:<22} {check:<14} {detail}")
            self.examples[key] = detail
        self.counts[key] += 1
        self.total_flags += 1
        self.first_seen.setdefault(key, ts)
        self.last_seen[key] = ts

        event = {"ts": ts, "check": check, "detail": detail}
        if value is not None:
            event["value"] = value
        self.client.publish(f"dq/{well}/{template}", json.dumps(event), qos=0)

    # ---------- per message ----------
    def on_reading(self, well: str, template_name: str, msg: dict) -> None:
        now = time.time()
        template = self.templates.get(template_name)
        ts = int(msg["ts"])
        if template is None or well not in self.assets:
            self.flag(well, template_name, "unknown_tag", ts, "tag is not in the registry")
            return

        with self.lock:
            self.last_msg_wall = now
            self.interval_s = float(msg.get("interval_s", self.interval_s))
            self.latencies.append(now - float(msg["sent_at"]))
            if self.feed_alarm:
                print(f"  RECOVERED  feed is flowing again")
                self.feed_alarm = False

            # Well-level bookkeeping: new field day for this well?
            prev = self.well_last_ts.get(well)
            if prev is None or ts > prev:
                if prev is not None and ts - prev > DAY:
                    missing = (ts - prev) // DAY - 1
                    self.flag(well, "_well", "well_gap", ts, f"{missing} day(s) with no data before this date")
                self.well_last_ts[well] = ts
                self.well_first_ts.setdefault(well, ts)
                self.well_days[well] += 1

            key = (well, template_name)
            self.tag_last_ts[key] = ts
            if key in self.stale:
                self.stale.discard(key)
                print(f"  RECOVERED  {iso(ts)}  {well:<6} {template_name}")

            value = msg.get("value")
            flags_before = self.total_flags
            if template_name == "on_stream_hours":
                self.flowing[(well, ts)] = bool(value and value > 0)
            flowing = self.flowing.get((well, ts), False)

            # 1. Units: if the unit is wrong, every other check on the value is meaningless
            if msg.get("unit") != template.unit:
                self.flag(well, template_name, "unit_mismatch", ts,
                          f"got {msg.get('unit')}, standard is {template.unit}", value)
                self.last_value.pop(key, None)
                return

            # 2. Completeness of the value itself
            if msg.get("quality") != "good" or value is None:
                self.flag(well, template_name, "missing_value", ts, "source sent no value")
                self.repeat_run[key] = 0
                return
            self.good_values[well] += 1

            # 3. Physical range from the registry
            if not (template.min <= value <= template.max):
                self.flag(well, template_name, "out_of_range", ts,
                          f"{value:g} {template.unit} outside [{template.min:g}, {template.max:g}]", value)

            # 4. A pressure/temperature gauge reading exactly 0 while the well flows = dead gauge
            if template.zero_is_bad_when_flowing and value == 0 and flowing:
                self.flag(well, template_name, "bad_zero", ts, "reads 0 while the well is flowing", value)

            # 5. Frozen value: real sensors drift, an identical average day after day is suspicious
            if template.frozen_check and flowing and value != 0 and self.last_value.get(key) == value:
                self.repeat_run[key] += 1
                if self.repeat_run[key] >= FROZEN_READINGS - 1:
                    self.flag(well, template_name, "frozen", ts,
                              f"same value {value:g} for {self.repeat_run[key] + 1} readings", value)
            else:
                self.repeat_run[key] = 0
            self.last_value[key] = value

            if self.total_flags == flags_before:
                self.valid_values[well] += 1

    # ---------- on a timer ----------
    def periodic(self) -> None:
        now = time.time()
        with self.lock:
            # Stale tags: compare each tag with the newest data from its own well.
            # A well that stops reporting entirely (shut in, end of life) is not "stale";
            # one tag going quiet while its siblings keep arriving is.
            for well, well_ts in self.well_last_ts.items():
                for name in self.templates:
                    key = (well, name)
                    last = self.tag_last_ts.get(key, self.well_first_ts[well] - DAY)
                    if well_ts - last >= STALE_DAYS * DAY and key not in self.stale:
                        self.stale.add(key)
                        self.flag(well, name, "stale_tag", well_ts,
                                  f"no data since {iso(last) if key in self.tag_last_ts else 'start'}"
                                  f" while {well} keeps reporting")

            # Whole-feed health, measured in wall-clock time
            quiet_for = None if self.last_msg_wall is None else now - self.last_msg_wall
            threshold = max(5.0, 5 * self.interval_s)
            if (quiet_for is not None and quiet_for > threshold and not self.feed_alarm
                    and self.publisher_status != "finished"):
                self.feed_alarm = True
                print(f"  ALARM      feed stale: nothing received for {quiet_for:.0f}s "
                      f"(publisher status: {self.publisher_status})")

            lat = sorted(self.latencies)
            lat_avg = statistics.fmean(lat) * 1000 if lat else 0.0
            lat_p95 = lat[int(0.95 * (len(lat) - 1))] * 1000 if lat else 0.0

            for well, well_ts in self.well_last_ts.items():
                expected = self.well_days[well] * len(self.templates)
                open_issues = sum(1 for (w, _) in self.stale if w == well)
                summary = {
                    "ts": well_ts,
                    "completeness_pct": round(100 * self.good_values[well] / expected, 2) if expected else 0,
                    "validity_pct": round(100 * self.valid_values[well] / self.good_values[well], 2)
                                    if self.good_values[well] else 0,
                    "issues_total": sum(c for (w, _, _), c in self.counts.items() if w == well),
                    "stale_tags": open_issues,
                    "latency_ms_avg": round(lat_avg, 2),
                    "latency_ms_p95": round(lat_p95, 2),
                    "feed_ok": 0 if self.feed_alarm else 1,
                    "publisher_online": 1 if self.publisher_status in ("online", "finished") else 0,
                }
                self.client.publish(f"dq_summary/{well}", json.dumps(summary), qos=0)

    # ---------- report ----------
    def write_report(self) -> None:
        REPORTS.mkdir(exist_ok=True)
        rows = sorted(self.counts.items(), key=lambda kv: (-kv[1], kv[0]))
        with open(REPORTS / "dq_report.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["well", "tag", "check", "count", "first_seen", "last_seen", "example"])
            for (well, tag, check), n in rows:
                key = (well, tag, check)
                w.writerow([well, tag, check, n, iso(self.first_seen[key]), iso(self.last_seen[key]),
                            self.examples[key]])

        lat = sorted(self.latencies)
        lines = ["# Data-quality summary", "",
                 f"Generated {datetime.now():%Y-%m-%d %H:%M}.", "",
                 "Completeness = share of expected readings that arrived with a value.",
                 "Validity = share of those values that passed every check.", "",
                 "| Well | Field days | Completeness | Validity | Issues |", "|---|---:|---:|---:|---:|"]
        for well in self.assets:
            if not self.well_days[well]:
                continue
            expected = self.well_days[well] * len(self.templates)
            issues = sum(c for (w, _, _), c in self.counts.items() if w == well)
            valid = 100 * self.valid_values[well] / self.good_values[well] if self.good_values[well] else 0
            lines.append(f"| {well} | {self.well_days[well]:,} | "
                         f"{100 * self.good_values[well] / expected:.1f}% | {valid:.1f}% | {issues:,} |")
        if lat:
            lines += ["", f"Transport latency: average {statistics.fmean(lat) * 1000:.1f} ms, "
                          f"p95 {lat[int(0.95 * (len(lat) - 1))] * 1000:.1f} ms "
                          f"(last {len(lat):,} messages)."]
        lines += ["", "| Well | Tag | Check | Count | First | Last |", "|---|---|---|---:|---|---|"]
        for (well, tag, check), n in rows:
            key = (well, tag, check)
            lines.append(f"| {well} | {tag} | {check} | {n:,} | {iso(self.first_seen[key])} | "
                         f"{iso(self.last_seen[key])} |")
        (REPORTS / "dq_summary.md").write_text("\n".join(lines) + "\n")
        print(f"\nReport written to {REPORTS / 'dq_report.csv'} and dq_summary.md")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--broker", default=os.getenv("MQTT_HOST", "localhost"))
    p.add_argument("--port", type=int, default=int(os.getenv("MQTT_PORT", "1883")))
    p.add_argument("--exit-when-done", action="store_true",
                   help="stop and write the report when the publisher says it finished")
    args = p.parse_args()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="volve-quality-monitor")
    monitor = QualityMonitor(client)
    done = threading.Event()

    def on_connect(c, userdata, flags, reason_code, properties):
        c.subscribe([("volve/#", 1), ("status/publisher", 1)])
        print(f"Monitoring {len(monitor.assets)} wells x {len(monitor.templates)} templates "
              f"on {args.broker}:{args.port}")

    def on_message(c, userdata, msg):
        if msg.topic == "status/publisher":
            status = msg.payload.decode()
            if status != monitor.publisher_status:
                print(f"  PUBLISHER  {status}")
            monitor.publisher_status = status
            if status == "finished" and args.exit_when_done:
                done.set()
            return
        try:
            _, well, template = msg.topic.split("/")
            monitor.on_reading(well, template, json.loads(msg.payload))
        except (ValueError, KeyError, json.JSONDecodeError) as e:
            print(f"  BAD MESSAGE on {msg.topic}: {e}")

    # `docker stop` and `kill` send SIGTERM; treat it like Ctrl-C so the report still gets written
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt))

    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(args.broker, args.port, keepalive=30)
    client.loop_start()
    try:
        while not done.wait(SUMMARY_EVERY_S):
            monitor.periodic()
        time.sleep(1)           # let the last messages drain
        monitor.periodic()
    except KeyboardInterrupt:
        pass
    finally:
        monitor.write_report()
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
