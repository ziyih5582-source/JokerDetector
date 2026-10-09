/* Run against a disposable, locally started backend; never point at real data. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

(async () => {
  const browser = await chromium.launch({ channel: process.env.TEST_BROWSER || 'msedge', headless: true });
  const page = await browser.newPage({ viewport: { width: 1360, height: 1000 } });
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  try {
    await page.goto(process.env.TEST_URL || 'http://127.0.0.1:8765/', { waitUntil: 'networkidle' });
    await page.locator('[data-go="book"]').first().click();
    await page.locator('#dossier-create-name').fill('小林 · 自动验收');
    await page.locator('#dossier-create-form button').click();
    await page.waitForFunction(() => document.getElementById('profile-name').textContent.includes('自动验收'));
    await page.locator('#dossier-tags').fill('同学，室友，小组成员');
    await page.locator('#dossier-background').fill('认识不久，合作过课程任务');
    await page.locator('#dossier-contact-form button').click();
    await page.waitForFunction(() => document.getElementById('dossier-status').textContent.includes('已保存'));
    await page.locator('#dossier-import-panel summary').click();

    async function upload(text, day) {
      await page.locator('#dossier-chat').fill(text);
      await page.locator('#dossier-other').fill('小林');
      await page.locator('#dossier-chat-date').fill(day);
      await page.locator('#dossier-preview').click();
      await page.locator('#dossier-commit').waitFor({ state: 'visible' });
      await page.locator('#dossier-save-consent').check();
      await page.locator('#dossier-commit').click();
      await page.waitForFunction(() => document.getElementById('dossier-status').textContent.includes('已保存选中的更新'));
    }
    const first = '我：今天聊聊安排\n小林：我比较慢热，刚认识的时候不太爱说话。\n小林：分工直接告诉我做什么、几点前要。\n小林：别在群里拿我开玩笑。\n小林：我10月12号有面试。';
    await upload(first, '2026-10-01');
    assert.equal(await page.locator('#dossier-groups article').count(), 4);
    await upload('我：今天聊聊安排\n小林：别只说快点交，告诉我哪一部分、截止几点。\n小林：群里说任务没关系，我是不喜欢被拿来开玩笑。', '2026-10-03');
    assert.equal(await page.locator('#dossier-groups article').count(), 4);
    await upload('我：今天聊聊安排\n小林：最近忙的时候短语音可以，重要安排还是文字发我。\n小林：面试改到10月15号了。', '2026-10-05');
    await upload('我：今天聊聊安排\n小林：面试定在10月12号。', '2026-09-29');
    const event = page.locator('#dossier-groups article').filter({ has: page.locator('h4', { hasText: '面试：' }) });
    assert.match(await event.textContent(), /事件日期：2026-10-15/);

    await page.locator('#dossier-chat').fill(first);
    await page.locator('#dossier-chat-date').fill('2026-10-01');
    await page.locator('#dossier-preview').click();
    await page.waitForFunction(() => document.getElementById('dossier-preview-result').textContent.includes('已完整导入'));
    assert.equal(await page.locator('#dossier-commit').isVisible(), false);

    const trait = page.locator('#dossier-groups article').filter({ has: page.locator('h4', { hasText: '熟悉程度与表达：' }) });
    await trait.locator('button', { hasText: '人工修正' }).click();
    await page.locator('#dossier-text').fill('熟悉之后很健谈，只是刚认识慢热 <img src=x onerror=alert(1)>');
    await page.locator('#dossier-manual-save').click();
    await page.waitForFunction(() => document.getElementById('dossier-status').textContent.includes('人工信息已保存'));
    assert.equal(await page.locator('#dossier-groups img').count(), 0);
    assert.match(await trait.textContent(), /受保护/);
    assert.match(await trait.textContent(), /<img src=x onerror=alert\(1\)>/);

    const output = process.env.TEST_OUTPUT_DIR;
    if (output) { fs.mkdirSync(output, { recursive: true }); await page.screenshot({ path: path.join(output, 'dossier-desktop.png'), fullPage: true }); }
    await page.setViewportSize({ width: 390, height: 844 });
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), 'mobile horizontal overflow');
    if (output) await page.screenshot({ path: path.join(output, 'dossier-mobile.png'), fullPage: true });
    assert.deepEqual(errors, []);
    console.log('PASS: create, tags, four imports, old dates, duplicate, manual edit, XSS escaping, mobile width.');
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
