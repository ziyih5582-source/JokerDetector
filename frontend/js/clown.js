/**
 * 小丑鉴定所 · 形象与全屏弹跳层
 *
 * 纯 DOM/SVG 绘制，不依赖外部图片。
 * - Clown.bust(type)   → 六型专属半身小丑（SVG 字符串，viewBox 0 0 140 158）
 * - Clown.circus()     → 经典马戏团小丑全身（SVG 字符串，viewBox 0 0 120 230）
 * - Clown.start(level, type) 生成对应类型的小丑并开启动画；Clown.stop() 渐隐清除。
 */
(function () {
  'use strict';

  var LAYER_ID = 'clown-layer';
  var BUBBLE_WORDS = [
    '小丑竟是我自己', '万一呢', '它回我了！', '再等等', '我没事',
    '只要它开心就好', '我不配', '我等你', '还有机会', '我都可以'
  ];

  var TYPE_COLOR = {
    '殉道型': '#C46868', '镜像型': '#6B8DB5', '弄臣型': '#D4A853',
    '幻恋型': '#8B6FAF', '守候型': '#7A5A3A', '单向型': '#8A4A6A'
  };

  // ------------------------------------------------------------ 六型半身形象（内容，不含 <svg> 外壳）
  var FACE = '<circle cx="70" cy="86" r="42" fill="#fffdf8" stroke="#2b2724" stroke-width="2.2"/>';
  var NOSE = '<circle cx="70" cy="93" r="10.5" fill="#cf3b2a"/><circle cx="66" cy="89" r="3.4" fill="#ff9a80"/>';

  var BUST = {
    '殉道型': function (c) {
      return '<ellipse cx="70" cy="24" rx="24" ry="6.5" fill="none" stroke="' + c + '" stroke-width="3.4"/>'
        + '<path d="M32 54 Q70 10 108 54 Z" fill="' + c + '"/>'
        + FACE
        + '<path d="M44 84 q9 8 18 0" fill="none" stroke="#2b2724" stroke-width="2.4" stroke-linecap="round"/>'
        + '<path d="M78 84 q9 8 18 0" fill="none" stroke="#2b2724" stroke-width="2.4" stroke-linecap="round"/>'
        + '<path d="M52 88 q-3 11 0 15 q3 -4 0 -15" fill="#7fa3c9"/>'
        + '<path d="M88 88 q3 11 0 15 q-3 -4 0 -15" fill="#7fa3c9"/>'
        + NOSE
        + '<path d="M55 108 q15 9 30 0" fill="none" stroke="#b03028" stroke-width="3" stroke-linecap="round"/>'
        + '<path d="M70 150 c-8 -9 -16 -14 -16 -22 a8 8 0 0 1 16 -3 a8 8 0 0 1 16 3 c0 8 -8 13 -16 22 Z" fill="' + c + '"/>';
    },
    '镜像型': function (c) {
      return '<path d="M34 56 Q70 16 106 56 L106 70 L34 70 Z" fill="#3a4250"/>'
        + FACE
        + '<path d="M70 44 a42 42 0 0 0 0 84 Z" fill="' + c + '" opacity="0.30"/>'
        + '<line x1="70" y1="44" x2="70" y2="128" stroke="#2b2724" stroke-width="1.6" stroke-dasharray="3 3"/>'
        + '<path d="M46 80 l7 -7 l7 7 l-7 7 Z" fill="#2b2724"/>'
        + '<path d="M80 84 q8 6 16 0" fill="none" stroke="#2b2724" stroke-width="2.4" stroke-linecap="round"/>'
        + '<circle cx="88" cy="84" r="3" fill="#2b2724"/>'
        + NOSE
        + '<path d="M52 110 q18 -8 36 0" fill="none" stroke="#b03028" stroke-width="3" stroke-linecap="round"/>'
        + '<path d="M104 40 l3 8 l8 3 l-8 3 l-3 8 l-3 -8 l-8 -3 l8 -3 Z" fill="#cfd8e6"/>';
    },
    '弄臣型': function (c) {
      return '<path d="M70 30 L44 8 Q52 30 64 34 Z" fill="' + c + '"/>'
        + '<path d="M70 30 L96 8 Q88 30 76 34 Z" fill="#2b2724"/>'
        + '<path d="M70 30 L70 6 Q74 22 72 32 Z" fill="#b03028"/>'
        + '<circle cx="44" cy="8" r="5" fill="' + c + '" stroke="#2b2724" stroke-width="1.4"/>'
        + '<circle cx="96" cy="8" r="5" fill="#e2c04a" stroke="#2b2724" stroke-width="1.4"/>'
        + '<circle cx="70" cy="6" r="4.5" fill="#e2c04a" stroke="#2b2724" stroke-width="1.4"/>'
        + FACE
        + '<path d="M44 82 q9 -8 18 0" fill="none" stroke="#2b2724" stroke-width="2.4" stroke-linecap="round"/>'
        + '<path d="M78 82 q9 -8 18 0" fill="none" stroke="#2b2724" stroke-width="2.4" stroke-linecap="round"/>'
        + '<ellipse cx="47" cy="98" rx="8" ry="5" fill="rgba(214,106,82,.4)"/>'
        + '<ellipse cx="93" cy="98" rx="8" ry="5" fill="rgba(214,106,82,.4)"/>'
        + NOSE
        + '<path d="M50 106 q20 22 40 0 Z" fill="#7a2a24" stroke="#2b2724" stroke-width="1.6"/>'
        + '<rect x="62" y="106" width="16" height="5" fill="#fffdf8"/>';
    },
    '幻恋型': function (c) {
      return '<path d="M34 56 Q70 18 106 56 Z" fill="' + c + '"/>'
        + '<circle cx="34" cy="56" r="5" fill="' + c + '"/><circle cx="106" cy="56" r="5" fill="' + c + '"/>'
        + FACE
        + '<path d="M44 86 q9 -9 18 0" fill="none" stroke="#2b2724" stroke-width="2.4" stroke-linecap="round"/>'
        + '<path d="M78 86 q9 -9 18 0" fill="none" stroke="#2b2724" stroke-width="2.4" stroke-linecap="round"/>'
        + '<ellipse cx="48" cy="97" rx="7" ry="4.5" fill="rgba(214,106,82,.35)"/>'
        + '<ellipse cx="92" cy="97" rx="7" ry="4.5" fill="rgba(214,106,82,.35)"/>'
        + NOSE
        + '<path d="M58 110 q12 8 24 0" fill="none" stroke="#b03028" stroke-width="3" stroke-linecap="round"/>'
        + '<path d="M112 34 c-6 -7 -13 -11 -13 -17 a6 6 0 0 1 13 -2 a6 6 0 0 1 13 2 c0 6 -7 10 -13 17 Z" fill="' + c + '"/>'
        + '<path d="M24 30 l2 6 l6 2 l-6 2 l-2 6 l-2 -6 l-6 -2 l6 -2 Z" fill="#c9b6e6"/>'
        + '<path d="M30 96 l1.6 4.4 l4.4 1.6 l-4.4 1.6 l-1.6 4.4 l-1.6 -4.4 l-4.4 -1.6 l4.4 -1.6 Z" fill="#c9b6e6"/>';
    },
    '守候型': function (c) {
      return '<path d="M34 56 Q70 22 106 56 Z" fill="' + c + '"/>'
        + '<circle cx="70" cy="26" r="4" fill="' + c + '"/>'
        + FACE
        + '<path d="M44 82 q9 -6 18 0" fill="none" stroke="#2b2724" stroke-width="2.4" stroke-linecap="round"/>'
        + '<path d="M78 82 q9 -6 18 0" fill="none" stroke="#2b2724" stroke-width="2.4" stroke-linecap="round"/>'
        + NOSE
        + '<path d="M58 112 q12 -5 24 0" fill="none" stroke="#7a5a3a" stroke-width="2.6" stroke-linecap="round"/>'
        + '<rect x="104" y="104" width="16" height="30" rx="3" fill="#f4ead0" stroke="#7a5a3a" stroke-width="1.6"/>'
        + '<path d="M112 92 q5 8 0 12 q-5 -4 0 -12" fill="#e2a33c"/>'
        + '<path d="M112 96 q3 5 0 8 q-3 -3 0 -8" fill="#fff2b0"/>';
    },
    '单向型': function (c) {
      return '<path d="M34 56 Q70 20 106 56 Z" fill="' + c + '"/>'
        + '<circle cx="106" cy="58" r="5" fill="' + c + '"/>'
        + FACE
        + '<path d="M42 80 q10 -7 20 -1" fill="none" stroke="#2b2724" stroke-width="2.6" stroke-linecap="round"/>'
        + '<circle cx="52" cy="88" r="4.6" fill="#2b2724"/>'
        + '<path d="M80 82 q8 -3 15 0" fill="none" stroke="#2b2724" stroke-width="2.6" stroke-linecap="round"/>'
        + NOSE
        + '<path d="M56 110 q16 8 30 -2" fill="none" stroke="#b03028" stroke-width="3" stroke-linecap="round"/>'
        + '<g stroke="' + c + '" stroke-width="3.4" stroke-linecap="round" fill="none">'
        + '<line x1="20" y1="132" x2="104" y2="132"/><path d="M96 126 l10 6 l-10 6"/></g>';
    }
  };

  // 未判定为小丑（或类型未知）时的中性形象
  function defaultBust(c) {
    return '<path d="M34 56 Q70 20 106 56 Z" fill="' + c + '"/>'
      + FACE
      + '<circle cx="52" cy="82" r="4.6" fill="#2b2724"/>'
      + '<circle cx="88" cy="82" r="4.6" fill="#2b2724"/>'
      + NOSE
      + '<path d="M56 108 q14 9 28 0" fill="none" stroke="#b03028" stroke-width="3" stroke-linecap="round"/>';
  }

  function bustMarkup(type) {
    var c = TYPE_COLOR[type] || '#a63c30';
    var fn = BUST[type] || defaultBust;
    return '<svg width="100%" height="100%" viewBox="0 0 140 158" preserveAspectRatio="xMidYMid meet" role="img" aria-label="小丑形象">'
      + fn(c) + '</svg>';
  }

  // ------------------------------------------------------------ 经典马戏团小丑（全身）
  function circusMarkup() {
    return '<svg width="100%" height="100%" viewBox="0 0 120 230" preserveAspectRatio="xMidYMid meet" role="img" aria-label="经典马戏团小丑">'
      + '<ellipse cx="60" cy="216" rx="42" ry="8" fill="rgba(35,33,32,.10)"/>'
      + '<circle cx="60" cy="10" r="6" fill="#e2c04a"/>'
      + '<path d="M60 14 L42 52 L78 52 Z" fill="#cf3b2a"/>'
      + '<rect x="38" y="50" width="44" height="7" rx="3.5" fill="#b03028"/>'
      + '<circle cx="30" cy="62" r="9" fill="#e2a33c"/>'
      + '<circle cx="90" cy="62" r="9" fill="#e2a33c"/>'
      + '<circle cx="60" cy="66" r="30" fill="#fffdf8" stroke="#232120" stroke-width="2.2"/>'
      + '<circle cx="48" cy="60" r="3.6" fill="#232120"/><circle cx="72" cy="60" r="3.6" fill="#232120"/>'
      + '<circle cx="49" cy="59" r="1.2" fill="#fff"/><circle cx="73" cy="59" r="1.2" fill="#fff"/>'
      + '<ellipse cx="42" cy="74" rx="6" ry="4" fill="rgba(214,106,82,.35)"/>'
      + '<ellipse cx="78" cy="74" rx="6" ry="4" fill="rgba(214,106,82,.35)"/>'
      + '<circle cx="60" cy="68" r="8" fill="#cf3b2a"/><circle cx="57" cy="65" r="2.6" fill="#ff9a80"/>'
      + '<path d="M42 78 Q60 98 78 78" fill="none" stroke="#b03028" stroke-width="3.4" stroke-linecap="round"/>'
      + '<path d="M40 96 q10 10 20 0 q10 10 20 0" fill="none" stroke="#e2c04a" stroke-width="4"/>'
      + '<path d="M60 96 l-12 -6 v12 Z" fill="#3a6ea5"/><path d="M60 96 l12 -6 v12 Z" fill="#3a6ea5"/>'
      + '<circle cx="60" cy="96" r="3.2" fill="#2b2724"/>'
      + '<path d="M40 100 h40 q8 30 6 62 h-52 q-2 -32 6 -62 Z" fill="#3a6ea5"/>'
      + '<circle cx="50" cy="120" r="3" fill="#fffdf8" opacity=".85"/>'
      + '<circle cx="70" cy="128" r="3" fill="#fffdf8" opacity=".85"/>'
      + '<circle cx="54" cy="142" r="3" fill="#fffdf8" opacity=".85"/>'
      + '<circle cx="72" cy="150" r="3" fill="#fffdf8" opacity=".85"/>'
      + '<circle cx="46" cy="156" r="3" fill="#fffdf8" opacity=".85"/>'
      + '<path d="M42 106 Q22 96 16 76" fill="none" stroke="#cf3b2a" stroke-width="9" stroke-linecap="round"/>'
      + '<circle cx="15" cy="72" r="7" fill="#fffdf8" stroke="#232120" stroke-width="1.6"/>'
      + '<path d="M78 106 Q96 124 96 146" fill="none" stroke="#cf3b2a" stroke-width="9" stroke-linecap="round"/>'
      + '<circle cx="96" cy="150" r="7" fill="#fffdf8" stroke="#232120" stroke-width="1.6"/>'
      + '<rect x="42" y="162" width="11" height="34" rx="5" fill="#cf3b2a"/>'
      + '<rect x="67" y="162" width="11" height="34" rx="5" fill="#cf3b2a"/>'
      + '<ellipse cx="46" cy="200" rx="15" ry="9" fill="#2b2724"/>'
      + '<ellipse cx="74" cy="200" rx="15" ry="9" fill="#2b2724"/>'
      + '</svg>';
  }

  // ------------------------------------------------------------ 弹跳层
  var state = { raf: null, running: false, clowns: [], bubbleTimer: null };

  function rand(min, max) { return min + Math.random() * (max - min); }

  function makeClown(type, size) {
    var el = document.createElement('div');
    el.className = 'clown';
    el.style.width = size + 'px';
    el.style.height = size + 'px';
    el.innerHTML = bustMarkup(type);
    return el;
  }

  function spawnBubble(layer) {
    var bubble = document.createElement('div');
    bubble.className = 'clown-bubble';
    bubble.textContent = BUBBLE_WORDS[Math.floor(Math.random() * BUBBLE_WORDS.length)];
    bubble.style.left = rand(8, 82) + 'vw';
    bubble.style.top = rand(12, 78) + 'vh';
    bubble.style.fontSize = rand(14, 22) + 'px';
    layer.appendChild(bubble);
    requestAnimationFrame(function () { bubble.classList.add('show'); });
    setTimeout(function () {
      bubble.classList.remove('show');
      setTimeout(function () { bubble.remove(); }, 600);
    }, 3600);
  }

  function tick(layer) {
    if (!state.running) return;
    var W = window.innerWidth;
    var H = window.innerHeight;
    state.clowns.forEach(function (c) {
      c.x += c.vx;
      c.y += c.vy;
      c.rot += c.vrot;
      if (c.x < -c.size * 0.3) { c.x = -c.size * 0.3; c.vx *= -1; }
      if (c.x > W - c.size * 0.7) { c.x = W - c.size * 0.7; c.vx *= -1; }
      if (c.y < -c.size * 0.3) { c.y = -c.size * 0.3; c.vy *= -1; }
      if (c.y > H - c.size * 0.7) { c.y = H - c.size * 0.7; c.vy *= -1; }
      if (Math.random() < 0.008) {
        c.vx = rand(-c.speed, c.speed);
        c.vy = rand(-c.speed, c.speed);
      }
      c.el.style.transform = 'translate(' + c.x + 'px,' + c.y + 'px) rotate(' + c.rot + 'deg)';
    });
    state.raf = requestAnimationFrame(function () { tick(layer); });
  }

  function countByLevel(level) {
    if (level === 'confirmed') return 18;
    if (level === 'high_risk') return 14;
    if (level === 'suspicious') return 11;
    if (level === 'mild') return 7;
    return 10;
  }

  function start(level, type) {
    stop(true);
    var layer = document.createElement('div');
    layer.id = LAYER_ID;
    document.body.appendChild(layer);

    var n = countByLevel(level);
    var W = window.innerWidth;
    var H = window.innerHeight;
    for (var i = 0; i < n; i++) {
      var size = rand(56, 104);
      var el = makeClown(type, size);
      var speed = rand(3.4, 7.2);
      layer.appendChild(el);
      state.clowns.push({
        el: el, size: size,
        x: rand(0, Math.max(0, W - size)),
        y: rand(0, Math.max(0, H - size)),
        vx: rand(-speed, speed) || speed,
        vy: rand(-speed, speed) || -speed,
        speed: speed,
        rot: rand(-14, 14),
        vrot: rand(-0.6, 0.6)
      });
    }

    state.running = true;
    state.raf = requestAnimationFrame(function () { tick(layer); });
    spawnBubble(layer);
    state.bubbleTimer = setInterval(function () { spawnBubble(layer); }, 2400);
    layer.classList.add('active');
  }

  function stop(silent) {
    state.running = false;
    if (state.raf) cancelAnimationFrame(state.raf);
    state.raf = null;
    if (state.bubbleTimer) clearInterval(state.bubbleTimer);
    state.bubbleTimer = null;
    state.clowns = [];
    var layer = document.getElementById(LAYER_ID);
    if (layer) {
      if (silent) { layer.remove(); }
      else {
        layer.classList.add('fade-out');
        setTimeout(function () { layer.remove(); }, 900);
      }
    }
  }

  window.Clown = {
    start: start,
    stop: stop,
    bust: bustMarkup,
    circus: circusMarkup,
    isRunning: function () { return state.running; }
  };
})();
