#!/usr/bin/env bash
set -euo pipefail

exec kubectl exec -n "$NAMESPACE" -it "$DEVBOX_DEPLOY" -- \
  tmux new-session -A -s "$DEVBOX_SESSION"
