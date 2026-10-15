import { test, expect } from '@playwright/test';

const BASE_URL = process.env.BASE_URL || 'http://localhost:8501';

/**
 * Streamlit apps don't provide a conventional router; navigation is done via sidebar radio.
 * These helpers use role/text based locators that are typically stable across Streamlit versions.
 */
async function gotoApp(page) {
  await page.goto(BASE_URL, { waitUntil: 'domcontentloaded' });
  // Streamlit may re-render after first load.
  await page.waitForTimeout(300);
}

async function openIntelligentQueryAssistance(page) {
  // Ensure sidebar is visible and select the page.
  // The label in app.py is exactly: "Intelligent Query Assistance"
  const nav = page.getByText('Navigation');
  await expect(nav).toBeVisible();

  await page.getByRole('radio', { name: 'Go to' }).getByText('Intelligent Query Assistance').click();
  await page.waitForTimeout(300);

  await expect(page.getByRole('heading', { name: 'Intelligent Query Assistance' })).toBeVisible();
}

async function ensureDbMissingUi(page) {
  await expect(page.getByText(/Database not found/i)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Initialize database' })).toBeVisible();
}

test.describe('IntelliSQL - Intelligent Query Assistance', () => {
  test('shows DB missing banner and Initialize button when DB is missing', async ({ page }) => {
    // This assertion assumes the DB file is absent on the machine running the test.
    // If you already have a DB at DB_PATH, delete it to exercise this scenario.
    await gotoApp(page);
    await openIntelligentQueryAssistance(page);
    await ensureDbMissingUi(page);
  });

  test('shows missing GOOGLE_API_KEY error on submit', async ({ page }) => {
    // This test requires DB to be initialized already.
    // It intentionally does NOT set GOOGLE_API_KEY.
    await gotoApp(page);
    await openIntelligentQueryAssistance(page);

    await page.getByLabel('Enter Your Query:').fill('Show all students');
    await page.getByRole('button', { name: 'Get Answer' }).click();

    await expect(page.getByText(/Missing GOOGLE_API_KEY/i)).toBeVisible();
  });

  test('shows warning for empty question on submit (when API key configured)', async ({ page }) => {
    test.skip(!process.env.GOOGLE_API_KEY, 'GOOGLE_API_KEY is required for this test');

    await gotoApp(page);
    await openIntelligentQueryAssistance(page);

    await page.getByRole('button', { name: 'Get Answer' }).click();
    await expect(page.getByText(/Please enter a question/i)).toBeVisible();
  });

  test('renders Generated SQL expander after submit (requires API key + model availability)', async ({ page }) => {
    test.skip(!process.env.GOOGLE_API_KEY, 'GOOGLE_API_KEY is required for this test');

    await gotoApp(page);
    await openIntelligentQueryAssistance(page);

    await page.getByLabel('Enter Your Query:').fill('Show first 5 students');
    await page.getByRole('button', { name: 'Get Answer' }).click();

    // We expect an expander labelled "Generated SQL" (Streamlit expander uses a button).
    await expect(page.getByRole('button', { name: 'Generated SQL' })).toBeVisible();

    // Also expect the response header.
    await expect(page.getByRole('heading', { name: 'The Response is:' })).toBeVisible();
  });
});
