# Data-quality summary

Generated 2026-10-13 12:32.

Completeness = share of expected readings that arrived with a value.
Validity = share of those values that passed every check.

| Well | Field days | Completeness | Validity | Issues |
|---|---:|---:|---:|---:|
| F-12 | 3,056 | 99.8% | 89.5% | 3,980 |
| F-14 | 3,056 | 98.0% | 99.7% | 888 |
| F-11 | 1,165 | 99.7% | 99.9% | 63 |
| F-1C | 744 | 91.7% | 99.9% | 744 |
| F-15D | 978 | 100.0% | 99.9% | 8 |
| F-5 | 144 | 74.5% | 100.0% | 443 |

Transport latency: average 16.7 ms, p95 28.6 ms (last 2,000 messages).

| Well | Tag | Check | Count | First | Last |
|---|---|---|---:|---|---|
| F-12 | downhole_pressure | bad_zero | 1,907 | 2010-10-12 | 2016-08-12 |
| F-12 | downhole_temperature | bad_zero | 1,907 | 2010-10-12 | 2016-08-12 |
| F-1C | annulus_pressure | missing_value | 728 | 2014-04-23 | 2016-04-20 |
| F-14 | annulus_pressure | missing_value | 523 | 2008-07-09 | 2010-03-23 |
| F-14 | choke_opening | missing_value | 196 | 2008-02-12 | 2011-08-03 |
| F-5 | downhole_pressure | missing_value | 144 | 2016-04-12 | 2016-09-17 |
| F-5 | downhole_temperature | missing_value | 144 | 2016-04-12 | 2016-09-17 |
| F-5 | tubing_dp | missing_value | 144 | 2016-04-12 | 2016-09-17 |
| F-14 | downhole_temperature | frozen | 55 | 2011-04-20 | 2016-03-11 |
| F-12 | _well | well_gap | 46 | 2008-04-29 | 2014-02-08 |
| F-14 | _well | well_gap | 46 | 2008-04-29 | 2014-02-08 |
| F-12 | choke_opening | missing_value | 44 | 2008-03-27 | 2011-08-03 |
| F-14 | downhole_pressure | bad_zero | 15 | 2009-04-05 | 2013-09-28 |
| F-14 | downhole_temperature | bad_zero | 15 | 2009-04-05 | 2013-09-28 |
| F-12 | annulus_pressure | missing_value | 13 | 2009-11-14 | 2009-11-26 |
| F-5 | wellhead_temperature | missing_value | 8 | 2016-04-12 | 2016-04-19 |
| F-12 | annulus_pressure | frozen | 7 | 2011-04-20 | 2015-01-19 |
| F-12 | downhole_pressure | frozen | 7 | 2008-05-13 | 2008-05-19 |
| F-12 | downhole_temperature | frozen | 7 | 2008-05-13 | 2008-05-19 |
| F-11 | annulus_pressure | missing_value | 6 | 2013-07-10 | 2013-07-30 |
| F-11 | choke_dp | missing_value | 6 | 2013-07-10 | 2013-07-30 |
| F-11 | downhole_pressure | missing_value | 6 | 2013-07-10 | 2013-07-30 |
| F-11 | downhole_temperature | missing_value | 6 | 2013-07-10 | 2013-07-30 |
| F-11 | tubing_dp | missing_value | 6 | 2013-07-10 | 2013-07-30 |
| F-11 | wellhead_pressure | missing_value | 6 | 2013-07-10 | 2013-07-30 |
| F-11 | wellhead_temperature | missing_value | 6 | 2013-07-10 | 2013-07-30 |
| F-12 | downhole_pressure | missing_value | 6 | 2009-01-07 | 2009-01-12 |
| F-12 | downhole_temperature | missing_value | 6 | 2009-01-07 | 2009-01-12 |
| F-12 | tubing_dp | missing_value | 6 | 2009-01-07 | 2009-01-12 |
| F-12 | wellhead_temperature | frozen | 6 | 2011-04-22 | 2015-01-19 |
| F-14 | downhole_pressure | missing_value | 6 | 2009-01-07 | 2009-01-12 |
| F-14 | downhole_temperature | missing_value | 6 | 2009-01-07 | 2009-01-12 |
| F-14 | tubing_dp | missing_value | 6 | 2009-01-07 | 2009-01-12 |
| F-14 | wellhead_temperature | frozen | 6 | 2011-04-22 | 2015-01-19 |
| F-12 | on_stream_hours | out_of_range | 5 | 2008-10-26 | 2014-10-26 |
| F-12 | tubing_dp | frozen | 5 | 2011-04-22 | 2015-01-19 |
| F-12 | wellhead_pressure | frozen | 5 | 2011-04-22 | 2015-01-19 |
| F-14 | on_stream_hours | out_of_range | 5 | 2008-10-26 | 2014-10-26 |
| F-11 | _well | well_gap | 3 | 2013-09-20 | 2014-02-08 |
| F-14 | tubing_dp | frozen | 3 | 2011-04-20 | 2015-01-19 |
| F-1C | downhole_pressure | missing_value | 3 | 2014-04-08 | 2014-04-10 |
| F-1C | downhole_temperature | missing_value | 3 | 2014-04-08 | 2014-04-10 |
| F-1C | tubing_dp | missing_value | 3 | 2014-04-08 | 2014-04-10 |
| F-5 | _well | well_gap | 3 | 2016-05-05 | 2016-09-13 |
| F-11 | choke_opening | missing_value | 2 | 2013-07-10 | 2013-07-12 |
| F-11 | downhole_pressure | bad_zero | 2 | 2013-07-28 | 2013-07-29 |
| F-11 | downhole_temperature | bad_zero | 2 | 2013-07-28 | 2013-07-29 |
| F-11 | on_stream_hours | out_of_range | 2 | 2013-10-27 | 2014-10-26 |
| F-11 | wellhead_pressure | bad_zero | 2 | 2013-07-28 | 2013-07-29 |
| F-11 | wellhead_temperature | bad_zero | 2 | 2013-07-28 | 2013-07-29 |
| F-12 | water_volume | out_of_range | 2 | 2008-04-23 | 2012-08-13 |
| F-14 | water_volume | out_of_range | 2 | 2009-03-03 | 2012-08-13 |
| F-15D | _well | well_gap | 2 | 2014-01-31 | 2014-02-08 |
| F-11 | annulus_pressure | frozen | 1 | 2015-01-19 | 2015-01-19 |
| F-11 | downhole_pressure | frozen | 1 | 2015-01-19 | 2015-01-19 |
| F-11 | downhole_temperature | frozen | 1 | 2015-01-19 | 2015-01-19 |
| F-11 | tubing_dp | frozen | 1 | 2015-01-19 | 2015-01-19 |
| F-11 | wellhead_pressure | frozen | 1 | 2015-01-19 | 2015-01-19 |
| F-11 | wellhead_temperature | frozen | 1 | 2015-01-19 | 2015-01-19 |
| F-12 | wellhead_pressure | bad_zero | 1 | 2008-06-03 | 2008-06-03 |
| F-14 | annulus_pressure | frozen | 1 | 2015-01-19 | 2015-01-19 |
| F-14 | downhole_pressure | frozen | 1 | 2015-01-19 | 2015-01-19 |
| F-14 | wellhead_pressure | bad_zero | 1 | 2009-09-05 | 2009-09-05 |
| F-14 | wellhead_pressure | frozen | 1 | 2015-01-19 | 2015-01-19 |
| F-15D | annulus_pressure | frozen | 1 | 2015-01-19 | 2015-01-19 |
| F-15D | downhole_pressure | frozen | 1 | 2015-01-19 | 2015-01-19 |
| F-15D | downhole_temperature | frozen | 1 | 2015-01-19 | 2015-01-19 |
| F-15D | tubing_dp | frozen | 1 | 2015-01-19 | 2015-01-19 |
| F-15D | wellhead_pressure | frozen | 1 | 2015-01-19 | 2015-01-19 |
| F-15D | wellhead_temperature | frozen | 1 | 2015-01-19 | 2015-01-19 |
| F-1C | _well | well_gap | 1 | 2014-07-08 | 2014-07-08 |
| F-1C | downhole_pressure | frozen | 1 | 2015-01-19 | 2015-01-19 |
| F-1C | downhole_temperature | frozen | 1 | 2015-01-19 | 2015-01-19 |
| F-1C | on_stream_hours | out_of_range | 1 | 2014-10-26 | 2014-10-26 |
| F-1C | tubing_dp | frozen | 1 | 2015-01-19 | 2015-01-19 |
| F-1C | wellhead_pressure | frozen | 1 | 2015-01-19 | 2015-01-19 |
| F-1C | wellhead_temperature | frozen | 1 | 2015-01-19 | 2015-01-19 |
