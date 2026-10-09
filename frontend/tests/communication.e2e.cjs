/* Run with a disposable backend and AI disabled. No live model requests. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

(async () => {
  const browser = await chromium.launch({ channel: process.env.TEST_BROWSER || 'msedge', headless: true });
  const page = await browser.newPage({ viewport: { width: 1360, height: 1000 } });
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('dialog', d => d.accept());
  try {
    await page.goto(process.env.TEST_URL || 'http://127.0.0.1:8767/', { waitUntil: 'networkidle' });
    await page.locator('[data-go="book"]').first().click();
    await page.locator('#campus-create-panel > summary').click();
    await page.locator('#dossier-create-name').fill('小林 · 新版验收');
    await page.locator('#dossier-create-form button').click();
    await page.waitForFunction(() => document.getElementById('profile-name').textContent.includes('新版验收'));
    assert.equal(await page.locator('#dossier-contact-form').isVisible(), false);
    await page.locator('#campus-add-chat').click();
    const raw = '我：这次展示你负责第二部分可以吗？\n小林：能不能以后分工把哪部分、几点前要一起说清楚？\n我：我把口误截图发群里逗大家？\n小林：别在群里拿我开玩笑。';
    await page.locator('#dossier-chat').fill(raw);
    await page.locator('#dossier-ai').uncheck();
    await page.locator('#memory-consent').check();
    await page.locator('#memory-run').click();
    await page.waitForFunction(() => document.querySelectorAll('#memory-cards article').length === 2);
    assert.match(await page.locator('#memory-cards').textContent(), /任务|安排/);
    assert.match(await page.locator('#memory-cards').textContent(), /个人的玩笑/);
    const dir = process.env.TEST_OUTPUT_DIR;
    if (dir) { fs.mkdirSync(dir, { recursive: true }); await page.screenshot({ path: path.join(dir, 'communication-desktop.png'), fullPage: true }); }
    await page.setViewportSize({ width: 390, height: 844 });
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1));
    if (dir) await page.screenshot({ path: path.join(dir, 'communication-mobile.png'), fullPage: true });
    await page.setViewportSize({ width: 1360, height: 1000 });
    await page.locator('#memory-run').click();
    await page.waitForFunction(() => document.getElementById('memory-update').textContent.includes('没有重复'));
    const taskCard = page.locator('#memory-cards article').filter({ has: page.locator('h4', { hasText: '任务' }) });
    await taskCard.locator('.campus-detail > summary').click();
    await taskCard.locator('button').click();
    await page.locator('#memory-note').fill('用户补充：分工时提前说清楚 <img src=x onerror=alert(1)>');
    await page.locator('#memory-note-form button[type=submit]').click();
    await page.waitForFunction(() => document.querySelectorAll('#memory-cards article').length === 1);
    await page.locator('#memory-basis summary').first().click();
    assert.equal(await page.locator('#dossier-groups img').count(), 0);
    assert.match(await page.locator('#dossier-groups').textContent(), /<img src=x/);
    const boundary = page.locator('#dossier-groups article').filter({ has: page.locator('h4', { hasText: '群内个人玩笑' }) });
    await boundary.locator('button', { hasText: '删除' }).click();
    await page.waitForFunction(() => document.querySelectorAll('#memory-cards article').length === 0);

    await page.locator('[data-go="flow"]').first().click();
    await page.locator('#chat-text').fill('我：这次分工怎么安排？\n小林：请告诉我做什么、几点前要。\n我：好的，我把任务和时间一起说。');
    await page.locator('#parse-text').click();
    await page.locator('#speaker-panel').waitFor({ state: 'visible' });
    await page.locator('#contact-select').selectOption('');
    await page.locator('#use-ai').uncheck();
    await page.locator('#include-guidance').uncheck();
    const response = page.waitForResponse(r => r.url().endsWith('/api/analyze/unified') && r.request().method() === 'POST');
    await page.locator('#run-btn').click();
    const result = await (await response).json();
    assert(result.analysis.statistics && result.analysis.verdict);
    assert.equal(result.profile, null);
    assert.deepEqual(errors, []);
    console.log('PASS: useful cards first, request recognition, duplicate, correction invalidation, deletion, safe text, mobile width, original analysis. No live API used.');
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
