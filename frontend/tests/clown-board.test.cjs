// node --test frontend/tests/clown-board.test.cjs
// 只测纯逻辑（不碰 DOM）：解析、归一化、等级与分数格式，以及「有没有真的接进页面」。
const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');

const jsDir = path.join(__dirname, '../js');
const source = fs.readFileSync(path.join(jsDir, 'clown-board.js'), 'utf8');
const indexHtml = fs.readFileSync(path.join(__dirname, '../index.html'), 'utf8');
const inkSource = fs.readFileSync(path.join(jsDir, 'ink.js'), 'utf8');

function load() {
  const documentEvents = {};
  const document = {
    readyState: 'loading', // 停在挂载之前，于是整段模块都能在无 DOM 的环境里加载
    addEventListener(name, callback) { documentEvents[name] = callback; }
  };
  const window = { addEventListener() {} };
  vm.runInNewContext(source, { window, document });
  return { api: window.ClownBoard, documentEvents, window };
}

test('模块加载后不碰 DOM，只暴露 ClownBoard', () => {
  const { api, documentEvents, window } = load();
  assert.ok(api, 'window.ClownBoard 必须存在');
  assert.equal(api.version, 'joker-board-1.0');
  assert.equal(typeof api.publish, 'function');
  assert.equal(typeof documentEvents.DOMContentLoaded, 'function', '等 DOM 就绪再挂载');
  assert.equal(window.document, undefined);
});

test('「发言人：内容」解析成规范化消息，并认出「我」', () => {
  const { api } = load();
  const parsed = api.parseChatText('我：在忙吗\n对方: 嗯\n我：忙完了吗');
  assert.equal(parsed.messages.length, 3);
  assert.equal(parsed.speakers.length, 2);
  assert.equal(parsed.speakers[0], '我');
  assert.equal(parsed.speakers[1], '对方');
  assert.equal(parsed.self, '我');
  assert.equal(parsed.other, '对方');
  assert.equal(parsed.messages[1].speaker, '对方');
  assert.equal(parsed.messages[1].content, '嗯');
});

test('没有「我」时把第一位发言者当成自己', () => {
  const { api } = load();
  const parsed = api.parseChatText('阿泽：周末有空吗\n小鹿：再说吧');
  assert.equal(parsed.self, '阿泽');
  assert.equal(parsed.other, '小鹿');
});

test('格式错误要说清是第几行', () => {
  const { api } = load();
  assert.throws(() => api.parseChatText('我：在忙吗\n这是一句没有冒号的话'), /第 2 行/);
  assert.throws(() => api.parseChatText(''), /先粘一段聊天记录/);
});

test('只支持两个人：群聊会被挡下来', () => {
  const { api } = load();
  assert.throws(() => api.parseChatText('我：在吗\n对方：嗯\n路人：路过'), /两位发言者/);
  assert.throws(() => api.parseChatText('我：在吗\n我：还在吗'), /两位发言者/);
});

test('鉴定所结果（signs）能换算成六维看板', () => {
  const { api } = load();
  const board = api.normalize({
    is_joker: true,
    type: '单向型',
    level: 'high_risk',
    score: 63.4,
    signs: {
      one_way: { label: '单向推进', hit: true, score: 0.9, detail: '你发了 7 条，对方 2 条' },
      self_moved: { label: '自我感动', hit: false, score: 0.2, detail: '低姿态语言密度 PLD=+0.10' },
      fantasy: { label: '幻想脑补', hit: false, score: 0.1, detail: '脑补类词汇出现 0 次' },
      boundary: { label: '边界失守', hit: false, score: 0.0, detail: '牺牲/托付型表达出现 0 次' },
      no_accept_reject: { label: '不接受拒绝', hit: true, score: 0.5, detail: '拒绝后继续发送比例 50%' },
      self_mockery: { label: '事后自嘲', hit: true, score: 0.8, detail: '自贬词汇出现 3 次' }
    }
  });
  assert.equal(board.dimensions.length, 6);
  assert.equal(board.dimensions[0].key, 'one_way');
  assert.equal(board.dimensions[0].points, 90);
  assert.equal(board.dimensions[0].weight, 0.24);
  assert.equal(board.hit_count, 3);
  assert.equal(board.level_label, '高度疑似');
  assert.match(board.summary, /命中 3 项/);
});

test('看板接口返回的 dimensions 原样保留权重与依据', () => {
  const { api } = load();
  const board = api.normalize({
    score: 58.2,
    weighted_score: 51.3,
    level: 'suspicious',
    level_label: '轻度倾向',
    is_joker: true,
    type: '弄臣型',
    dimensions: [
      { key: 'self_mockery', label: '事后自嘲', hit: true, score: 0.8, points: 80, weight: 0.14,
        detail: '自贬词汇出现 3 次', evidence: ['「我不配，救命」', '「我这种人真是废物」'] }
    ],
    next_steps: ['下次想自嘲时，把那句话改成一句真实的需求。']
  });
  assert.equal(board.dimensions[0].weight, 0.14);
  assert.equal(board.hit_count, 1);
  assert.equal(board.next_steps.length, 1);
  assert.equal(board.dimensions[0].evidence.length, 2);
  assert.equal(board.dimensions[0].evidence[0], '「我不配，救命」');
  assert.match(api.boardSummary(board), /事后自嘲 80/);
});

test('空的或坏掉的输入不会炸掉看板', () => {
  const { api } = load();
  assert.equal(api.normalize(null), null);
  assert.equal(api.normalize('nonsense'), null);
  const empty = api.normalize({});
  assert.equal(empty.dimensions.length, 0);
  assert.match(api.boardSummary(empty), /一项都没命中/);
  assert.equal(api.formatScore(null), '—');
  assert.equal(api.formatScore('abc'), '—');
  assert.equal(api.formatScore(63.4), '63.4');
});

test('等级颜色与文案齐全，未知等级回落到清醒玩家', () => {
  const { api } = load();
  for (const level of ['confirmed', 'high_risk', 'suspicious', 'mild', 'healthy']) {
    const meta = api.levelMeta(level);
    assert.ok(meta.label && meta.color && meta.note, level);
  }
  assert.equal(api.levelMeta('没这个等级').label, '清醒玩家');
});

test('页面真的引了看板的样式与脚本', () => {
  assert.match(indexHtml, /\/static\/css\/clown-board\.css\?v=joker-board-1\.0/);
  assert.match(indexHtml, /\/static\/js\/clown-board\.js\?v=joker-board-1\.0/);
});

test('鉴定所开鉴之后会把结果推给看板', () => {
  assert.match(inkSource, /window\.ClownBoard\.publish\(result/);
});
