# IntelliSQL Playwright E2E tests

These tests validate the main IntelliSQL Streamlit flow:
- Database missing banner + Initialize flow
- Submit validation (missing API key, empty question)
- Generated SQL displayed
- Safe query execution and results rendering
- Unsafe query blocked

## Prerequisites
1. Start the Streamlit app:
   ```bash
   streamlit run app.py
   ```
2. Ensure the app is reachable at `http://localhost:8501` (default).

## Running tests (example)
```bash
npm install
npx playwright install --with-deps
npx playwright test
```

## Environment variables
- `BASE_URL` (optional): defaults to `http://localhost:8501`
- `GOOGLE_API_KEY`: required for tests that press "Get Answer" unless the test explicitly verifies the missing-key validation.

## Notes
Streamlit renders many widgets without stable selectors; these tests rely on accessible roles/text and a small amount of defensive waiting.
If UI labels change, update the locators in `tests/e2e/playwright/intellisql.spec.ts`.
