# E2E Tests (Playwright)

## Setup
```
npm create playwright@latest
# choose JS or TS, include tests and browsers
```

## Example flow to implement
- Open Streamlit on http://localhost:8501
- Upload sample PDF
- Wait for table to populate
- Assert a minimum number of clauses displayed
- Click Export buttons and assert downloads occur

## Run
```
npx playwright test
```
