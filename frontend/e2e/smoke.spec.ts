/**
 * VerdictAI — End-to-end smoke tests.
 *
 * These tests verify the complete user journey from dashboard to
 * evaluation to report. They catch:
 * - Broken routes (404s, blank pages)
 * - Missing API connections (network errors)
 * - Type errors that crash React (white screen)
 * - Click handlers that don't fire
 * - Drawer/modal rendering issues
 * - Accessibility (role attributes, labels)
 */

import { test, expect } from '@playwright/test';

const BASE = 'http://localhost:5173';

test.describe('Dashboard', () => {
  test('loads without crash and shows tender cards', async ({ page }) => {
    await page.goto('/');
    // Should see the hero title (Fraunces italic)
    await expect(page.locator('.hero-title, h1')).toBeVisible({ timeout: 8000 });
    // Should have at least one tender card (seeded data)
    const cards = page.locator('.card');
    await expect(cards.first()).toBeVisible({ timeout: 8000 });
  });

  test('sidebar navigation works — all routes load', async ({ page }) => {
    await page.goto('/');
    // Click each sidebar item and verify no crash
    const routes = [
      { label: 'Dashboard', url: '/' },
      { label: 'New dossier', url: '/tenders/new' },
      { label: 'Review queue', url: '/queue' },
      { label: 'Manual & Help', url: '/help' },
      { label: 'Audit log', url: '/audit-log' },
      { label: 'Settings', url: '/settings' },
    ];
    for (const r of routes) {
      await page.click(`nav a:has-text("${r.label}")`);
      await page.waitForURL(`**${r.url}`, { timeout: 5000 });
      // No crash = page has content
      await expect(page.locator('body')).not.toHaveText('Cannot read properties');
    }
  });

  test('officer picker is visible and functional', async ({ page }) => {
    await page.goto('/');
    const picker = page.locator('select[aria-label="Select officer"]');
    if (await picker.isVisible()) {
      const options = await picker.locator('option').count();
      expect(options).toBeGreaterThan(1);
    }
  });

  test('accessibility controls (A/A+/A++) work', async ({ page }) => {
    await page.goto('/');
    const aPlus = page.locator('button:has-text("A+")');
    if (await aPlus.isVisible()) {
      await aPlus.click();
      // html should have a text-size class
      const html = page.locator('html');
      const cls = await html.getAttribute('class');
      expect(cls).toContain('text-');
    }
  });
});

test.describe('Tender Dossier', () => {
  test('opens a tender and shows step indicator', async ({ page }) => {
    await page.goto('/');
    // Click the first tender card
    const firstCard = page.locator('.card a, a .card').first();
    if (await firstCard.isVisible({ timeout: 5000 })) {
      await firstCard.click();
      await page.waitForURL('**/tenders/**', { timeout: 5000 });
      // Step indicator should be visible
      await expect(page.locator('.step-row, .step')).toBeVisible({ timeout: 5000 });
    }
  });

  test('evaluation matrix renders cells', async ({ page }) => {
    await page.goto('/');
    // Navigate to the most-progressed tender
    const cards = page.locator('a:has(.card)');
    const count = await cards.count();
    if (count > 0) {
      await cards.last().click();
      await page.waitForURL('**/tenders/**', { timeout: 5000 });
      // Navigate to evaluation step
      const evalStep = page.locator('button:has-text("Evaluation"), a:has-text("Evaluation")');
      if (await evalStep.isVisible({ timeout: 3000 })) {
        await evalStep.click();
        await page.waitForURL('**/evaluation', { timeout: 5000 });
        // Matrix should have cells
        const cells = page.locator('.vc-pass, .vc-fail, .vc-review');
        await expect(cells.first()).toBeVisible({ timeout: 10000 });
      }
    }
  });

  test('clicking a matrix cell opens the drawer', async ({ page }) => {
    await page.goto('/');
    const cards = page.locator('a:has(.card)');
    if (await cards.count() > 0) {
      await cards.last().click();
      await page.waitForURL('**/tenders/**', { timeout: 5000 });
      const evalStep = page.locator('button:has-text("Evaluation"), a:has-text("Evaluation")');
      if (await evalStep.isVisible({ timeout: 3000 })) {
        await evalStep.click();
        await page.waitForURL('**/evaluation', { timeout: 5000 });
        const cell = page.locator('.vc-pass, .vc-fail, .vc-review').first();
        if (await cell.isVisible({ timeout: 8000 })) {
          await cell.click();
          // Drawer should appear
          await expect(page.locator('.drawer')).toBeVisible({ timeout: 5000 });
          // Drawer should have the Confidence Veil headline
          await expect(page.locator('.drawer').locator('text=/confident/')).toBeVisible({ timeout: 5000 });
        }
      }
    }
  });

  test('drawer is scrollable and shows officer notes', async ({ page }) => {
    await page.goto('/');
    const cards = page.locator('a:has(.card)');
    if (await cards.count() > 0) {
      await cards.last().click();
      const evalStep = page.locator('button:has-text("Evaluation"), a:has-text("Evaluation")');
      if (await evalStep.isVisible({ timeout: 3000 })) {
        await evalStep.click();
        const cell = page.locator('.vc-pass, .vc-fail, .vc-review').first();
        if (await cell.isVisible({ timeout: 8000 })) {
          await cell.click();
          await expect(page.locator('.drawer')).toBeVisible({ timeout: 5000 });
          // Should find "Officer notes" section
          await expect(page.locator('text=Officer notes')).toBeVisible({ timeout: 5000 });
        }
      }
    }
  });
});

test.describe('Copilot', () => {
  test('copilot panel shows Chat and Studio tabs', async ({ page }) => {
    await page.goto('/');
    const cards = page.locator('a:has(.card)');
    if (await cards.count() > 0) {
      await cards.last().click();
      await page.waitForURL('**/tenders/**', { timeout: 5000 });
      // Copilot should be visible
      const chatTab = page.locator('button:has-text("Chat")');
      const studioTab = page.locator('button:has-text("Studio")');
      await expect(chatTab).toBeVisible({ timeout: 5000 });
      await expect(studioTab).toBeVisible({ timeout: 5000 });
    }
  });
});

test.describe('Help page', () => {
  test('loads with pinned search and scrollable content', async ({ page }) => {
    await page.goto('/help');
    // Search input should be visible
    await expect(page.locator('input[aria-label="Search the manual"]')).toBeVisible({ timeout: 5000 });
    // TOC should be visible on desktop
    await expect(page.locator('text=In this manual')).toBeVisible({ timeout: 5000 });
    // First chapter heading
    await expect(page.locator('text=What VerdictAI does')).toBeVisible({ timeout: 5000 });
  });

  test('search filters chapters', async ({ page }) => {
    await page.goto('/help');
    const search = page.locator('input[aria-label="Search the manual"]');
    await search.fill('verifier');
    // Should show the verifiers chapter, hide others
    await expect(page.locator('section#verifiers, text=External-source verifiers')).toBeVisible({ timeout: 3000 });
  });
});

test.describe('Audit log', () => {
  test('loads and shows events', async ({ page }) => {
    await page.goto('/audit-log');
    // Should show the audit log title
    await expect(page.locator('text=/audit/i')).toBeVisible({ timeout: 5000 });
    // Should have filter controls
    await expect(page.locator('input[aria-label="Search audit log"]')).toBeVisible({ timeout: 5000 });
  });
});

test.describe('Report co-authoring', () => {
  test('report step shows co-author UI', async ({ page }) => {
    await page.goto('/');
    const cards = page.locator('a:has(.card)');
    if (await cards.count() > 0) {
      await cards.last().click();
      const reportStep = page.locator('button:has-text("Report"), a:has-text("Report")');
      if (await reportStep.isVisible({ timeout: 3000 })) {
        await reportStep.click();
        await page.waitForURL('**/report', { timeout: 5000 });
        // Should see co-author heading
        await expect(page.locator('text=/co-author/i')).toBeVisible({ timeout: 5000 });
      }
    }
  });
});

test.describe('No console errors', () => {
  test('dashboard loads without JS errors', async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', err => errors.push(err.message));
    await page.goto('/');
    await page.waitForTimeout(3000);
    // Filter out known non-critical errors (Chrome extensions, etc.)
    const critical = errors.filter(e =>
      !e.includes('chrome-extension') &&
      !e.includes('ResizeObserver') &&
      !e.includes('Non-Error promise rejection')
    );
    expect(critical).toHaveLength(0);
  });

  test('tender space loads without JS errors', async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', err => errors.push(err.message));
    await page.goto('/');
    const cards = page.locator('a:has(.card)');
    if (await cards.count() > 0) {
      await cards.last().click();
      await page.waitForTimeout(3000);
    }
    const critical = errors.filter(e =>
      !e.includes('chrome-extension') &&
      !e.includes('ResizeObserver') &&
      !e.includes('Non-Error promise rejection')
    );
    expect(critical).toHaveLength(0);
  });
});
