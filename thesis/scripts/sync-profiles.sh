#!/usr/bin/env bash
set -euo pipefail

REPO="kubernetes-sigs/inference-perf"
REF="${REF:-v0.6.1}"
BASE="https://raw.githubusercontent.com/$REPO/$REF/workload-catalog"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
THESIS_DIR="$(dirname "$SCRIPT_DIR")"
DEST="$THESIS_DIR/profiles/inference-perf"
TEMPLATE="$DEST/template.yaml"

if ! command -v yq >/dev/null 2>&1; then
  echo "error: yq is required but not installed." >&2
  exit 1
fi

if [[ ! -f "$TEMPLATE" ]]; then
  echo "error: template not found: $TEMPLATE" >&2
  exit 1
fi

WORKLOADS=(
  interactive-chat
  batch-summarization-rag
  deep-research
  reasoning
  code-generation
  batch-synthetic-data-generation
)

mkdir -p "$DEST"
echo "syncing from $REPO@$REF"

for name in "${WORKLOADS[@]}"; do
  out="$DEST/$name.yaml"

  raw="$(curl -fsSL "$BASE/$name/inference-perf.yaml")" || {
    echo "WARN fetch failed: $name -- skipping" >&2
    continue
  }

  yq eval-all '. as $item ireduce ({}; . * $item)' \
    "$TEMPLATE" \
    <(printf '%s\n' "$raw" | yq '{"data": .data}') \
    > "$out"

  echo "vendored $name -> $out"
done
