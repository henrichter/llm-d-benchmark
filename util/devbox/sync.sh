#!/usr/bin/env bash

set -euo pipefail

NAMESPACE="llmdbench"
DEPLOY="deploy/devbox"
DEST="/workspace/llm-d-benchmark"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

echo ">> syncing $REPO_ROOT -> ${NAMESPACE}/${DEPLOY}:${DEST}"
kubectl exec -n "$NAMESPACE" "$DEPLOY" -- mkdir -p "$DEST"

RSH="sh -c 'shift; exec kubectl exec -n $NAMESPACE -i $DEPLOY -- \"\$@\"' rsh"
rsync -azi --delete \
  --exclude '.git/' \
  --filter=':- .gitignore' \
  -e "$RSH" \
  ./ "x:${DEST}/"
echo "done."
