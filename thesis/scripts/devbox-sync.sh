#!/usr/bin/env bash
set -euo pipefail

cd "$REPO_ROOT"

echo ">> syncing $REPO_ROOT -> ${NAMESPACE}/${DEVBOX_DEPLOY}:${DEVBOX_DEST}"
kubectl exec -n "$NAMESPACE" "$DEVBOX_DEPLOY" -- mkdir -p "$DEVBOX_DEST"

RSH="sh -c 'shift; exec kubectl exec -n $NAMESPACE -i $DEVBOX_DEPLOY -- \"\$@\"' rsh"
rsync -azi --delete \
  --exclude '.git/' \
  --filter=':- .gitignore' \
  -e "$RSH" \
  ./ "x:${DEVBOX_DEST}/"
echo "done."
