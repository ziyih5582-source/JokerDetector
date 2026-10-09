/* Communication memory: useful methods first; management remains optional. */
(function () {
  'use strict';
  var p = null, hooks = null, ready = false, busy = false, editing = null, manualRoles = false, demo = null, ocrRows = null, ocrText = '';
  var names = { communication_request: '沟通要求', boundary: '边界', support_need: '本次支持需要', situated_trait: '情境特点', shared_understanding: '澄清过的误解', stage_context: '阶段背景', event: '重要事情', useful_preference: '有用偏好', user_note: '用户补充' };
  var actions = { add: '新增', evidence: '补充依据', refine: '细化理解', branch: '补充场景', change: '更新状态', historical: '补充历史', conflict: '暂待确认', end: '明确结束' };
  Object.assign(names, { relationship_position: '本人关系态度', interaction_signal: '实际互动', personal_view: '个人观点', emotional_state: '当时的心情', useful_preference: '兴趣与喜好' });
  function $(id) { return document.getElementById(id); }
  function el(tag, text, cls) { var n = document.createElement(tag); if (text !== undefined) n.textContent = text; if (cls) n.className = cls; return n; }
  function status(text, error) { ['dossier-status', 'archive-upload-status', 'archive-tools-status'].forEach(function (id) { var n = $(id); if (n) { n.textContent = text; n.classList.toggle('error', !!error); } }); }
  function openTools(mode) {
    ['records', 'notes', 'person'].forEach(function (name) { $('archive-' + name + '-pane').hidden = name !== mode; });
    $('archive-tools-title').textContent = { records: '全部记录与历史', notes: editing ? '修正这条认识' : '补充一条认识', person: '称呼与备注' }[mode];
    if (!$('archive-tools-dialog').open) $('archive-tools-dialog').showModal();
    document.querySelectorAll('.campus-manage').forEach(function (n) { n.open = false; });
  }
  function path(id) { return '/api/profiles/contacts/' + encodeURIComponent(id || p.id); }
  async function api(url, method, data) {
    var form = data instanceof FormData;
    var r = await fetch(url, { method: method || 'GET', headers: form ? undefined : { 'Content-Type': 'application/json' }, body: data === undefined ? undefined : form ? data : JSON.stringify(data) });
    var body = await r.json(); if (!r.ok) throw new Error(typeof body.detail === 'string' ? body.detail : '请检查输入、发言者和日期格式'); return body;
  }
  async function run(task) {
    if (busy) return; busy = true; var id = p && p.id;
    var nodes = Array.from(document.querySelectorAll('.view[data-view="book"] button, .view[data-view="book"] input, .view[data-view="book"] textarea, .view[data-view="book"] select'));
    var old = nodes.map(function (e) { return e.disabled; }); nodes.forEach(function (e) { e.disabled = true; });
    try { await task(); } catch (e) { if (p && p.id === id) status(e.message, true); }
    finally { nodes.forEach(function (e, i) { e.disabled = old[i]; }); busy = false; }
  }
  function evidence(rows, versions) {
    var d = el('details'); d.append(el('summary', '查看 ' + rows.length + ' 条原文依据' + (versions && versions.length ? '与旧记录' : '')));
    rows.forEach(function (r) { var q = el('blockquote', r.quote); q.append(el('p', (r.role === 'self' ? '自己' : '对方') + ' · 聊天 ' + (r.chat_date || '日期未确认') + ' · 第 ' + r.message_number + ' 条' + (r.historical ? ' · 历史' : ''), 'note')); d.append(q); });
    (versions || []).forEach(function (v) { d.append(el('p', '旧记录：' + v.text + (v.event_date ? ' · ' + v.event_date : ''), 'note')); }); return d;
  }
  function edit(f) { editing = f.id; $('memory-note').value = f.text; $('memory-note-ai').checked = false; $('memory-note-target').textContent = '修正“' + f.topic + '”。旧方法会停用，保存为受保护的用户补充。'; $('memory-note-panel').open = true; openTools('notes'); $('memory-note').focus(); }
  function memoryTile(row) {
    var a = el('article', undefined, 'campus-memory'); a.dataset.factId = row.id;
    var who = row.subject === 'self' ? '我' : row.subject === 'relation' ? '我们' : 'TA';
    if (row.source === '我的补充 / 修正') a.append(el('p', '我的补充 / 修正', 'campus-meta'));
    else if (row.subject === 'self') a.append(el('p', '我的表达', 'campus-meta'));
    a.append(el('h4', row.topic), el('p', row.text));
    if (row.source === '旧版摘录，待复核') a.append(el('p', '旧版线索，尚未按新标准复核', 'campus-meta'));
    if (row.historical) a.append(el('p', (row.observed_on || '过去') + '的表达，当前是否仍适用尚不确定。', 'campus-caution'));
    if (row.interpretation) a.append(el('p', '可能的理解：' + row.interpretation, 'campus-caution'));
    var detail = el('details', undefined, 'campus-detail'); detail.append(el('summary', '依据与适用范围'));
    detail.append(el('p', who + ' · ' + row.source + (row.observed_on ? ' · ' + row.observed_on : ' · 聊天日期未知'), 'campus-meta'));
    if (row.scope) detail.append(el('p', '适用情境：' + row.scope, 'note'));
    if (row.temporary) detail.append(el('p', row.historical ? '过去或时间未明的记录，不能代表今天。' : '仅代表当时状态。', 'campus-caution'));
    if (row.event_date || row.date_text) detail.append(el('p', '节点：' + (row.event_date || row.date_text), 'campus-node'));
    if (row.dated_observations > 1) detail.append(el('p', '见于 ' + row.dated_observations + ' 个聊天日期；不等于独立验证', 'note'));
    if (row.alternative) detail.append(el('p', '其他可能解释：' + row.alternative, 'note'));
    if (row.limitation) detail.append(el('p', '理解的限度：' + row.limitation, 'note'));
    (row.branches || []).forEach(function (b) { detail.append(el('p', '另一种情境 · ' + b.scope + '：' + b.fact, 'note')); });
    (row.evidence || []).forEach(function (q) { detail.append(el('blockquote', q.quote)); });
    (row.versions || []).forEach(function (v) { detail.append(el('p', '旧记录：' + v.text, 'note')); });
    var button = el('button', '修正这条认识', 'campus-edit'); button.type = 'button'; button.addEventListener('click', function () { var f = p.facts.find(function (f) { return f.id === row.id; }); if (f) edit(f); }); detail.append(button); a.append(detail);
    return a;
  }
  function campus(profile) {
    var board = profile.campus_board; if (!board) return;
    var overview = $('campus-overview'); overview.replaceChildren();
    if (!board.portrait && (board.stances.length || board.interactions.length)) {
      var hero = el('section', undefined, 'campus-relationship'); hero.append(el('h3', '关于你们的关系'));
      hero.append(el('p', '记住明确表达，也给尚未说清楚的感受留出空间。', 'note'));
      var stances = el('div', undefined, 'campus-grid'); board.stances.forEach(function (r) { stances.append(memoryTile(r)); }); hero.append(stances);
      board.unknowns.forEach(function (text) { hero.append(el('p', text, 'campus-unknown')); });
      if (board.interactions.length) { var d = el('details', undefined, 'campus-interactions'); d.append(el('summary', '你们实际发生的互动 · ' + board.interactions.length)); var list = el('div', undefined, 'campus-grid'); board.interactions.slice(0, 4).forEach(function (r) { list.append(memoryTile(r)); }); d.append(list, el('p', '一次邀约、热情回应或分享，只说明这次互动；不能直接确定好感程度。', 'note')); hero.append(d); }
      overview.append(hero);
    }
    overview.hidden = !overview.childElementCount && !board.pending;
    if (board.pending) overview.append(el('p', '有 ' + board.pending + ' 条内容仍有冲突或依据不足，暂不用于相处建议；可在全部记录中核对。', 'campus-caution'));
    var sections = $('campus-sections'); sections.replaceChildren();
    (board.portrait || board.sections.filter(function (g) { return g.title !== '最近提到的事'; })).forEach(function (group) { var s = el('section', undefined, 'campus-section'); s.append(el('h3', group.title)); var grid = el('div', undefined, 'campus-grid'); group.items.slice(0, 2).forEach(function (r) { grid.append(memoryTile(r)); }); s.append(grid); sections.append(s); });
    if (!sections.childElementCount) sections.append(el('p', '上传聊天后，值得记住的兴趣、特点和边界会出现在这里。', 'campus-empty'));
    var reviews = $('campus-reviews'); reviews.replaceChildren(); reviews.hidden = !(board.reviews || []).length;
    (board.reviews || []).forEach(function (r) { var a = el('article', undefined, 'campus-review'); a.append(el('h4', '确认一下：' + r.topic), el('p', '之前：' + r.before), el('p', '这次：' + r.after)); ['accept', 'keep'].forEach(function (decision) { var b = el('button', decision === 'accept' ? '采用这次的认识' : '保留之前的认识', 'line-btn quiet'); b.type = 'button'; b.addEventListener('click', function () { var id = p.id, revision = p.revision, callback = hooks.onUpdate; run(async function () { await callback(await api(path(id) + '/memory/' + r.id + '/resolve', 'POST', { revision: revision, decision: decision })); }); }); a.append(b); }); reviews.append(a); });
    var line = $('campus-timeline'); line.replaceChildren(); var changes = board.timeline;
    changes.forEach(function (t) { var a = el('article', undefined, 'campus-change'); a.append(el('p', (t.date || '聊天日期未知') + ' · ' + t.topic + (t.manual ? ' · 我的修正' : ''), 'campus-meta'), el('p', '之前：' + t.before), el('p', '后来：' + t.after)); line.append(a); });
    if (!changes.length) line.append(el('p', '暂时没有前后变化。新的聊天可以补充原话、增加适用情境，或修正之前的认识。', 'note'));
  }
  function cards(profile) {
    var box = $('memory-cards'); box.replaceChildren(); var list = profile.campus_board ? profile.campus_board.methods : profile.method_cards || [];
    $('campus-method-heading').hidden = !list.length; box.hidden = !list.length;
    if (!list.length) box.append(el('p', '还没有适合生成方法的信息。上传聊天后，明确要求与澄清过的误解会逐渐形成方法；没有依据时就留空。', 'note'));
    list.slice(0, 2).forEach(function (c) {
      var f = profile.facts.find(function (f) { return f.id === c.fact_id; }); var a = el('article', undefined, 'memory-method'); a.dataset.factId = c.fact_id;
      a.append(el('h4', f ? f.topic : c.title), el('p', c.method, 'memory-action'));
      var detail = el('details', undefined, 'campus-detail'); detail.append(el('summary', '为什么这样建议'), el('p', c.finding, 'note'));
      if (c.example) detail.append(el('p', '表达示例：' + c.example + '（按当前事情调整）', 'note'));
      if (c.alternative) detail.append(el('p', '其他可能解释：' + c.alternative, 'note'));
      if (c.limitation) detail.append(el('p', c.limitation, 'note'));
      detail.append(evidence(c.evidence || [], f && f.versions)); var button = el('button', '这条需要修正', 'line-btn quiet'); button.type = 'button'; button.addEventListener('click', function () { if (f) edit(f); }); detail.append(button); a.append(detail); box.append(a);
    });
    var ctx = $('memory-context'); ctx.replaceChildren(); var events = profile.campus_board ? [] : profile.facts.filter(function (f) { return f.memory_version === 3 && f.memory_type === 'event'; });
    if (events.length) ctx.append(el('h3', '重要事情与已知状态'));
    events.slice(-5).forEach(function (f) { ctx.append(el('p', f.text + (f.event_date ? ' · ' + f.event_date : f.date_text ? ' · 日期原话：' + f.date_text : '') + (f.conflict ? ' · 待确认' : f.validity === 'ended' ? ' · 已明确结束，结果以原话为准' : ' · 没有依据的结果不推测'), 'note')); });
  }
  function records(profile) {
    var box = $('dossier-groups'); box.replaceChildren();
    profile.facts.forEach(function (f) {
      var a = el('article', undefined, 'fact' + (f.conflict ? ' conflict' : ''));
      a.append(el('div', (names[f.memory_type] || (f.origin === 'manual' ? '用户补充' : '旧版资料')) + ' · ' + (f.manual_locked ? '用户补充 / 修正' : f.source_level === 'interaction' ? '双方互动' : '原话记录') + (f.conflict || f.retention === 'pending' ? ' · 待确认' : '') + (f.retention === 'temporary' ? ' · 限本次或阶段' : ''), 'dossier-tags'));
      a.append(el('h4', f.topic + '：' + f.text)); if (f.context) a.append(el('p', '范围：' + f.context, 'note')); if (f.interpretation) a.append(el('p', '可能的理解：' + f.interpretation, 'note'));
      a.append(evidence(f.evidence || [], f.versions)); (f.branches || []).forEach(function (b) { a.append(el('p', '另一个条件：' + b.scope + ' · ' + b.fact, 'note')); });
      (f.alternatives || []).forEach(function (v) { a.append(el('p', '另一种说法：' + v.text + ' · ' + (v.observed_on || '时间未确认'), 'note')); });
      var bar = el('div', undefined, 'line-actions'), button = el('button', '修正', 'line-btn quiet'); button.type = 'button'; button.addEventListener('click', function () { edit(f); });
      var del = el('button', '删除', 'line-btn danger'); del.type = 'button'; del.addEventListener('click', function () { if (!confirm('删除这条与关联方法？旧原话不会自动恢复它。')) return; var id = profile.id, callback = hooks.onUpdate; run(async function () { await callback(await api(path(id) + '/facts/' + f.id, 'PATCH', { revision: profile.revision, action: 'delete' })); if (p.id === id) status('记录与关联方法已删除。'); }); });
      bar.append(button, del); a.append(bar); box.append(a);
    });
    if (!profile.facts.length) box.append(el('p', '目前没有可保存的信息。', 'note'));
  }
  function textRows() {
    var rows = []; $('dossier-chat').value.split(/\r?\n/).forEach(function (line) { if (!line.trim()) return; var m = line.match(/^([^：:]{1,100})[：:]\s*(.+)$/); if (m) rows.push({ speaker: m[1].trim(), content: m[2].trim() }); else if (rows.length) rows[rows.length - 1].content += '\n' + line; else throw new Error('每行请写“发言者：内容”'); });
    if (rows.length < 2) throw new Error('至少需要两条双方聊天，或先导入文件'); return rows;
  }
  function speakers(rows) {
    var list = Array.from(new Set(rows.map(function (m) { return m.speaker; }))), mine = list.find(function (n) { return ['我', '自己', '本人'].includes(n); });
    if (!manualRoles && list.length === 2 && mine) { $('dossier-self').value = mine; $('dossier-other').value = list.find(function (n) { return n !== mine; }); }
    $('memory-speakers').textContent = '本段发言者：' + $('dossier-self').value + ' / ' + $('dossier-other').value + ' · 日期不明可留空';
  }
  function input() { var rows = textRows(); speakers(rows); var original = ocrRows && $('dossier-chat').value === ocrText; if (original) rows = ocrRows; return { revision: p.revision, messages: rows, self_speaker: $('dossier-self').value.trim(), other_speaker: $('dossier-other').value.trim(), chat_date: $('dossier-chat-date').value || null, scene: $('dossier-scene').value.trim(), source_kind: original ? 'ocr' : 'chat', time_reliability: original || $('dossier-chat-date').value ? 'confirmed' : 'unknown', use_ai: $('dossier-ai').checked, cloud_consent: $('memory-consent').checked, save_consent: $('memory-consent').checked }; }
  function consent() { $('memory-consent-text').textContent = $('dossier-ai').checked ? '我已核对双方、聊天文字与日期线索，同意发送脱敏聊天和必要背景到当前 AI 服务，并保存有用信息与短依据' : '我已核对双方、聊天文字与日期线索，同意保存本次有用信息与脱敏依据（本地规则能力有限）'; }
  function clearNote() { editing = null; $('memory-note-form').reset(); $('memory-note-target').textContent = '这是你的补充，会与对方原话区分。'; }
  function init() {
    if (ready) return; ready = true;
    ['archive-upload-dialog', 'archive-tools-dialog'].forEach(function (id) { var dialog = $(id); var s = el('p', undefined, 'note archive-dialog-status'); s.id = id === 'archive-upload-dialog' ? 'archive-upload-status' : 'archive-tools-status'; s.setAttribute('role', 'status'); dialog.querySelector('.archive-dialog-head').after(s); });
    document.querySelectorAll('[data-close-archive]').forEach(function (b) { b.addEventListener('click', function () { $(b.dataset.closeArchive).close(); }); });
    $('archive-view-records').addEventListener('click', function () { openTools('records'); });
    $('archive-add-note').addEventListener('click', function () { clearNote(); $('memory-note-panel').open = true; openTools('notes'); });
    $('archive-edit-person').addEventListener('click', function () { openTools('person'); });
    function showDemo(r) { demo = r; $('campus-demo-text').textContent = (r.next_date ? r.next_date + '\n' : '') + r.next_text; $('campus-demo-status').textContent = '已加入 ' + r.step + ' / ' + r.count + ' 段' + (r.rejected && r.rejected.length ? ' · 拦截了 ' + r.rejected.length + ' 条缺乏依据的候选' : ''); $('campus-demo-next').disabled = r.step >= r.count; }
    if (new URLSearchParams(window.location.search).has('preview')) {
      api('/api/campus-preview/cases').then(function (r) { $('campus-demo-panel').hidden = false; r.cases.forEach(function (c) { var option = el('option', c.name + ' · ' + c.count + ' 段'); option.value = c.id; $('campus-demo-case').append(option); }); }).catch(function () { /* normal application does not enable developer replay */ });
      $('campus-demo-start').addEventListener('click', async function () { if (busy) return; this.disabled = true; try { var r = await api('/api/campus-preview/start', 'POST', { case_id: $('campus-demo-case').value }); await hooks.onCreated(r.profile); showDemo(r); } catch (err) { $('campus-demo-status').textContent = err.message; } finally { this.disabled = false; } });
      $('campus-demo-next').addEventListener('click', async function () { if (!demo || busy) return; this.disabled = true; try { var r = await api('/api/campus-preview/next', 'POST', { contact_id: demo.profile.id, revision: demo.profile.revision }); await hooks.onCreated(r.profile); showDemo(r); } catch (err) { $('campus-demo-status').textContent = err.message; this.disabled = false; } });
    }
    $('campus-add-chat').addEventListener('click', function () { $('dossier-import-panel').open = true; $('archive-upload-dialog').showModal(); $('dossier-chat').focus({ preventScroll: true }); });
    $('dossier-create-form').addEventListener('submit', async function (e) { e.preventDefault(); var b = this.querySelector('button'); if (b.disabled) return; b.disabled = true; try { var c = await api('/api/profiles/contacts', 'POST', { name: $('dossier-create-name').value.trim() }); await hooks.onCreated(c); $('dossier-create-name').value = ''; } catch (err) { $('dossier-create-status').textContent = err.message; } finally { b.disabled = false; } });
    $('dossier-ai').addEventListener('change', function () { $('memory-consent').checked = false; consent(); });
    ['dossier-self', 'dossier-other'].forEach(function (id) { $(id).addEventListener('input', function () { manualRoles = true; }); });
    $('dossier-chat').addEventListener('change', function () { try { speakers(textRows()); } catch (e) { /* validate at submission */ } });
    $('memory-run').addEventListener('click', function () { run(async function () { var id = p.id, callback = hooks.onUpdate, data = input(); if (!data.save_consent) throw new Error('先核对双方并勾选本次使用确认'); status(data.use_ai ? 'AI正在理解双方互动，检查哪些信息值得留下……' : '正在摘录明确表达……'); var r = await api(path(id) + '/memory/import', 'POST', data); await callback(r.profile); if (!p || p.id !== id) return; var box = $('memory-update'); box.replaceChildren(); if (r.duplicate) box.append(el('p', '这段已处理，没有重复调用或计数。', 'note')); else if (!r.changes.length) box.append(el('p', '本次没有值得新增的信息，原有内容保持。', 'note')); else r.changes.slice(0, 6).forEach(function (c) { box.append(el('p', (actions[c.action] || '更新') + '：' + c.text + ' · ' + c.reason, 'note')); }); status(r.notice + (r.rejected_count ? ' · 有 ' + r.rejected_count + ' 项未通过校验。' : '')); }); });
    $('dossier-redact').addEventListener('click', function () { run(async function () { var id = p.id, data = input(); delete data.save_consent; delete data.source_kind; delete data.time_reliability; data.messages = data.messages.map(function (m) { return { speaker: m.speaker, content: m.content }; }); var r = await api(path(id) + '/imports/redact', 'POST', data); if (p.id !== id) return; $('dossier-redacted').textContent = r.messages.map(function (m) { return (m.role === 'self' ? '自己' : '对方') + '：' + m.content; }).join('\n'); $('dossier-redacted').hidden = false; status('请核对敏感细节，基础遮盖不能识别所有隐私。'); }); });
    $('memory-note-reset').addEventListener('click', clearNote);
    $('memory-note-form').addEventListener('submit', function (e) { e.preventDefault(); var id = p.id, callback = hooks.onUpdate, data = { revision: p.revision, fact_id: editing, text: $('memory-note').value.trim(), use_in_ai: $('memory-note-ai').checked }; run(async function () { await callback(await api(path(id) + '/memory/notes', 'POST', data)); if (p.id !== id) return; clearNote(); $('archive-tools-dialog').close(); status('补充已保存，相关旧方法已停用；后续导入不会自动改写你的认识。'); }); });
    $('dossier-contact-form').addEventListener('submit', function (e) { e.preventDefault(); var id = p.id, callback = hooks.onUpdate, data = { revision: p.revision, name: $('dossier-name').value.trim(), relationship_tags: $('dossier-tags').value.split(/[,，、]/).map(function (x) { return x.trim(); }).filter(Boolean), background: $('dossier-background').value }; run(async function () { await callback(await api(path(id), 'PATCH', data)); if (p.id === id) status('可选资料已保存。'); }); });
    [['dossier-excel', '/api/profiles/parse'], ['dossier-images', '/api/profiles/parse-image']].forEach(function (pair) { $(pair[0]).addEventListener('change', function () { var files = Array.from(this.files); if (!files.length) return; run(async function () { var id = p.id, form = new FormData(); files.forEach(function (f) { form.append(pair[0] === 'dossier-excel' ? 'file' : 'files', f); }); status('正在读取聊天，请稍后校对……'); var r = await api(pair[1], 'POST', form); if (p.id !== id) return; manualRoles = false; ocrRows = pair[0] === 'dossier-images' ? r.messages.map(function (m) { return { speaker: m.speaker, content: m.content, time: m.time || null, time_guessed: !!m.time_guessed, kind: m.kind || 'text' }; }) : null; $('dossier-chat').value = r.messages.map(function (m) { return m.speaker + '：' + m.content; }).join('\n'); ocrText = $('dossier-chat').value; var dates = Array.from(new Set(r.messages.map(function (m) { var t = (m.time || '').match(/^\d{1,2}\/\d{1,2}\/(?:20\d{2}|\d{2})/); return t ? t[0] : ''; }).filter(Boolean))); $('archive-ocr-dates').hidden = !dates.length; $('archive-ocr-dates').textContent = '截图中的日期线索：' + dates.join('、') + '。请对照原图核对；统一日期留空时会使用这些线索。'; speakers(r.messages); $('memory-input-details').open = true; status((r.warning || '已读入。') + ' 请核对双方、文字与日期。'); $(pair[0]).value = ''; }); }); });
    api('/api/health').then(function (r) { $('dossier-ai').checked = !!r.ai_available; consent(); }).catch(consent);
  }
  window.ProfileEditor = { render: function (profile, callbacks) { init(); hooks = callbacks; var changed = !p || !profile || p.id !== profile.id; p = profile; if (!p) return; if (changed) { manualRoles = false; ocrRows = null; ocrText = ''; $('archive-ocr-dates').hidden = true; $('dossier-chat').value = ''; $('dossier-self').value = '我'; $('dossier-other').value = p.name; $('dossier-chat-date').value = ''; $('dossier-scene').value = ''; $('memory-consent').checked = false; $('memory-update').replaceChildren(); $('dossier-redacted').hidden = true; clearNote(); status(''); } $('dossier-name').value = p.name; $('dossier-tags').value = (p.relationship_tags || []).join('，'); $('dossier-background').value = p.background || ''; campus(p); cards(p); records(p); consent(); } };
}());
