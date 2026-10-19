// apps/website/tests/visual_consistency.test.mjs
// Visual consistency test: renders button, card, status chip on site and in product,
// and compares computed styles and tokens so the match is verified in CI.

import { test, expect } from '@playwright/test';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const TOKENS_PATH = path.resolve(__dirname, '../../../packages/design-tokens/tokens.css');
const SITE_STYLES_PATH = path.resolve(__dirname, '../src/styles/custom.css');

test.describe('RyouU Visual Consistency & Token Verification', () => {
  test('Design tokens file exists and contains canonical product colors', () => {
    expect(fs.existsSync(TOKENS_PATH)).toBe(true);
    const tokensContent = fs.readFileSync(TOKENS_PATH, 'utf-8');

    // Canonical tokens
    expect(tokensContent).toContain('--primary: #65A30D;');
    expect(tokensContent).toContain('--primary-hover: #4D7C0F;');
    expect(tokensContent).toContain('--primary-light: #F7FEE7;');
    expect(tokensContent).toContain("--font-main: 'Plus Jakarta Sans'");
    expect(tokensContent).toContain('--signal-clear: #15803D;');
    expect(tokensContent).toContain('--signal-caution: #B45309;');
    expect(tokensContent).toContain('--signal-flag: #B91C1C;');
  });

  test('Website custom.css imports canonical design tokens', () => {
    expect(fs.existsSync(SITE_STYLES_PATH)).toBe(true);
    const siteStyles = fs.readFileSync(SITE_STYLES_PATH, 'utf-8');

    // Must import canonical design tokens
    expect(siteStyles).toMatch(/@import\s+["'].*tokens\.css["']/);
  });

  test('Component computed styles match product design tokens', async ({ page }) => {
    // Render an HTML harness containing both website and product components
    const testHtml = `
      <!DOCTYPE html>
      <html>
      <head>
        <link rel="stylesheet" href="file://${TOKENS_PATH.replace(/\\/g, '/')}" />
        <link rel="stylesheet" href="file://${SITE_STYLES_PATH.replace(/\\/g, '/')}" />
        <style>
          body { font-family: var(--font-main); }
        </style>
      </head>
      <body>
        <button id="test-btn" class="btn btn-primary">Verify Identity</button>
        <div id="test-card" class="card-surface">Card Body</div>
        <span id="test-chip-stable" class="status-chip stable">Stable</span>
        <span id="test-chip-review" class="status-chip beta">Review</span>
        <span id="test-chip-flagged" class="status-chip experimental">Flagged</span>
      </body>
      </html>
    `;

    await page.setContent(testHtml);

    // 1. Button primary styles
    const btn = page.locator('#test-btn');
    const btnBg = await btn.evaluate((el) => window.getComputedStyle(el).backgroundColor);
    // rgb(101, 163, 13) is #65A30D
    expect(btnBg).toBe('rgb(101, 163, 13)');

    const btnRadius = await btn.evaluate((el) => window.getComputedStyle(el).borderRadius);
    expect(btnRadius).toBe('9999px'); // var(--radius-pill)

    // 2. Card surface styles
    const card = page.locator('#test-card');
    const cardBorderRadius = await card.evaluate((el) => window.getComputedStyle(el).borderRadius);
    expect(cardBorderRadius).toBe('14px'); // var(--radius-md)

    // 3. Status chip colors
    const stableChip = page.locator('#test-chip-stable');
    const stableColor = await stableChip.evaluate((el) => window.getComputedStyle(el).color);
    // rgb(21, 128, 61) is #15803D (var(--signal-clear))
    expect(stableColor).toBe('rgb(21, 128, 61)');

    const reviewChip = page.locator('#test-chip-review');
    const reviewColor = await reviewChip.evaluate((el) => window.getComputedStyle(el).color);
    // rgb(180, 83, 9) is #B45309 (var(--signal-caution))
    expect(reviewColor).toBe('rgb(180, 83, 9)');

    const flaggedChip = page.locator('#test-chip-flagged');
    const flaggedColor = await flaggedChip.evaluate((el) => window.getComputedStyle(el).color);
    // rgb(185, 28, 28) is #B91C1C (var(--signal-flag))
    expect(flaggedColor).toBe('rgb(185, 28, 28)');
  });
});
