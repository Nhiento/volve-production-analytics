# Batch pipeline, one command per step.
#   make pipeline   clean the raw file, build the Python summaries, then build and test the dbt warehouse
#   make test       unit tests for the cleaning script and the real-time quality rules
#
# The real-time demo (Grafana) is separate: see realtime/README.md.

.PHONY: pipeline clean-data marts dbt test

pipeline: clean-data marts dbt

clean-data:
	python python/clean.py

marts:
	python python/monthly_totals.py
	python python/decline_curves.py

dbt:
	cd dbt && dbt build --profiles-dir .

test:
	python -m pytest -q tests
	cd realtime && python -m pytest -q
