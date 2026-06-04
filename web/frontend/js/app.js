/**
 * Joker Detector Pro - 主应用逻辑
 */

// ==================== 全局状态 ====================
const STATE = {
    result: null,
    selectedFile: null
};

// ==================== 粒子背景 ====================
class ParticleBackground {
    constructor() {
        this.canvas = document.getElementById('particles');
        this.ctx = this.canvas.getContext('2d');
        this.particles = [];
        this.mouseX = 0;
        this.mouseY = 0;
        this.resize();
        this.init();
        this.bindEvents();
        this.animate();
    }

    resize() {
        this.canvas.width = window.innerWidth;
        this.canvas.height = window.innerHeight;
    }

    init() {
        const count = Math.floor((this.canvas.width * this.canvas.height) / 15000);
        this.particles = [];
        for (let i = 0; i < count; i++) {
            this.particles.push({
                x: Math.random() * this.canvas.width,
                y: Math.random() * this.canvas.height,
                vx: (Math.random() - 0.5) * 0.4,
                vy: (Math.random() - 0.5) * 0.4,
                radius: Math.random() * 1.8 + 0.3,
                opacity: Math.random() * 0.4 + 0.1
            });
        }
    }

    bindEvents() {
        window.addEventListener('resize', () => {
            this.resize();
            this.init();
        });
        document.addEventListener('mousemove', (e) => {
            this.mouseX = e.clientX;
            this.mouseY = e.clientY;
        });
    }

    animate() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        this.particles.forEach(p => {
            p.x += p.vx;
            p.y += p.vy;
            if (p.x < 0) p.x = this.canvas.width;
            if (p.x > this.canvas.width) p.x = 0;
            if (p.y < 0) p.y = this.canvas.height;
            if (p.y > this.canvas.height) p.y = 0;

            const dx = this.mouseX - p.x;
            const dy = this.mouseY - p.y;
            const dist = Math.sqrt(dx * dx + dy * dy);
            const edgeDist = 120;

            if (dist < edgeDist) {
                const force = (1 - dist / edgeDist) * 0.5;
                p.x -= dx * force * 0.02;
                p.y -= dy * force * 0.02;
            }

            this.ctx.beginPath();
            this.ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
            this.ctx.fillStyle = `rgba(139, 92, 246, ${p.opacity})`;
            this.ctx.fill();
        });

        // 连线
        for (let i = 0; i < this.particles.length; i++) {
            for (let j = i + 1; j < this.particles.length; j++) {
                const dx = this.particles[i].x - this.particles[j].x;
                const dy = this.particles[i].y - this.particles[j].y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (dist < 100) {
                    this.ctx.beginPath();
                    this.ctx.moveTo(this.particles[i].x, this.particles[i].y);
                    this.ctx.lineTo(this.particles[j].x, this.particles[j].y);
                    this.ctx.strokeStyle = `rgba(139, 92, 246, ${0.06 * (1 - dist / 100)})`;
                    this.ctx.lineWidth = 0.5;
                    this.ctx.stroke();
                }
            }
        }

        requestAnimationFrame(() => this.animate());
    }
}

// ==================== 加载动画 ====================
const loadingMessages = [
    '🔍 正在扫描你的舔狗行为...',
    '🤔 分析你的自我感动指数...',
    '📊 计算消息比例中...',
    '🎭 判断小丑人格类型...',
    '💔 检测单向情感输出...',
    '🃏 小丑指数量化中...',
    '📝 AI 正在撰写诊断报告...'
];

function showLoading() {
    const overlay = document.getElementById('loading-overlay');
    overlay.classList.remove('hidden');
    const textEl = document.getElementById('loading-text');
    let idx = 0;
    textEl.textContent = loadingMessages[0];
    const interval = setInterval(() => {
        idx = (idx + 1) % loadingMessages.length;
        textEl.textContent = loadingMessages[idx];
        textEl.style.opacity = '0';
        setTimeout(() => { textEl.style.opacity = '1'; }, 100);
    }, 1800);
    return () => { clearInterval(interval); };
}

function hideLoading(stopFn) {
    if (stopFn) stopFn();
    document.getElementById('loading-overlay').classList.add('hidden');
}

// ==================== API 调用 ====================
async function apiCall(url, options = {}) {
    const resp = await fetch(url, {
        headers: { 'Content-Type': 'application/json' },
        ...options
    });
    if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: '未知错误' }));
        throw new Error(err.detail || `HTTP ${resp.status}`);
    }
    return resp.json();
}

async function checkHealth() {
    try {
        const data = await apiCall('/api/health');
        const statusText = data.ai_available
            ? `✅ AI 已连接 (${data.ai_model || 'deepseek-chat'})`
            : '⚠️ 仅算法模式';
        document.getElementById('footer-status').textContent = statusText;
        // 更新 AI 状态指示灯
        const dot = document.getElementById('ai-status-dot');
        if (data.ai_available) {
            dot.classList.add('active');
        } else {
            dot.classList.remove('active');
        }
        return data;
    } catch {
        document.getElementById('footer-status').textContent = '❌ 后端未连接';
        return null;
    }
}

async function loadDemos() {
    const data = await apiCall('/api/demos');
    renderDemoCards(data.demos);
}

function renderDemoCards(demos) {
    const container = document.getElementById('demo-cards');
    container.innerHTML = demos.map(d => `
        <div class="demo-card" onclick="runDemo(${d.id})" data-demo-id="${d.id}">
            <div class="demo-card-title">${d.title}</div>
            <div class="demo-card-desc">${d.description}</div>
            <div class="demo-card-meta">
                👤 ${d.self_name} vs ${d.other_name} · ${d.message_count} 条消息
            </div>
        </div>
    `).join('');
}

async function runDemo(demoId) {
    const stopLoading = showLoading();
    try {
        const result = await apiCall(`/api/analyze/demo/${demoId}`, { method: 'POST' });
        displayResult(result);
    } catch (err) {
        alert('分析失败: ' + err.message);
    } finally {
        hideLoading(stopLoading);
    }
}

// ==================== 文件上传 ====================
function setupUpload() {
    const zone = document.getElementById('upload-zone');
    const input = document.getElementById('file-input');
    const selectDiv = document.getElementById('speaker-select');

    zone.addEventListener('click', () => input.click());
    zone.addEventListener('dragover', (e) => {
        e.preventDefault();
        zone.classList.add('drag-over');
    });
    zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
    zone.addEventListener('drop', (e) => {
        e.preventDefault();
        zone.classList.remove('drag-over');
        const file = e.dataTransfer.files[0];
        if (file) handleFileSelect(file);
    });

    input.addEventListener('change', () => {
        if (input.files[0]) handleFileSelect(input.files[0]);
    });

    document.getElementById('analyze-btn').addEventListener('click', async () => {
        if (!STATE.selectedFile) return;
        const selfIndex = parseInt(document.querySelector('input[name="self_index"]:checked').value);
        const stopLoading = showLoading();
        try {
            const formData = new FormData();
            formData.append('file', STATE.selectedFile);
            const resp = await fetch(`/api/analyze/upload?self_index=${selfIndex}`, {
                method: 'POST',
                body: formData
            });
            if (!resp.ok) {
                const err = await resp.json().catch(() => ({ detail: '未知错误' }));
                throw new Error(err.detail);
            }
            const result = await resp.json();
            displayResult(result);
        } catch (err) {
            alert('分析失败: ' + err.message);
        } finally {
            hideLoading(stopLoading);
        }
    });
}

async function handleFileSelect(file) {
    if (!file.name.endsWith('.xlsx') && !file.name.endsWith('.xls')) {
        alert('仅支持 .xlsx 或 .xls 格式');
        return;
    }
    STATE.selectedFile = file;
    const selectDiv = document.getElementById('speaker-select');
    selectDiv.classList.remove('hidden');

    document.getElementById('speaker-0').textContent = '用户 0';
    document.getElementById('speaker-1').textContent = '用户 1';
}

// ==================== 结果显示 ====================
function displayResult(data) {
    STATE.result = data;

    // 隐藏 hero，显示 result
    document.getElementById('hero-section').classList.add('hidden');
    document.getElementById('result-section').classList.remove('hidden');
    window.scrollTo({ top: 0, behavior: 'smooth' });

    const v = data.verdict;
    const stats = data.statistics;
    const z = data.z_metrics;

    // ---- 判定头部 ----
    const badge = document.getElementById('verdict-badge');
    const icon = document.getElementById('verdict-icon');
    const label = document.getElementById('verdict-label');
    const scoreNum = document.getElementById('score-number');
    const sub = document.getElementById('score-subtitle');

    if (v.is_joker) {
        badge.className = 'verdict-badge joker';
        icon.textContent = '🤡';
        label.textContent = v.label + ' —— ' + v.type;
        sub.textContent = getLevelText(v.level);
    } else {
        badge.className = 'verdict-badge healthy';
        icon.textContent = '👑';
        label.textContent = v.label;
        sub.textContent = v.desc || '继续保持！';
    }

    // 分数数字动画
    const targetScore = Math.round(v.score);
    animateScore(scoreNum, targetScore);

    // ---- 小丑类型卡片 ----
    const typeCard = document.getElementById('type-card');
    if (v.is_joker && v.type_info) {
        typeCard.classList.remove('hidden');
        document.getElementById('type-name').textContent = '🎭 ' + v.type;
        document.getElementById('type-desc').textContent = v.type_info.desc;
        document.getElementById('type-suggestion').textContent = '💡 ' + v.type_info.suggestion;
        document.getElementById('type-color-bar').style.background = v.type_info.color;
    } else {
        typeCard.classList.add('hidden');
    }

    // ---- 五维仪表盘 ----
    const ratios = stats.ratios;
    updateGauge('gauge-message', ratios.message);
    updateGauge('gauge-chars', ratios.chars);
    updateGauge('gauge-sticker', ratios.sticker);
    updateGauge('gauge-streak', ratios.streak);
    updateGauge('gauge-picture', ratios.picture);

    // ---- 图表 ----
    renderCharts(z, stats);

    // ---- 聊天回放 ----
    renderChatReplay(data.messages_for_display);

    // ---- AI 疏导 ----
    const guidanceSection = document.getElementById('guidance-section');
    if (data.guidance) {
        guidanceSection.classList.remove('hidden');
        document.getElementById('guidance-title').textContent =
            v.is_joker ? '💌 AI 深度情感诊断报告' : '👑 AI 高阶博弈复盘';
        document.getElementById('guidance-content').textContent = data.guidance;
    } else {
        guidanceSection.classList.add('hidden');
    }

    // ---- 分享按钮 ----
    document.getElementById('share-btn').onclick = () => generateShareImage();

    // ---- 触发音乐 ----
    playMusicForType(v.is_joker ? v.type : null);
}

function getLevelText(level) {
    const map = {
        'confirmed': '🔴 确诊纯小丑 —— 情感投入严重失衡，请立即清醒！',
        'high_risk': '🟠 高度疑似小丑 —— 比对方主动太多，存在自我感动风险',
        'suspicious': '🟡 轻度小丑倾向 —— 偶尔失衡，但总体可控',
        'mild': '🟢 健康社交模式 —— 关系基本对等，继续保持',
        'healthy': '🟢 绝对理性人 —— 你是这段关系里的清醒玩家'
    };
    return map[level] || '';
}

function animateScore(el, target) {
    let current = 0;
    const duration = 1500;
    const startTime = performance.now();

    function step(timestamp) {
        const elapsed = timestamp - startTime;
        const progress = Math.min(elapsed / duration, 1);
        // easeOutExpo
        const eased = progress === 1 ? 1 : 1 - Math.pow(2, -10 * progress);
        current = Math.round(eased * target);
        el.textContent = current;
        if (progress < 1) {
            requestAnimationFrame(step);
        } else {
            el.textContent = target;
            el.classList.add('score-bouncing');
            setTimeout(() => el.classList.remove('score-bouncing'), 600);
        }
    }

    requestAnimationFrame(step);
}

function updateGauge(id, ratio) {
    const card = document.getElementById(id);
    const valueEl = card.querySelector('.gauge-value');
    const ringEl = card.querySelector('.gauge-ring');

    // ratio: self/other, cap display at 10x
    let displayRatio = Math.min(ratio, 10);
    let percent;
    if (ratio >= 1) {
        percent = Math.min(50 + (displayRatio - 1) / 9 * 50, 100);
    } else {
        percent = Math.max(ratio * 50, 5);
    }
    valueEl.textContent = ratio.toFixed(1) + 'x';
    ringEl.style.setProperty('--percent', `${percent}%`);

    // Color coding
    if (ratio >= 3) {
        ringEl.style.background = `conic-gradient(#e74c6f ${percent}%, var(--border) ${percent}%)`;
    } else if (ratio >= 1.5) {
        ringEl.style.background = `conic-gradient(#f0c040 ${percent}%, var(--border) ${percent}%)`;
    } else {
        ringEl.style.background = `conic-gradient(#4ade80 ${percent}%, var(--border) ${percent}%)`;
    }
}

// ==================== 聊天回放 ====================
function renderChatReplay(messages) {
    const container = document.getElementById('chat-replay');
    container.innerHTML = '';

    // 打字机效果逐条显示
    let i = 0;
    const batchSize = 3;

    function showBatch() {
        const batch = messages.slice(i, i + batchSize);
        batch.forEach(msg => {
            const div = document.createElement('div');
            div.className = `chat-msg ${msg.is_self ? 'self' : 'other'}`;
            div.innerHTML = `
                <div class="chat-msg-speaker">${msg.speaker}</div>
                <div class="chat-msg-content">${escapeHtml(msg.content)}</div>
            `;
            container.appendChild(div);
        });
        i += batchSize;
        if (i < messages.length) {
            container.scrollTop = container.scrollHeight;
            setTimeout(showBatch, 200);
        }
    }

    if (messages.length > 0) {
        showBatch();
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ==================== 分享图片生成 ====================
async function generateShareImage() {
    const card = document.getElementById('report-card');
    try {
        const canvas = await html2canvas(card, {
            backgroundColor: '#14141f',
            scale: 2,
            useCORS: true,
            logging: false
        });
        const link = document.createElement('a');
        link.download = 'Joker_Report.png';
        link.href = canvas.toDataURL('image/png');
        link.click();
    } catch (err) {
        alert('图片生成失败: ' + err.message);
    }
}

// ==================== AI 配置面板 ====================
function setupAIConfig() {
    const toggle = document.getElementById('ai-config-toggle');
    const body = document.getElementById('ai-config-body');
    const saveBtn = document.getElementById('ai-save-btn');
    const msgEl = document.getElementById('ai-config-msg');

    toggle.addEventListener('click', () => {
        body.classList.toggle('hidden');
        toggle.classList.toggle('open');
    });

    saveBtn.addEventListener('click', async () => {
        const apiKey = document.getElementById('ai-api-key').value.trim();
        const model = document.getElementById('ai-model').value;
        const baseUrl = document.getElementById('ai-base-url').value.trim();

        if (!apiKey) {
            msgEl.textContent = '请输入 API Key';
            msgEl.className = 'ai-config-msg error';
            return;
        }

        saveBtn.disabled = true;
        saveBtn.textContent = '⏳ 连接中...';
        msgEl.textContent = '';

        try {
            const resp = await fetch('/api/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ api_key: apiKey, model, base_url: baseUrl })
            });
            const data = await resp.json();
            if (data.success) {
                msgEl.textContent = `✅ AI 已连接！模型：${data.model}`;
                msgEl.className = 'ai-config-msg';
                document.getElementById('ai-status-dot').classList.add('active');
                document.getElementById('footer-status').textContent =
                    `✅ AI 已连接 (${data.model})`;
                body.classList.add('hidden');
                toggle.classList.remove('open');
            } else {
                msgEl.textContent = '❌ 连接失败，请检查 API Key 和地址';
                msgEl.className = 'ai-config-msg error';
            }
        } catch (err) {
            msgEl.textContent = '❌ 网络错误：' + err.message;
            msgEl.className = 'ai-config-msg error';
        } finally {
            saveBtn.disabled = false;
            saveBtn.textContent = '✅ 连接并启用 AI';
        }
    });
}

// ==================== 音乐播放器 ====================
const JOKER_MUSIC_MAP = {
    '殉道型': '过火.MP3',
    '镜像型': '一直很安静.MP3',
    '弄臣型': '怪咖.MP3',
    '幻恋型': '水星记.MP3'
};

function setupMusic() {
    const audio = document.getElementById('music-audio');
    const toggleBtn = document.getElementById('music-toggle-btn');
    const volumeSlider = document.getElementById('music-volume');

    audio.volume = volumeSlider.value / 100;

    toggleBtn.addEventListener('click', () => {
        if (audio.paused) {
            audio.play().catch(() => {});
            toggleBtn.textContent = '⏸';
        } else {
            audio.pause();
            toggleBtn.textContent = '▶';
        }
    });

    volumeSlider.addEventListener('input', () => {
        audio.volume = volumeSlider.value / 100;
    });

    audio.addEventListener('play', () => { toggleBtn.textContent = '⏸'; });
    audio.addEventListener('pause', () => { toggleBtn.textContent = '▶'; });
}

function playMusicForType(jokerType) {
    const bar = document.getElementById('music-bar');
    bar.classList.remove('hidden');

    const musicFile = jokerType ? JOKER_MUSIC_MAP[jokerType] : null;
    const audio = document.getElementById('music-audio');
    const trackName = document.getElementById('music-track-name');

    if (musicFile) {
        const src = `/music/${encodeURIComponent(musicFile)}`;
        if (!audio.src.endsWith(encodeURIComponent(musicFile))) {
            audio.src = src;
            trackName.textContent = musicFile.replace('.MP3', '').replace('.mp3', '');
        }
        audio.play().catch(() => {});
    }
}

// ==================== 初始化 ====================
document.addEventListener('DOMContentLoaded', () => {
    new ParticleBackground();
    checkHealth();
    loadDemos();
    setupUpload();
    setupAIConfig();
    setupMusic();
});
