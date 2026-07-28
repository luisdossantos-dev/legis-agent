# Promptfoo Evaluation Configuration — Legis Agent

## Quick Start
```bash
npx promptfoo@latest eval
npx promptfoo@latest view
```

## Thresholds
| Metric | Threshold | Action |
|--------|-----------|--------|
| RAG accuracy | < 85% | ❌ PR fails |
| Cost per call | > $0.05 | ❌ PR fails |
| Latency p95 | > 5s | ❌ PR fails |
| Draft completeness | Missing required fields | ❌ PR fails |

## Test Suites

### 1. RAG Accuracy (`rag-accuracy`)
Tests that the retrieval system returns relevant chunks.

### 2. Draft Quality (`draft-quality`)
Tests that generated documents contain all required fields.

### 3. Cost Monitoring (`cost-monitoring`)
Tests that each LLM call stays under budget.

### 4. Latency (`latency`)
Tests that responses are fast enough.
