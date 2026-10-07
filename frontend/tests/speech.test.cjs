// node --test frontend/tests/speech.test.cjs
const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');

const source = fs.readFileSync(path.join(__dirname, '../js/speech.js'), 'utf8');

function fixture(options = {}) {
  const documentEvents = {}, windowEvents = {}, spoken = [];
  const nodes = {};
  for (const id of ['guidance-speech-toggle', 'guidance-speech-status', 'guidance-speech']) {
    nodes[id] = { textContent: '', disabled: false, hidden: false, attrs: {}, events: {},
      setAttribute(key, value) { this.attrs[key] = value; },
      addEventListener(name, callback) { this.events[name] = callback; } };
  }
  let cancellations = 0;
  const synth = {
    cancel() { cancellations += 1; },
    getVoices() { return options.voices || []; },
    speak(utterance) { if (options.throwOnSpeak) throw new Error('engine unavailable'); spoken.push(utterance); },
  };
  const document = { hidden: false, getElementById(id) { return nodes[id]; },
    addEventListener(name, callback) { documentEvents[name] = callback; } };
  const window = { addEventListener(name, callback) { windowEvents[name] = callback; } };
  if (!options.unsupported) {
    window.speechSynthesis = synth;
    window.SpeechSynthesisUtterance = function (text) { this.text = text; };
  }
  vm.runInNewContext(source, { window, document });
  documentEvents.DOMContentLoaded();
  return { api: window.AnalysisSpeech, nodes, document, documentEvents, windowEvents, spoken,
    click() { nodes['guidance-speech-toggle'].events.click(); },
    get cancellations() { return cancellations; } };
}

test('long Chinese text is read once in order and completion restores the button', () => {
  const f = fixture();
  const text = '我能理解你此刻的心情。下一次可以把自己的需要说清楚。'.repeat(90);
  f.api.setText(text);
  assert.equal(f.spoken.length, 0, 'does not autoplay');
  f.click();
  assert.equal(f.nodes['guidance-speech-toggle'].attrs['aria-pressed'], 'true');
  let i = 0;
  while (i < f.spoken.length) {
    assert.ok(Array.from(f.spoken[i].text).length <= 180);
    f.spoken[i].onstart();
    f.spoken[i++].onend();
    assert.ok(i < 100, 'queue terminates');
  }
  assert.equal(f.spoken.map(u => u.text).join(''), text);
  assert.equal(f.nodes['guidance-speech-status'].textContent, '朗读完毕。');
  assert.equal(f.nodes['guidance-speech-toggle'].attrs['aria-pressed'], 'false');
});

test('stop and restart ignore delayed events from the previous playback', () => {
  const f = fixture();
  f.api.setText('第一段。'.repeat(100)); f.click();
  const stale = f.spoken[0];
  f.click(); f.click();
  const count = f.spoken.length;
  stale.onend(); stale.onerror(); stale.onstart();
  assert.equal(f.spoken.length, count);
  assert.equal(f.nodes['guidance-speech-toggle'].attrs['aria-pressed'], 'true');
  f.spoken.at(-1).onstart();
  assert.match(f.nodes['guidance-speech-status'].textContent, /正在朗读/);
});

test('replacing or clearing a report cancels the old queue and hides absent content', () => {
  const f = fixture();
  f.api.setText('旧报告。'.repeat(100)); f.click();
  const old = f.spoken[0];
  f.api.setText('新的报告。'); old.onend();
  assert.equal(f.spoken.length, 1);
  f.click(); assert.equal(f.spoken[1].text, '新的报告。');
  f.api.setText('');
  assert.equal(f.nodes['guidance-speech'].hidden, true);
  assert.equal(f.nodes['guidance-speech-toggle'].disabled, true);
});

test('unsupported devices remain disabled even after global busy controls reset', () => {
  const f = fixture({ unsupported: true });
  f.api.setText('有内容'); f.api.sync(true); f.api.sync(false); f.click();
  assert.equal(f.nodes['guidance-speech-toggle'].disabled, true);
  assert.match(f.nodes['guidance-speech-status'].textContent, /不支持/);
  assert.equal(f.spoken.length, 0);
});

test('preferred voice is local Chinese and empty voice lists retain a Chinese language hint', () => {
  const remote = { lang: 'zh-CN', localService: false };
  const local = { lang: 'zh-CN', localService: true };
  const f = fixture({ voices: [{ lang: 'en-US', localService: true }, remote, local] });
  f.api.setText('你好'); f.click();
  assert.equal(f.spoken[0].voice, local);
  const g = fixture(); g.api.setText('你好'); g.click();
  assert.equal(g.spoken[0].lang, 'zh-CN');
});

test('voice list is re-read on playback after asynchronous device voice loading', () => {
  const options = { voices: [] }, f = fixture(options);
  const voice = { lang: 'zh-CN', localService: true };
  options.voices = [voice];
  f.api.setText('你好'); f.click();
  assert.equal(f.spoken[0].voice, voice);
});

test('engine failure is recoverable and returns controls to idle', () => {
  const f = fixture(); f.api.setText('你好'); f.click();
  f.spoken[0].onerror();
  assert.equal(f.nodes['guidance-speech-toggle'].attrs['aria-pressed'], 'false');
  assert.match(f.nodes['guidance-speech-status'].textContent, /暂时无法/);
  f.click(); assert.equal(f.spoken.length, 2);
  const g = fixture({ throwOnSpeak: true }); g.api.setText('你好'); g.click();
  assert.match(g.nodes['guidance-speech-status'].textContent, /暂时无法/);
});

test('backgrounding and page exit cancel playback; busy blocks new starts', () => {
  const f = fixture(); f.api.setText('你好'); f.click();
  f.document.hidden = true; f.documentEvents.visibilitychange();
  assert.equal(f.nodes['guidance-speech-toggle'].attrs['aria-pressed'], 'false');
  f.document.hidden = false; f.click(); f.windowEvents.pagehide();
  assert.equal(f.nodes['guidance-speech-toggle'].attrs['aria-pressed'], 'false');
  f.api.sync(true); const count = f.spoken.length; f.click();
  assert.equal(f.spoken.length, count);
});

test('Markdown is spoken as readable text and unicode characters are not split', () => {
  const f = fixture();
  f.api.setText('# 标题\n- **建议**：[慢慢说](https://example.org)\n```js\nsecret()\n```\n' + '🙂'.repeat(200));
  f.click();
  let i = 0; while (i < f.spoken.length) f.spoken[i++].onend();
  const read = f.spoken.map(u => u.text).join('');
  assert.ok(read.startsWith('标题 建议：慢慢说'));
  assert.ok(!read.includes('secret') && !read.includes('https'));
  assert.equal(Array.from(read).filter(c => c === '🙂').length, 200);
});

test('reading pauses background music to avoid competing audio', () => {
  const f = fixture();
  let paused = 0;
  f.nodes['music-audio'] = { paused: false, pause() { paused += 1; this.paused = true; } };
  f.api.setText('你好'); f.click();
  assert.equal(paused, 1);
  f.click();
  assert.equal(f.nodes['music-audio'].paused, true, 'stopping speech does not autoplay music');
});
