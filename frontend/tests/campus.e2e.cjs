/* Browser acceptance with recorded fictional data. No model calls. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

(async () => {
  const base = process.env.TEST_URL || 'http://127.0.0.1:8768';
  const output = process.env.TEST_OUTPUT_DIR;
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const page = await browser.newPage({ viewport: { width: 1500, height: 1050 } });
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('dialog', d => d.accept());
  const initial = await (await page.request.get(base + '/api/profiles/contacts')).json();
  const ids = new Set(initial.contacts.map(c => c.id));
  const primary = initial.contacts.find(c => c.name.includes('小夏'));
  assert(primary);
  try {
    await page.goto(base + '/profiles?preview=1&contact=' + primary.id, { waitUntil: 'networkidle' });
    await page.locator('#campus-overview').getByText('关于你们的关系', { exact: true }).waitFor();
    assert.match(await page.locator('#campus-overview').textContent(), /慢慢了解|确定关系/);
    const knowledge = await page.locator('#campus-sections').textContent();
    assert.match(knowledge, /慢热/);
    assert.match(knowledge, /星露谷/);
    assert.match(knowledge, /群/);
    assert.equal(await page.locator('#campus-scenes, [data-scene]').count(), 0);
    assert.equal(await page.locator('.campus-interactions').getAttribute('open'), null);
    assert.equal(await page.locator('#dossier-contact-form').isVisible(), false);
    if (output) { fs.mkdirSync(output, { recursive: true }); await page.screenshot({ path: path.join(output, 'campus-full.png'), fullPage: true }); await page.screenshot({ path: path.join(output, 'campus-first-screen.png') }); }
    await page.locator('#campus-demo-panel > summary').click();
    await page.locator('#campus-demo-case').selectOption('R02');
    await page.locator('#campus-demo-start').click();
    await page.waitForFunction(() => document.getElementById('campus-demo-status').textContent.includes('0 / 2'));
    await page.locator('#campus-demo-next').click();
    await page.waitForFunction(() => document.getElementById('campus-demo-status').textContent.includes('1 / 2'));
    assert.match(await page.locator('#campus-overview').textContent(), /朋友/);
    await page.locator('#campus-demo-next').click();
    await page.waitForFunction(() => document.getElementById('campus-demo-status').textContent.includes('2 / 2'));
    assert.match(await page.locator('#campus-overview').textContent(), /愿意.*约会/);
    assert.equal(await page.locator('#campus-demo-next').isDisabled(), true);
    await page.locator('#campus-tools > summary').click();
    await page.locator('#campus-timeline-panel > summary').click();
    assert.match(await page.locator('#campus-timeline').textContent(), /之前：.*朋友/s);
    assert.match(await page.locator('#campus-timeline').textContent(), /后来：.*约会/s);
    const id = await page.evaluate(async () => { const r = await (await fetch('/api/profiles/contacts')).json(); return r.contacts[0].id; });
    const context = await (await page.request.post(base + '/api/fisherman/context', { data: { contact_id: id, query: '怎么继续了解她？' } })).json();
    assert.match(context.text, /约会/);
    await page.locator('#campus-overview .campus-detail > summary').first().click();
    await page.locator('#campus-overview .campus-edit').first().click();
    await page.locator('#memory-note').fill('我的看法仍不确定 <img src=x onerror=alert(1)>');
    await page.locator('#memory-note-form button[type=submit]').click();
    await page.waitForFunction(() => document.getElementById('dossier-status').textContent.includes('补充已保存'));
    assert.equal(await page.locator('#campus-overview').isVisible(), false);
    assert.match(await page.locator('#campus-sections').textContent(), /我的看法仍不确定/);
    assert.equal(await page.locator('#campus-sections img').count(), 0);
    await page.locator('#memory-basis > summary').click();
    assert.equal(await page.locator('#dossier-groups img').count(), 0);
    const elder = initial.contacts.find(c => c.name.includes('陈叔'));
    await page.goto(base + '/profiles?preview=1&contact=' + elder.id, { waitUntil: 'networkidle' });
    assert.equal(await page.locator('#campus-overview').isVisible(), false);
    assert.match(await page.locator('#campus-sections').textContent(), /文字|称呼/);
    const task = initial.contacts.find(c => c.name.includes('周老师'));
    await page.goto(base + '/profiles?preview=1&contact=' + task.id, { waitUntil: 'networkidle' });
    assert.match(await page.locator('#campus-sections').textContent(), /2026-10-15/);
    assert.deepEqual(errors, []);
    console.log('PASS: unified archive, mixed memories visible together, two-step relationship update, old/new history, retrieval, correction, HTML safety, elder context, updated task date. No live API calls.');
  } finally {
    const now = await (await page.request.get(base + '/api/profiles/contacts')).json();
    for (const c of now.contacts) if (!ids.has(c.id)) await page.request.delete(base + '/api/profiles/contacts/' + c.id);
    await browser.close();
  }
})().catch(e => { console.error(e); process.exitCode = 1; });
