PYTHON ?= python

.PHONY: test plots all

test:
	$(PYTHON) run.py test

plots:
	$(PYTHON) run.py plots

all:
	$(PYTHON) run.py all
