PY ?= python
.PHONY: data run app test demo quality
data:      ## download real ECB rates via Frankfurter (needs internet)
	$(PY) -m fxlab init && $(PY) -m fxlab ingest --start 2010-01-01
run:       ## walk-forward experiment on real data
	$(PY) -m fxlab run --horizons 1 5 20
quality:
	$(PY) -m fxlab quality
app:
	$(PY) -m fxlab app
test:
	$(PY) -m pytest -q
demo:      ## offline demo using SIMULATED data in a separate DB (never mixed with real data)
	FXLAB_DB=data/demo.db $(PY) -m fxlab demo && FXLAB_DB=data/demo.db $(PY) -m fxlab run --quick && FXLAB_DB=data/demo.db $(PY) -m fxlab app
