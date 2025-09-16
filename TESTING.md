# Testing & CI Plan

## Unit Tests
- Parsers & OCR: `utils/preprocess.py` — verify text/blocks, offsets, OCR conf flags.
- Segmenters: `utils/segmenter.py` — heading detection, merging, chunking.
- Features: `utils/features.py` — placeholders, modals/negations, keywords.
- APIs: FastAPI routes — upload/analyze/status/results/download/feedback contracts.

## Integration Tests
- End-to-end from upload → analyze → results JSON using sample PDFs/DOCX.
- Report generation JSON/CSV/PDF schema checks.

## Model Tests
- Regression suite per model version:
  - Macro-F1, per-class F1 compared to baseline.
  - False negative rate for High severity clauses.
  - Confidence calibration (optional).
- Smoke test loads artifact and scores a small sample.

## E2E UI Tests
- Playwright/Cypress flows: upload → highlights view → filter → export.
- Accessibility checks: keyboard nav and color contrast.

## CI Pipeline
- On PR: lint, unit tests, integration tests (light), model smoke.
- On main: build images, push to registry, trigger staging deploy.

## Canary & Rollback
- Canary model version to 5–10% traffic; watch error rate, macro-F1 on streaming eval set, drift PSI.
- Auto-rollback if thresholds breached (Alertmanager → workflow dispatcher).

## Data Privacy
- Use sanitized fixtures; avoid real PII in tests.
