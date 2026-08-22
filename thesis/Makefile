THESIS_DIR  	:= $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
SCRIPTS_DIR 	:= $(THESIS_DIR)scripts
EXPERIMENTS_DIR := $(THESIS_DIR)experiments
RESULTS_DIR     := $(THESIS_DIR)results
PROFILES_DIR    := $(THESIS_DIR)profiles
REPO_ROOT       := $(abspath $(THESIS_DIR)..)
SPEC        	:= $(THESIS_DIR)spec.yaml.j2

# --- constants (single source of truth; scripts read these via the env) -------
NAMESPACE		?= llmdbench
BENCH			:= llmdbenchmark
PYTHON			?= python3
GATEWAY_CLASSES	:= none epponly aibrix

# devbox (in-cluster dev/run environment)
DEVBOX_DEPLOY	?= deploy/devbox
DEVBOX_DEST		?= /workspace/llm-d-benchmark
DEVBOX_SESSION	?= bench

# Exported so the scripts (which set -u and derive no paths of their own) see
# them. Every directory a script touches originates here -- no in-script paths.
export NAMESPACE DEVBOX_DEPLOY DEVBOX_DEST DEVBOX_SESSION REPO_ROOT


.PHONY: sync-profiles
sync-profiles:
	@find $(PROFILES_DIR) -mindepth 2 -name '*.yaml' | while read src; do \
	  dataset_path=$$(echo "$$src" | awk -F'$(PROFILES_DIR)/' '{print $$2}' | sed 's/\.yaml$$//'); \
	  yq eval ".data.weka_trace_replay.hf_dataset_path = \"$$dataset_path\"" \
	    $(PROFILES_DIR)/template.yaml > "$$src"; \
	  echo "wrote $$src"; \
	done

# --- devbox ------------------------------------------------------------------
.PHONY: devbox-deploy
devbox-deploy:
	kubectl apply -f $(SCRIPTS_DIR)/devbox.yaml

.PHONY: devbox-sync
devbox-sync:
	bash $(SCRIPTS_DIR)/devbox-sync.sh

.PHONY: devbox-attach
devbox-attach:
	bash $(SCRIPTS_DIR)/devbox-tmux.sh



.PHONY: teardown
teardown:
	$(BENCH) --spec $(SPEC) teardown -p $(NAMESPACE) --gateway-class epponly
	$(BENCH) --spec $(SPEC) teardown -p $(NAMESPACE) --gateway-class aibrix
	$(BENCH) --spec $(SPEC) teardown -p $(NAMESPACE) --gateway-class none

.PHONY: experiment-smoke
experiment-smoke:
	$(BENCH) --spec $(SPEC) experiment -e $(EXPERIMENTS_DIR)/smoke.yaml -p $(NAMESPACE)


.PHONY: experiment-2
experiment-2:
	$(BENCH) --spec $(SPEC) experiment -e $(EXPERIMENTS_DIR)/2-replica.yaml -p $(NAMESPACE)

.PHONY: experiment-8
experiment-8:
	$(BENCH) --spec $(SPEC) experiment -e $(EXPERIMENTS_DIR)/8-replica.yaml -p $(NAMESPACE)

.PHONY: experiment-scaling
experiment-scaling:
	$(BENCH) --spec $(SPEC) experiment -e $(EXPERIMENTS_DIR)/4-replica.yaml -p $(NAMESPACE) ; \
	$(BENCH) --spec $(SPEC) experiment -e $(EXPERIMENTS_DIR)/2-replica.yaml -p $(NAMESPACE) ; \
	$(BENCH) --spec $(SPEC) experiment -e $(EXPERIMENTS_DIR)/1-replica.yaml -p $(NAMESPACE)

.PHONY: fetch-results
fetch-results:
	@test -n "$(EXP)" && test -n "$(RUN)" || { echo "usage: make fetch-results EXP=<name> RUN=<devbox-run-dir>"; exit 1; }
	RUN="$(RUN)" DEST_ROOT="$(RESULTS_DIR)/$(EXP)" bash $(SCRIPTS_DIR)/fetch-results.sh

.PHONY: plot
plot:
	@for d in $(RESULTS_DIR)/$(EXP)/*/; do \
	  [ -e "$$d"stage_1_lifecycle_metrics.json ] || continue; \
	  echo ">> plotting $$d"; \
	  $(PYTHON) $(SCRIPTS_DIR)/plot_sweep.py "$$d" --title "$(EXP) / $$(basename $$d)"; \
	done
