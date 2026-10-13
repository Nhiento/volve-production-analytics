# Real-time layer: Volve as a live sensor feed

This folder turns the historical Volve well data into a live industrial-style data feed:
an edge publisher streams 72 sensor tags over MQTT, Telegraf stores them in an InfluxDB
historian, Grafana shows them live, and a quality monitor checks every reading against a
governed tag registry.

```
Volve Excel → replay_publisher.py → Mosquitto (MQTT) → Telegraf → InfluxDB → Grafana
                                          ↕
                                 quality_monitor.py → data-quality events + reports
```

- **Architecture, tag model, source-to-target mapping:** [docs/architecture.md](docs/architecture.md)
- **Why it is built this way:** [docs/decisions.md](docs/decisions.md)
- **Full data-quality results:** [docs/sample_dq_summary.md](docs/sample_dq_summary.md)

## What it found in the real data

Replaying all 9,143 producing well-days (2008–2016):

| Well | Completeness | Validity | Main finding |
|---|---:|---:|---|
| F-12 | 99.8% | 89.5% | Downhole gauge dead from 2010-10-12: pressure and temperature both read 0 for 1,907 producing days |
| F-14 | 98.0% | 99.7% | Annulus pressure missing for 523 days (2008–2010); choke opening missing for 196 days |
| F-11 | 99.7% | 99.9% | Clean |
| F-1C | 91.7% | 99.9% | Annulus pressure missing on 728 of 744 days |
| F-15D | 100.0% | 99.9% | Clean |
| F-5 | 74.5% | 100.0% | No downhole gauge data at all (pressure, temperature, tubing ΔP) |

*Completeness* = expected readings that arrived with a value. *Validity* = arrived values
that passed every check.

Also flagged: 101 days where a well skipped a day (F-12 and F-14 have 46 each, on exactly
the same dates, so it is a platform reporting gap, not a well problem), 13 on-stream values
above 24 hours (all on late-October Sundays, when clocks go back for daylight saving), negative water volumes, and days where several
tags on several wells repeat the exact same value (2011-04-20, 2015-01-19), which points to
values being copied forward by the reporting system rather than many sensors failing at once.

## Run it

Needs Docker Desktop.

```bash
cd realtime
docker compose up -d --build                          # broker, historian, collector, Grafana, monitor
docker compose run --rm publisher --speed 5           # replay all history (~10 min at 5 days/s)
```

Open **http://localhost:3000** (admin / volve-admin). The *Volve real-time wells* dashboard
fills in as the replay runs. Pick a well at the top. The monitor's console output:

```bash
docker compose logs -f monitor
```

A shorter replay: `docker compose run --rm publisher --speed 10 --start 2014-01-01`

Stop and wipe everything: `docker compose down -v`

**Start clean before screenshots or a demo.** InfluxDB keeps everything you have ever
replayed, including fault-demo data (the psi spike from `--wrong-unit`). Wipe it and do
one full replay:

```bash
docker compose down -v
docker compose up -d --build
docker compose run --rm publisher --speed 10
```

### Break it on purpose

```bash
docker compose run --rm publisher --speed 5 --start 2015-03-01 --fault-after-days 10 \
  --drop F-14.downhole_pressure \
  --freeze F-11.wellhead_pressure \
  --wrong-unit F-12.wellhead_pressure \
  --crash-after-days 40
```

The monitor reports each one:

```
NEW ISSUE  2015-03-11  F-12   wellhead_pressure   unit_mismatch  got psi, standard is bar
NEW ISSUE  2015-03-13  F-11   wellhead_pressure   frozen         same value 40.4217 for 3 readings
NEW ISSUE  2015-03-16  F-14   downhole_pressure   stale_tag      no data since 2015-03-10 while F-14 keeps reporting
PUBLISHER  offline
ALARM      feed stale: nothing received for 6s (publisher status: offline)
```

### Without Docker (Python only)

You still need an MQTT broker (`brew install mosquitto && mosquitto`), then:

```bash
pip install -r requirements.txt
python quality_monitor.py --exit-when-done     # terminal 1
python replay_publisher.py --speed 20          # terminal 2
python -m pytest -q test_quality_checks.py     # unit tests for the rules
```

The report lands in `reports/dq_summary.md` and `reports/dq_report.csv`.

## Files

```
realtime/
├── tags/
│   ├── assets.csv              ← one row per well
│   └── tag_templates.csv       ← one row per measurement: source column, unit, range, checks
├── registry.py                 ← builds the 72 tags (asset × template)
├── replay_publisher.py         ← the edge: Excel → MQTT, with fault injection
├── quality_monitor.py          ← the checks, scorecard and reports
├── test_quality_checks.py      ← unit tests for every rule
├── docker-compose.yml
├── Dockerfile                  ← image for the publisher and monitor
├── config/
│   ├── mosquitto.conf
│   ├── telegraf.conf           ← MQTT topics → InfluxDB tags/fields
│   └── grafana/                ← data source + dashboard, loaded automatically
└── docs/
    ├── architecture.md
    ├── decisions.md
    ├── sample_dq_summary.md
    └── sample_dq_report.csv
```
