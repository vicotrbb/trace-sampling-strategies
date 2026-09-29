PYTHON ?= .venv/bin/python
RAW ?= data/raw/homelab
REVISION_RAW ?= data/raw/revision-20260924
COST_RAW ?= data/raw/final-cost-20260925
SECOND_RAW ?= data/raw/second-audit-20260925
THIRD_RAW ?= data/raw/third-audit-20260925
FIFTH_RAW ?= data/raw/fifth-audit-20260928
.NOTPARALLEL:
.PHONY: verify-third analyze-third analyze-fourth homelab-third all analyze analyze-original analyze-revision analyze-cost analyze-second verify verify-original verify-revision verify-cost verify-second verify-proof paper homelab homelab-revision homelab-cost homelab-second
all: verify verify-proof analyze paper
verify: verify-original verify-revision verify-cost verify-second verify-third verify-fifth
verify-original:
	$(PYTHON) scripts/verify_artifact.py $(RAW)
	$(PYTHON) scripts/summarize_probes.py $(RAW)
verify-revision:
	$(PYTHON) scripts/verify_revision.py $(REVISION_RAW)/confirm-v1
	$(PYTHON) scripts/verify_followups.py $(REVISION_RAW)
verify-cost:
	$(PYTHON) scripts/verify_cost_study.py $(COST_RAW)/pilot-v1
	$(PYTHON) scripts/verify_cost_study.py $(COST_RAW)/confirm-v1
verify-second:
	$(PYTHON) scripts/verify_second_audit.py load $(SECOND_RAW)/load-confirm-v1
	$(PYTHON) scripts/verify_second_audit.py corpus $(SECOND_RAW)/diagnosis-confirm-v1
	$(PYTHON) scripts/verify_second_audit_contract.py
verify-proof:
	lean proofs/TraceSampling.lean
analyze: analyze-original analyze-revision analyze-cost analyze-second analyze-third analyze-fourth analyze-fifth
analyze-original:
	XDG_CACHE_HOME=$(CURDIR)/tmp/cache MPLCONFIGDIR=$(CURDIR)/tmp/matplotlib $(PYTHON) scripts/analyze.py --raw $(RAW)
	$(PYTHON) scripts/summarize_probes.py $(RAW) --write
analyze-revision:
	XDG_CACHE_HOME=$(CURDIR)/tmp/cache MPLCONFIGDIR=$(CURDIR)/tmp/matplotlib $(PYTHON) scripts/analyze_revision.py --raw $(REVISION_RAW)
analyze-cost:
	$(PYTHON) scripts/analyze_cost_study.py $(COST_RAW)/confirm-v1
	XDG_CACHE_HOME=$(CURDIR)/tmp/cache MPLCONFIGDIR=$(CURDIR)/tmp/matplotlib $(PYTHON) scripts/plot_cost_study.py
	$(PYTHON) scripts/inspect_cost_serialization.py $(COST_RAW)/confirm-v1
analyze-second:
	$(PYTHON) scripts/analyze_second_audit.py --raw $(SECOND_RAW)
	$(PYTHON) scripts/verify_second_audit.py replay $(SECOND_RAW)/diagnosis-replay-v1 --corpus $(SECOND_RAW)/diagnosis-confirm-v1 --analysis data/derived/second-audit-20260925
	$(PYTHON) scripts/verify_load_summaries.py --raw $(SECOND_RAW)/load-confirm-v1
	XDG_CACHE_HOME=$(CURDIR)/tmp/cache MPLCONFIGDIR=$(CURDIR)/tmp/matplotlib $(PYTHON) scripts/render_second_audit.py
paper:
	$(PYTHON) scripts/prepare_mathematical_appendix.py
	cd paper && latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
	mkdir -p output/pdf
	cp paper/main.pdf output/pdf/trace-sampling-collector-boundary.pdf
homelab:
	bash experiments/run_homelab.sh
homelab-revision:
	bash experiments/revision/run_homelab.sh
homelab-cost:
	bash experiments/final_cost/run_homelab.sh
homelab-second:
	bash experiments/second_audit/run_homelab.sh

verify-third:
	$(PYTHON) scripts/verify_third_audit.py load $(THIRD_RAW)/load-confirm-v1
	$(PYTHON) scripts/verify_third_audit.py replay $(THIRD_RAW)/diagnosis-replay-v1 --corpus $(THIRD_RAW)/diagnosis-confirm-v1 --calibration $(THIRD_RAW)/calibration-v1 --analysis data/derived/third-audit-20260925
	$(PYTHON) scripts/verify_third_replay_grid.py $(THIRD_RAW)/diagnosis-replay-v1/trials.jsonl.gz
analyze-third:
	$(PYTHON) scripts/analyze_third_audit.py all --raw $(THIRD_RAW)
	$(PYTHON) scripts/verify_third_audit.py replay $(THIRD_RAW)/diagnosis-replay-v1 --corpus $(THIRD_RAW)/diagnosis-confirm-v1 --calibration $(THIRD_RAW)/calibration-v1 --analysis data/derived/third-audit-20260925
	XDG_CACHE_HOME=$(CURDIR)/tmp/cache MPLCONFIGDIR=$(CURDIR)/tmp/matplotlib $(PYTHON) scripts/render_third_audit.py
homelab-third:
	bash experiments/third_audit/run_homelab.sh
analyze-fourth:
	XDG_CACHE_HOME=$(CURDIR)/tmp/cache MPLCONFIGDIR=$(CURDIR)/tmp/matplotlib $(PYTHON) scripts/render_fourth_revision.py

.PHONY: verify-fifth analyze-fifth homelab-fifth
verify-fifth:
	$(PYTHON) scripts/verify_fifth_audit.py $(FIFTH_RAW)/placement-confirm-v1 --receipt docs/fifth-audit-20260928/placement-validation.json
	$(PYTHON) scripts/verify_fifth_batched.py $(FIFTH_RAW)/batching-confirm-v2 --receipt docs/fifth-audit-20260928/batching-validation.json
	$(PYTHON) scripts/verify_fifth_contract.py --raw $(FIFTH_RAW) --receipt docs/fifth-audit-20260928/contract-validation.json
	$(PYTHON) scripts/verify_fifth_context.py
	$(PYTHON) scripts/verify_fifth_exclusions.py
analyze-fifth:
	$(PYTHON) scripts/analyze_fifth_current.py --raw $(FIFTH_RAW) --out data/derived/fifth-audit-20260928
	XDG_CACHE_HOME=$(CURDIR)/tmp/cache MPLCONFIGDIR=$(CURDIR)/tmp/matplotlib $(PYTHON) scripts/render_fifth_revision.py
	XDG_CACHE_HOME=$(CURDIR)/tmp/cache MPLCONFIGDIR=$(CURDIR)/tmp/matplotlib $(PYTHON) scripts/render_fifth_localization.py
homelab-fifth:
	bash experiments/fifth_audit/run_homelab.sh

.PHONY: verify-current mathematical-supplement
verify-current:
	$(PYTHON) release/check_paper.py
	$(PYTHON) scripts/verify_fifth_context.py
	$(PYTHON) scripts/verify_publication_mechanisms.py
mathematical-supplement:
	cd proofs && latexmk -pdf -interaction=nonstopmode -halt-on-error reference-results.tex
	cp proofs/reference-results.pdf output/pdf/trace-sampling-mathematical-supplement.pdf
