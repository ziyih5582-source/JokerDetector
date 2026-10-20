/* Real local API + browser acceptance, isolated fictional contacts, no paid calls. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

(async () => {
  const base = process.env.TEST_URL || 'http://127.0.0.1:8020';
  const out = process.env.TEST_OUTPUT_DIR;
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1050 } });
  const errors = [];
  let ownId;
  page.on('pageerror', e => errors.push(e.message));
  try {
    const all = await (await page.request.get(base + '/api/profiles/contacts')).json();
    const rich = all.contacts.find(c => c.name === '实测虚构·三次了解同一兴趣');
    assert(rich, 'Seed actual-model fictional preview contacts before this test');
    const p = await (await page.request.get(base + '/api/profiles/contacts/' + rich.id)).json();
    assert.equal(p.archive.version, 'archive-v8.1');
    assert.equal(p.archive.portrait_style, 'personality-v2');
    for (const role of ['other', 'self']) for (const trait of p.archive.portraits[role].traits) {
      assert(trait.title.length <= 12 && trait.text.length <= 140, 'Personality labels stay short; interpretations remain one small paragraph');
      assert.doesNotMatch(trait.title, /这段互动|初步理解/);
    }
    assert(!p.archive_v8 && !p.archive.sources, 'Raw interaction bank must stay private');
    await page.goto(base + '/profiles?contact=' + rich.id, { waitUntil: 'networkidle' });
    await page.locator('.archive-v8').waitFor();
    assert.match(await page.locator('.archive-information').innerText(), /星桥/);
    assert.match(await page.locator('.archive-information').innerText(), /A.*B|A和B/s);
    assert((await page.locator('.archive-trait').count()) > 0);
    assert((await page.locator('.archive-suggestion').count()) <= 3);
    assert((await page.locator('.archive-information > .archive-information-grid > .archive-topic').count()) <= 6);
    assert.equal(await page.locator('#memory-cards').isVisible(), false);
    assert.equal(await page.locator('#dossier-contact-form').isVisible(), false);
    assert.equal(await page.locator('#dossier-import-panel').isVisible(), false);
    await page.locator('.archive-trait .campus-detail > summary').first().click();
    assert.match(await page.locator('.archive-trait').first().innerText(), /其他可能解释/);
    assert((await page.locator('.archive-trait blockquote').count()) > 0);
    await page.locator('.archive-trait .campus-detail > summary').first().click();
    for (const nav of ['flow', 'joker', 'community']) assert(await page.locator('[data-go="' + nav + '"]').count());
    const oldTitles = await page.locator('.archive-trait h4').allTextContents();
    await page.locator('[data-portrait-role="self"]').click();
    assert.equal(await page.locator('.archive-profile-content').getAttribute('data-subject'), 'self');
    await page.locator('[data-portrait-role="other"]').click();
    assert.deepEqual(await page.locator('.archive-trait h4').allTextContents(), oldTitles);
    await page.locator('#campus-add-chat').click();
    assert(await page.locator('#archive-upload-dialog').isVisible());
    assert(await page.getByRole('button', { name: '只整理已有资料', exact: true }).isVisible());
    await page.locator('[data-close-archive="archive-upload-dialog"]').click();
    if (out) {
      fs.mkdirSync(out, { recursive: true });
      await page.screenshot({ path: path.join(out, 'archive-v8-desktop.png'), fullPage: true });
    }
    await page.setViewportSize({ width: 390, height: 844 });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 2), false);
    if (out) await page.screenshot({ path: path.join(out, 'archive-v8-narrow.png'), fullPage: true });
    await page.setViewportSize({ width: 1440, height: 1050 });

    const created = await (await page.request.post(base + '/api/profiles/contacts', { data: { name: 'QA虚构·档案交互' } })).json();
    ownId = created.id;
    let denied = await page.request.post(base + '/api/profiles/contacts/' + ownId + '/archive/rebuild', { data: { revision: 0, cloud_consent: false, save_consent: true } });
    assert.equal(denied.status(), 400, 'No paid rebuild without cloud consent');
    denied = await page.request.post(base + '/api/profiles/contacts/' + ownId + '/archive/rebuild', { data: { revision: 99, cloud_consent: true, save_consent: true } });
    assert.equal(denied.status(), 409, 'No paid rebuild after stale revision');
    const noted = await page.request.post(base + '/api/profiles/contacts/' + ownId + '/memory/notes', { data: { revision: 0, text: '对方重视守时，见面安排需要先确认。', use_in_ai: false } });
    assert.equal(noted.status(), 200);
    await page.goto(base + '/profiles?contact=' + ownId, { waitUntil: 'networkidle' });
    assert.match(await page.locator('.archive-information').innerText(), /重视守时/);
    await page.locator('.archive-topic .campus-detail > summary').first().click();
    await page.locator('.archive-topic .campus-edit').first().click();
    await page.locator('#memory-note').fill('修正：只在这次见面需要先确认时间，不能推断一贯守时。');
    await page.locator('#memory-note-form button[type="submit"]').click();
    await page.waitForFunction(() => !document.getElementById('archive-tools-dialog').open);
    assert.match(await page.locator('.archive-information').innerText(), /不能推断一贯守时/);
    assert.deepEqual(errors, []);
    console.log('PASS: V8 local API, true-model fixtures, named interest, evidence, TA/self, <=3 suggestions, <=6 main topics, consent, stale revision, private manual correction, nav, 390px.');
  } finally {
    if (ownId) await page.request.delete(base + '/api/profiles/contacts/' + ownId);
    await browser.close();
  }
})().catch(e => { console.error(e); process.exitCode = 1; });
