#!/usr/bin/env bash
set -euo pipefail

FILES=(config.yaml run_metadata.yaml summary_lifecycle_metrics.json summary_session_lifecycle_metrics.json)

echo ">> $NAMESPACE/$DEVBOX_DEPLOY run=$RUN -> $DEST_ROOT"

mapfile -t RESULT_DIRS < <(kubectl exec -n "$NAMESPACE" "$DEVBOX_DEPLOY" -- \
  bash -c "find '$RUN' -type d -name 'inference-perf-*_*' -path '*/results/*'" | sort)

[[ ${#RESULT_DIRS[@]} -gt 0 ]] || { echo "no result subdirs under $RUN" >&2; exit 1; }

for rd in "${RESULT_DIRS[@]}"; do
  base="$(basename "$rd")"
  workload="$(echo "$base" | sed -E 's/^inference-perf-//; s/-[0-9]+-[a-z0-9]+_[0-9]+$//')"
  dest="$DEST_ROOT/$workload"
  mkdir -p "$dest"
  echo "   $workload"

  for f in "${FILES[@]}"; do
    if kubectl exec -n "$NAMESPACE" "$DEVBOX_DEPLOY" -- test -f "$rd/$f" 2>/dev/null; then
      kubectl exec -n "$NAMESPACE" "$DEVBOX_DEPLOY" -- cat "$rd/$f" > "$dest/$f"
    fi
  done

  mapfile -t STAGE_FILES < <(kubectl exec -n "$NAMESPACE" "$DEVBOX_DEPLOY" -- \
    bash -c "ls '$rd' | grep -E '^stage_[0-9]+_(session_)?lifecycle_metrics\.json$'")
  for f in "${STAGE_FILES[@]}"; do
    kubectl exec -n "$NAMESPACE" "$DEVBOX_DEPLOY" -- cat "$rd/$f" > "$dest/$f"
  done
done

echo ">> done. $DEST_ROOT ready to commit."
