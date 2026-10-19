// apps/website/tests/visual_consistency.test.js
// Visual consistency test: renders button, card, status chip on site and in product,
// and compares computed styles and tokens so the match is verified in CI.

import test from 'node:test';
import assert from 'node:assert';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
let chromium;
try {
  chromium = require('playwright').chromium;
} catch (e) {
  try {
    chromium = require('../../../apps/overlay/node_modules/@playwright/test').chromium;
  } catch (e2) {
    chromium = require('../../../node_modules/playwright').chromium;
  }
}

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const TOKENS_PATH = path.resolve(__dirname, '../../../packages/design-tokens/tokens.css');
const SITE_STYLES_PATH = path.resolve(__dirname, '../.vitepress/theme/custom.css');

test('RyouU Visual Consistency: Design tokens contain canonical product colors', () => {
  assert.strictEqual(fs.existsSync(TOKENS_PATH), true, 'tokens.css must exist');
  const tokensContent = fs.readFileSync(TOKENS_PATH, 'utf-8');

  // Verify canonical tokens extracted during design audit
  assert.match(tokensContent, /--primary:\s*#65A30D;/);
  assert.match(tokensContent, /--primary-hover:\s*#4D7C0F;/);
  assert.match(tokensContent, /--primary-light:\s*#F7FEE7;/);
  assert.match(tokensContent, /--font-main:\s*'Plus Jakarta Sans'/);
  assert.match(tokensContent, /--signal-clear:\s*#15803D;/);
  assert.match(tokensContent, /--signal-caution:\s*#B45309;/);
  assert.match(tokensContent, /--signal-flag:\s*#B91C1C;/);
});

test('RyouU Visual Consistency: Website custom.css imports canonical design tokens', () => {
  assert.strictEqual(fs.existsSync(SITE_STYLES_PATH), true, 'custom.css must exist');
  const siteStyles = fs.readFileSync(SITE_STYLES_PATH, 'utf-8');

  assert.match(siteStyles, /@import\s+["'].*tokens\.css["']/);
});

test('RyouU Visual Consistency: Component computed styles match product design tokens', async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();

  const tokensCss = fs.readFileSync(TOKENS_PATH, 'utf-8');
  const siteCss = fs.readFileSync(SITE_STYLES_PATH, 'utf-8');

  const testHtml = `
    <!DOCTYPE html>
    <html>
    <head>
      <style>
        ${tokensCss}
        ${siteCss}
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
  assert.strictEqual(btnBg, 'rgb(101, 163, 13)', 'Primary button background must match --primary (#65A30D)');

  const btnRadius = await btn.evaluate((el) => window.getComputedStyle(el).borderRadius);
  assert.strictEqual(btnRadius, '9999px', 'Primary button border-radius must match --radius-pill');

  // 2. Card surface styles
  const card = page.locator('#test-card');
  const cardBorderRadius = await card.evaluate((el) => window.getComputedStyle(el).borderRadius);
  assert.strictEqual(cardBorderRadius, '14px', 'Card surface border-radius must match --radius-md (14px)');

  // 3. Status chip colors
  const stableChip = page.locator('#test-chip-stable');
  const stableColor = await stableChip.evaluate((el) => window.getComputedStyle(el).color);
  assert.strictEqual(stableColor, 'rgb(21, 128, 61)', 'Stable chip text must match --signal-clear (#15803D)');

  const reviewChip = page.locator('#test-chip-review');
  const reviewColor = await reviewChip.evaluate((el) => window.getComputedStyle(el).color);
  assert.strictEqual(reviewColor, 'rgb(180, 83, 9)', 'Review chip text must match --signal-caution (#B45309)');

  const flaggedChip = page.locator('#test-chip-flagged');
  const flaggedColor = await flaggedChip.evaluate((el) => window.getComputedStyle(el).color);
  assert.strictEqual(flaggedColor, 'rgb(185, 28, 28)', 'Flagged chip text must match --signal-flag (#B91C1C)');

  await browser.close();
});
