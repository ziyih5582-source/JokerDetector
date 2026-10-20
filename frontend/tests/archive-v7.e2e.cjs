/* Real local API and DOM acceptance. Fictional data, no cloud requests. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

(async () => {
  const base = process.env.TEST_URL || 'http://127.0.0.1:8019';
  const out = process.env.TEST_OUTPUT_DIR;
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1050 } });
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  let ownId;
  try {
    const all = await (await page.request.get(base + '/api/profiles/contacts')).json();
    const rich = all.contacts.find(c => c.name === '示例·持续了解小林');
    assert(rich, 'Run the isolated V7 preview seed script first');
    await page.goto(base + '/profiles?contact=' + rich.id, { waitUntil: 'networkidle' });
    await page.locator('.archive-v7').waitFor();
    assert.match(await page.locator('#campus-sections').innerText(), /星桥.*A\/B|星桥.*A和B/s);
    assert.match(await page.locator('#campus-sections').innerText(), /11月19日/);
    assert.match(await page.locator('#campus-sections').innerText(), /提议，尚未约定/);
    assert.equal(await page.locator('#memory-cards').isVisible(), false);
    assert.equal(await page.locator('#dossier-contact-form').isVisible(), false);
    assert.equal(await page.locator('#dossier-import-panel').isVisible(), false);
    await page.locator('[data-portrait-role="self"]').click();
    assert.match(await page.locator('.archive-profile-content').innerText(), /两个选择/);
    assert.doesNotMatch(await page.locator('.archive-profile-content').innerText(), /同人话题/);
    await page.locator('[data-portrait-role="other"]').click();
    await page.locator('.archive-more > summary').click();
    assert.match(await page.locator('.archive-more').innerText(), /已完成/);
    assert(await page.locator('[data-go="flow"]').count());
    assert(await page.locator('[data-go="joker"]').count());
    assert(await page.locator('[data-go="community"]').count());
    await page.locator('#campus-add-chat').click();
    assert(await page.locator('#archive-upload-dialog').isVisible());
    await page.locator('[data-close-archive="archive-upload-dialog"]').click();
    if (out) {
      fs.mkdirSync(out, { recursive: true });
      await page.locator('.archive-more > summary').click();
      await page.screenshot({ path: path.join(out, 'archive-v7-desktop.png'), fullPage: true });
    }
    await page.setViewportSize({ width: 390, height: 844 });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 2), false);
    if (out) await page.screenshot({ path: path.join(out, 'archive-v7-narrow.png'), fullPage: true });
    await page.setViewportSize({ width: 1440, height: 1050 });
    const created = await (await page.request.post(base + '/api/profiles/contacts', { data: { name: 'QA临时虚构联系人' } })).json();
    ownId = created.id;
    const imported = await page.request.post(base + '/api/profiles/contacts/' + ownId + '/memory/import', { data: {
      revision: created.revision, messages: [{ speaker: '我', content: '你平时怎么样' }, { speaker: 'TA', content: '我刚认识人时话少，熟悉了话多' }],
      self_speaker: '我', other_speaker: 'TA', use_ai: false, save_consent: true, cloud_consent: false,
      role_reliability: 'confirmed', time_reliability: 'confirmed', chat_date: '2026-10-18'
    } });
    assert.equal(imported.status(), 200);
    await page.goto(base + '/profiles?contact=' + ownId, { waitUntil: 'networkidle' });
    await page.locator('.archive-profile .archive-trait details > summary').first().click();
    await page.locator('.archive-profile .campus-edit').first().click();
    assert(await page.locator('#archive-tools-dialog').isVisible());
    await page.locator('#memory-note').fill('其实只是对当时的话题不熟悉，不能概括成慢热。');
    await page.locator('#memory-note-form button[type="submit"]').click();
    await page.waitForFunction(() => !document.getElementById('archive-tools-dialog').open);
    assert.match(await page.locator('.archive-profile-content').innerText(), /只是对当时的话题/);
    assert.deepEqual(errors, []);
    console.log('PASS: real API, TA/self separation, exact interest/date, pending vs completed, collapsed tools, edit propagation, navigation, 390px overflow.');
  } finally {
    if (ownId) await page.request.delete(base + '/api/profiles/contacts/' + ownId);
    await browser.close();
  }
})().catch(e => { console.error(e); process.exitCode = 1; });
