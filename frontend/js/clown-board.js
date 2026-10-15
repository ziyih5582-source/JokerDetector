/**
 * 小丑看板（ClownBoard）：页面右上角常驻的小丑头像 + 「小丑值」。
 *
 * 数据有两条来路，走的是同一个本地六征引擎（都不调用云端 AI）：
 * 1. 小丑鉴定所开鉴之后，ink.js 调 ClownBoard.publish(result, context) 推过来；
 * 2. 看板面板里直接粘一段「发言者：内容」，POST /api/joker/board 现算。
 *
 * 约定：纯静态、无第三方依赖、无内联脚本；分数只写在本机 localStorage，
 * 不上传、不入库，换台电脑就看不见了。
 */
(function () {
  'use strict';

  var VERSION = 'joker-board-1.0';
  var STORE_KEY = 'joker.board.v1';
  var COLLAPSE_KEY = 'joker.board.collapsed';
  var API_PATH = '/api/joker/board';

  var SIGN_ORDER = ['one_way', 'self_moved', 'fantasy', 'boundary', 'no_accept_reject', 'self_mockery'];
  var SIGN_FALLBACK_LABEL = {
    one_way: '单向推进',
    self_moved: '自我感动',
    fantasy: '幻想脑补',
    boundary: '边界失守',
    no_accept_reject: '不接受拒绝',
    self_mockery: '事后自嘲'
  };
  // 与后端 app/services/joker_board.py 的 SIGN_WEIGHT 保持一致；
  // 后端返回 dimensions 时以返回值为准，这里只是「只有鉴定所结果」时的兜底。
  var SIGN_FALLBACK_WEIGHT = {
    one_way: 0.24, self_moved: 0.16, fantasy: 0.14,
    boundary: 0.14, no_accept_reject: 0.18, self_mockery: 0.14
  };

  var LEVELS = {
    confirmed: { label: '确诊小丑', color: '#a63c30', note: '投入严重失衡：这段对话几乎是你一个人在撑。先停一停，看看对方有没有伸手。' },
    high_risk: { label: '高度疑似', color: '#b4573f', note: '你比对方主动太多。热情没有错，但要小心只是感动了自己。' },
    suspicious: { label: '轻度倾向', color: '#c08a2c', note: '偶尔失衡，总体还在控制里。留意一下谁在起话题、谁在收尾。' },
    mild: { label: '基本对等', color: '#6f8f9c', note: '关系基本对等。这种节奏比任何话术都稳，继续保持。' },
    healthy: { label: '清醒玩家', color: '#5b8a6a', note: '主动、表达与回应大致对等：清醒地相处，也别忘了把话说明白。' }
  };

  var EMPTY_TEXT = '还没有量过。粘一段聊天、导入 Excel 或长截图，都能得到这张小丑值。';

  // ------------------------------------------------------------ 纯函数（可在 Node 里直接测）

  function levelMeta(level) {
    return LEVELS[level] || LEVELS.healthy;
  }

  function formatScore(value) {
    var number = Number(value);
    if (value === null || value === undefined || value === '' || isNaN(number)) return '—';
    return number.toFixed(1);
  }

  function clamp(value, min, max) {
    var number = Number(value);
    if (isNaN(number)) number = 0;
    return Math.max(min, Math.min(max, number));
  }

  /** 「发言人：内容」→ 规范化消息；格式不对就抛错，错在哪一行要能说清。 */
  function parseChatText(text) {
    var lines = String(text || '').split(/\r?\n/).filter(function (line) { return line.trim(); });
    if (!lines.length) throw new Error('先粘一段聊天记录，一行一条，写成「发言人：内容」');
    var messages = lines.map(function (line, index) {
      var match = line.match(/^([^:：]{1,60})[:：]\s*(.+)$/);
      if (!match) throw new Error('第 ' + (index + 1) + ' 行不是「发言人：内容」的格式');
      return { speaker: match[1].trim(), content: match[2].trim() };
    });
    var speakers = [];
    messages.forEach(function (message) {
      if (speakers.indexOf(message.speaker) < 0) speakers.push(message.speaker);
    });
    if (speakers.length !== 2) {
      throw new Error('需要明确的两位发言者：群聊请先整理成两个人');
    }
    var self = speakers.indexOf('我') >= 0 ? '我' : speakers[0];
    var other = speakers.filter(function (name) { return name !== self; })[0];
    return { messages: messages, speakers: speakers, self: self, other: other };
  }

  function dimensionFromSign(key, sign) {
    var score = clamp(sign && sign.score, 0, 1);
    return {
      key: key,
      label: (sign && sign.label) || SIGN_FALLBACK_LABEL[key] || key,
      hit: !!(sign && sign.hit),
      score: score,
      points: Number((score * 100).toFixed(1)),
      weight: SIGN_FALLBACK_WEIGHT[key] || 0,
      detail: (sign && sign.detail) || '',
      evidence: (sign && sign.evidence) || []
    };
  }

  /** 一句话把「命中了几项、哪几项最突出」说清楚（后端给了 summary 就以后端为准）。 */
  function summarize(dimensions) {
    var hit = (dimensions || []).filter(function (item) { return item.hit; })
      .sort(function (a, b) { return b.points - a.points; });
    if (!hit.length) return '六征一项都没命中：主动与回应大致对等，这段关系现在还是清醒的。';
    return '六征里命中 ' + hit.length + ' 项：' + hit.slice(0, 3).map(function (item) {
      return item.label + ' ' + item.points;
    }).join('、') + ' 最突出。';
  }

  /**
   * 把两种输入统一成看板结构：
   * - 鉴定所返回值（有 signs）：现场换算六维；
   * - /api/joker/board 返回值（有 dimensions）：直接用，并补上缺失字段。
   */
  function normalize(payload) {
    if (!payload || typeof payload !== 'object') return null;
    var dimensions = [];
    if (Array.isArray(payload.dimensions) && payload.dimensions.length) {
      dimensions = payload.dimensions.map(function (item) {
        var weight = typeof item.weight === 'number' ? item.weight : (SIGN_FALLBACK_WEIGHT[item.key] || 0);
        return {
          key: item.key,
          label: item.label || SIGN_FALLBACK_LABEL[item.key] || item.key,
          hit: !!item.hit,
          score: clamp(item.score, 0, 1),
          points: typeof item.points === 'number' ? clamp(item.points, 0, 100) : clamp(item.score, 0, 1) * 100,
          weight: weight,
          detail: item.detail || '',
          evidence: Array.isArray(item.evidence) ? item.evidence.slice(0, 3) : []
        };
      });
    } else if (payload.signs && typeof payload.signs === 'object') {
      dimensions = SIGN_ORDER.filter(function (key) { return payload.signs[key]; })
        .map(function (key) { return dimensionFromSign(key, payload.signs[key]); });
    }
    var hitCount = dimensions.filter(function (item) { return item.hit; }).length;
    return {
      score: typeof payload.score === 'number' ? payload.score : null,
      weighted_score: typeof payload.weighted_score === 'number' ? payload.weighted_score : null,
      level: payload.level || 'healthy',
      level_label: payload.level_label || levelMeta(payload.level).label,
      is_joker: !!payload.is_joker,
      type: payload.type || null,
      hit_count: typeof payload.hit_count === 'number' ? payload.hit_count : hitCount,
      dimensions: dimensions,
      summary: payload.summary || summarize(dimensions),
      next_steps: Array.isArray(payload.next_steps) ? payload.next_steps.slice(0, 3) : [],
      message_counts: payload.message_counts || null,
      engine: payload.engine || '本地六征 v1 · 不调用云端 AI',
      updated_at: payload.updated_at || payload.generated_at || new Date().toISOString(),
      source: payload.source || ''
    };
  }

  function boardSummary(board) {
    if (!board) return EMPTY_TEXT;
    if (board.summary) return board.summary;
    return summarize(board.dimensions);
  }

  // ------------------------------------------------------------ 本地存储

  function storage() {
    try {
      return window.localStorage || null;
    } catch (error) {
      return null;
    }
  }

  function loadBoard() {
    var store = storage();
    if (!store) return null;
    try {
      var raw = store.getItem(STORE_KEY);
      return raw ? normalize(JSON.parse(raw)) : null;
    } catch (error) {
      return null;
    }
  }

  function saveBoard(board) {
    var store = storage();
    if (!store || !board) return;
    try {
      store.setItem(STORE_KEY, JSON.stringify(board));
    } catch (error) {
      /* 隐私模式下写不进去也不影响这一屏的显示 */
    }
  }

  function loadCollapsed() {
    var store = storage();
    if (!store) return false;
    return store.getItem(COLLAPSE_KEY) === '1';
  }

  function saveCollapsed(value) {
    var store = storage();
    if (!store) return;
    try {
      store.setItem(COLLAPSE_KEY, value ? '1' : '0');
    } catch (error) {
      /* 同上 */
    }
  }

  // ------------------------------------------------------------ 小丑头像（纯 SVG，不依赖图片）

  var faceSeed = 0;

  function faceMarkup() {
    faceSeed += 1;
    var id = 'cb-face-' + faceSeed;
    var nose = 'cb-nose-' + faceSeed;
    return '<svg viewBox="0 0 120 120" role="img" aria-label="小丑头像" focusable="false">'
      + '<defs>'
      + '<radialGradient id="' + id + '" cx="38%" cy="30%" r="78%">'
      + '<stop offset="0%" stop-color="#fffdf6"/><stop offset="62%" stop-color="#fdf3d9"/>'
      + '<stop offset="100%" stop-color="#f2e2bd"/>'
      + '</radialGradient>'
      + '<radialGradient id="' + nose + '" cx="36%" cy="32%" r="72%">'
      + '<stop offset="0%" stop-color="#f2564a"/><stop offset="100%" stop-color="#a81f16"/>'
      + '</radialGradient>'
      + '</defs>'
      // 两侧蓬松红发
      + '<g class="cb-hair">'
      + '<circle cx="26" cy="30" r="13" fill="#c62b20"/><circle cx="15" cy="45" r="11.5" fill="#c62b20"/>'
      + '<circle cx="34" cy="17" r="10.5" fill="#d63a2c"/><circle cx="21" cy="60" r="9" fill="#b32218"/>'
      + '<circle cx="22" cy="36" r="5" fill="#e2503f" opacity=".55"/>'
      + '<circle cx="94" cy="30" r="13" fill="#c62b20"/><circle cx="105" cy="45" r="11.5" fill="#c62b20"/>'
      + '<circle cx="86" cy="17" r="10.5" fill="#d63a2c"/><circle cx="99" cy="60" r="9" fill="#b32218"/>'
      + '<circle cx="98" cy="36" r="5" fill="#e2503f" opacity=".55"/>'
      + '</g>'
      // 脸
      + '<ellipse cx="60" cy="62" rx="40" ry="38" fill="url(#' + id + ')" stroke="rgba(35,33,32,.16)" stroke-width="1.4"/>'
      // 腮红
      + '<ellipse cx="31" cy="73" rx="10.5" ry="7" fill="#ee8a6c" opacity=".5"/>'
      + '<ellipse cx="89" cy="73" rx="10.5" ry="7" fill="#ee8a6c" opacity=".5"/>'
      // 眉毛
      + '<path d="M29 41 q11 -9 22 -3" fill="none" stroke="#232120" stroke-width="3.2" stroke-linecap="round"/>'
      + '<path d="M91 41 q-11 -9 -22 -3" fill="none" stroke="#232120" stroke-width="3.2" stroke-linecap="round"/>'
      // 眼：蓝圈 + 黑瞳（会眨）
      + '<g class="cb-eye">'
      + '<ellipse cx="43" cy="61" rx="13.4" ry="16.8" fill="#fffdf8" stroke="#2f6fb5" stroke-width="4.2"/>'
      + '<ellipse cx="43" cy="61" rx="6.4" ry="9.6" fill="#232120"/>'
      + '<circle cx="40.6" cy="56.4" r="2.1" fill="#fffdf8" opacity=".92"/>'
      + '</g>'
      + '<g class="cb-eye">'
      + '<ellipse cx="77" cy="61" rx="13.4" ry="16.8" fill="#fffdf8" stroke="#2f6fb5" stroke-width="4.2"/>'
      + '<ellipse cx="77" cy="61" rx="6.4" ry="9.6" fill="#232120"/>'
      + '<circle cx="74.6" cy="56.4" r="2.1" fill="#fffdf8" opacity=".92"/>'
      + '</g>'
      // 红鼻子
      + '<circle class="cb-nose" cx="60" cy="74.5" r="8.6" fill="url(#' + nose + ')"/>'
      + '<circle cx="57" cy="71.4" r="2.5" fill="#ff9d86" opacity=".85"/>'
      // 大嘴：红唇 + 白牙
      + '<path d="M23 76 C31 112 89 112 97 76 C88 92 32 92 23 76 Z" fill="#c8281f"/>'
      + '<path d="M28 78 C36 103 84 103 92 78 C84 91 36 91 28 78 Z" fill="#fffdf8"/>'
      + '<path d="M28 78 C36 91 84 91 92 78" fill="none" stroke="#8d2119" stroke-width="1.6"/>'
      + '</svg>';
  }

  // ------------------------------------------------------------ DOM

  var state = {
    board: null,
    open: false,
    collapsed: false,
    mounted: false,
    busy: false,
    nodes: {},
    scoreShown: null,
    renderedScore: undefined
  };

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function text(value) {
    return value === undefined || value === null ? '' : String(value);
  }

  function mount() {
    if (state.mounted || !document.body) return;
    var root = el('div', 'cb-root');
    root.id = 'clown-board';
    root.setAttribute('data-level', 'healthy');

    var head = el('button', 'cb-head');
    head.type = 'button';
    head.setAttribute('aria-expanded', 'false');
    head.setAttribute('aria-controls', 'clown-board-panel');

    var chip = el('span', 'cb-chip');
    chip.append(el('span', 'cb-chip-label', '小丑值'));
    var score = el('b', 'cb-chip-score', '—');
    score.id = 'cb-score';
    score.setAttribute('aria-live', 'polite');
    chip.append(score);
    var level = el('span', 'cb-chip-level', '还没量过');
    level.id = 'cb-level';
    chip.append(level);

    var figure = el('span', 'cb-figure');
    figure.innerHTML = faceMarkup();
    var tip = el('span', 'cb-tip', '点我 · 看六维依据');

    head.append(chip, figure, tip);

    var collapse = el('button', 'cb-collapse', '›');
    collapse.type = 'button';
    collapse.title = '收起 / 展开小丑看板';
    collapse.setAttribute('aria-label', '收起小丑看板');

    var built = buildPanel();
    var panel = built.panel;

    root.append(head, collapse, panel);
    document.body.append(root);

    state.nodes = {
      root: root, head: head, chip: chip, score: score, level: level,
      figure: figure, tip: tip, collapse: collapse, panel: panel
    };
    // 面板内部的节点由 buildPanel 一起交回来，避免这里整体赋值时被覆盖掉
    Object.keys(built.parts).forEach(function (key) {
      state.nodes[key] = built.parts[key];
    });

    head.addEventListener('click', function () { toggle(); });
    collapse.addEventListener('click', function (event) {
      event.stopPropagation();
      setCollapsed(!state.collapsed);
    });
    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && state.open) close();
    });
    window.addEventListener('resize', place);
    window.addEventListener('storage', function (event) {
      if (event.key === STORE_KEY) refresh();
    });

    state.mounted = true;
    state.board = loadBoard();
    state.collapsed = loadCollapsed();
    applyCollapsed();
    place();
    render();
  }

  function buildPanel() {
    var panel = el('aside', 'cb-panel');
    panel.id = 'clown-board-panel';
    panel.hidden = true;
    panel.setAttribute('aria-label', '小丑看板详情');

    var head = el('header', 'cb-panel-head');
    var scoreBox = el('div', 'cb-panel-score');
    var big = el('b', 'cb-panel-score-value', '—');
    scoreBox.append(big, el('span', 'cb-panel-score-unit', '小丑值 / 100'));
    var meta = el('div', 'cb-panel-meta');
    var seal = el('span', 'cb-seal', '未鉴定');
    var tag = el('span', 'cb-level-tag', '');
    var stamp = el('span', 'cb-time', '');
    meta.append(seal, tag, stamp);
    var close = el('button', 'cb-close', '×');
    close.type = 'button';
    close.setAttribute('aria-label', '关闭小丑看板');
    close.addEventListener('click', function () { closePanel(); });
    head.append(scoreBox, meta, close);

    var summary = el('p', 'cb-summary', EMPTY_TEXT);
    var dims = el('ol', 'cb-dims');
    var steps = el('div', 'cb-steps');
    var quick = buildQuick();
    var actions = el('footer', 'cb-actions');

    var toRoom = el('button', 'cb-primary', '导入 Excel / 长截图 → 去小丑鉴定所');
    toRoom.type = 'button';
    toRoom.setAttribute('data-go', 'joker');
    toRoom.addEventListener('click', function () {
      closePanel();
      var target = document.getElementById('joker-chat-text');
      if (target) setTimeout(function () { target.focus(); }, 320);
    });

    var toBoard = el('button', 'cb-secondary', '把这次结果送上榜单');
    toBoard.type = 'button';
    toBoard.addEventListener('click', function () { publishToCommunity(); });

    var clear = el('button', 'cb-quiet', '清掉这块看板');
    clear.type = 'button';
    clear.addEventListener('click', function () { clearBoard(); });

    actions.append(toRoom, toBoard, clear);

    var foot = el('p', 'cb-foot',
      '判定在你自己的电脑上完成（本地六征，不调用云端 AI），分数只存在这台设备的浏览器里。'
      + '它不是诊断，也不替你决定任何事。');

    panel.append(head, summary, dims, steps, quick, actions, foot);
    return {
      panel: panel,
      parts: {
        panelScore: big,
        panelSeal: seal,
        panelTag: tag,
        panelTime: stamp,
        dims: dims,
        steps: steps,
        summary: summary,
        quickNote: quick.note,
        quickInput: quick.input,
        quickButton: quick.button
      }
    };
  }

  function buildQuick() {
    var box = el('details', 'cb-quick');
    box.append(el('summary', null, '直接在这里粘一段聊天，立刻量一量'));
    var input = document.createElement('textarea');
    input.rows = 4;
    input.spellcheck = false;
    input.placeholder = '我：在忙吗\n对方：嗯\n我：忙完了吗';
    var actions = el('div', 'cb-quick-actions');
    var button = el('button', 'cb-measure', '开始量一量');
    button.type = 'button';
    var note = el('span', 'cb-quick-note', '格式：发言人：内容，一个人一行；两个人各说至少一句。');
    actions.append(button, note);
    box.append(input, actions);
    button.addEventListener('click', function () { measure(input.value); });
    return { box: box, input: input, button: button, note: note };
  }

  /** 看板贴在右上角：高度跟着页眉走，窄屏不压住导航。 */
  function place() {
    if (!state.nodes.root) return;
    var masthead = document.querySelector('.masthead');
    var bottom = masthead ? masthead.getBoundingClientRect().bottom : 0;
    var width = window.innerWidth;
    // 宽屏时导航两侧本来就留了空档，直接贴右上角；窄屏时顺到页眉下面，避免压住导航
    var top = width >= 1400 ? 16 : Math.max(16, Math.round(bottom + 10));
    state.nodes.root.style.setProperty('--cb-top', top + 'px');
  }

  function applyCollapsed() {
    var root = state.nodes.root;
    if (!root) return;
    root.setAttribute('data-collapsed', state.collapsed ? 'true' : 'false');
    state.nodes.collapse.textContent = state.collapsed ? '‹' : '›';
    state.nodes.collapse.setAttribute('aria-label', state.collapsed ? '展开小丑看板' : '收起小丑看板');
    if (state.collapsed) closePanel();
  }

  function setCollapsed(value) {
    state.collapsed = !!value;
    saveCollapsed(state.collapsed);
    applyCollapsed();
  }

  // ------------------------------------------------------------ 渲染

  function animateScore(next) {
    var node = state.nodes.score;
    if (!node) return;
    var target = Number(next);
    if (isNaN(target)) { node.textContent = '—'; state.scoreShown = null; return; }
    var from = typeof state.scoreShown === 'number' ? state.scoreShown : 0;
    state.scoreShown = target;
    // 系统开了「减少动态效果」就直接跳到结果，不做数字滚动
    var calm = typeof window.matchMedia === 'function'
      && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (calm || typeof window.requestAnimationFrame !== 'function' || from === target) {
      node.textContent = formatScore(target);
      return;
    }
    var started = null;
    var step = function (now) {
      if (started === null) started = now;
      var ratio = Math.min(1, (now - started) / 700);
      var eased = 1 - Math.pow(1 - ratio, 3);
      node.textContent = (from + (target - from) * eased).toFixed(1);
      if (ratio < 1) window.requestAnimationFrame(step);
      else node.textContent = formatScore(target);
    };
    window.requestAnimationFrame(step);
  }

  function pulse() {
    var root = state.nodes.root;
    if (!root) return;
    root.setAttribute('data-pulse', 'true');
    setTimeout(function () { root.removeAttribute('data-pulse'); }, 820);
  }

  function render() {
    if (!state.mounted) return;
    var board = state.board;
    var root = state.nodes.root;
    var meta = levelMeta(board ? board.level : 'healthy');
    var nextScore = board ? board.score : null;
    var isNew = state.renderedScore !== undefined && state.renderedScore !== nextScore && nextScore !== null;
    state.renderedScore = nextScore;
    if (isNew) pulse();

    root.setAttribute('data-level', board ? board.level : 'none');
    root.style.setProperty('--cb-tone', meta.color);

    animateScore(board ? board.score : null);
    state.nodes.level.textContent = board ? meta.label : '还没量过';
    state.nodes.tip.textContent = board ? '点我 · 看六维依据' : '点我 · 量一量自己';

    var seal = state.nodes.panelSeal;
    seal.textContent = board && board.type ? board.type.replace('型', '') : (board ? '清醒' : '未鉴定');
    state.nodes.panelTag.textContent = board ? meta.label : '';
    state.nodes.panelTime.textContent = board && board.updated_at
      ? '更新于 ' + shortTime(board.updated_at)
      : '';
    state.nodes.panelScore.textContent = board ? formatScore(board.score) : '—';
    state.nodes.summary.textContent = boardSummary(board);

    renderDimensions(board);
    renderSteps(board);
  }

  function shortTime(value) {
    var date = new Date(value);
    if (isNaN(date.getTime())) return '';
    var pad = function (number) { return (number < 10 ? '0' : '') + number; };
    return (date.getMonth() + 1) + '月' + date.getDate() + '日 '
      + pad(date.getHours()) + ':' + pad(date.getMinutes());
  }

  function renderDimensions(board) {
    var box = state.nodes.dims;
    box.replaceChildren();
    if (!board || !board.dimensions.length) {
      var empty = el('li', 'cb-dim-empty');
      empty.append(el('p', 'cb-empty-title', '还没有六维数据'));
      empty.append(el('p', 'cb-empty-body', EMPTY_TEXT));
      box.append(empty);
      return;
    }
    board.dimensions.forEach(function (item) {
      var row = el('li', 'cb-dim');
      row.setAttribute('data-hit', item.hit ? 'true' : 'false');

      var head = el('div', 'cb-dim-head');
      head.append(el('span', 'cb-dim-label', item.label));
      var right = el('span', 'cb-dim-right');
      right.append(el('span', 'cb-dim-state', item.hit ? '命中' : '未中'));
      right.append(el('b', 'cb-dim-score', formatScore(item.points)));
      head.append(right);

      var bar = el('div', 'cb-bar');
      var fill = el('i', 'cb-bar-fill');
      fill.style.width = clamp(item.points, 0, 100) + '%';
      bar.append(fill);

      var weightNote = el('p', 'cb-dim-weight',
        '权重 ' + Math.round(item.weight * 100) + '%　·　本项贡献 ' + formatScore(item.contribution || item.points * item.weight));
      row.append(head, bar, weightNote);
      if (item.detail) row.append(el('p', 'cb-dim-detail', item.detail));

      if (item.evidence && item.evidence.length) {
        var list = el('ul', 'cb-evidence');
        item.evidence.forEach(function (quote) { list.append(el('li', null, quote)); });
        row.append(list);
      } else if (item.hit) {
        row.append(el('p', 'cb-dim-detail cb-dim-hint', '命中但没有可引用的原句：可能来自发送节奏或字数的整体统计。'));
      }
      box.append(row);
    });
  }

  function renderSteps(board) {
    var box = state.nodes.steps;
    box.replaceChildren();
    if (!board || !board.next_steps.length) return;
    box.append(el('h4', null, '下一步可以做'));
    var list = el('ul', null);
    board.next_steps.forEach(function (step) { list.append(el('li', null, step)); });
    box.append(list);
  }

  // ------------------------------------------------------------ 交互

  function open() {
    if (!state.mounted) mount();
    state.open = true;
    state.nodes.panel.hidden = false;
    state.nodes.root.setAttribute('data-open', 'true');
    state.nodes.head.setAttribute('aria-expanded', 'true');
  }

  function closePanel() {
    if (!state.mounted) return;
    state.open = false;
    state.nodes.panel.hidden = true;
    state.nodes.root.setAttribute('data-open', 'false');
    state.nodes.head.setAttribute('aria-expanded', 'false');
  }

  function toggle() {
    if (state.open) closePanel();
    else open();
  }

  async function requestBoard(messages, self, other) {
    var response = await fetch(API_PATH, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages: messages, self_speaker: self, other_speaker: other })
    });
    var data = null;
    try { data = await response.json(); } catch (error) { data = null; }
    if (!response.ok) {
      var detail = data && data.detail;
      throw new Error(typeof detail === 'string' ? detail : '这次没量出来，请检查聊天内容');
    }
    return data;
  }

  async function measure(raw) {
    var parsed;
    try {
      parsed = parseChatText(raw);
    } catch (error) {
      setQuickNote(error.message, true);
      return;
    }
    state.busy = true;
    setQuickNote('正在数谁先开口、谁在收尾…');
    try {
      var board = await requestBoard(parsed.messages, parsed.self, parsed.other);
      saveBoard(normalize(Object.assign({}, board, { source: '看板速测' })));
      state.board = loadBoard();
      render();
      setQuickNote('量完了：' + formatScore(state.board.score) + ' 分 · ' + levelMeta(state.board.level).label);
      open();
    } catch (error) {
      setQuickNote(error.message || '这次没量出来', true);
    } finally {
      state.busy = false;
    }
  }

  function setQuickNote(message, isError) {
    var note = state.nodes.quickNote;
    if (!note) return;
    note.textContent = message;
    note.setAttribute('data-error', isError ? 'true' : 'false');
  }

  function publishToCommunity() {
    if (!state.board) return;
    var payload = {
      score: state.board.score,
      type: state.board.type || '清醒型',
      is_joker: state.board.is_joker
    };
    if (typeof window.CommunityOpenSubmit === 'function') {
      window.CommunityOpenSubmit(payload);
      return;
    }
    if (typeof window.switchToCommunity === 'function') window.switchToCommunity();
  }

  function clearBoard() {
    var store = storage();
    if (store) {
      try { store.removeItem(STORE_KEY); } catch (error) { /* 忽略 */ }
    }
    state.board = null;
    state.scoreShown = null;
    render();
    setQuickNote('已清掉这块看板。');
  }

  /** 鉴定所开鉴后把结果推过来：先即时更新，再向 /api/joker/board 补齐依据原句。 */
  async function publish(payload, context) {
    var board = normalize(payload);
    if (!board) return;
    if (context && context.source) board.source = context.source;
    saveBoard(board);
    state.board = board;
    state.scoreShown = null;
    render();

    if (context && context.messages && context.messages.length) {
      try {
        var enriched = await requestBoard(
          context.messages.map(function (message) {
            return { speaker: message.speaker, content: message.content };
          }),
          context.self,
          context.other
        );
        saveBoard(normalize(Object.assign({}, enriched, { source: '小丑鉴定所' })));
        state.board = loadBoard();
        render();
      } catch (error) {
        /* 依据补齐失败不影响总分显示：看板先显示已经拿到的部分 */
      }
    }
  }

  function refresh() {
    state.board = loadBoard();
    render();
  }

  function boot() {
    if (!document.body) return;
    mount();
  }

  window.ClownBoard = {
    version: VERSION,
    mount: mount,
    boot: boot,
    open: open,
    close: closePanel,
    toggle: toggle,
    publish: publish,
    refresh: refresh,
    clear: clearBoard,
    setCollapsed: setCollapsed,
    levelMeta: levelMeta,
    formatScore: formatScore,
    parseChatText: parseChatText,
    normalize: normalize,
    boardSummary: boardSummary,
    summarize: summarize,
    faceMarkup: faceMarkup,
    keys: { store: STORE_KEY, collapse: COLLAPSE_KEY, api: API_PATH },
    state: state
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
