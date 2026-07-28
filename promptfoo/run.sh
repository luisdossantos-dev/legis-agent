#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# Legis Agent — Promptfoo Evaluation Runner
# ──────────────────────────────────────────────────────────────
# Run this script to execute the full evaluation suite locally.
# Requires:
#   - Backend running on localhost:8000
#   - A configured API key (via Settings UI or runtime.json)
#   - An eval document uploaded (eval-doc-1)
#
# Usage:
#   ./run.sh                 # Full suite
#   ./run.sh rag-accuracy    # Only RAG tests
#   ./run.sh latency         # Only latency tests
#   ./run.sh security        # Only security tests
#   ./run.sh --view          # Open the promptfoo web UI
#   ./run.sh --help          # Show help
# ──────────────────────────────────────────────────────────────

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

FILTER=""
VIEW=false

for arg in "$@"; do
  case "$arg" in
    --view) VIEW=true ;;
    --help)
      echo "Usage: $0 [test-filter] [--view]"
      echo ""
      echo "Filters:"
      echo "  rag-accuracy   Only RAG accuracy tests"
      echo "  draft-quality  Only draft quality tests"
      echo "  latency        Only latency/cost tests"
      echo "  security       Only security tests"
      echo ""
      echo "Examples:"
      echo "  $0                     # Run full suite"
      echo "  $0 rag-accuracy       # RAG tests only"
      echo "  $0 --view             # Open web UI"
      exit 0
      ;;
    *) FILTER="$arg" ;;
  esac
done

# ── Prerequisites check ─────────────────────────────────────────
echo "🔍 Checking prerequisites..."

if ! command -v npx &>/dev/null; then
  echo "❌ npx not found. Install Node.js >= 18."
  exit 1
fi

if ! curl -s http://localhost:8000/health >/dev/null 2>&1; then
  echo "❌ Backend not running on localhost:8000."
  echo "   Start it with: start.sh (option 2: Backend only)"
  exit 1
fi

echo "✅ Prerequisites OK"

# ── Install promptfoo if needed ─────────────────────────────────
if ! npx --yes promptfoo --version >/dev/null 2>&1; then
  echo "📦 Installing promptfoo..."
  npm install -g promptfoo
fi

# ── Run evaluation ──────────────────────────────────────────────
if [ "$VIEW" = true ]; then
  echo "📊 Opening promptfoo web UI..."
  npx promptfoo view
  exit 0
fi

echo ""
echo "═══════════════════════════════════════════════"
echo "  📊 Legis Agent — Promptfoo Evaluation"
echo "  Filter: ${FILTER:-none (all tests)}"
echo "═══════════════════════════════════════════════"
echo ""

CMD="npx promptfoo eval --config promptfoo.yaml --output result.json --verbose"

if [ -n "$FILTER" ]; then
  CMD="$CMD --filter $FILTER"
fi

echo "Running: $CMD"
echo ""
eval "$CMD"

# ── Check results ───────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════"
echo "  📋 Results Summary"
echo "═══════════════════════════════════════════════"

python3 << 'PYEOF'
import json

try:
    with open('result.json') as f:
        results = json.load(f)
except FileNotFoundError:
    print("❌ No results found. Evaluation may have failed.")
    exit(1)

test_results = results.get('results', [])
total = len(test_results)
passed = sum(1 for t in test_results if t.get('success', False))
failed = total - passed

# Group by type
by_type = {}
for t in test_results:
    desc = t.get('description', 'unknown')
    prefix = desc.split(' — ')[0] if ' — ' in desc else 'other'
    by_type.setdefault(prefix, []).append(t)

print(f"\n📊 Total: {total} tests | ✅ {passed} passed | ❌ {failed} failed\n")

for category, tests in sorted(by_type.items()):
    cat_pass = sum(1 for t in tests if t.get('success', False))
    cat_total = len(tests)
    status = "✅" if cat_pass == cat_total else "❌"
    print(f"  {status} {category}: {cat_pass}/{cat_total}")

if failed > 0:
    print(f"\n{'─'*50}")
    print("FAILED TESTS:")
    for t in test_results:
        if not t.get('success', False):
            desc = t.get('description', 'unknown')
            cost = t.get('cost', 0)
            latency = t.get('latency_ms', 0)
            failures = t.get('assertionFailures', [])
            reasons = [f.get('reason', 'unknown') for f in failures]
            print(f"  ❌ {desc}")
            print(f"     Cost: ${cost:.4f} | Latency: {latency}ms")
            if reasons:
                print(f"     Reasons: {'; '.join(reasons[:3])}")

    accuracy = (passed / total) * 100 if total > 0 else 0
    if accuracy < 85:
        print(f"\n❌ ACCURACY {accuracy:.1f}% < 85% THRESHOLD")
        exit(1)
    else:
        print(f"\n⚠️  {failed} failures but accuracy {accuracy:.1f}% >= 85%")

print(f"\n{'─'*50}")
print(f"✅ Evaluation complete")
PYEOF
