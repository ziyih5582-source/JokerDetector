/**
 * 观心潭 · 主逻辑
 *
 * 一条流程同时驱动两件事：
 *   1) 情感分析（本地统计 + 可选 AI 长文）
 *   2) 联系人名册（可选：提取喜好、追加依据、冲突与修正）
 * 前端只调用融合接口 /api/analyze/unified，示例走 /api/analyze/demo/{id} 的同一套参数。
 */
(function () {
  'use strict';

  var $ = function (id) { return document.getElementById(id); };

  var state = {
    contacts: [],
    profile: null,
    messages: [],
    editFactId: null,
    pendingDelete: null,
    selection: 0,
    busy: false,
    lastResult: null,
    music: [],
    health: null,
    fisher: { list: [], activeId: null, streaming: false }
  };

  var SAMPLES = [
    '我：周末有什么安排？\n小林：我喜欢徒步\n我：想喝点什么？\n小林：我喜欢咖啡\n我：好的，周末见！\n小林：我的电话是13812345678',
    '我：最近口味有没有变化？\n小林：我现在不喜欢咖啡\n我：那我们换个活动吧\n小林：我喜欢看电影\n我：徒步还去吗？\n小林：我喜欢徒步'
  ];

  var LEVEL_NAME = {
    confirmed: '确诊小丑',
    high_risk: '高度疑似',
    suspicious: '轻度倾向',
    mild: '基本对等',
    healthy: '清醒玩家'
  };
  var LEVEL_TEXT = {
    confirmed: '投入严重失衡：你一个人把这段对话撑了起来。先停一停，看看对方有没有伸手。',
    high_risk: '你比对方主动太多。热情没有错，但要小心只是感动了自己。',
    suspicious: '偶尔失衡，总体还在控制里。留意一下谁在起话题、谁在收尾。',
    mild: '关系基本对等。这种节奏比任何话术都稳，继续保持。',
    healthy: '没有明显失衡：主动、表达与回应大致对等。清醒地相处，也别忘了把话说明白。'
  };
  var METRIC_ORDER = ['SSDT', 'PFI', 'PLD', 'EPEG', 'CONV'];
  // 类型 → 朱砂以外的墨色倾向（用于印章与配图氛围）
  var TYPE_INK = {
    '殉道型': '#A8443A', '镜像型': '#4A6478', '弄臣型': '#9A7628', '幻恋型': '#6B5580'
  };

  // ------------------------------------------------------------ 基础工具

  function plain(text) {
    return String(text == null ? '' : text)
      .replace(/[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}\u{2B00}-\u{2BFF}\u{FE0F}\u{2190}-\u{21FF}]/gu, '')
      .trim();
  }

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function date(value) {
    try { return new Date(value).toLocaleString('zh-CN', { hour12: false }); }
    catch (e) { return value; }
  }

  function toast(message, isError) {
    var node = $('toast');
    node.textContent = message || '';
    node.className = 'toast' + (isError ? ' error' : '');
    node.hidden = !message;
  }

  var toastTimer = null;
  function say(message, isError) {
    toast(message, isError);
    clearTimeout(toastTimer);
    if (message) toastTimer = setTimeout(function () { toast(''); }, isError ? 8000 : 6000);
  }

  var LOADING_WORDS = ['研墨中…', '看水纹的走向…', '数一数谁先开的口…', '称一称字数的轻重…', '翻一翻旧笔记…'];
  var loadingTimer = null;
  function loading(on, words) {
    var box = $('loading');
    box.hidden = !on;
    clearInterval(loadingTimer);
    if (!on) return;
    var list = words || LOADING_WORDS, i = 0;
    $('loading-text').textContent = list[0];
    loadingTimer = setInterval(function () {
      i = (i + 1) % list.length;
      $('loading-text').textContent = list[i];
    }, 2200);
  }

  function busy(on) {
    state.busy = on;
    var controls = document.querySelectorAll('button, input, select, textarea');
    Array.prototype.forEach.call(controls, function (c) { c.disabled = on; });
    if (!on) { syncOptions(); }
  }

  async function api(path, options) {
    options = options || {};
    var isForm = options.body instanceof FormData;
    var response = await fetch(path, {
      method: options.method || 'GET',
      headers: isForm ? undefined : { 'Content-Type': 'application/json' },
      body: options.body
    });
    var data = null;
    try { data = await response.json(); } catch (e) { data = null; }
    if (!response.ok) {
      var detail = data && data.detail;
      throw new Error(typeof detail === 'string' ? detail : '请求失败，请检查输入内容');
    }
    return data;
  }

  function go(view) {
    document.body.dataset.view = view;
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  // ------------------------------------------------------------ 水面交互

  function initPond() {
    window.Pond.init($('pond-canvas'));

    // 整页纸面都可以投食：只要不是点在控件上
    document.addEventListener('pointerdown', function (event) {
      if (event.button !== 0) return;
      var tag = (event.target.tagName || '').toLowerCase();
      if (['button', 'a', 'input', 'select', 'textarea', 'label', 'summary', 'dialog'].indexOf(tag) >= 0) return;
      if (event.target.closest && event.target.closest('dialog, .scroll a, .scroll button')) return;
      window.Pond.feed(event.clientX, event.clientY);
    });

    $('pond-scatter').addEventListener('click', function () {
      for (var i = 0; i < 6; i++) {
        setTimeout(function () {
          window.Pond.feed(Math.random() * window.innerWidth, Math.random() * window.innerHeight);
        }, i * 90);
      }
      say('撒了一把食，鱼会自己找。');
    });

    $('pond-toggle').addEventListener('click', function () {
      var paused = window.Pond.setPaused(!window.Pond.isPaused());
      $('pond-toggle').textContent = paused ? '活水（继续游动）' : '静水（停动画）';
    });
  }

  // ------------------------------------------------------------ 视图与导航

  function initNav() {
    document.addEventListener('click', function (event) {
      var trigger = event.target.closest ? event.target.closest('[data-go]') : null;
      if (!trigger) return;
      if (trigger.tagName === 'A') event.preventDefault();
      go(trigger.dataset.go);
    });
    $('goto-book-from-result').addEventListener('click', function () { go('book'); });
    $('goto-flow').addEventListener('click', function () { go('flow'); });
  }

  // ------------------------------------------------------------ 名册（联系人）

  async function refreshContacts() {
    var data = await api('/api/profiles/contacts');
    state.contacts = data.contacts || [];
    renderContacts();
    renderContactSelect();
  }

  function renderContacts() {
    var list = $('contact-list');
    list.replaceChildren();
    var query = ($('contact-search').value || '').toLowerCase();
    var shown = state.contacts.filter(function (c) { return c.name.toLowerCase().indexOf(query) >= 0; });
    if (!shown.length) {
      list.append(el('p', 'note', query ? '没有合得上这个名字。' : '还没有录过名。左侧输入称呼即可。'));
      return;
    }
    shown.forEach(function (c) {
      var button = el('button', 'roster-item' + (state.profile && state.profile.id === c.id ? ' active' : ''));
      button.type = 'button';
      button.setAttribute('aria-pressed', String(!!(state.profile && state.profile.id === c.id)));
      button.append(el('span', 'dot'));
      button.append(el('b', '', c.name));
      button.append(el('small', '', c.fact_count + ' 条 · ' + c.batch_count + ' 次投食'));
      button.addEventListener('click', function () {
        guard(function () { return selectContact(c.id); });
      });
      list.append(button);
    });
  }

  function renderContactSelect() {
    var select = $('contact-select');
    var current = select.value;
    select.replaceChildren();
    var none = el('option', '', '不建档 · 只看水纹');
    none.value = '';
    select.append(none);
    state.contacts.forEach(function (c) {
      var option = el('option', '', '记入《' + c.name + '》');
      option.value = c.id;
      select.append(option);
    });
    if (current && state.contacts.some(function (c) { return c.id === current; })) select.value = current;
    syncOptions();
    renderFisherContacts();
  }

  function syncOptions() {
    var hasContact = !!$('contact-select').value;
    $('save-consent').disabled = !hasContact;
    $('run-btn').textContent = hasContact ? '洒入水中 · 记名册' : '洒入水中 · 只看不记';
    if (!hasContact) $('save-consent').checked = false;
    $('archive-note').textContent = hasContact
      ? '这段聊天的喜好与观察会写进所选名册；需要勾选下面第一项确认。'
      : '只做分析，不写入名册、不落一笔。聊天的完整内容不会进入任何数据库。';
  }

  async function selectContact(id) {
    var serial = ++state.selection;
    var profile = await api('/api/profiles/contacts/' + id);
    if (serial !== state.selection) return;
    state.profile = profile;
    renderProfile();
    renderContacts();
    $('contact-select').value = id;
    syncOptions();
  }

  function renderProfile() {
    var p = state.profile;
    $('no-contact').hidden = !!p;
    $('contact-workspace').hidden = !p;
    if (!p) return;

    $('profile-name').textContent = p.name;
    $('profile-meta').textContent = '建立于 ' + date(p.created_at) + ' · 同名不会自动合并，需要你自己分辨';
    $('fact-count').textContent = p.facts.length;
    $('review-count').textContent = p.facts.filter(function (f) {
      return f.status === 'unreviewed' || f.conflict;
    }).length;
    $('batch-count').textContent = p.batches.length;
    $('revision').textContent = p.revision;

    var box = $('facts');
    box.replaceChildren();
    if (!p.facts.length) {
      box.append(el('p', 'note', '还没有可记录的信息。投入一段聊天后，有明确依据的喜好会出现在这里；没有依据就留白。'));
    }
    p.facts.forEach(function (f) { box.append(factNode(f, p)); });

    var history = $('history');
    history.replaceChildren();
    if (!p.batches.length) history.append(el('p', 'note', '还没有投过聊天。'));
    p.batches.slice().reverse().forEach(function (b, index) {
      var row = el('div', 'history-row');
      var left = el('div');
      left.append(el('strong', '', '第 ' + (p.batches.length - index) + ' 次 · ' + date(b.at)));
      if (b.warning) left.append(el('p', '', b.warning));
      row.append(left);
      row.append(el('span', 'muted', b.message_count + ' 条 · ' + (
        b.mode === 'ai' ? 'AI + 本地' : b.mode === 'local_fallback' ? '本地（AI 失败）' : '本地提取')));
      history.append(row);
    });
  }

  function factNode(f, p) {
    var wrap = el('article', 'fact' + (f.conflict ? ' conflict' : ''));

    var tags = el('div', 'tags');
    var parts = [];
    parts.push(el('span', '', f.kind === 'preference' ? '日常喜好' : '沟通观察'));
    parts.push(el('span', '', f.certainty === 'stated' ? '原话提取' : 'AI 推测 · 待核实'));
    if (f.status !== 'unreviewed') parts.push(el('span', '', f.status === 'corrected' ? '人工修正' : '人工确认'));
    if (f.conflict) parts.push(el('span', 'warn', '两种说法 · 请核实'));
    parts.forEach(function (node, i) {
      if (i) tags.append(el('span', 'sep', '｜'));
      tags.append(node);
    });
    wrap.append(tags);

    wrap.append(el('h4', '', f.text));

    var details = el('details');
    details.append(el('summary', '', '查看 ' + f.evidence.length + ' 条脱敏依据 · 最近 ' + date(f.last_seen)));
    f.evidence.forEach(function (e) {
      var quote = el('blockquote');
      quote.append(el('div', '', '「' + e.quote + '」'));
      quote.append(el('small', 'note', date(e.at) + ' · 该片段第 ' + e.message_number + ' 条 · 来自对方'));
      details.append(quote);
    });
    wrap.append(details);

    var actions = el('div', 'line-actions');
    if (f.status !== 'confirmed') {
      var confirm = el('button', 'line-btn quiet', '确认无误');
      confirm.type = 'button';
      confirm.addEventListener('click', function () {
        guard(async function () {
          state.profile = await api('/api/profiles/contacts/' + p.id + '/facts/' + f.id, {
            method: 'PATCH', body: JSON.stringify({ revision: p.revision, action: 'confirm' })
          });
          renderProfile(); renderContacts();
          say('已标为人工确认。');
        });
      });
      actions.append(confirm);
    }
    var edit = el('button', 'line-btn quiet', '修正');
    edit.type = 'button';
    edit.addEventListener('click', function () {
      state.editFactId = f.id;
      $('edit-text').value = f.text;
      $('edit-dialog').showModal();
    });
    actions.append(edit);

    var remove = el('button', 'line-btn danger', '抹去这条');
    remove.type = 'button';
    remove.addEventListener('click', function () {
      state.pendingDelete = { factId: f.id, contactId: p.id, revision: p.revision };
      $('delete-title').textContent = '抹去这一条？';
      $('delete-description').textContent = '这条信息与它的引用都会消失；同主题同倾向的自动提取也会被忽略，避免下次投食又冒出来。';
      $('delete-dialog').showModal();
    });
    actions.append(remove);

    wrap.append(actions);
    return wrap;
  }

  function guard(operation) {
    if (state.busy) return Promise.resolve();
    busy(true);
    return Promise.resolve()
      .then(operation)
      .catch(function (error) { say(error.message, true); })
      .finally(function () { busy(false); });
  }

  // ------------------------------------------------------------ 投食：解析与提交

  function clearChat() {
    state.messages = [];
    $('chat-text').value = '';
    $('chat-file').value = '';
    $('speaker-panel').hidden = true;
    $('redacted-preview').textContent = '';
    $('message-count').textContent = '';
    $('save-consent').checked = false;
  }

  function payload() {
    return {
      messages: state.messages,
      self_speaker: $('self-speaker').value,
      other_speaker: $('other-speaker').value,
      contact_id: $('contact-select').value || null,
      save_consent: $('save-consent').checked,
      use_ai: $('use-ai').checked,
      include_guidance: $('include-guidance').checked
    };
  }

  async function preview() {
    $('save-consent').checked = false;
    $('redacted-preview').textContent = '';
    // 预览接口只认这几个字段（extra="forbid"），所以不能直接丢整个 payload 过去
    var body = payload();
    delete body.contact_id;
    var data = await api('/api/profiles/preview', { method: 'POST', body: JSON.stringify(body) });
    $('redacted-preview').textContent = data.messages.map(function (m) {
      return (m.id + 1) + '. ' + (m.role === 'self' ? '自己' : '对方') + '：' + m.content;
    }).join('\n');
    $('preview-count').textContent = '· ' + data.messages.length + ' 条';
    syncOptions();
  }

  async function setMessages(messages) {
    state.messages = [];
    $('speaker-panel').hidden = true;
    var speakers = [];
    messages.forEach(function (m) { if (speakers.indexOf(m.speaker) < 0) speakers.push(m.speaker); });
    if (speakers.length !== 2) {
      throw new Error('需要明确的两位发言者：群聊请先整理，或检查「发言者：内容」格式');
    }
    state.messages = messages;
    ['self-speaker', 'other-speaker'].forEach(function (id) {
      var select = $(id);
      select.replaceChildren();
      speakers.forEach(function (s) {
        var option = el('option', '', s);
        option.value = s;
        select.append(option);
      });
    });
    $('self-speaker').value = speakers.indexOf('我') >= 0 ? '我' : speakers[0];
    $('other-speaker').value = speakers.filter(function (s) { return s !== $('self-speaker').value; })[0];
    $('message-count').textContent = '已认出 ' + messages.length + ' 条消息，请核对双方';
    await preview();
    $('speaker-panel').hidden = false;
  }

  async function parseText() {
    var lines = $('chat-text').value.split(/\r?\n/).filter(function (line) { return line.trim(); });
    if (!lines.length) throw new Error('先粘贴或输入一些聊天内容');
    var messages = lines.map(function (line, i) {
      var match = line.match(/^([^:：]{1,100})[:：]\s*(.+)$/);
      if (!match) throw new Error('第 ' + (i + 1) + ' 行不是「发言者：内容」的格式');
      return { speaker: match[1].trim(), content: match[2].trim() };
    });
    await setMessages(messages);
  }

  // 快照/比对：让结果页能说清「这次名册动了哪几条」
  async function snapshotFacts(contactId) {
    if (!contactId) return null;
    try {
      var profile = await api('/api/profiles/contacts/' + contactId);
      var map = {};
      profile.facts.forEach(function (f) { map[f.id] = { text: f.text, evidence: f.evidence.length }; });
      return { name: profile.name, map: map };
    } catch (e) { return null; }
  }

  async function submit() {
    if (!state.messages.length) throw new Error('还没有可分析的聊天：先「辨认说话的人」或选一个示例');
    var data = payload();
    if (data.contact_id && !data.save_consent) throw new Error('要写进名册，请先勾选第一项确认。');
    if (data.self_speaker === data.other_speaker) throw new Error('「我」和「对方」不能是同一个人');

    var before = await snapshotFacts(data.contact_id);
    var useAI = data.use_ai;
    loading(true, useAI
      ? ['正在请云端读这段对话…', '脱敏片段已发出，等模型回应…', '长文可能还要一会儿…']
      : LOADING_WORDS);
    try {
      var result = await api('/api/analyze/unified', { method: 'POST', body: JSON.stringify(data) });
    } finally {
      loading(false);
    }
    renderResult(result, { before: before, contactId: data.contact_id });
    go('result');
    $('save-consent').checked = false;
    if (data.contact_id) {
      state.profile = result.profile || state.profile;
      await refreshContacts();
      if (state.profile) renderProfile();
    }
    if (result.duplicate && !result.report_regenerated) {
      say('这段聊天已经投过一次：名册没有重复记账，也没有重复调用云端。');
    } else if (result.warning) {
      say(result.warning, true);
    } else if (data.contact_id) {
      say('水纹已出，名册也更新了。');
    } else {
      say('水纹已出（没有写入名册）。');
    }
  }

  async function runDemo(demoId, title) {
    var contactId = $('contact-select').value || null;
    if (contactId && !$('save-consent').checked) {
      throw new Error('示例内容是虚构的。要写进名册请先勾选确认，或把名册设为「不建档」。');
    }
    var before = await snapshotFacts(contactId);
    var query = [
      'cloud_consent=' + ($('use-ai').checked ? 'true' : 'false'),
      'include_guidance=' + ($('include-guidance').checked ? 'true' : 'false')
    ];
    if (contactId) query.push('contact_id=' + encodeURIComponent(contactId), 'save_consent=true');

    loading(true, $('use-ai').checked ? ['示例已投入水中，等云端回应…'] : ['示例已投入水中…']);
    try {
      var result = await api('/api/analyze/demo/' + demoId + '?' + query.join('&'), { method: 'POST' });
    } finally {
      loading(false);
    }
    renderResult(result, { before: before, contactId: contactId, demoTitle: plain(title) });
    go('result');
    if (contactId) {
      state.profile = result.profile || state.profile;
      await refreshContacts();
      if (state.profile) renderProfile();
      say('示例是虚构内容，已按你的选择记入《' + (before ? before.name : '名册') + '》。');
    } else {
      say('示例分析完成（未写入名册）。');
    }
  }

  // ------------------------------------------------------------ 结果渲染

  function renderResult(result, meta) {
    // 重复片段只返回档案，不再返回水纹：此时保留上一次的水纹与分享图
    if (result.analysis) state.lastResult = result;
    meta = meta || {};
    // 兼容：统一接口把水纹放在 analysis 里，这里也容忍直接返回分析对象
    var data = result.analysis || (result.verdict ? result : null);

    if (data) {
      var v = data.verdict;
      var isJoker = v.is_joker && v.type;
      $('source-note').textContent = '其二 · 水纹 · ' + plain(data.source || meta.demoTitle || '本次聊天片段');

      $('verdict-label').textContent = isJoker
        ? (v.type + ' · ' + (LEVEL_NAME[v.level] || '小丑倾向'))
        : '清醒玩家';
      $('score-subtitle').textContent = isJoker
        ? (LEVEL_TEXT[v.level] || LEVEL_TEXT.suspicious)
        : LEVEL_TEXT.healthy;
      animateScore($('score-number'), Math.round(v.score));

      var seal = $('type-seal');
      if (isJoker && v.type_info) {
        seal.hidden = false;
        $('type-seal-text').textContent = v.type.replace('型', '');
        seal.style.color = TYPE_INK[v.type] || v.type_info.color || 'var(--vermilion)';
        seal.style.borderColor = (TYPE_INK[v.type] || v.type_info.color || '#a63c30') + '99';
        $('type-block').hidden = false;
        $('type-desc').textContent = v.type_info.desc;
        $('type-suggestion').textContent = '建议 · ' + v.type_info.suggestion;
        $('type-keywords').textContent = '关键信号：' + (v.type_info.keywords || []).join(' · ');
      } else {
        seal.hidden = true;
        $('type-block').hidden = true;
      }

      drawRadar(data.z_metrics);
      renderMetrics(data.z_metrics);
      renderCompare(data.statistics);

      var guidanceBlock = $('guidance-block');
      if (data.guidance) {
        guidanceBlock.hidden = false;
        $('guidance-title').textContent = 'AI 情感分析长文';
        $('guidance-content').textContent = data.guidance;
      } else if (data.guidance_error) {
        guidanceBlock.hidden = false;
        $('guidance-title').textContent = 'AI 长文暂未生成';
        $('guidance-content').textContent = data.guidance_error + '。本地统计已保留，修好配置后重新投一次即可。';
      } else {
        guidanceBlock.hidden = true;
      }

      playMusicForType(isJoker ? v.type : null);
    }

    renderProfileOutcome(result, meta);
  }

  function animateScore(node, target) {
    var start = performance.now();
    var duration = 1200;
    function step(now) {
      var p = Math.min((now - start) / duration, 1);
      var eased = p === 1 ? 1 : 1 - Math.pow(2, -10 * p);
      node.textContent = Math.round(eased * target);
      if (p < 1) requestAnimationFrame(step); else node.textContent = target;
    }
    requestAnimationFrame(step);
  }

  function renderProfileOutcome(result, meta) {
    var block = $('profile-result');
    var body = $('profile-result-body');
    body.replaceChildren();
    block.hidden = false;

    if (!meta.contactId) {
      body.append(el('p', 'note', '这次选择了「不建档」：只出分析结果，名册里没有留下任何东西。想积累观察，可以在「投食」里选一个名册条目。'));
      return;
    }

    var profile = result.profile;
    if (!profile) {
      body.append(el('p', 'note', '名册没有变化。'));
      return;
    }

    if (result.duplicate && !result.report_regenerated) {
      body.append(el('p', 'note', '这段聊天之前已经投过（同一段脱敏片段），名册没有重复记账。'));
      body.append(el('p', 'note', '《' + profile.name + '》现有 ' + profile.facts.length + ' 条档案、' + profile.batches.length + ' 次投食记录。'));
      return;
    }

    var before = meta.before;
    var added = [], changed = [];
    profile.facts.forEach(function (f) {
      var old = before && before.map[f.id];
      if (!old) added.push(f);
      else if (old.evidence !== f.evidence.length || old.text !== f.text) changed.push(f);
    });

    var head = el('p', 'note', '写进《' + profile.name + '》：新增 ' + added.length + ' 条' +
      (changed.length ? '、补充依据 ' + changed.length + ' 条' : '') +
      '；这份名册现在共 ' + profile.facts.length + ' 条。');
    body.append(head);

    var listing = added.concat(changed).slice(0, 6);
    if (listing.length) {
      var list = el('div', 'facts');
      listing.forEach(function (f) {
        var row = el('div', 'fact' + (f.conflict ? ' conflict' : ''));
        var tags = el('div', 'tags');
        tags.append(el('span', '', added.indexOf(f) >= 0 ? '新增' : '补充依据'));
        tags.append(el('span', 'sep', '｜'));
        tags.append(el('span', '', f.certainty === 'stated' ? '原话提取' : 'AI 推测 · 待核实'));
        if (f.conflict) { tags.append(el('span', 'sep', '｜')); tags.append(el('span', 'warn', '与旧记录冲突')); }
        row.append(tags);
        row.append(el('h4', '', f.text));
        list.append(row);
      });
      body.append(list);
    } else if (!profile.facts.length) {
      body.append(el('p', 'note', '这段聊天里没有认出明确的喜好。名册留白也是一种记录。'));
    }

    var actions = el('div', 'line-actions');
    var more = el('button', 'line-btn quiet', '去名册细看与修正');
    more.type = 'button';
    more.addEventListener('click', function () {
      state.profile = profile;
      renderProfile(); renderContacts();
      go('book');
    });
    actions.append(more);
    body.append(actions);

    if (result.warning) body.append(el('p', 'note', '提示：' + result.warning));
  }

  // ---- 五维墨线雷达（手绘感：固定抖动，非实时随机） ----
  function drawRadar(metrics) {
    var svg = $('radar');
    svg.replaceChildren();
    var cx = 160, cy = 148, R = 92;
    var keys = METRIC_ORDER.filter(function (k) { return metrics[k]; });
    var n = keys.length;
    if (!n) return;

    function point(i, r) {
      var angle = -Math.PI / 2 + i * (Math.PI * 2 / n);
      return [cx + Math.cos(angle) * r, cy + Math.sin(angle) * r];
    }
    // 稳定抖动：同一索引永远得到同一偏移，看起来像手画的而不是机器画的
    function jitter(i) {
      var s = Math.sin(i * 12.9898) * 43758.5453;
      return (s - Math.floor(s) - 0.5) * 3.2;
    }
    function ring(scale, opacity, dash) {
      var pts = [];
      for (var i = 0; i < n; i++) {
        var p = point(i, R * scale);
        pts.push((p[0] + jitter(i)) + ',' + (p[1] + jitter(i + 7)));
      }
      var poly = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
      poly.setAttribute('points', pts.join(' '));
      poly.setAttribute('fill', 'none');
      poly.setAttribute('stroke', 'rgba(35,33,32,' + opacity + ')');
      poly.setAttribute('stroke-width', '1');
      if (dash) poly.setAttribute('stroke-dasharray', dash);
      svg.append(poly);
    }
    ring(1, 0.12);
    ring(0.66, 0.09);
    ring(0.33, 0.07);

    // 轴线
    for (var i = 0; i < n; i++) {
      var a = point(i, R + 4);
      var line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      line.setAttribute('x1', cx); line.setAttribute('y1', cy);
      line.setAttribute('x2', a[0].toFixed(1)); line.setAttribute('y2', a[1].toFixed(1));
      line.setAttribute('stroke', 'rgba(35,33,32,0.10)');
      svg.append(line);
    }

    // 数据墨形
    var vals = keys.map(function (k) {
      return Math.max(0, Math.min(100, (metrics[k].value + 1) * 50));
    });
    var dataPts = [];
    for (var j = 0; j < n; j++) {
      var p2 = point(j, R * (vals[j] / 100));
      dataPts.push((p2[0] + jitter(j) * 0.8) + ',' + (p2[1] + jitter(j + 3) * 0.8));
    }
    var shape = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
    shape.setAttribute('points', dataPts.join(' '));
    shape.setAttribute('fill', 'rgba(35,33,32,0.07)');
    shape.setAttribute('stroke', 'rgba(35,33,32,0.62)');
    shape.setAttribute('stroke-width', '1.5');
    shape.setAttribute('stroke-linejoin', 'round');
    svg.append(shape);

    // 顶点：最高的一项点朱砂
    var maxIndex = vals.indexOf(Math.max.apply(null, vals));
    for (var k2 = 0; k2 < n; k2++) {
      var pk = point(k2, R * (vals[k2] / 100));
      var dot = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      dot.setAttribute('cx', (pk[0] + jitter(k2) * 0.8).toFixed(1));
      dot.setAttribute('cy', (pk[1] + jitter(k2 + 3) * 0.8).toFixed(1));
      dot.setAttribute('r', k2 === maxIndex ? '3.2' : '2');
      dot.setAttribute('fill', k2 === maxIndex ? '#a63c30' : 'rgba(35,33,32,0.6)');
      svg.append(dot);

      var label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      var lp = point(k2, R + 26);
      label.setAttribute('x', lp[0].toFixed(1));
      label.setAttribute('y', (lp[1] + 4).toFixed(1));
      label.setAttribute('text-anchor', Math.abs(lp[0] - cx) < 6 ? 'middle' : (lp[0] > cx ? 'start' : 'end'));
      label.setAttribute('font-size', '11.5');
      label.setAttribute('fill', k2 === maxIndex ? '#a63c30' : 'rgba(77,73,69,0.95)');
      label.setAttribute('font-family', 'var(--serif)');
      label.textContent = metrics[keys[k2]].label;
      svg.append(label);
    }
  }

  function renderMetrics(metrics) {
    var list = $('metric-list');
    list.replaceChildren();
    METRIC_ORDER.forEach(function (key) {
      var metric = metrics[key];
      if (!metric) return;
      var li = el('li', 'metric-item');
      li.append(el('span', 'name', metric.label));
      var track = el('span', 'track');
      var fill = el('span', 'fill');
      var value = Math.max(-1, Math.min(1, metric.value));
      var width = Math.abs(value) * 50;
      if (value >= 0) { fill.style.left = '50%'; } else { fill.style.left = (50 - width) + '%'; }
      fill.style.width = width + '%';
      fill.title = metric.desc;
      track.append(fill);
      li.append(track);
      li.append(el('span', 'val', (value >= 0 ? '偏上 ' : '偏下 ') + Math.abs(value).toFixed(2)));
      list.append(li);
    });
    list.append(el('p', 'note', '墨线从中线出发：向右是「比对方更重」，向左是「比对方更轻」。悬停可见每项含义。'));
  }

  function renderCompare(stats) {
    var box = $('compare');
    box.replaceChildren();
    var rows = [
      ['消息数', stats.message_count.self, stats.message_count.other],
      ['总字数', stats.total_chars.self, stats.total_chars.other],
      ['表情包', stats.sticker_count.self, stats.sticker_count.other],
      ['图片', stats.picture_count.self, stats.picture_count.other],
      ['最长连发', stats.max_streak.self, stats.max_streak.other],
      ['平均字数', stats.avg_chars.self, stats.avg_chars.other]
    ];
    rows.forEach(function (row) {
      var max = Math.max(row[1], row[2], 1);
      var wrap = el('div', 'compare-row');
      wrap.append(el('span', 'label', row[0]));
      var bars = el('span', 'compare-bars');
      var selfBar = el('span', 'bar');
      selfBar.style.width = Math.max(2, (row[1] / max) * 100) + '%';
      var otherBar = el('span', 'bar other');
      otherBar.style.width = Math.max(2, (row[2] / max) * 100) + '%';
      bars.append(selfBar, otherBar);
      wrap.append(bars);
      var ratio = row[2] === 0 ? (row[1] > 0 ? '∞' : '0') : (row[1] / row[2]).toFixed(2);
      wrap.append(el('span', 'nums', '我 ' + row[1] + ' / 对方 ' + row[2] + '\n倍 ' + ratio));
      box.append(wrap);
    });
    if (stats.has_voice_or_call) {
      box.append(el('p', 'note', '这段聊天里出现了语音或通话记录，算法对它额外加了权重。'));
    }
    box.append(el('p', 'note', '深色墨线是你，浅色是对方。只看线长，不必在意数值本身。'));
  }

  // ------------------------------------------------------------ 分享图片（本机绘制，不依赖外部库）

  function shareImage() {
    var data = state.lastResult && state.lastResult.analysis;
    if (!data) { say('先投一次食，才有可拓的水纹。', true); return; }
    var W = 900, H = 1240;
    var canvas = document.createElement('canvas');
    canvas.width = W; canvas.height = H;
    var c = canvas.getContext('2d');
    var serif = '"Songti SC", "STSong", "Noto Serif SC", serif';

    c.fillStyle = '#f4f0e6';
    c.fillRect(0, 0, W, H);
    // 淡墨晕染 + 三条鱼的剪影
    for (var i = 0; i < 14; i++) {
      var x = Math.random() * W, y = Math.random() * H, r = 90 + Math.random() * 260;
      var g = c.createRadialGradient(x, y, 0, x, y, r);
      g.addColorStop(0, 'rgba(38,36,34,0.045)');
      g.addColorStop(1, 'rgba(38,36,34,0)');
      c.fillStyle = g;
      c.beginPath(); c.arc(x, y, r, 0, Math.PI * 2); c.fill();
    }
    c.save();
    c.shadowColor = 'rgba(38,36,34,0.28)';
    c.shadowBlur = 22;
    [[180, 300, 1], [700, 220, -1], [420, 980, 1]].forEach(function (f) {
      var fx = f[0], fy = f[1], dir = f[2], size = 44;
      c.beginPath();
      c.moveTo(fx - dir * size, fy);
      c.quadraticCurveTo(fx, fy - size * 0.55, fx + dir * size, fy);
      c.quadraticCurveTo(fx, fy + size * 0.55, fx - dir * size, fy);
      c.fillStyle = 'rgba(38,36,34,0.30)';
      c.fill();
      c.beginPath();
      c.moveTo(fx - dir * size, fy);
      c.quadraticCurveTo(fx - dir * size * 1.6, fy - size * 0.5, fx - dir * size * 1.9, fy - size * 0.55);
      c.moveTo(fx - dir * size, fy);
      c.quadraticCurveTo(fx - dir * size * 1.6, fy + size * 0.5, fx - dir * size * 1.9, fy + size * 0.55);
      c.strokeStyle = 'rgba(38,36,34,0.22)';
      c.lineWidth = 5;
      c.lineCap = 'round';
      c.stroke();
    });
    c.restore();

    var ink = '#232120', soft = '#7c766c';
    c.fillStyle = soft;
    c.font = '20px ' + serif;
    c.fillText('观心潭 · 情感分析', 70, 96);
    c.fillStyle = 'rgba(35,33,32,0.16)';
    c.fillRect(70, 120, W - 140, 1);
    c.fillStyle = soft;
    c.font = '17px ' + serif;
    c.fillText(plain(data.source || ''), 70, 158);

    var v = data.verdict;
    c.fillStyle = ink;
    c.font = '150px ' + serif;
    c.fillText(String(Math.round(v.score)), 64, 330);
    c.font = '22px ' + serif;
    c.fillStyle = soft;
    c.fillText('/ 100', 70 + c.measureText(String(Math.round(v.score))).width + 190, 328);

    c.fillStyle = ink;
    c.font = '40px ' + serif;
    c.fillText(v.is_joker && v.type ? v.type + ' · ' + (LEVEL_NAME[v.level] || '') : '清醒玩家', 70, 400);
    c.fillStyle = soft;
    c.font = '20px ' + serif;
    wrapText(c, LEVEL_TEXT[v.level] || '', 70, 448, W - 150, 34);

    var y = 560;
    c.fillStyle = 'rgba(35,33,32,0.16)';
    c.fillRect(70, y, W - 140, 1);
    y += 46;
    c.fillStyle = ink;
    c.font = '24px ' + serif;
    c.fillText('五维墨线', 70, y);
    y += 44;
    METRIC_ORDER.forEach(function (key) {
      var metric = data.z_metrics[key];
      if (!metric) return;
      var value = Math.max(-1, Math.min(1, metric.value));
      c.fillStyle = soft;
      c.font = '19px ' + serif;
      c.fillText(metric.label, 70, y + 6);
      c.fillStyle = 'rgba(35,33,32,0.14)';
      c.fillRect(300, y + 1, 420, 1);
      c.fillStyle = 'rgba(35,33,32,0.65)';
      var w = Math.abs(value) * 210;
      c.fillRect(value >= 0 ? 510 : 510 - w, y, w, 2);
      c.fillStyle = soft;
      c.fillText(value.toFixed(2), 760, y + 6);
      y += 46;
    });

    y += 10;
    c.fillStyle = 'rgba(35,33,32,0.16)';
    c.fillRect(70, y, W - 140, 1);
    y += 46;
    var s = data.statistics;
    c.fillStyle = ink;
    c.font = '24px ' + serif;
    c.fillText('双方比对', 70, y);
    y += 42;
    [['消息数', s.message_count], ['总字数', s.total_chars], ['表情包', s.sticker_count], ['最长连发', s.max_streak]]
      .forEach(function (row) {
        c.fillStyle = soft;
        c.font = '19px ' + serif;
        c.fillText(row[0], 70, y + 6);
        c.fillStyle = ink;
        c.fillText('我 ' + row[1].self + '   /   对方 ' + row[1].other, 300, y + 6);
        y += 40;
      });

    c.fillStyle = soft;
    c.font = '16px ' + serif;
    wrapText(c, '仅供课程学习与娱乐，请勿用于真实情感决策。数值只描述这段聊天，不代表感情、动机或人格。',
      70, H - 90, W - 150, 26);

    var url = canvas.toDataURL('image/png');
    var link = document.createElement('a');
    link.href = url;
    link.download = '观心潭水纹.png';
    link.click();
    say('已拓成一张纸，检查下载目录。');
  }

  function wrapText(c, text, x, y, maxWidth, lineHeight) {
    var line = '';
    for (var i = 0; i < text.length; i++) {
      var test = line + text[i];
      if (c.measureText(test).width > maxWidth && line) {
        c.fillText(line, x, y);
        line = text[i];
        y += lineHeight;
      } else {
        line = test;
      }
    }
    if (line) c.fillText(line, x, y);
  }

  // ------------------------------------------------------------ AI 配置

  async function health() {
    try {
      var data = await api('/api/health');
      state.health = data;
      $('footer-status').textContent = data.ai_available
        ? (data.ai_verified ? 'AI 已配置并已验证 · ' + data.ai_model : 'AI 已配置，尚未验证 · ' + data.ai_model)
        : '仅本地模式 · 未配置云端 AI';
      $('ai-status').textContent = data.ai_available
        ? '云端已就绪：' + data.ai_model + '（只有勾选后才会发送脱敏片段）'
        : '未配置云端 AI。本地统计与喜好提取可直接使用。';
      if ($('fisher-status') && !state.fisher.streaming) {
        $('fisher-status').textContent = data.ai_available
          ? '钓翁已就绪 · ' + data.ai_model
          : '未配置云端 AI · 到「墨设」配置后钓翁才听得见';
      }
      return data;
    } catch (e) {
      $('footer-status').textContent = '后端未连接，请检查服务是否在运行';
      $('ai-status').textContent = '读不到后端状态。';
      return null;
    }
  }

  function initConfig() {
    $('ai-save-btn').addEventListener('click', function () {
      guard(async function () {
        var apiKey = $('ai-api-key').value.trim();
        var model = $('ai-model').value.trim();
        var baseUrl = $('ai-base-url').value.trim();
        if (!apiKey) throw new Error('请填入 API Key');
        if (!model) throw new Error('请填入服务商提供的完整模型 ID');
        var data = await api('/api/config', {
          method: 'POST', body: JSON.stringify({ api_key: apiKey, model: model, base_url: baseUrl })
        });
        $('ai-api-key').value = '';
        $('ai-config-msg').textContent = data.success
          ? '已保存 ' + data.model + '，接着点「验证调用」确认真的能用。'
          : '配置未被接受，请检查 Key 与地址。';
        await health();
      });
    });

    $('ai-test-btn').addEventListener('click', function () {
      guard(async function () {
        $('ai-config-msg').textContent = '正在发送一段固定的虚构示例…';
        var data = await api('/api/config/test', { method: 'POST' });
        $('ai-config-msg').textContent = data.success ? '验证成功：' + data.message : '验证失败：' + data.error.message;
        await health();
      });
    });
  }

  // ------------------------------------------------------------ 配乐

  var TYPE_MUSIC = { '殉道型': '过火', '镜像型': '一直很安静', '弄臣型': '怪咖', '幻恋型': '水星记' };

  function initMusic() {
    var audio = $('music-audio');
    audio.volume = $('music-volume').value / 100;
    $('music-volume').addEventListener('input', function () { audio.volume = this.value / 100; });
    $('music-toggle-btn').addEventListener('click', function () {
      if (!audio.src) { say('还没有选曲目：先做一次分析，或把 mp3 放进 music/ 目录。', true); return; }
      if (audio.paused) { audio.play().catch(function () {}); }
      else { audio.pause(); }
    });
    audio.addEventListener('play', function () { $('music-toggle-btn').textContent = '❚❚ 暂停'; });
    audio.addEventListener('pause', function () { $('music-toggle-btn').textContent = '▶ 播放'; });

    api('/api/music').then(function (data) { state.music = data.music || []; }).catch(function () {});
  }

  function playMusicForType(type) {
    if (!type) return;
    var wanted = TYPE_MUSIC[type];
    if (!wanted || !state.music.length) return;
    var file = state.music.filter(function (f) {
      return f.replace(/\.[^.]+$/, '') === wanted;
    })[0];
    if (!file) return;
    var audio = $('music-audio');
    var src = '/music/' + encodeURIComponent(file);
    if (audio.getAttribute('src') !== src) {
      audio.setAttribute('src', src);
      $('music-track-name').textContent = file.replace(/\.[^.]+$/, '');
    }
    audio.play().catch(function () {});
  }

  // ------------------------------------------------------------ 示例列表

  async function loadDemos() {
    var box = $('demo-list');
    try {
      var data = await api('/api/demos');
      data.demos.forEach(function (d) {
        var button = el('button', 'demo-item');
        button.type = 'button';
        button.append(el('b', '', plain(d.title)));
        button.append(el('span', '', d.description + ' · ' + d.self_name + ' / ' + d.other_name + ' · ' + d.message_count + ' 条'));
        button.addEventListener('click', function () {
          guard(function () { return runDemo(d.id, d.title); });
        });
        box.append(button);
      });
    } catch (e) {
      box.append(el('p', 'note', '读不到内置示例。'));
    }
  }

  // ------------------------------------------------------------ 事件绑定

  function initFlow() {
    $('parse-text').addEventListener('click', function () { guard(parseText); });
    $('clear-chat').addEventListener('click', function () { clearChat(); syncOptions(); say('已清空本次内容。'); });

    $('sample-one').addEventListener('click', function () {
      guard(async function () {
        $('chat-text').value = SAMPLES[0];
        await parseText();
        say('已填入虚构示例，请核对双方对应关系。');
      });
    });
    $('sample-two').addEventListener('click', function () {
      guard(async function () {
        $('chat-text').value = SAMPLES[1];
        await parseText();
        say('第二个示例里有口味变化，可以看冲突提示与去重。');
      });
    });

    $('chat-text').addEventListener('input', function () {
      state.messages = [];
      $('speaker-panel').hidden = true;
      $('message-count').textContent = '文本变了，请重新辨认';
      $('redacted-preview').textContent = '';
    });

    $('chat-file').addEventListener('change', function () {
      var input = this;
      guard(async function () {
        var file = input.files[0];
        if (!file) return;
        clearChat();
        if (file.size > 5 * 1024 * 1024) throw new Error('文件不能超过 5 MB');
        var form = new FormData();
        form.append('file', file);
        var parsed = await api('/api/profiles/parse', { method: 'POST', body: form });
        await setMessages(parsed.messages);
        say('Excel 已解析。文件不会被保存进名册，请核对「我 / 对方」。');
      });
    });

    ['self-speaker', 'other-speaker'].forEach(function (id) {
      $(id).addEventListener('change', function () {
        var opposite = id === 'self-speaker' ? 'other-speaker' : 'self-speaker';
        var speakers = [];
        state.messages.forEach(function (m) { if (speakers.indexOf(m.speaker) < 0) speakers.push(m.speaker); });
        $(opposite).value = speakers.filter(function (s) { return s !== $(id).value; })[0] || '';
        guard(preview);
      });
    });

    $('contact-select').addEventListener('change', syncOptions);

    $('create-contact').addEventListener('click', function () {
      guard(async function () {
        var name = $('contact-name').value.trim();
        if (!name) throw new Error('先写一个称呼');
        var created = await api('/api/profiles/contacts', { method: 'POST', body: JSON.stringify({ name: name }) });
        $('contact-name').value = '';
        await refreshContacts();
        await selectContact(created.id);
        say('已录名《' + created.name + '》。可以开始投食了。');
      });
    });

    $('use-ai').addEventListener('change', function () {
      $('include-guidance').checked = this.checked;
    });
    $('include-guidance').addEventListener('change', function () {
      if (this.checked) $('use-ai').checked = true;
    });

    $('run-btn').addEventListener('click', function () { guard(submit); });
    $('share-btn').addEventListener('click', shareImage);
  }

  function initBook() {
    $('contact-search').addEventListener('input', renderContacts);
    $('export-contact').addEventListener('click', function () {
      if (!state.profile) return;
      var data = Object.assign({}, state.profile, {
        export_note: '含脱敏依据的个人档案，请妥善保管。时间为导入时间，推测不代表完整人格。'
      });
      var url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json;charset=utf-8' }));
      var link = el('a');
      link.href = url;
      link.download = 'contact-profile-' + state.profile.id.slice(0, 8) + '.json';
      link.click();
      setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
      say('已导出 JSON（明文文件，请自行保管）。');
    });

    $('delete-contact').addEventListener('click', function () {
      if (!state.profile) return;
      state.pendingDelete = { contactId: state.profile.id };
      $('delete-title').textContent = '抹去《' + state.profile.name + '》？';
      $('delete-description').textContent = '本机数据库里的联系人、全部依据与投食记录都会消失。已导出的文件、或第三方服务收到的内容不受影响。';
      $('delete-dialog').showModal();
    });

    $('cancel-delete').addEventListener('click', function () { $('delete-dialog').close(); });
    $('confirm-delete').addEventListener('click', function () {
      guard(async function () {
        var pending = state.pendingDelete;
        if (pending.factId) {
          state.profile = await api('/api/profiles/contacts/' + pending.contactId + '/facts/' + pending.factId, {
            method: 'PATCH', body: JSON.stringify({ revision: pending.revision, action: 'delete' })
          });
        } else {
          await api('/api/profiles/contacts/' + pending.contactId, { method: 'DELETE' });
          state.profile = null;
          clearChat();
        }
        $('delete-dialog').close();
        renderProfile(); await refreshContacts();
        say('已抹去。');
      });
    });

    $('cancel-edit').addEventListener('click', function () { $('edit-dialog').close(); });
    $('edit-form').addEventListener('submit', function (event) {
      event.preventDefault();
      guard(async function () {
        state.profile = await api('/api/profiles/contacts/' + state.profile.id + '/facts/' + state.editFactId, {
          method: 'PATCH',
          body: JSON.stringify({ revision: state.profile.revision, action: 'correct', text: $('edit-text').value })
        });
        $('edit-dialog').close();
        renderProfile(); await refreshContacts();
        say('已保存人工修正，之后的自动提取不会覆盖它。');
      });
    });
  }

  // ------------------------------------------------------------ 问钓翁（情感对话）
  // 对话只存在内存里；服务端不保存。选定名册里的某个人并勾选后，
  // 才把 TA 的脱敏档案作为背景发出去（可得先用预览确认发了什么）。

  var fisherSeq = 0;

  function activeChat() {
    var list = state.fisher.list;
    if (!list.length) return newChat(false);
    for (var i = 0; i < list.length; i++) if (list[i].id === state.fisher.activeId) return list[i];
    return list[list.length - 1];
  }

  function newChat(redraw) {
    fisherSeq += 1;
    var select = $('fisher-contact');
    var chat = {
      id: 'chat' + fisherSeq,
      title: '',
      contactId: select ? select.value : '',
      useProfile: false,
      messages: []
    };
    state.fisher.list.push(chat);
    state.fisher.activeId = chat.id;
    if (redraw !== false) { renderFisherList(); renderThread(); syncFisherControls(); }
    return chat;
  }

  function whoLabel(contactId) {
    if (!contactId) return '随便聊聊';
    var found = state.contacts.filter(function (c) { return c.id === contactId; })[0];
    return found ? '谈《' + found.name + '》' : '谈某段关系';
  }

  function renderFisherList() {
    var box = $('fisher-list');
    box.replaceChildren();
    if (!state.fisher.list.length) {
      box.append(el('p', 'note', '还没有对话。'));
      return;
    }
    state.fisher.list.slice().reverse().forEach(function (chat) {
      var button = el('button', 'roster-item' + (chat.id === state.fisher.activeId ? ' active' : ''));
      button.type = 'button';
      button.append(el('span', 'dot'));
      button.append(el('b', '', chat.title || '新的对话'));
      button.append(el('small', '', whoLabel(chat.contactId) + ' · ' + chat.messages.length + ' 句'));
      button.addEventListener('click', function () {
        state.fisher.activeId = chat.id;
        renderFisherList(); renderThread(); syncFisherControls();
      });
      box.append(button);
    });
  }

  function renderFisherContacts() {
    var select = $('fisher-contact');
    if (!select) return;
    var current = select.value;
    select.replaceChildren();
    var none = el('option', '', '不谈具体的人 · 随便聊聊');
    none.value = '';
    select.append(none);
    state.contacts.forEach(function (c) {
      var option = el('option', '', '谈《' + c.name + '》');
      option.value = c.id;
      select.append(option);
    });
    var stillThere = !current || state.contacts.some(function (c) { return c.id === current; });
    select.value = stillThere ? current : '';
    syncFisherControls();
  }

  function syncFisherControls() {
    var chat = activeChat();
    var select = $('fisher-contact');
    if (chat && chat.contactId && state.contacts.some(function (c) { return c.id === chat.contactId; })) {
      select.value = chat.contactId;
    } else if (chat) {
      chat.contactId = '';
      select.value = '';
    }
    var hasPerson = !!select.value;
    $('fisher-use-profile').disabled = !hasPerson;
    $('fisher-use-profile').checked = !!(chat && hasPerson && chat.useProfile);
    refreshFisherContext();
  }

  function renderThread() {
    var chat = activeChat();
    var box = $('fisher-thread');
    box.replaceChildren();
    if (!chat || !chat.messages.length) {
      var empty = el('div', 'thread-empty');
      empty.append(el('p', '', '潭水很静。'));
      empty.append(el('p', 'note', '说点什么都可以：今天为什么难受、那条消息要不要发、这段关系是不是只有你在用力。钓翁会先听，再和你一起看。'));
      box.append(empty);
      return;
    }
    chat.messages.forEach(function (message) { box.append(messageNode(message)); });
  }

  function messageNode(message) {
    var mine = message.role === 'user';
    var wrap = el('div', 'msg ' + (mine ? 'me' : 'fisher') + (message.meta && message.meta.error ? ' error' : ''));
    wrap.append(el('div', 'who', mine ? '我' : '钓翁'));
    var body = el('div', 'body', message.content || '');
    wrap.append(body);
    message.node = body;

    if (!mine) {
      var notes = [];
      if (message.meta && message.meta.usedFacts) {
        notes.push('参考了 TA 的 ' + message.meta.usedFacts + ' 条档案' +
          (message.meta.conflicts ? '（其中 ' + message.meta.conflicts + ' 条互相冲突）' : ''));
      }
      if (message.meta && message.meta.redacted) notes.push('发送前已做基础脱敏');
      if (notes.length) wrap.append(el('div', 'meta', notes.join(' · ')));
    }
    return wrap;
  }

  async function refreshFisherContext() {
    var box = $('fisher-context-box');
    var id = $('fisher-contact').value;
    var wanted = $('fisher-use-profile').checked && !!id;
    if (!wanted) {
      box.hidden = true;
      $('fisher-context').textContent = '';
      return;
    }
    box.hidden = false;
    $('fisher-context-count').textContent = '· 读取中…';
    try {
      var data = await api('/api/fisherman/context', {
        method: 'POST', body: JSON.stringify({ contact_id: id })
      });
      $('fisher-context').textContent = data.text;
      $('fisher-context-count').textContent = '· ' + data.fact_count + ' 条' +
        (data.conflicts ? '，其中 ' + data.conflicts + ' 条有冲突' : '');
    } catch (error) {
      $('fisher-context').textContent = error.message;
      $('fisher-context-count').textContent = '';
    }
  }

  function nearBottom() {
    return window.innerHeight + window.scrollY >= document.body.scrollHeight - 180;
  }

  function applyEvent(event, reply) {
    if (event.type === 'start') {
      reply.meta.usedFacts = event.used_facts || 0;
      reply.meta.conflicts = event.conflicts || 0;
      reply.meta.redacted = !!event.redacted;
    } else if (event.type === 'delta') {
      reply.content += event.text;
      if (reply.node) reply.node.textContent = reply.content;
    } else if (event.type === 'error') {
      reply.meta.error = true;
      reply.content = reply.content || event.message;
      if (reply.node) reply.node.textContent = reply.content;
    }
  }

  function consume(block, reply) {
    var wasNear = nearBottom();
    block.split('\n').forEach(function (line) {
      if (line.indexOf('data: ') !== 0) return;
      var event = null;
      try { event = JSON.parse(line.slice(6)); } catch (e) { return; }
      applyEvent(event, reply);
    });
    if (wasNear) window.scrollTo({ top: document.body.scrollHeight });
  }

  async function streamReply(chat, reply) {
    state.fisher.streaming = true;
    $('fisher-send').disabled = true;
    $('fisher-status').textContent = '钓翁正在听…';
    var history = chat.messages.slice(0, -1).map(function (message) {
      return { role: message.role, content: message.content };
    });
    try {
      var response = await fetch('/api/fisherman/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: history,
          contact_id: chat.contactId || null,
          use_profile: !!chat.useProfile
        })
      });
      if (!response.ok) {
        var detail = null;
        try { detail = (await response.json()).detail; } catch (e) { detail = null; }
        throw new Error(typeof detail === 'string' ? detail : '请求失败（HTTP ' + response.status + '）');
      }
      var reader = response.body.getReader();
      var decoder = new TextDecoder('utf-8');
      var buffer = '';
      for (;;) {
        var chunk = await reader.read();
        if (chunk.done) break;
        buffer += decoder.decode(chunk.value, { stream: true });
        var blocks = buffer.split('\n\n');
        buffer = blocks.pop();
        blocks.forEach(function (block) { consume(block, reply); });
      }
      if (buffer.trim()) consume(buffer, reply);
    } catch (error) {
      reply.meta.error = true;
      reply.content = reply.content || error.message;
    } finally {
      state.fisher.streaming = false;
      $('fisher-send').disabled = false;
      $('fisher-status').textContent = '';
      renderThread();
      if (nearBottom()) window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
    }
  }

  async function sendFisher() {
    if (state.fisher.streaming) return;
    var input = $('fisher-input');
    var text = input.value.trim();
    if (!text) { say('先写点什么，再交给钓翁。', true); return; }
    var health = state.health || await health();
    if (!health || !health.ai_available) {
      $('fisher-status').textContent = '钓翁要连通云端才听得见你说话。';
      say('还没有配置云端 AI。到「墨设」填好 API Key、模型 ID 与地址，点「验证调用」之后就能聊了。', true);
      return;
    }
    var chat = activeChat();
    chat.contactId = $('fisher-contact').value || '';
    chat.useProfile = !!($('fisher-use-profile').checked && chat.contactId);
    chat.messages.push({ role: 'user', content: text });
    if (!chat.title) chat.title = text.slice(0, 16) + (text.length > 16 ? '…' : '');
    input.value = '';
    var reply = { role: 'assistant', content: '', meta: {} };
    chat.messages.push(reply);
    renderFisherList();
    renderThread();
    if (nearBottom()) window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
    await streamReply(chat, reply);
  }

  function initFisherman() {
    $('fisher-new').addEventListener('click', function () {
      newChat();
      $('fisher-input').focus();
      say('开了一段新对话。');
    });
    $('fisher-contact').addEventListener('change', function () {
      var chat = activeChat();
      chat.contactId = this.value || '';
      if (!chat.contactId) chat.useProfile = false;
      syncFisherControls();
      renderFisherList();
    });
    $('fisher-use-profile').addEventListener('change', function () {
      activeChat().useProfile = this.checked;
      refreshFisherContext();
    });
    $('fisher-send').addEventListener('click', function () { sendFisher(); });
    $('fisher-input').addEventListener('keydown', function (event) {
      if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
        event.preventDefault();
        sendFisher();
      }
    });
    newChat();
    renderThread();
  }

  // ------------------------------------------------------------ 启动

  document.addEventListener('DOMContentLoaded', function () {
    initPond();
    initNav();
    initFlow();
    initBook();
    initConfig();
    initMusic();
    initFisherman();
    // 云端与长文默认都关掉，由用户自己打开
    $('include-guidance').checked = false;
    $('use-ai').checked = false;
    syncOptions();
    guard(refreshContacts);
    health();
    loadDemos();
    window.addEventListener('focus', function () { health(); });
  });
})();
