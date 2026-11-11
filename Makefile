# Batch pipeline, one command per step.
#   make pipeline   clean the raw file, then build and test the dbt warehouse
#   make test       unit tests for the cleaning script and the real-time quality rules
#
# The real-time demo (Grafana) is separate: see realtime/README.md.

.PHONY: pipeline clean-data dbt test

pipeline: clean-data dbt

clean-data:
	python python/clean.py

dbt:
	cd dbt && dbt build --profiles-dir .

test:
	python -m pytest -q tests
	cd realtime && python -m pytest -q
