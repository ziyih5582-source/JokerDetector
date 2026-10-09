/* Final archive acceptance. Recorded fictional data; all API requests are local. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

(async () => {
  const base = process.env.TEST_URL || 'http://127.0.0.1:8768';
  const out = process.env.TEST_OUTPUT_DIR;
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const page = await browser.newPage({ viewport: { width: 1500, height: 1050 } });
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  const initial = await (await page.request.get(base + '/api/profiles/contacts')).json();
  const ids = new Set(initial.contacts.map(c => c.id));
  try {
    const short = initial.contacts.find(c => c.name.includes('两段短聊'));
    await page.goto(base + '/profiles?preview=1&contact=' + short.id, { waitUntil: 'networkidle' });
    assert.match(await page.locator('#campus-sections').textContent(), /星露谷/);
    assert.match(await page.locator('#memory-cards .memory-action').allTextContents().then(x => x.join(' ')), /每天.*追问|追问.*每天/);
    assert.match(await page.locator('#memory-cards .memory-action').allTextContents().then(x => x.join(' ')), /星露谷/);
    assert.equal(await page.locator('#dossier-import-panel').isVisible(), false);
    assert.equal(await page.locator('#dossier-contact-form').isVisible(), false);
    assert.equal(await page.locator('#campus-tools').getAttribute('open'), null);
    assert.equal(await page.locator('[data-scene]').count(), 0);
    assert(await page.locator('#memory-cards > article').count() <= 3);
    assert(await page.locator('#campus-sections > section > .campus-grid > article').count() <= 4);
    if (out) { fs.mkdirSync(out, { recursive: true }); await page.screenshot({ path: path.join(out, 'archive-final-first-screen.png') }); }

    const rich = initial.contacts.find(c => c.name.includes('丰富聊天'));
    await page.goto(base + '/profiles?preview=1&contact=' + rich.id, { waitUntil: 'networkidle' });
    assert.match(await page.locator('#campus-sections').textContent(), /熟人|陌生/);
    assert(await page.locator('#campus-sections > section > .campus-grid > article').count() <= 4);
    if (out) await page.screenshot({ path: path.join(out, 'archive-final-rich-profile.png'), fullPage: true });

    await page.locator('#campus-demo-panel > summary').click();
    await page.locator('#campus-demo-case').selectOption('V5-R02');
    await page.locator('#campus-demo-start').click();
    await page.waitForFunction(() => document.getElementById('campus-demo-status').textContent.includes('0 / 2'));
    await page.locator('#campus-demo-next').click();
    await page.waitForFunction(() => document.getElementById('campus-demo-status').textContent.includes('1 / 2'));
    assert.match(await page.locator('#campus-sections').textContent(), /朋友/);
    await page.locator('#campus-demo-next').click();
    await page.waitForFunction(() => document.getElementById('campus-demo-status').textContent.includes('2 / 2'));
    await page.locator('#campus-reviews').waitFor({ state: 'visible' });
    assert.match(await page.locator('#campus-reviews').textContent(), /朋友/);
    assert.match(await page.locator('#campus-reviews').textContent(), /约会/);
    await page.locator('#campus-reviews button', { hasText: '采用这次的认识' }).click();
    await page.waitForFunction(() => document.getElementById('campus-reviews').hidden);
    assert.match(await page.locator('#campus-sections').textContent(), /约会/);
    await page.locator('.campus-manage > summary').click();
    await page.locator('#archive-view-records').click();
    await page.locator('#archive-tools-dialog').waitFor({ state: 'visible' });
    await page.locator('#campus-timeline-panel > summary').click();
    assert.match(await page.locator('#campus-timeline').textContent(), /之前：.*朋友/s);
    assert.deepEqual(errors, []);
    console.log('PASS: compact main page, short-chat benefit, rich continuous profile, major change confirmation, prior history. No paid calls.');
  } finally {
    const now = await (await page.request.get(base + '/api/profiles/contacts')).json();
    for (const c of now.contacts) if (!ids.has(c.id)) await page.request.delete(base + '/api/profiles/contacts/' + c.id);
    await browser.close();
  }
})().catch(e => { console.error(e); process.exitCode = 1; });
