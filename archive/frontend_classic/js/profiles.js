'use strict';
// Dossier contents live only in memory; never localStorage or browser telemetry.
const $ = id => document.getElementById(id);
const state = { contacts: [], profile: null, messages: [], busy: false, editId: null, pendingDelete: null, selection: 0 };
const samples = [
  '我：周末有什么安排？\n小林：我喜欢徒步\n我：想喝点什么？\n小林：我喜欢咖啡\n我：好的，周末见！\n小林：我的电话是13812345678',
  '我：最近口味有没有变化？\n小林：我现在不喜欢咖啡\n我：那我们换个活动吧\n小林：我喜欢看电影\n我：徒步还去吗？\n小林：我喜欢徒步'
];
function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
function notice(message, error = false) {
  $('notice').textContent = message;
  $('notice').className = 'notice' + (error ? ' error' : '');
  $('notice').hidden = !message;
}
async function api(path, options = {}) {
  const response = await fetch('/api/profiles' + path, {
    ...options, headers: options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }
  });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : '输入格式有误，请检查内容和长度');
  return data;
}
async function run(operation) {
  if (state.busy) return;
  state.busy = true;
  const controls = [...document.querySelectorAll('button,input,select,textarea')];
  controls.forEach(control => { control.disabled = true; });
  try { await operation(); } catch (error) { notice(error.message, true); }
  finally {
    state.busy = false;
    document.querySelectorAll('button,input,select,textarea').forEach(control => { control.disabled = false; });
  }
}
function date(value) { return new Date(value).toLocaleString('zh-CN', { hour12: false }); }
async function refreshContacts() {
  state.contacts = (await api('/contacts')).contacts;
  renderContacts();
}
function renderContacts() {
  $('contact-count').textContent = state.contacts.length;
  const list = $('contact-list'); list.replaceChildren();
  const query = $('contact-search').value.toLowerCase();
  state.contacts.filter(c => c.name.toLowerCase().includes(query)).forEach(c => {
    const button = el('button', 'contact-item' + (state.profile?.id === c.id ? ' active' : ''));
    button.setAttribute('aria-pressed', String(state.profile?.id === c.id));
    button.append(el('span', 'avatar', [...c.name][0]));
    const copy = el('span'); copy.append(el('strong', '', c.name), el('small', '', `${c.fact_count} 条信息 · ${c.batch_count} 次更新`));
    button.append(copy); button.onclick = () => run(() => selectContact(c.id));
    list.append(button);
  });
  if (!list.childElementCount) list.append(el('p', 'muted', query ? '没有匹配的联系人' : '还没有联系人，先新建一个吧。'));
}
async function selectContact(id) {
  const selection = ++state.selection;
  const profile = await api('/contacts/' + id);
  if (selection !== state.selection) return;
  state.profile = profile;
  clearChat();
  $('session-analysis').hidden = true;
  notice(''); renderProfile(); renderContacts();
}
function renderProfile() {
  const p = state.profile;
  $('no-contact').hidden = !!p;
  $('contact-workspace').hidden = !p;
  if (!p) return;
  $('profile-name').textContent = p.name;
  $('profile-meta').textContent = `建立于 ${date(p.created_at)} · 不自动识别或合并同名联系人`;
  $('fact-count').textContent = p.facts.length;
  $('review-count').textContent = p.facts.filter(f => f.status === 'unreviewed' || f.conflict).length;
  $('batch-count').textContent = p.batches.length;
  $('revision').textContent = `版本 ${p.revision}`;
  const facts = $('facts'); facts.replaceChildren();
  if (!p.facts.length) facts.append(el('p', 'muted', '还没有可记录的信息。导入聊天后，有明确依据的喜好会出现在这里；没有依据时保留空白。'));
  p.facts.forEach(f => {
    const card = el('article', 'fact' + (f.conflict ? ' conflict' : ''));
    const tags = el('div', 'fact-top');
    tags.append(el('span', 'tag', f.kind === 'preference' ? '日常喜好' : '沟通观察'));
    tags.append(el('span', 'tag', f.certainty === 'stated' ? '原话提取' : 'AI 推测 · 待核实'));
    if (f.status !== 'unreviewed') tags.append(el('span', 'tag verified', f.status === 'corrected' ? '人工修正' : '人工确认'));
    if (f.conflict) tags.append(el('span', 'tag warn', '存在不同说法 · 请核实'));
    card.append(tags, el('h3', '', f.text));
    const evidence = el('details'); evidence.append(el('summary', '', `查看 ${f.evidence.length} 条脱敏依据 · 最近记录 ${date(f.last_seen)}`));
    f.evidence.forEach(e => {
      const quote = el('blockquote'); quote.append(el('div', '', `“${e.quote}”`), el('small', 'muted', `${date(e.at)} · 该片段第 ${e.message_number} 条 · 对方`));
      evidence.append(quote);
    });
    card.append(evidence);
    const actions = el('div', 'actions');
    const confirm = el('button', 'secondary', '确认');
    confirm.onclick = () => run(async () => {
      state.profile = await api(`/contacts/${p.id}/facts/${f.id}`, { method: 'PATCH', body: JSON.stringify({ revision: p.revision, action: 'confirm' }) });
      renderProfile(); notice('已标记人工确认。');
    });
    const edit = el('button', 'secondary', '修正');
    edit.onclick = () => { state.editId = f.id; $('edit-text').value = f.text; $('edit-dialog').showModal(); };
    const remove = el('button', 'text-danger', '删除');
    remove.onclick = () => {
      state.pendingDelete = { factId: f.id, contactId: p.id, revision: p.revision };
      $('delete-title').textContent = '删除这条档案信息？';
      $('delete-description').textContent = '这条信息及其引用将移除。相同主题与倾向的自动提取结果也会被忽略，避免下次导入重新出现。';
      $('delete-dialog').showModal();
    };
    actions.append(confirm, edit, remove); card.append(actions); facts.append(card);
  });
  const history = $('history'); history.replaceChildren();
  if (!p.batches.length) history.append(el('p', 'muted', '尚未追加聊天记录。'));
  [...p.batches].reverse().forEach((b, index) => {
    const row = el('div', 'history-row'); const left = el('div');
    left.append(el('strong', '', `第 ${p.batches.length - index} 次更新 · ${date(b.at)}`));
    if (b.warning) left.append(el('p', '', b.warning));
    row.append(left, el('span', 'muted', `${b.message_count} 条消息 · ${b.mode === 'ai' ? 'AI + 本地' : b.mode === 'local_fallback' ? '本地（AI 失败）' : '本地提取'}`));
    history.append(row);
  });
}
function clearChat() {
  state.messages = [];
  $('chat-text').value = ''; $('chat-file').value = '';
  $('speaker-panel').hidden = true;
  $('redacted-preview').textContent = ''; $('message-count').textContent = '';
  $('save-consent').checked = false; $('use-ai').checked = false;
}
function payload() {
  return { messages: state.messages, self_speaker: $('self-speaker').value, other_speaker: $('other-speaker').value,
    save_consent: $('save-consent').checked, use_ai: $('use-ai').checked, include_guidance: $('include-guidance').checked };
}
async function preview() {
  $('save-consent').checked = false;
  $('redacted-preview').textContent = '';
  const data = await api('/preview', { method: 'POST', body: JSON.stringify(payload()) });
  $('redacted-preview').textContent = data.messages.map(m => `${m.id + 1}. ${m.role === 'self' ? '自己' : '对方'}：${m.content}`).join('\n');
  $('preview-count').textContent = `· ${data.messages.length} 条`;
}
async function setMessages(messages) {
  state.messages = [];
  $('speaker-panel').hidden = true;
  const speakers = [...new Set(messages.map(m => m.speaker))];
  if (speakers.length !== 2) throw new Error('需要明确的两位发言者，请先整理群聊或检查“发言者：内容”格式');
  state.messages = messages;
  for (const id of ['self-speaker', 'other-speaker']) {
    $(id).replaceChildren(...speakers.map(s => { const option = el('option', '', s); option.value = s; return option; }));
  }
  $('self-speaker').value = speakers.includes('我') ? '我' : speakers[0];
  $('other-speaker').value = speakers.find(s => s !== $('self-speaker').value);
  $('message-count').textContent = `已识别 ${messages.length} 条消息，请核对双方`;
  await preview();
  $('speaker-panel').hidden = false;
}
async function parseText() {
  const lines = $('chat-text').value.split(/\r?\n/).filter(line => line.trim());
  const messages = lines.map((line, i) => {
    const match = line.match(/^([^:：]{1,100})[:：]\s*(.+)$/);
    if (!match) throw new Error(`第 ${i + 1} 行格式不正确，请使用“发言者：内容”`);
    return { speaker: match[1].trim(), content: match[2].trim() };
  });
  await setMessages(messages);
}
async function health() {
  try {
    const data = await (await fetch('/api/health')).json();
    $('ai-status').textContent = data.ai_available ? `已配置：${data.ai_model} · ${data.ai_provider}（本次勾选后才会发送）` : '未配置云端 AI。本地喜好提取可直接使用；如需 AI，请先到首页配置服务。';
  } catch { $('ai-status').textContent = '无法连接后端，请检查服务是否启动。'; }
}
$('create-form').onsubmit = event => {
  event.preventDefault(); run(async () => {
    const created = await api('/contacts', { method: 'POST', body: JSON.stringify({ name: $('contact-name').value }) });
    $('contact-name').value = ''; await refreshContacts(); await selectContact(created.id);
    notice('联系人已建立，可以添加第一段聊天。');
  });
};
$('contact-search').oninput = renderContacts;
$('sample-one').onclick = () => run(async () => { $('chat-text').value = samples[0]; await parseText(); notice('已填入虚构示例，请核对联系人后再更新档案。'); });
$('sample-two').onclick = () => run(async () => { $('chat-text').value = samples[1]; await parseText(); notice('第二个示例包含咖啡喜好的变化，可体验冲突提示与信息去重。'); });
$('parse-text').onclick = () => run(parseText);
$('chat-text').oninput = () => { state.messages = []; $('speaker-panel').hidden = true; $('save-consent').checked = false; $('redacted-preview').textContent = ''; $('message-count').textContent = '文本已变化，请重新识别'; };
$('clear-chat').onclick = clearChat;
$('chat-file').onchange = () => run(async () => {
  const file = $('chat-file').files[0]; if (!file) return;
  clearChat();
  if (file.size > 5 * 1024 * 1024) throw new Error('文件不能超过 5 MB');
  const form = new FormData(); form.append('file', file);
  const parsed = await api('/parse', { method: 'POST', body: form });
  await setMessages(parsed.messages);
  notice('Excel 已解析，请核对“我”和“对方”，文件不会保存到档案库。');
});
for (const id of ['self-speaker', 'other-speaker']) $(id).onchange = () => run(async () => {
  const opposite = id === 'self-speaker' ? 'other-speaker' : 'self-speaker';
  $(opposite).value = [...new Set(state.messages.map(m => m.speaker))].find(s => s !== $(id).value);
  await preview();
});
$('analyze-profile').onclick = () => run(async () => {
  if (!$('save-consent').checked) throw new Error('请先确认联系人对应关系与本机保存选项。');
  const p = state.profile;
  notice($('use-ai').checked ? '正在请求云端 AI 并更新档案；如同时生成情感长文，可能需等待约两分钟…' : '正在提取喜好并更新档案…');
  const data = await api(`/contacts/${p.id}/analyze`, { method: 'POST', body: JSON.stringify(payload()) });
  state.profile = data.profile;
  renderProfile(); await refreshContacts();
  notice(data.report_regenerated ? (data.warning || '档案未重复导入，已重新生成本次 AI 情感长文。') : data.duplicate ? '这个片段已经导入，未重复更新档案或调用 AI。' : (data.warning || '档案已更新。请检查新条目和需要核实的不同说法。'));
  $('save-consent').checked = false;
  $('use-ai').checked = false;
  if (data.analysis) {
    const stats = data.analysis.statistics;
    $('analysis-summary').replaceChildren(el('span', '', `我：${stats.message_count.self} 条消息 / ${stats.total_chars.self} 字`), el('span', '', `对方：${stats.message_count.other} 条消息 / ${stats.total_chars.other} 字`));
    $('profile-guidance').hidden = !(data.analysis.guidance || data.analysis.guidance_error);
    $('profile-guidance-text').textContent = data.analysis.guidance || (data.analysis.guidance_error ? '长文暂未生成：' + data.analysis.guidance_error : '');
    $('session-analysis').hidden = false;
  }
});
$('export-contact').onclick = () => {
  const data = { ...state.profile, export_note: '含脱敏证据的个人档案，请妥善保管。时间为导入时间，推测不代表完整人格。' };
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json;charset=utf-8' }));
  const anchor = el('a'); anchor.href = url; anchor.download = `contact-profile-${state.profile.id.slice(0, 8)}.json`;
  anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
};
$('delete-contact').onclick = () => {
  state.pendingDelete = { contactId: state.profile.id };
  $('delete-title').textContent = `删除“${state.profile.name}”？`;
  $('delete-description').textContent = '将删除本机数据库中的联系人、全部档案依据和更新记录。已导出的文件或第三方服务收到的内容不受此操作影响。';
  $('delete-dialog').showModal();
};
$('cancel-delete').onclick = () => $('delete-dialog').close();
$('confirm-delete').onclick = () => run(async () => {
  const pending = state.pendingDelete;
  if (pending.factId) {
    state.profile = await api(`/contacts/${pending.contactId}/facts/${pending.factId}`, { method: 'PATCH', body: JSON.stringify({ revision: pending.revision, action: 'delete' }) });
  } else {
    await api('/contacts/' + pending.contactId, { method: 'DELETE' }); state.profile = null; clearChat();
  }
  $('delete-dialog').close(); renderProfile(); await refreshContacts(); notice('已删除。');
});
$('cancel-edit').onclick = () => $('edit-dialog').close();
$('edit-form').onsubmit = event => {
  event.preventDefault(); run(async () => {
    state.profile = await api(`/contacts/${state.profile.id}/facts/${state.editId}`, { method: 'PATCH', body: JSON.stringify({ revision: state.profile.revision, action: 'correct', text: $('edit-text').value }) });
    $('edit-dialog').close(); renderProfile(); notice('已保存人工修正，之后的自动提取不会覆盖这段描述。');
  });
};
run(refreshContacts);
health();
window.addEventListener('focus', health);
