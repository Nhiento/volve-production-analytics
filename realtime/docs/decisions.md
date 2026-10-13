# Technical decision records

Short records of the choices behind this pipeline: what was decided, why, and what it costs.

---

### DR-001: MQTT for transport, not OPC-UA

**Decision.** The publisher sends readings over MQTT.

**Why.** MQTT is publish/subscribe: the edge publishes once and any number of consumers
(Telegraf, the quality monitor, anything added later) subscribe without the edge knowing
about them. It is light enough for constrained links like offshore satellite. OPC-UA is
client/server and richer (typed data, built-in information models, security), and is the
usual choice *on* the plant network, next to the controllers.

**Trade-off.** Plain MQTT has no data model, so topic names and payload schema have to be
governed separately. That is the job of the tag registry and the message contracts in
`architecture.md`. Sparkplug B adds a standard model on top of MQTT and would be the next step.

---

### DR-002: One registry drives every component

**Decision.** Units, valid ranges and check settings live only in `tags/*.csv`. The
publisher and the monitor both read them; nothing is hard-coded.

**Why.** If the standard says downhole pressure is in bar with a 0–450 range, that should be
written once. Adding a well is one row in `assets.csv`; adding a measurement is one row in
`tag_templates.csv`. This is the PI Asset Framework template idea.

---

### DR-003: A gauge reading exactly 0 while the well flows is bad data, not a value

**Decision.** For downhole and wellhead pressure and temperature, a reading of exactly 0 on a
day with on-stream hours > 0 is flagged `bad_zero` and excluded from validity.

**Why.** A producing well cannot have 0 bar at the bottom of the hole or 0 °C at the wellhead.
Exactly 0, rather than a small number, is what a dead or disconnected gauge often reports.
On F-12 the downhole pressure **and** temperature both go to 0 on 2010-10-12 and stay there
until the end of the data, 1,907 producing days. Both readings come from the same downhole
gauge, which points to one failed instrument, not two.

**Trade-off.** Annulus pressure can legitimately be 0 (bled off), so the rule is per template,
not global.

---

### DR-004: Stale means "one tag went quiet while its well keeps reporting"

**Decision.** A tag is `stale_tag` when it has not arrived for 3 field days while other tags
from the same well keep arriving. A whole well going quiet is **not** stale.

**Why.** Wells stop reporting for real reasons: F-1 C's records end in April 2016 while the
other wells continue. Comparing each tag with its own well avoids false alarms for wells that are shut in.
Whole-feed outages are caught separately, in wall-clock time (`feed_stale`), and by the
publisher's MQTT Last Will.

---

### DR-005: Units are assumed for most columns and checked on every message

**Decision.** The Volve file only states the unit for choke opening (%). Pressures are taken
as bar, temperatures as °C, volumes as Sm3, based on their value ranges (downhole pressure
around 250, wellhead temperature around 90). Every message carries a unit and the monitor
rejects any message whose unit differs from the registry.

**Why.** Unit mix-ups are a classic integration failure: a vendor configured for psi sends
580 for what should be 40 bar, the number is still "in range" for some checks and goes
straight into a dashboard. Rejecting on unit first means range checks never run on a
misread value.

---

### DR-006: Security is out of scope for the local demo

**Decision.** Mosquitto allows anonymous connections, InfluxDB and Grafana use demo
passwords, nothing uses TLS.

**What a real deployment needs.** TLS on the broker (port 8883), per-client credentials or
certificates, topic access control (the edge may only publish to its own `volve/<asset>/#`),
the broker in a DMZ between the OT and IT networks with firewall rules allowing only the
needed ports, and secrets kept out of the repo.

---

### DR-007: Replay at accelerated time; the timestamp is the field date

**Decision.** One field day is replayed per real second by default, and each reading is
stored at its original date (2008–2016), not at the time it was replayed.

**Why.** Storing at the field date keeps the history correct and repeatable: replaying twice
writes the same points. Latency is still measurable because every message also carries the
wall-clock send time.

**Trade-off.** The Grafana time range is pinned to 2008–2016 instead of "last 6 hours", and
the bucket has no retention limit (InfluxDB would otherwise refuse 2008 data).

---

### DR-008: Report the 25-hour days instead of capping them

**Decision.** `on_stream_hours` above 24 is flagged `out_of_range` rather than silently capped.

**Why.** Every one of these days is a Sunday at the end of October (2008-10-26, 2009-10-25,
2010-10-31, 2013-10-27, 2014-10-26): the night clocks go back for daylight saving and the day
really has 25 hours. That is a known, explainable cause, but the data platform should surface
it so anyone computing uptime (hours ÷ 24) knows to handle it. The notebook caps uptime at
100% for the same reason.
