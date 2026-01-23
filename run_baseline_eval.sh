#!/bin/bash
# Run Baseline Video Complex Queries Automated Eval

set -e

# Activate venv
source venv/bin/activate

# Default URL - user can override
TEST_URL="${1:-https://baseline.apple.com}"

echo "============================================"
echo "Baseline Video Complex Queries - Test 2"
echo "============================================"
echo ""
echo "This will:"
echo "1. Open a browser (visible by default)"
echo "2. Navigate to BaseLine"
echo "3. Wait for you to log in if needed"
echo "4. Auto-evaluate and submit answers"
echo ""
echo "Press Ctrl+C to abort, or Enter to continue..."
read

python -m baseline_eval --url "$TEST_URL" --output-dir ./baseline_eval_results

echo ""
echo "Results saved to ./baseline_eval_results/"
