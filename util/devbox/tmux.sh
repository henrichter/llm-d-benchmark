#!/usr/bin/env bash

set -euo pipefail

NAMESPACE="llmdbench"
DEPLOY="deploy/devbox"
SESSION="bench"

exec kubectl exec -n "$NAMESPACE" -it "$DEPLOY" -- \
  tmux new-session -A -s "$SESSION"
