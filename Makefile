# DataCivicLab — Partecipate Monitor
TOOLKIT = toolkit
PREFIX = partecipate-pubbliche

DATASETS := $(shell find datasets -name dataset.yml 2>/dev/null | sort)

.PHONY: run check registry registry-write dashboard clean help

run:
	@for f in $(DATASETS); do \
		echo "=== $$f ==="; \
		$(TOOLKIT) run --config "$$f" || exit 1; \
	done

check:
	@for f in $(DATASETS); do \
		$(TOOLKIT) run preflight --config "$$f" > /dev/null 2>&1 || exit 1; \
	done
	@echo "All configs valid"

registry:
	$(TOOLKIT) registry build --prefix $(PREFIX)

registry-write:
	$(TOOLKIT) registry build --prefix $(PREFIX) --write

dashboard:
	cd dashboard && streamlit run app.py

clean:
	rm -rf out/

help:
	@grep -E '^[a-zA-Z_-]+:' Makefile | sort
