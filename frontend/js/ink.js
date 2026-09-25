/**
 * 交心 · 思源湖研究所 · 主逻辑
 *
 * 一条流程同时驱动两件事：
 *   1) 情感分析（本地统计 + 可选 AI 长文）
 *   2) 人物档案（可选：提取喜好、追加依据、冲突与修正）
 * 前端只调用融合接口 /api/analyze/unified，示例走 /api/analyze/demo/{id} 的同一套参数。
 */
(function () {
  'use strict';

  var $ = function (id) { return document.getElementById(id); };

  var state = {
    contacts: [],
    profile: null,
    messages: [],
    ocrUsed: false,
    ocrAvatars: null,
    ocrOtherName: null,
    editFactId: null,
    pendingDelete: null,
    selection: 0,
    busy: false,
    lastResult: null,
    music: [],
    health: null,
    guide: null,
    theoryDone: false,
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
    // 五维指标的悬停释义
  var METRIC_TIPS = {
    SSDT: {
      title: '连续发送倾向',
      body: '比较你与对方连续发送消息的情况。数值偏上，表示这一行为在你的聊天中相对更多。',
      method: '算法依据：统计相邻消息是否连续由同一人发送。'
    },
    PFI: {
      title: '自我中心指数',
      body: '观察聊天中“我、俺、自己”和“我们、咱们”等词语的相对使用情况。',
      method: '算法依据：比较双方自我指代词与集体指代词的相对使用程度。'
    },
    PLD: {
      title: '低姿态语言密度',
      body: '观察道歉、犹豫、缓和语气等表达在聊天中的出现密度。数值偏上，表示这类表达在你的消息中相对更多。',
      method: '算法依据：统计“可能、也许、对吧、对不起、抱歉”等预设词语及相关符号。'
    },
    EPEG: {
      title: '情感表达差',
      body: '比较你与对方在情感词和情感符号上的使用强度差异。',
      method: '算法依据：统计预设情感词以及“！”等情感信号的出现情况。'
    },
    CONV: {
      title: '对话衔接度',
      body: '观察你的回复与对方上一条消息在用词上的衔接程度。数值偏上，表示你的回复更常出现这种衔接。',
      method: '算法依据：检查相邻双方消息是否共同出现预设的功能词。'
    }
  };

  var metricTooltip = null;
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

  // 导航上的「你在这里」：页面名与按钮同名，第一次用也能对上
  var VIEW_LABELS = {
    pond: '首页 · 思源湖',
    flow: '谈心分析',
    result: '分析结果',
    fisherman: '找钓翁聊聊',
    book: '人物档案',
    theory: '心理学依据',
    guide: '使用说明',
    config: '设置'
  };

  function setHere(view) {
    var node = $('nav-here');
    if (node) node.textContent = VIEW_LABELS[view] || '';
  }

  function go(view) {
    document.body.dataset.view = view;
    setHere(view);
    if (view === 'theory') renderTheory();
    if (view === 'guide') renderGuide();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  // ------------------------------------------------------------ 湖面交互

  function initPond() {
    window.Pond.init($('pond-canvas'));

    // 首页放的是思源湖画卷，鱼留到别的页面；其余页面整片纸面都能投食（只要不是点在控件上）
    document.addEventListener('pointerdown', function (event) {
      if (event.button !== 0) return;
      if (document.body.dataset.view === 'pond') return;
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
      $('pond-toggle').textContent = paused ? '继续湖面动画' : '暂停湖面动画';
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

  // ------------------------------------------------------------ 人物档案

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
      button.append(el('small', '', c.fact_count + ' 条 · ' + c.batch_count + ' 次分析'));
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
    $('run-btn').textContent = hasContact ? '开始分析 · 存入档案' : '开始分析 · 只看不记';
    if (!hasContact) $('save-consent').checked = false;
    $('archive-note').textContent = hasContact
      ? '这段聊天的喜好与观察会写进所选档案；需要勾选下面第一项确认。'
      : '只做分析，不写入档案、不落一笔。聊天的完整内容不会进入任何数据库。';
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

    var remove = el('button', 'line-btn danger', '删除这条');
    remove.type = 'button';
    remove.addEventListener('click', function () {
      state.pendingDelete = { factId: f.id, contactId: p.id, revision: p.revision };
      $('delete-title').textContent = '删除这一条？';
      $('delete-description').textContent = '这条信息与它的引用都会消失；同主题同倾向的自动提取也会被忽略，避免下次分析又冒出来。';
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

  // ------------------------------------------------------------ 谈心分析：解析与提交

  function clearChat() {
    state.messages = [];
    state.ocrUsed = false;
    state.ocrAvatars = null;
    state.ocrOtherName = null;
    $('chat-text').value = '';
    $('chat-file').value = '';
    $('chat-image').value = '';
    $('speaker-panel').hidden = true;
    $('ocr-review').hidden = true;
    $('ocr-table').replaceChildren();
    $('ocr-note').textContent = '';
    $('redacted-preview').textContent = '';
    $('message-count').textContent = '';
    $('save-consent').checked = false;
  }

  function payload() {
    return {
      messages: state.messages.map(function (m) {
        var message = { speaker: m.speaker, content: m.content };
        if (m.emoji_emotion) message.emotion = m.emoji_emotion;
        return message;
      }),
      self_speaker: $('self-speaker').value,
      other_speaker: $('other-speaker').value,
      contact_id: $('contact-select').value || null,
      save_consent: $('save-consent').checked,
      use_ai: $('use-ai').checked,
      include_guidance: $('include-guidance').checked
    };
  }

  function applyPreview(data) {
    $('redacted-preview').textContent = data.messages.map(function (m) {
      var emotion = m.emotion ? '（表情情绪：' + m.emotion + '）' : '';
      return (m.id + 1) + '. ' + (m.role === 'self' ? '自己' : '对方') + '：' + m.content + emotion;
    }).join('\n');
    $('preview-count').textContent = '· ' + data.messages.length + ' 条';
    syncOptions();
  }

  function previewBody() {
    // 预览接口只认这几个字段（extra="forbid"），所以不能直接丢整个 payload 过去
    var body = payload();
    delete body.contact_id;
    return body;
  }

  async function preview() {
    $('save-consent').checked = false;
    $('redacted-preview').textContent = '';
    var data = await api('/api/profiles/preview', { method: 'POST', body: JSON.stringify(previewBody()) });
    applyPreview(data);
  }

  // 编辑校对表时用：不打断输入（不 busy、不重置确认），失败就静默等到提交时再说
  async function softPreview() {
    if (state.busy) return;
    try {
      var data = await api('/api/profiles/preview', { method: 'POST', body: JSON.stringify(previewBody()) });
      applyPreview(data);
    } catch (e) { /* 编辑过程中的中间态可以不是合法双人聊天 */ }
  }

  async function setMessages(messages) {
    state.messages = [];
    state.ocrUsed = false;
    state.ocrOtherName = null;
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

  // ------------------------------------------------------------ 长截图识别：校对表

  var OCR_KINDS = [['text', '文字'], ['sticker', '表情'], ['image', '图片'], ['voice', '语音']];
  var OCR_KIND_LABEL = { text: '文字', sticker: '表情', image: '图片', voice: '语音' };
  var OCR_KIND_DEFAULT = { text: '', sticker: '[表情]', image: '[图片]', voice: '[语音]' };
  var OCR_EMOTIONS = ['', '开心', '伤心', '生气', '惊讶', '无语', '害羞', '爱心', '疑问'];

  function labeledSelect(options, value, onPick, title) {
    var select = el('select', 'ocr-select');
    if (title) select.title = title;
    options.forEach(function (pair) {
      var option = el('option', '', pair[1]);
      option.value = pair[0];
      select.append(option);
    });
    select.value = value;
    select.addEventListener('change', function () { onPick(select.value); });
    return select;
  }

  var previewTimer = null;
  function schedulePreview() {
    clearTimeout(previewTimer);
    previewTimer = setTimeout(function () { softPreview(); }, 400);
  }

  function updateOcrCount() {
    $('message-count').textContent = '已识别 ' + state.messages.length + ' 条，请逐条核对';
  }

  function updateTimeBadge(foot, message) {
    var old = foot.querySelector('.ocr-guess');
    if (old) old.remove();
    if (message.time_guessed && message.time) foot.append(el('span', 'ocr-guess', '推测'));
  }

  function isVisualKind(kind) {
    return kind === 'sticker' || kind === 'image';
  }

  function kindLabel(kind) {
    return OCR_KIND_LABEL[kind] || '文字';
  }

  function timeLabel(message) {
    if (!message.time) return '时间未知';
    return message.time + (message.time_guessed ? '（推测）' : '');
  }

  function speakerOptions() {
    return [['我', '我'], ['对方', state.ocrOtherName || '对方']];
  }

  function displayName(speaker) {
    return speaker === '对方' ? (state.ocrOtherName || '对方') : '我';
  }

  function emotionOptions(message) {
    var emotions = OCR_EMOTIONS.slice();
    if (message.emoji_emotion && emotions.indexOf(message.emoji_emotion) < 0) emotions.push(message.emoji_emotion);
    return emotions.map(function (emotion) { return [emotion, emotion || '情绪?']; });
  }

  function applyKindChange(message, value) {
    var previous = OCR_KIND_DEFAULT[message.kind] || '';
    message.kind = value;
    var next = OCR_KIND_DEFAULT[value] || '';
    if (!message.content || message.content === previous) message.content = next;
  }

  function openImageView(source) {
    if (!source) return;
    $('image-dialog-img').src = source;
    var dialog = $('image-dialog');
    if (dialog.showModal) dialog.showModal();
  }

  function renderOcrReview(warning) {
    $('ocr-note').textContent = warning ||
      '识别结果仅供参考：文字默认折叠，点「展开」可改字、切换发言者、修正时间；图片与表情常展开，可直接选情绪并点缩略图查看原图。标「推测」的时间来自最近的一个可见时间分隔。';
    var table = $('ocr-table');
    table.replaceChildren();
    state.messages.forEach(function (message, index) {
      var visual = isVisualKind(message.kind);
      var expanded = visual || !!message.open;
      var row = el('div', 'ocr-row' + (expanded ? '' : ' closed'));
      row.dataset.kind = message.kind || 'text';

      var head = el('div', 'ocr-row-head');
      head.append(el('span', 'ocr-index', String(index + 1)));
      if (visual) {
        head.append(labeledSelect(speakerOptions(), message.speaker, function (value) {
          message.speaker = value;
          schedulePreview();
        }, '这条是谁说的'));
        head.append(labeledSelect(OCR_KINDS, message.kind, function (value) {
          applyKindChange(message, value);
          renderOcrReview(warning);
          schedulePreview();
        }, '消息类型'));
        head.append(labeledSelect(emotionOptions(message), message.emoji_emotion || '', function (value) {
          message.emoji_emotion = value;
          schedulePreview();
        }, '表情情绪（可自动或手选）'));
      } else {
        var summary = el('button', 'ocr-summary');
        summary.type = 'button';
        summary.title = expanded ? '点击收起修改' : '点击展开修改';
        summary.setAttribute('aria-expanded', expanded ? 'true' : 'false');
        summary.append(el('span', 'ocr-speaker', displayName(message.speaker)));
        summary.append(el('span', 'ocr-meta', kindLabel(message.kind) + ' · ' + timeLabel(message)));
        summary.append(el('span', 'ocr-preview', message.content));
        summary.addEventListener('click', function () {
          message.open = !message.open;
          renderOcrReview(warning);
        });
        head.append(summary);
      }
      var remove = el('button', 'line-btn quiet ocr-del', '删除');
      remove.type = 'button';
      remove.addEventListener('click', function () {
        state.messages.splice(index, 1);
        renderOcrReview(warning);
        updateOcrCount();
        schedulePreview();
      });
      head.append(remove);
      row.append(head);

      if (expanded) {
        var body = el('div', 'ocr-row-body');
        if (visual && message.image) {
          var thumb = document.createElement('img');
          thumb.className = 'ocr-thumb';
          thumb.src = message.image;
          thumb.alt = kindLabel(message.kind);
          thumb.title = '点击查看大图';
          thumb.addEventListener('click', function () { openImageView(message.image); });
          body.append(thumb);
        }
        if (!visual) {
          var controls = el('div', 'ocr-row-controls');
          controls.append(labeledSelect(speakerOptions(), message.speaker, function (value) {
            message.speaker = value;
            schedulePreview();
          }, '这条是谁说的'));
          controls.append(labeledSelect(OCR_KINDS, message.kind || 'text', function (value) {
            applyKindChange(message, value);
            renderOcrReview(warning);
            schedulePreview();
          }, '消息类型'));
          body.append(controls);
        }
        var content = document.createElement('input');
        content.type = 'text';
        content.className = 'ocr-content';
        content.value = message.content;
        content.placeholder = '消息内容';
        content.addEventListener('input', function () {
          message.content = content.value;
          schedulePreview();
        });
        body.append(content);

        var foot = el('div', 'ocr-row-foot');
        var time = document.createElement('input');
        time.type = 'text';
        time.className = 'ocr-time';
        time.value = message.time || '';
        time.placeholder = '时间（可空）';
        time.addEventListener('input', function () {
          message.time = time.value;
          message.time_guessed = false;
          updateTimeBadge(foot, message);
        });
        foot.append(time);
        updateTimeBadge(foot, message);
        if (!visual) {
          var collapse = el('button', 'line-btn quiet ocr-collapse', '收起');
          collapse.type = 'button';
          collapse.addEventListener('click', function () {
            message.open = false;
            renderOcrReview(warning);
          });
          foot.append(collapse);
        }
        body.append(foot);
        row.append(body);
      }
      table.append(row);
    });
    $('ocr-review').hidden = false;
  }

  function renderOcrAvatars() {
    var box = $('ocr-avatars');
    var avatars = state.ocrAvatars;
    if (!avatars) {
      box.hidden = true;
      box.replaceChildren();
      return;
    }
    box.replaceChildren();
    box.append(el('p', 'note', '从截图里读到的两侧头像（仅作参考）：'));
    var row = el('div', 'ocr-avatar-row');
    [['other', '对方'], ['self', '我']].forEach(function (pair) {
      var cell = el('div', 'ocr-avatar');
      var image = document.createElement('img');
      image.src = avatars[pair[0]].image;
      image.alt = pair[1] + '的头像';
      cell.append(image);
      cell.append(el('span', '', pair[0] === 'other' ? displayName('对方') : '我'));
      row.append(cell);
    });
    box.append(row);
    box.append(el('p', 'note', avatars.note));
    avatars.confirmed = !!avatars.couple_suspected;
    var label = el('label', 'check');
    var checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.checked = avatars.confirmed;
    checkbox.addEventListener('change', function () { avatars.confirmed = checkbox.checked; });
    label.append(checkbox);
    label.append(el('span', '', '我确认这两张是情侣头像（仅为展示，不参与评分）'));
    box.append(label);
    box.hidden = false;
  }

  async function setOcrMessages(messages, warning, avatars, otherName) {
    state.messages = messages.map(function (message) {
      return {
        speaker: message.speaker === '我' ? '我' : '对方',
        content: message.content,
        time: message.time || '',
        time_guessed: !!message.time_guessed,
        kind: message.kind || 'text',
        emoji_emotion: message.emoji_emotion || '',
        image: message.image || null,
        open: false
      };
    });
    state.ocrUsed = true;
    state.ocrAvatars = avatars || null;
    state.ocrOtherName = otherName || null;
    ['self-speaker', 'other-speaker'].forEach(function (id) {
      var select = $(id);
      select.replaceChildren();
      speakerOptions().forEach(function (pair) {
        var option = el('option', '', pair[1]);
        option.value = pair[0];
        select.append(option);
      });
    });
    $('self-speaker').value = '我';
    $('other-speaker').value = '对方';
    $('speaker-panel').hidden = false;
    renderOcrReview(warning);
    renderOcrAvatars();
    updateOcrCount();
    await preview();
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

  // 快照/比对：让结果页能说清「这次档案动了哪几条」
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
    if (data.contact_id && !data.save_consent) throw new Error('要写进档案，请先勾选第一项确认。');
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
    renderResult(result, { before: before, contactId: data.contact_id, ocr: state.ocrUsed });
    go('result');
    $('save-consent').checked = false;
    if (data.contact_id) {
      state.profile = result.profile || state.profile;
      await refreshContacts();
      if (state.profile) renderProfile();
    }
    if (result.duplicate && !result.report_regenerated) {
      say('这段聊天已经分析过一次：档案没有重复记账，也没有重复调用云端。');
    } else if (result.warning) {
      say(result.warning, true);
    } else if (data.contact_id) {
      say('水纹已出，人物档案也更新了。');
    } else {
      say('水纹已出（没有写入档案）。');
    }
  }

  async function runDemo(demoId, title) {
    var contactId = $('contact-select').value || null;
    if (contactId && !$('save-consent').checked) {
      throw new Error('示例内容是虚构的。要写进档案请先勾选确认，或把档案设为「不建档」。');
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
      say('示例是虚构内容，已按你的选择记入《' + (before ? before.name : '档案') + '》。');
    } else {
      say('示例分析完成（未写入档案）。');
    }
  }

  // ------------------------------------------------------------ 结果渲染

  function renderOcrSummary() {
    var block = $('ocr-summary');
    var body = $('ocr-summary-body');
    if (!state.ocrUsed || !state.messages.length) {
      block.hidden = true;
      return;
    }
    body.replaceChildren();
    body.append(el('p', 'note', '以下是从长截图里识别到的补充信息，仅供核对；它们不参与任何评分。'));
    if (state.ocrAvatars) {
      var avatars = state.ocrAvatars;
      var guess = avatars.couple_suspected ? '疑似情侣头像' : '不像情侣头像';
      var confirmed = avatars.confirmed ? '你已确认是情侣头像' : '你未确认为情侣头像';
      body.append(el('p', 'note', '头像相似度 ' + avatars.similarity + '，识别为' + guess + '；' + confirmed + '。'));
    }
    state.messages.forEach(function (message, index) {
      var wrap = el('div', 'ocr-summary-item');
      var row = el('div', 'row two');
      row.append(el('span', 'k', (index + 1) + '. ' + displayName(message.speaker)));
      var time = message.time ? ('时间 ' + message.time + (message.time_guessed ? '（推测）' : '')) : '时间未知';
      var detail = (OCR_KIND_LABEL[message.kind] || '文字') + ' · ' + time;
      if (message.emoji_emotion) detail += ' · 情绪 ' + message.emoji_emotion;
      row.append(el('span', 'v', detail + ' · ' + message.content));
      wrap.append(row);
      if (message.image) {
        var thumb = document.createElement('img');
        thumb.className = 'ocr-thumb small';
        thumb.src = message.image;
        thumb.alt = kindLabel(message.kind);
        thumb.title = '点击查看大图';
        thumb.addEventListener('click', function () { openImageView(message.image); });
        wrap.append(thumb);
      }
      body.append(wrap);
    });
    block.hidden = false;
  }

  function renderResult(result, meta) {
    // 重复片段只返回档案，不再返回水纹：此时保留上一次的水纹与分享图
    if (result.analysis) state.lastResult = result;
    meta = meta || {};
    if (meta.ocr) renderOcrSummary();
    else $('ocr-summary').hidden = true;
    // 兼容：统一接口把水纹放在 analysis 里，这里也容忍直接返回分析对象
    var data = result.analysis || (result.verdict ? result : null);

    if (data) {
      var v = data.verdict;
      var isJoker = v.is_joker && v.type;
      $('source-note').textContent = '分析结果 · 水纹 · ' + plain(data.source || meta.demoTitle || '本次聊天片段');

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
        $('guidance-content').textContent = data.guidance_error + '。本地统计已保留，修好配置后重新分析一次即可。';
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

  // ------------------------------------------------------------ 五维指标悬停提示

  function ensureMetricTooltip() {
    if (metricTooltip) return metricTooltip;

    metricTooltip = el('div', 'metric-tooltip');
    metricTooltip.id = 'metric-tooltip';
    metricTooltip.setAttribute('role', 'tooltip');

    var kicker = el('div', 'metric-tooltip-kicker', '五维释义');
    var title = el('div', 'metric-tooltip-title');
    var body = el('div', 'metric-tooltip-body');
    var method = el('div', 'metric-tooltip-method');

    metricTooltip.append(kicker, title, body, method);
    document.body.append(metricTooltip);

    return metricTooltip;
  }

  function metricTipContent(key, metric) {
    var tip = METRIC_TIPS[key] || {};
    return {
      title: tip.title || (metric && metric.label) || key,
      body: tip.body || (metric && metric.desc) || '',
      method: tip.method || ''
    };
  }

  function moveMetricTooltip(clientX, clientY) {
    if (!metricTooltip) return;

    var gap = 16;
    var pad = 14;
    var width = metricTooltip.offsetWidth;
    var height = metricTooltip.offsetHeight;
    var left = clientX + gap;
    var top = clientY + gap;

    if (left + width > window.innerWidth - pad) {
      left = clientX - width - gap;
    }
    if (top + height > window.innerHeight - pad) {
      top = clientY - height - gap;
    }

    left = Math.max(pad, left);
    top = Math.max(pad, top);
    metricTooltip.style.left = left + 'px';
    metricTooltip.style.top = top + 'px';
  }

  function showMetricTooltip(key, metric, clientX, clientY) {
    var tip = ensureMetricTooltip();
    var content = metricTipContent(key, metric);

    tip.querySelector('.metric-tooltip-title').textContent = content.title;
    tip.querySelector('.metric-tooltip-body').textContent = content.body;
    tip.querySelector('.metric-tooltip-method').textContent = content.method;
    tip.classList.add('is-visible');
    moveMetricTooltip(clientX, clientY);
  }

  function hideMetricTooltip() {
    if (!metricTooltip) return;
    metricTooltip.classList.remove('is-visible');
  }

  function bindMetricTooltip(node, key, metric) {
    if (!node) return;

    node.classList.add('metric-help-target');
    node.setAttribute('tabindex', '0');
    node.setAttribute('aria-describedby', 'metric-tooltip');

    node.addEventListener('mouseenter', function (event) {
      showMetricTooltip(key, metric, event.clientX, event.clientY);
    });
    node.addEventListener('mousemove', function (event) {
      moveMetricTooltip(event.clientX, event.clientY);
    });
    node.addEventListener('mouseleave', function () {
      hideMetricTooltip();
    });
    node.addEventListener('focus', function () {
      var rect = node.getBoundingClientRect();
      showMetricTooltip(key, metric, rect.left + rect.width / 2, rect.top + rect.height / 2);
    });
    node.addEventListener('blur', function () {
      hideMetricTooltip();
    });
  }

  function renderProfileOutcome(result, meta) {
    var block = $('profile-result');
    var body = $('profile-result-body');
    body.replaceChildren();
    block.hidden = false;

    if (!meta.contactId) {
      body.append(el('p', 'note', '这次选择了「不建档」：只出分析结果，档案里没有留下任何东西。想积累观察，可以在「谈心分析」里选一个档案条目。'));
      return;
    }

    var profile = result.profile;
    if (!profile) {
      body.append(el('p', 'note', '档案没有变化。'));
      return;
    }

    if (result.duplicate && !result.report_regenerated) {
      body.append(el('p', 'note', '这段聊天之前已经分析过（同一段脱敏片段），档案没有重复记账。'));
      body.append(el('p', 'note', '《' + profile.name + '》现有 ' + profile.facts.length + ' 条档案、' + profile.batches.length + ' 次分析记录。'));
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
      '；这份档案现在共 ' + profile.facts.length + ' 条。');
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
      body.append(el('p', 'note', '这段聊天里没有认出明确的喜好。档案留白也是一种记录。'));
    }

    var actions = el('div', 'line-actions');
    var more = el('button', 'line-btn quiet', '去人物档案细看与修正');
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
var metricKey = keys[k2];
var metric = metrics[metricKey];

label.setAttribute('x', lp[0].toFixed(1));
label.setAttribute('y', (lp[1] + 4).toFixed(1));
label.setAttribute(
  'text-anchor',
  Math.abs(lp[0] - cx) < 6 ? 'middle' : (lp[0] > cx ? 'start' : 'end')
);
label.setAttribute('font-size', '11.5');
label.setAttribute(
  'fill',
  k2 === maxIndex ? '#a63c30' : 'rgba(77,73,69,0.95)'
);
label.setAttribute('font-family', 'var(--serif)');
label.textContent = metric.label;

// 鼠标悬停显示指标释义
bindMetricTooltip(label, metricKey, metric);

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

      var name = el('span', 'name', metric.label);
      bindMetricTooltip(name, key, metric);
      li.append(name);

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
    var explain = el('button', 'line-btn quiet', '这几项是怎么算的');
    explain.type = 'button';
    explain.addEventListener('click', function () { go('guide'); });
    list.append(explain);
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
    if (!data) { say('先分析一段聊天，才有可导出的水纹。', true); return; }
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
    c.fillText('交心 · 思源湖研究所 · 水纹', 70, 96);
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
    link.download = '交心-思源湖研究所-水纹.png';
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
        ? (data.ai_verified ? '云端 AI 已就绪并已验证 · ' + data.ai_model : '云端 AI 已就绪，尚未验证 · ' + data.ai_model)
        : '仅本地模式 · 云端 AI 未配置';
      $('ai-status').textContent = data.ai_available
        ? '云端已就绪：' + data.ai_model + '（只有勾选后才会发送脱敏片段）'
        : '云端 AI 未配置，本地统计与喜好提取可直接使用。';
      var stateEl = $('ai-config-state');
      if (stateEl) {
        stateEl.textContent = data.ai_available
          ? (data.ai_verified ? '已配置并验证通过 · ' + data.ai_model : '已配置，尚未验证 · ' + data.ai_model)
          : '未配置：请在项目根目录 .env 填写 DEEPSEEK_API_KEY 后点「重新加载配置」。';
      }
      if ($('fisher-status') && !state.fisher.streaming) {
        $('fisher-status').textContent = data.ai_available
          ? '钓翁已就绪 · ' + data.ai_model
          : '云端 AI 未配置 · 钓翁暂时听不见';
      }
      return data;
    } catch (e) {
      $('footer-status').textContent = '后端未连接，请检查服务是否在运行';
      $('ai-status').textContent = '读不到后端状态。';
      return null;
    }
  }

  function initConfig() {
    $('ai-test-btn').addEventListener('click', function () {
      guard(async function () {
        $('ai-config-msg').textContent = '正在发送一段固定的虚构示例…';
        var data = await api('/api/config/test', { method: 'POST' });
        $('ai-config-msg').textContent = data.success ? '验证成功：' + data.message : '验证失败：' + data.error.message;
        await health();
      });
    });

    $('ai-reload-btn').addEventListener('click', function () {
      guard(async function () {
        var data = await api('/api/config/reload', { method: 'POST' });
        $('ai-config-msg').textContent = data.success
          ? '已重新加载：' + data.model + '，可点「测试连接」确认。'
          : '仍未读到 Key，请检查项目根目录 .env 的 DEEPSEEK_API_KEY。';
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
      if (!audio.src) { say('还没有选曲目：先做一次分析，或把 mp3 放进 assets/music/ 目录。', true); return; }
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
      $('ocr-review').hidden = true;
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
        say('Excel 已解析。文件不会被保存进档案，请核对「我 / 对方」。');
      });
    });

    $('chat-image').addEventListener('change', function () {
      var input = this;
      guard(async function () {
        var files = Array.prototype.slice.call(input.files || []);
        if (!files.length) return;
        clearChat();
        if (files.length > 20) throw new Error('一次最多 20 张截图，请分几次导入');
        files.forEach(function (file) {
          if (file.size > 20 * 1024 * 1024) throw new Error(file.name + ' 超过 20 MB');
        });
        var form = new FormData();
        files.forEach(function (file) { form.append('files', file); });
        loading(true, files.length > 1
          ? ['正在读 ' + files.length + ' 张截图…', '把气泡摆回原位…', '接好每一段的缝…']
          : ['正在读这一长条截图…', '把气泡摆回原位…', '认出说话的人…']);
        var parsed;
        try {
          parsed = await api('/api/profiles/parse-image', { method: 'POST', body: form });
        } finally {
          loading(false);
        }
        await setOcrMessages(parsed.messages, parsed.warning, parsed.avatars, parsed.other_name);
        say('已在本机识别 ' + (parsed.image_count || files.length) + ' 张截图，图片不会被保存。请逐条核对校对表，再点「开始分析」。');
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
        say('已新建档案《' + created.name + '》。可以开始分析了。');
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
      $('delete-title').textContent = '删除《' + state.profile.name + '》？';
      $('delete-description').textContent = '本机数据库里的联系人、全部依据与分析记录都会消失。已导出的文件、或第三方服务收到的内容不受影响。';
      $('delete-dialog').showModal();
    });

    $('cancel-delete').addEventListener('click', function () { $('delete-dialog').close(); });
    $('close-image-dialog').addEventListener('click', function () { $('image-dialog').close(); });
    $('image-dialog').addEventListener('click', function (event) {
      if (event.target === this) this.close();
    });
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
        say('已删除。');
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

  // ------------------------------------------------------------ 解说页（讲解）
  // 数字全部来自 /api/guide（与判定逻辑同一份来源），文案在本文件里；
  // 目录由各板块标题自动生成，所以加了板块就会自动出现在目录里。

  function buildToc(viewName, tocId) {
    var view = document.querySelector('.view[data-view="' + viewName + '"]');
    var toc = $(tocId);
    if (!view || !toc) return;
    toc.replaceChildren();
    var nodes = view.querySelectorAll('.block-title, .group-title');
    Array.prototype.forEach.call(nodes, function (node, i) {
      if (!node.id) node.id = viewName + '-sec-' + i;
      // 标题里第一个 span 是朱砂序号，不进目录
      var clone = node.cloneNode(true);
      var mark = clone.querySelector('span');
      if (mark) mark.remove();
      var text = clone.textContent.replace(/\s+/g, ' ').trim();
      var link = el('a', '', text);
      link.href = '#' + node.id;
      toc.append(link);
    });
  }

  function row(k, v, w, two) {
    var node = el('div', 'row' + (two ? ' two' : ''));
    node.append(el('span', 'k', k));
    if (!two) node.append(el('span', 'w', w || ''));
    node.append(el('span', 'v', v));
    return node;
  }

  function rowRich(k, w, parts) {
    var node = el('div', 'row');
    node.append(el('span', 'k', k));
    node.append(el('span', 'w', w || ''));
    var v = el('span', 'v');
    parts.forEach(function (part) {
      if (part.em) v.append(el('em', '', part.text));
      else v.append(document.createTextNode(part.text));
    });
    node.append(v);
    return node;
  }

  var LIMIT_TEXT = {
    upload_mb: ['上传文件', '单个 Excel 不超过 5 MB'],
    image_mb: ['长截图', '单张微信长截图不超过 20 MB，识别全程在本机完成'],
    images: ['截图张数', '一次最多 20 张，按选择顺序拼接并去掉接缝重复'],
    max_rows: ['单次行数', '最多读取 1000 行'],
    max_chars: ['单次字数', '最多 12 万字'],
    cloud_chars: ['云端上限', '勾选云端 AI 时最多 4 万字，超出请拆分'],
    batches_per_contact: ['分析次数', '每位人物档案最多累积 200 次'],
    facts_per_contact: ['档案条目', '每位联系人最多 500 条']
  };
  var LIMIT_TAIL = {
    evidence_per_fact: ['每条依据', '同一条信息最多保留 10 条不同依据'],
    chat_turns: ['钓翁对话条数', '单次对话最多携带 40 条历史'],
    chat_chars: ['钓翁对话字数', '单次对话总字数不超过 2.4 万']
  };

  async function renderGuide() {
    buildToc('guide', 'guide-toc');
    if (state.guide === 'loading' || state.guide) return;
    state.guide = 'loading';
    var data;
    try {
      data = await api('/api/guide');
    } catch (error) {
      $('guide-score').textContent = '读不到讲解数据：' + error.message;
      state.guide = null;
      return;
    }
    state.guide = data;

    // 分数怎么来
    var scoreBox = $('guide-score');
    scoreBox.replaceChildren();
    scoreBox.append(el('p', 'note', data.score_scale.note));
    var formula = el('div', 'score-formula');
    var c1 = el('code', '', data.score_scale.formula);
    formula.append(c1);
    scoreBox.append(formula);
    var rows = el('div', 'rows');
    rows.append(rowRich('加权求和', '五维', [{ text: data.score_scale.z_total }]));
    rows.append(rowRich('语音折扣', '×' + data.score_scale.voice_penalty,
      [{ text: '这段聊天里出现语音或通话记录时，分数乘以该系数（旧版规则沿用至今）' }]));
    scoreBox.append(rows);

    // 五维
    var metrics = $('guide-metrics');
    metrics.replaceChildren();
    data.metrics.forEach(function (metric) {
      metrics.append(rowRich(metric.label, '权重 ' + metric.weight, [
        { text: metric.desc + '。' }, { text: '算法：' + metric.how, em: true }
      ]));
    });

    // 判定区间
    var levels = $('guide-levels');
    levels.replaceChildren();
    var sorted = data.levels.slice().sort(function (a, b) { return b.min - a.min; });
    sorted.forEach(function (level, i) {
      var upper = i === 0 ? null : sorted[i - 1].min;
      var range = upper === null ? level.min + ' 分以上' : (level.min + ' – ' + upper + ' 分');
      if (level.min === 0) range = '低于 ' + sorted[sorted.length - 2].min + ' 分';
      levels.append(rowRich(range, '', [
        { text: (LEVEL_NAME[level.key] || level.key) + ' —— ' },
        { text: LEVEL_TEXT[level.key] || '', em: true }
      ]));
    });

    // 类型
    $('guide-type-rule').textContent = data.type_rule;
    var types = $('guide-types');
    types.replaceChildren();
    Object.keys(data.types).forEach(function (name) {
      var info = data.types[name];
      var entry = el('div', 'type-entry');
      entry.append(el('h4', '', name));
      entry.append(el('p', '', info.desc));
      entry.append(el('p', '', '建议 · ' + info.suggestion));
      entry.append(el('p', 'keys', '关键信号：' + (info.keywords || []).join(' · ')));
      types.append(entry);
    });

    // 上限
    var limits = $('guide-limits');
    limits.replaceChildren();
    Object.keys(LIMIT_TEXT).concat(Object.keys(LIMIT_TAIL)).forEach(function (key) {
      var pair = LIMIT_TEXT[key] || LIMIT_TAIL[key];
      var value = data.limits[key];
      if (value === undefined) return;
      limits.append(row(pair[0], pair[1], value));
    });
  }

  // ------------------------------------------------------------ 理论页

  function renderTheory() {
    var data = window.THEORY;
    buildToc('theory', 'theory-toc');
    if (!data || state.theoryDone) return;
    state.theoryDone = true;

    var body = $('theory-body');
    body.replaceChildren();
    if (data.intro) body.append(el('p', 'note', data.intro));

    var idx = 0;
    data.groups.forEach(function (group) {
      var title = el('h3', 'group-title');
      title.append(el('span', '', group.mark || ''));
      title.append(el('span', '', group.title));
      body.append(title);
      if (group.note) body.append(el('p', 'group-note', group.note));

      group.items.forEach(function (item) {
        idx += 1;
        var entry = el('article', 'entry');

        var head = el('div', 'entry-head');
        head.append(el('span', 'idx', String(idx).padStart(2, '0')));
        head.append(el('h4', '', item.name));
        if (item.en) head.append(el('span', 'en', item.en));
        if (item.who) head.append(el('span', 'by', item.who + (item.year ? ' · ' + item.year : '')));
        entry.append(head);

        entry.append(el('p', 'core', item.core));

        var facts = el('dl', 'facts');
        [['关键发现', item.evidence], ['注意', item.caveat], ['在本项目里', item.inapp]].forEach(function (pair) {
          if (!pair[1]) return;
          facts.append(el('dt', '', pair[0]));
          facts.append(el('dd', '', pair[1]));
        });
        entry.append(facts);

        var foot = el('div', 'entry-foot');
        if (item.sources && item.sources.length) {
          var src = el('span', 'src', '出处：');
          item.sources.forEach(function (source) {
            var link = el('a', '', source.label);
            link.href = source.url;
            link.target = '_blank';
            link.rel = 'noopener noreferrer';
            src.append(link);
          });
          foot.append(src);
        }
        if (item.ask) {
          var ask = el('button', 'line-btn quiet', '去和钓翁聊聊');
          ask.type = 'button';
          ask.addEventListener('click', function () {
            go('fisherman');
            var input = $('fisher-input');
            input.value = item.ask;
            input.focus();
            say('已把这个问题放进「找钓翁聊聊」的输入框，你可以改完再发。');
          });
          foot.append(ask);
        }
        entry.append(foot);
        body.append(entry);
      });
    });

    var caveats = $('theory-caveats');
    caveats.replaceChildren();
    (data.caveats || []).forEach(function (text) { caveats.append(el('li', '', text)); });

    // 参考资料从各条目的出处汇总去重，避免两处维护对不上
    var refs = $('theory-refs');
    refs.replaceChildren();
    var collected = [];
    data.groups.forEach(function (group) {
      group.items.forEach(function (item) {
        (item.sources || []).forEach(function (source) {
          if (source.url) collected.push({ label: source.label, url: source.url, who: item.who || '', year: item.year || '' });
        });
      });
    });
    var used = {};
    collected.forEach(function (source) {
      if (used[source.url]) return;
      used[source.url] = true;
      var link = el('a', '', source.label);
      link.href = source.url;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.append(el('span', '', source.who + (source.year ? ' · ' + source.year : '')));
      refs.append(link);
    });
    if (!collected.length) refs.append(el('p', 'note', '出处正在补齐。'));
  }

  // ------------------------------------------------------------ 找钓翁聊聊（情感对话）
  // 对话只存在内存里；服务端不保存。选定档案里的某个人并勾选后，
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
      empty.append(el('p', '', '湖水很静。'));
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
      say('云端 AI 未配置：请在项目根目录 .env 填写 DEEPSEEK_API_KEY，到「设置」点「测试连接」后再试。', true);
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
    renderTheory();
    // 云端与长文默认都关掉，由用户自己打开
    $('include-guidance').checked = false;
    $('use-ai').checked = false;
    syncOptions();
    setHere(document.body.dataset.view);
    guard(refreshContacts);
    health();
    loadDemos();
    window.addEventListener('focus', function () { health(); });
  });
})();
