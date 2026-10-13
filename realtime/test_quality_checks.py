"""Unit tests for the data-quality rules. No broker needed.

Run from the realtime/ folder:
    python -m pytest -q test_quality_checks.py
"""
import time

from quality_monitor import DAY, QualityMonitor

T0 = 1_420_070_400  # 2015-01-01 00:00 UTC


class FakeClient:
    """Stands in for the MQTT client and records what the monitor publishes."""
    def __init__(self):
        self.published = []

    def publish(self, topic, payload, qos=0):
        self.published.append((topic, payload))


def reading(value, ts, unit="bar", quality="good"):
    msg = {"ts": ts, "unit": unit, "quality": quality, "sent_at": time.time(), "interval_s": 1.0}
    if value is not None:
        msg["value"] = value
    return msg


def flowing(m, well, ts, hours=24.0):
    m.on_reading(well, "on_stream_hours", reading(hours, ts, unit="h"))


def checks(m, well, tag):
    return {check: n for (w, t, check), n in m.counts.items() if w == well and t == tag}


def new_monitor():
    return QualityMonitor(FakeClient())


def test_zero_pressure_while_flowing_is_bad():
    m = new_monitor()
    flowing(m, "F-12", T0)
    m.on_reading("F-12", "downhole_pressure", reading(0.0, T0))
    assert checks(m, "F-12", "downhole_pressure") == {"bad_zero": 1}


def test_zero_pressure_while_shut_in_is_fine():
    m = new_monitor()
    flowing(m, "F-12", T0, hours=0.0)
    m.on_reading("F-12", "downhole_pressure", reading(0.0, T0))
    assert checks(m, "F-12", "downhole_pressure") == {}


def test_frozen_after_three_identical_readings():
    m = new_monitor()
    for day in range(3):
        ts = T0 + day * DAY
        flowing(m, "F-11", ts)
        m.on_reading("F-11", "wellhead_pressure", reading(40.42, ts))
    assert checks(m, "F-11", "wellhead_pressure") == {"frozen": 1}


def test_wrong_unit_is_rejected_before_range_check():
    m = new_monitor()
    flowing(m, "F-12", T0)
    m.on_reading("F-12", "wellhead_pressure", reading(580.0, T0, unit="psi"))  # 40 bar in psi
    assert checks(m, "F-12", "wellhead_pressure") == {"unit_mismatch": 1}


def test_out_of_range():
    m = new_monitor()
    flowing(m, "F-12", T0)
    m.on_reading("F-12", "water_volume", reading(-14.2, T0, unit="Sm3"))
    assert checks(m, "F-12", "water_volume") == {"out_of_range": 1}


def test_missing_value_counts_against_completeness():
    m = new_monitor()
    flowing(m, "F-5", T0)
    m.on_reading("F-5", "downhole_pressure", reading(None, T0, quality="no_data"))
    assert checks(m, "F-5", "downhole_pressure") == {"missing_value": 1}
    assert round(m.completeness("F-5"), 6) == round(100 / 12, 6)  # 1 of 12 expected readings had a value


def test_stale_tag_only_when_rest_of_well_keeps_reporting():
    m = new_monitor()
    for day in range(5):
        ts = T0 + day * DAY
        flowing(m, "F-14", ts)
        if day == 0:
            m.on_reading("F-14", "downhole_pressure", reading(250.0, ts))
    m.periodic()
    assert checks(m, "F-14", "downhole_pressure") == {"stale_tag": 1}


def test_well_gap():
    m = new_monitor()
    flowing(m, "F-15D", T0)
    flowing(m, "F-15D", T0 + 3 * DAY)
    assert checks(m, "F-15D", "_well") == {"well_gap": 1}


def test_unknown_tag_is_flagged():
    m = new_monitor()
    m.on_reading("F-12", "mystery_sensor", reading(1.0, T0))
    assert checks(m, "F-12", "mystery_sensor") == {"unknown_tag": 1}


def test_replaying_the_same_dates_does_not_double_count():
    m = new_monitor()
    for _ in range(3):                      # the same three days, replayed three times
        for day in range(3):
            ts = T0 + day * DAY
            flowing(m, "F-12", ts)
            m.on_reading("F-12", "downhole_pressure", reading(0.0, ts))
    assert m.well_days["F-12"] == 3
    assert round(m.completeness("F-12"), 6) == round(2 / 12 * 100, 6)      # 2 of 12 templates sent, every day
    assert m.validity("F-12") == 50.0                    # on_stream_hours valid, pressure bad
    assert checks(m, "F-12", "downhole_pressure") == {"bad_zero": 3}


def test_restarted_replay_does_not_fake_a_frozen_sensor():
    m = new_monitor()
    for start in (0, 0):                    # replay day 0-1, then start over at day 0
        for day in range(start, start + 2):
            ts = T0 + day * DAY
            flowing(m, "F-11", ts)
            m.on_reading("F-11", "wellhead_pressure", reading(40.0 + day, ts))
    assert checks(m, "F-11", "wellhead_pressure") == {}
