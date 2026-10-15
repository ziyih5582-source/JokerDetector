// -*- coding: utf-8 -*-
/**
 * 小丑社区页面逻辑 - 账号、排行榜与评论
 *
 * 读取榜单/评论不需要登录；上传小丑值、发表评论需要先登录。
 * token 存在 localStorage，随请求放在 Authorization: Bearer 头里。
 */

(function() {
    'use strict';

    const TOKEN_KEY = 'joker_community_token';
    const NAME_KEY = 'joker_community_username';
    const AVATAR_KEY = 'joker_community_avatar';

    // 可选头像：与六型小丑一一对应（clown.js 里有同名形象）
    const AVATAR_TYPES = ['殉道型', '镜像型', '弄臣型', '幻恋型', '守候型', '单向型'];
    const DEFAULT_AVATAR = '殉道型';

    let currentPage = 0;
    const pageSize = 20;
    let currentEntryId = null;
    let pendingResult = null;  // 从鉴定所带过来的结果
    let listenersBound = false;
    let authMode = 'login';    // 'login' | 'register'
    let selectedAvatar = DEFAULT_AVATAR;

    // ---------- 账号状态 ----------

    function getToken() {
        try { return localStorage.getItem(TOKEN_KEY) || ''; } catch (e) { return ''; }
    }

    function getUsername() {
        try { return localStorage.getItem(NAME_KEY) || ''; } catch (e) { return ''; }
    }

    function getAvatar() {
        try { return localStorage.getItem(AVATAR_KEY) || ''; } catch (e) { return ''; }
    }

    function setSession(token, username, avatarType) {
        try {
            localStorage.setItem(TOKEN_KEY, token);
            localStorage.setItem(NAME_KEY, username);
            if (avatarType) localStorage.setItem(AVATAR_KEY, avatarType);
        } catch (e) { /* 忽略隐私模式下的写入失败 */ }
        renderAccount();
    }

    function clearSession() {
        try {
            localStorage.removeItem(TOKEN_KEY);
            localStorage.removeItem(NAME_KEY);
            localStorage.removeItem(AVATAR_KEY);
        } catch (e) { /* 忽略 */ }
        renderAccount();
    }

    function authHeaders() {
        const token = getToken();
        return token ? { 'Authorization': 'Bearer ' + token } : {};
    }

    // 用 clown.js 的六型形象渲染一个头像（返回 SVG 字符串）
    function avatarSvg(type) {
        const t = AVATAR_TYPES.indexOf(type) >= 0 ? type : DEFAULT_AVATAR;
        if (window.Clown && typeof window.Clown.bust === 'function') {
            return window.Clown.bust(t);
        }
        return '';
    }

    function renderAccount() {
        const userEl = document.getElementById('community-user');
        const btn = document.getElementById('btn-auth');
        const who = document.getElementById('submit-who');
        const name = getUsername();
        if (userEl) {
            const avatar = getAvatar();
            userEl.innerHTML = '';
            if (name && avatar) {
                const av = document.createElement('span');
                av.className = 'account-avatar';
                av.innerHTML = avatarSvg(avatar);
                userEl.appendChild(av);
            }
            userEl.appendChild(document.createTextNode(name ? name : '未登录'));
        }
        if (btn) btn.textContent = name ? '退出登录' : '登录 / 注册';
        if (who) who.textContent = name || '你的账号';
    }

    // 确保已登录；未登录则打开登录框并返回 false
    function ensureLogin() {
        if (getUsername()) return true;
        openAuthModal('login');
        return false;
    }

    // ---------- 初始化 ----------

    function init() {
        if (!listenersBound) {
            setupEventListeners();
            listenersBound = true;
        }
        renderAccount();
        renderParade();
        syncSession();
        loadLeaderboard();
    }

    function bind() {
        if (!listenersBound) {
            setupEventListeners();
            listenersBound = true;
        }
        renderAccount();
        renderParade();
        syncSession();
    }

    // 用 /auth/me 校准本地会话（头像可能在别处改过 / token 已失效）
    async function syncSession() {
        const token = getToken();
        if (!token) return;
        try {
            const res = await fetch('/api/community/auth/me', { headers: authHeaders() });
            const data = await res.json();
            if (data.username) {
                setSession(token, data.username, data.avatar_type);
            } else {
                clearSession();
            }
        } catch (e) { /* 离线时保持本地状态 */ }
    }

    // 榜单上方的装饰小丑队列（会摇摆并捏鼻子）
    function renderParade() {
        const box = document.getElementById('clown-parade');
        if (!box || box.dataset.ready) return;
        if (window.Clown && typeof window.Clown.parade === 'function') {
            box.innerHTML = window.Clown.parade(5);
            box.dataset.ready = '1';
        }
    }

    function setupEventListeners() {
        const goJokerBtn = document.getElementById('btn-go-joker');
        if (goJokerBtn) {
            goJokerBtn.addEventListener('click', () => {
                if (typeof window.switchToJoker === 'function') window.switchToJoker();
            });
        }

        document.getElementById('prev-page').addEventListener('click', () => {
            if (currentPage > 0) { currentPage--; loadLeaderboard(); }
        });
        document.getElementById('next-page').addEventListener('click', () => {
            currentPage++;
            loadLeaderboard();
        });

        // 账号
        document.getElementById('btn-auth').addEventListener('click', () => {
            if (getUsername()) logout();
            else openAuthModal('login');
        });
        document.getElementById('close-auth').addEventListener('click', closeAuthModal);
        document.getElementById('btn-auth-submit').addEventListener('click', submitAuth);
        document.getElementById('link-auth-switch').addEventListener('click', (e) => {
            e.preventDefault();
            openAuthModal(authMode === 'login' ? 'register' : 'login');
        });

        // 评论
        document.getElementById('close-comments').addEventListener('click', closeCommentsModal);
        document.getElementById('btn-post-comment').addEventListener('click', postComment);

        // 提交评分
        document.getElementById('close-submit').addEventListener('click', closeSubmitModal);
        document.getElementById('btn-confirm-submit').addEventListener('click', submitScore);

        // 点击遮罩关闭
        window.addEventListener('click', (e) => {
            if (e.target === document.getElementById('comments-modal')) closeCommentsModal();
            if (e.target === document.getElementById('submit-modal')) closeSubmitModal();
            if (e.target === document.getElementById('auth-modal')) closeAuthModal();
        });
    }

    // ---------- 登录 / 注册 ----------

    function openAuthModal(mode) {
        authMode = mode || 'login';
        const title = document.getElementById('auth-title');
        const submit = document.getElementById('btn-auth-submit');
        const switcher = document.getElementById('link-auth-switch');
        const err = document.getElementById('auth-error');
        const pickerGroup = document.getElementById('avatar-picker-group');
        title.textContent = authMode === 'login' ? '登录' : '注册';
        submit.textContent = authMode === 'login' ? '登录' : '注册并登录';
        switcher.textContent = authMode === 'login' ? '去注册' : '去登录';
        if (err) { err.hidden = true; err.textContent = ''; }
        // 只有注册时才需要选头像
        if (pickerGroup) pickerGroup.hidden = authMode !== 'register';
        if (authMode === 'register') renderAvatarPicker();
        document.getElementById('auth-modal').hidden = false;
        document.getElementById('auth-username').focus();
    }

    // 渲染头像选择网格：六个小丑形象，点选高亮
    function renderAvatarPicker() {
        const box = document.getElementById('avatar-picker');
        if (!box) return;
        box.innerHTML = '';
        AVATAR_TYPES.forEach((type) => {
            const cell = document.createElement('button');
            cell.type = 'button';
            cell.className = 'avatar-option' + (type === selectedAvatar ? ' selected' : '');
            cell.dataset.avatar = type;
            cell.title = type;
            cell.setAttribute('aria-pressed', String(type === selectedAvatar));

            const fig = document.createElement('span');
            fig.className = 'avatar-option-fig';
            fig.innerHTML = avatarSvg(type);

            const name = document.createElement('span');
            name.className = 'avatar-option-name';
            name.textContent = type;

            cell.append(fig, name);
            cell.addEventListener('click', () => {
                selectedAvatar = type;
                renderAvatarPicker();
            });
            box.append(cell);
        });
    }

    function closeAuthModal() {
        document.getElementById('auth-modal').hidden = true;
        document.getElementById('auth-password').value = '';
        const err = document.getElementById('auth-error');
        if (err) { err.hidden = true; err.textContent = ''; }
    }

    async function submitAuth() {
        const username = document.getElementById('auth-username').value.trim();
        const password = document.getElementById('auth-password').value.trim();
        const err = document.getElementById('auth-error');

        if (!username) { showAuthError('请输入用户名'); return; }
        if (!/^\d{6}$/.test(password)) { showAuthError('密码必须是 6 位数字'); return; }
        if (authMode === 'register' && !selectedAvatar) { showAuthError('请选一个头像'); return; }

        const endpoint = authMode === 'login' ? '/api/community/auth/login' : '/api/community/auth/register';
        const payload = { username: username, password: password };
        if (authMode === 'register') payload.avatar_type = selectedAvatar;
        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await response.json();
            if (response.ok) {
                setSession(data.token, data.username, data.avatar_type);
                closeAuthModal();
                // 登录后如果有待提交的鉴定结果，直接继续提交
                if (pendingResult) {
                    openSubmitModal(pendingResult);
                }
            } else {
                showAuthError(data.detail || '操作失败');
            }
        } catch (e) {
            showAuthError('网络错误，请稍后重试');
        }
    }

    function showAuthError(msg) {
        const err = document.getElementById('auth-error');
        if (err) { err.textContent = msg; err.hidden = false; }
    }

    async function logout() {
        try {
            await fetch('/api/community/auth/logout', { method: 'POST', headers: authHeaders() });
        } catch (e) { /* 忽略 */ }
        clearSession();
        alert('已退出登录');
    }

    // ---------- 榜单 ----------

    async function loadLeaderboard() {
        const listContainer = document.getElementById('leaderboard-list');
        listContainer.innerHTML = '<p class="loading-note">加载中...</p>';
        try {
            const response = await fetch(`/api/community/leaderboard?limit=${pageSize}&offset=${currentPage * pageSize}`);
            const data = await response.json();
            if (!data.entries || data.entries.length === 0) {
                listContainer.innerHTML = '<p class="empty-note">暂无数据，快来提交第一个成绩吧！</p>';
                document.getElementById('pagination').hidden = true;
                return;
            }
            renderLeaderboard(data.entries);
            updatePagination(data.entries.length);
        } catch (error) {
            console.error('加载榜单失败:', error);
            listContainer.innerHTML = '<p class="error-note">加载失败，请稍后重试</p>';
        }
    }

    function renderLeaderboard(entries) {
        const listContainer = document.getElementById('leaderboard-list');
        listContainer.innerHTML = '';
        const medals = ['🥇', '🥈', '🥉'];

        entries.forEach((entry, index) => {
            const medal = index < 3 ? medals[index] : '';
            const rank = currentPage * pageSize + index + 1;

            const item = document.createElement('div');
            item.className = 'leaderboard-item';
            item.dataset.entryId = entry.id;

            const header = document.createElement('div');
            header.className = 'entry-header';

            const rankEl = document.createElement('span');
            rankEl.className = 'rank';
            rankEl.textContent = (medal ? medal + ' ' : '') + rank;

            const avatarEl = document.createElement('span');
            avatarEl.className = 'entry-avatar';
            avatarEl.innerHTML = avatarSvg(entry.avatar_type);
            avatarEl.title = entry.avatar_type || '';

            const nameEl = document.createElement('span');
            nameEl.className = 'user-name';
            nameEl.textContent = entry.user_name;

            const scoreEl = document.createElement('span');
            scoreEl.className = 'score';
            scoreEl.textContent = Number(entry.score).toFixed(1);

            const typeEl = document.createElement('span');
            typeEl.className = 'joker-type';
            typeEl.textContent = entry.joker_type;

            header.append(rankEl, avatarEl, nameEl, scoreEl, typeEl);

            const footer = document.createElement('div');
            footer.className = 'entry-footer';

            const timeEl = document.createElement('span');
            timeEl.className = 'timestamp';
            timeEl.textContent = formatTimestamp(entry.timestamp);

            const commentEl = document.createElement('span');
            commentEl.className = 'comment-count';
            commentEl.textContent = '💬 查看评论';

            footer.append(timeEl, commentEl);
            item.append(header, footer);

            item.addEventListener('click', () => openCommentsModal(entry.id));
            listContainer.append(item);
        });
    }

    function updatePagination(totalCount) {
        const pagination = document.getElementById('pagination');
        const pageInfo = document.getElementById('page-info');
        const prevBtn = document.getElementById('prev-page');
        const nextBtn = document.getElementById('next-page');
        const totalPages = Math.ceil(totalCount / pageSize);
        if (totalPages <= 1) { pagination.hidden = true; return; }
        pagination.hidden = false;
        pageInfo.textContent = `第 ${currentPage + 1} 页 / 共 ${totalPages} 页`;
        prevBtn.disabled = currentPage === 0;
        nextBtn.disabled = currentPage >= totalPages - 1;
    }

    // ---------- 评论 ----------

    async function openCommentsModal(entryId) {
        currentEntryId = entryId;
        const modal = document.getElementById('comments-modal');
        const hint = document.getElementById('comment-hint');
        hint.textContent = getUsername() ? ('以 ' + getUsername() + ' 的身份评论') : '发表评论需要先登录';

        try {
            const response = await fetch(`/api/community/entries/${entryId}/comments`);
            const data = await response.json();
            const title = document.getElementById('modal-entry-title');
            const list = document.getElementById('comments-list');

            const entryRes = await fetch(`/api/community/entries/${entryId}`);
            const entry = await entryRes.json();
            title.textContent = `${entry.user_name} - ${Number(entry.score).toFixed(1)}分 (${entry.joker_type})`;

            if (!data.comments || data.comments.length === 0) {
                list.innerHTML = '<p class="empty-note">暂无评论，来抢沙发吧！</p>';
            } else {
                renderComments(data.comments);
            }
            modal.hidden = false;
        } catch (error) {
            console.error('加载评论失败:', error);
            alert('加载评论失败，请稍后重试');
        }
    }

    function renderComments(comments) {
        const list = document.getElementById('comments-list');
        let html = '';
        comments.forEach(comment => {
            html += `
                <div class="comment-item">
                    <div class="comment-header">
                        <span class="comment-user">${escapeHtml(comment.user_name)}</span>
                        <span class="comment-time">${formatTimestamp(comment.timestamp)}</span>
                    </div>
                    <div class="comment-content">${escapeHtml(comment.content)}</div>
                </div>
            `;
        });
        list.innerHTML = html;
    }

    function closeCommentsModal() {
        document.getElementById('comments-modal').hidden = true;
        currentEntryId = null;
    }

    async function postComment() {
        if (!ensureLogin()) return;
        const content = document.getElementById('comment-input').value.trim();
        if (!content) { alert('请输入评论内容'); return; }
        if (content.length > 50) { alert('评论不能超过 50 字'); return; }
        if (!currentEntryId) { alert('错误：未找到条目 ID'); return; }

        try {
            const response = await fetch('/api/community/comments', {
                method: 'POST',
                headers: Object.assign({ 'Content-Type': 'application/json' }, authHeaders()),
                body: JSON.stringify({ entry_id: currentEntryId, content: content })
            });
            if (response.ok) {
                document.getElementById('comment-input').value = '';
                openCommentsModal(currentEntryId);
            } else {
                const data = await response.json();
                if (response.status === 401) { clearSession(); openAuthModal('login'); }
                alert('发布失败：' + (data.detail || '未知错误'));
            }
        } catch (error) {
            console.error('发布失败:', error);
            alert('发布失败，请稍后重试');
        }
    }

    // ---------- 提交评分 ----------

    function openSubmitModal(result) {
        pendingResult = result || null;
        const preview = document.getElementById('submit-preview');
        preview.innerHTML = '';
        if (pendingResult) {
            const scoreLine = document.createElement('div');
            scoreLine.className = 'preview-score';
            scoreLine.innerHTML = '<span class="preview-score-num">' +
                Number(pendingResult.score).toFixed(1) +
                '</span><span class="preview-score-unit">小丑值</span>';
            preview.appendChild(scoreLine);
            const typeLine = document.createElement('div');
            typeLine.className = 'preview-type';
            typeLine.textContent = '类型 · ' + pendingResult.type;
            preview.appendChild(typeLine);
        }
        renderAccount();
        document.getElementById('submit-modal').hidden = false;
    }

    function closeSubmitModal() {
        document.getElementById('submit-modal').hidden = true;
        pendingResult = null;
    }

    async function submitScore() {
        if (!pendingResult) {
            alert('没有可提交的鉴定结果，请先去小丑鉴定所开鉴');
            closeSubmitModal();
            return;
        }
        if (!ensureLogin()) return;

        try {
            const response = await fetch('/api/community/submit', {
                method: 'POST',
                headers: Object.assign({ 'Content-Type': 'application/json' }, authHeaders()),
                body: JSON.stringify({ score: pendingResult.score, joker_type: pendingResult.type })
            });
            if (response.ok) {
                closeSubmitModal();
                alert('提交成功！');
                if (typeof window.switchToCommunity === 'function') window.switchToCommunity();
                currentPage = 0;
                loadLeaderboard();
            } else {
                const data = await response.json();
                if (response.status === 401) { clearSession(); openAuthModal('login'); }
                alert('提交失败：' + (data.detail || '未知错误'));
            }
        } catch (error) {
            console.error('提交失败:', error);
            alert('提交失败，请稍后重试');
        }
    }

    // ---------- 工具 ----------

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function formatTimestamp(timestamp) {
        const date = new Date(timestamp.replace(' ', 'T') + 'Z');
        const now = new Date();
        const diff = now - date;
        if (isNaN(date.getTime())) return timestamp;
        if (diff < 60000) return '刚刚';
        if (diff < 3600000) return Math.floor(diff / 60000) + '分钟前';
        if (diff < 86400000) return Math.floor(diff / 3600000) + '小时前';
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        const hour = String(date.getHours()).padStart(2, '0');
        const minute = String(date.getMinutes()).padStart(2, '0');
        return year === now.getFullYear()
            ? `${month}-${day} ${hour}:${minute}`
            : `${year}-${month}-${day} ${hour}:${minute}`;
    }

    // ---------- 暴露 ----------

    window.openCommentsModal = openCommentsModal;
    window.CommunityInit = init;
    window.CommunityOpenSubmit = openSubmitModal;

    document.addEventListener('DOMContentLoaded', bind);
})();
