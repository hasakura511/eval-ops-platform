#!/usr/bin/env bash
set -euo pipefail

# Use venv python if present; otherwise fall back to python3
PY="./venv/bin/python"
if [[ ! -x "$PY" ]]; then
  PY="python3"
fi

# Paths
LAB_PATH="examples/fixture_labeled.jsonl"
CACHE_DIR="tests/fixtures/cache"
FEATURES_OUT="/tmp/features.fixtures.jsonl"
LABELED_WITH_FEATURES_OUT="/tmp/labeled_with_features.fixtures.jsonl"
FITTED_CFG="config/thresholds.fitted.fixtures.yaml"

echo "1) Extract features from fixtures cache"
"$PY" ./hint_eval extract --cache-dir "$CACHE_DIR" --out "$FEATURES_OUT"

echo "2) Join labels + features -> $LABELED_WITH_FEATURES_OUT"
"$PY" ./hint_eval join --labeled "$LAB_PATH" --features "$FEATURES_OUT" --out "$LABELED_WITH_FEATURES_OUT"

echo "3) Baseline eval"
"$PY" ./hint_eval eval --labeled "$LABELED_WITH_FEATURES_OUT" --config config/thresholds.yaml

echo "4) Fit thresholds -> $FITTED_CFG"
"$PY" ./hint_eval fit --train "$LABELED_WITH_FEATURES_OUT" \
  --config-in config/thresholds.yaml \
  --config-out "$FITTED_CFG"

echo "5) Eval with fitted thresholds"
"$PY" ./hint_eval eval --labeled "$LABELED_WITH_FEATURES_OUT" --config "$FITTED_CFG"

echo "Done."
