/**
 * 观心潭 · 水墨鱼塘
 *
 * 观感目标：宣纸底、墨韵浮动、鱼是「水墨画出来的」——
 * 不画清晰轮廓线，用低透明度叠加笔触 + 一次阴影扩散做出软边，
 * 再用水面墨雾盖在鱼身上，让鱼时隐时现、水不透彻。
 *
 * 性能约定（重要）：满屏 canvas 每一帧都很贵，所以
 *   1. 静态底纹（宣纸 + 深墨 + 纸纹）只画一次，缓存成 washLayer；
 *   2. 墨雾用预渲染的小图 drawImage 缩放，不再每帧新建径向渐变；
 *   3. 不使用 ctx.filter（离屏高斯模糊极慢），柔边只靠 shadowBlur 与叠色。
 *
 * 交互：点击任意纸面投食，附近的鱼会摆尾游过来吃掉。
 */
(function () {
  'use strict';

  var INK = '38,36,34';          // 主墨色（浓淡由 alpha 控制）
  var VERMILION = '148,58,46';   // 朱砂（少量红鱼与暖调墨雾）
  var PAPER = '244,240,230';     // 宣纸色

  var canvas, ctx, dpr = 1;
  var W = 0, H = 0;
  var washLayer = null;          // 静态底纹
  var moteSprites = [];          // 预渲染的墨雾小图
  var fish = [], foods = [], ripples = [], motes = [];
  var lastTime = 0, running = false, frameId = 0, paused = false, reduced = false;
  var fps = 0, fpsAcc = 0, fpsCount = 0, mistGradient = null;

  function rand(a, b) { return a + Math.random() * (b - a); }
  function clamp(v, a, b) { return v < a ? a : (v > b ? b : v); }

  function angleLerp(from, to, t) {
    var diff = ((to - from + Math.PI) % (Math.PI * 2)) - Math.PI;
    if (diff < -Math.PI) diff += Math.PI * 2;
    return from + diff * t;
  }

  // ---------------------------------------------------------------- 底纹

  function buildWash() {
    washLayer = document.createElement('canvas');
    washLayer.width = Math.max(1, Math.floor(W * dpr));
    washLayer.height = Math.max(1, Math.floor(H * dpr));
    var c = washLayer.getContext('2d');
    c.scale(dpr, dpr);

    c.fillStyle = 'rgba(' + PAPER + ',1)';
    c.fillRect(0, 0, W, H);

    // 几处极淡的暖色晕染，避免纸面过于均匀
    var tints = ['246,242,232', '242,236,224', '239,235,228', '247,244,236'];
    for (var t = 0; t < 4; t++) {
      var g = c.createRadialGradient(rand(0, W), rand(0, H), 0, rand(0, W), rand(0, H), Math.max(W, H) * rand(0.4, 0.8));
      g.addColorStop(0, 'rgba(' + tints[t] + ',0.85)');
      g.addColorStop(1, 'rgba(' + tints[t] + ',0)');
      c.fillStyle = g;
      c.fillRect(0, 0, W, H);
    }

    // 深层墨韵：水不清澈的底子
    c.save();
    c.globalCompositeOperation = 'multiply';
    for (var i = 0; i < 18; i++) {
      var x = rand(-0.1, 1.1) * W, y = rand(-0.1, 1.1) * H;
      var r = Math.max(W, H) * rand(0.10, 0.34);
      var g2 = c.createRadialGradient(x, y, r * 0.1, x, y, r);
      var a = rand(0.03, 0.075);
      g2.addColorStop(0, 'rgba(' + INK + ',' + a.toFixed(3) + ')');
      g2.addColorStop(0.55, 'rgba(' + INK + ',' + (a * 0.5).toFixed(3) + ')');
      g2.addColorStop(1, 'rgba(' + INK + ',0)');
      c.fillStyle = g2;
      c.beginPath();
      c.arc(x, y, r, 0, Math.PI * 2);
      c.fill();
    }
    c.restore();

    // 纸纹：细纤维与噪点
    c.save();
    for (var n = 0; n < Math.floor(W * H / 900); n++) {
      c.fillStyle = 'rgba(' + INK + ',' + rand(0.008, 0.03).toFixed(3) + ')';
      c.fillRect(Math.random() * W, Math.random() * H, rand(0.6, 1.8), rand(0.4, 1.0));
    }
    c.strokeStyle = 'rgba(' + INK + ',0.025)';
    c.lineWidth = 0.6;
    for (var f = 0; f < 40; f++) {
      var fy = Math.random() * H;
      c.beginPath();
      c.moveTo(rand(-40, W * 0.4), fy);
      c.lineTo(rand(W * 0.6, W + 40), fy + rand(-3, 3));
      c.stroke();
    }
    c.restore();

    // 水面淡纹：极淡的长弧，给「水」一点质感
    c.save();
    c.globalCompositeOperation = 'multiply';
    c.lineCap = 'round';
    for (var b = 0; b < 26; b++) {
      var by2 = rand(0, H);
      var bx2 = rand(-W * 0.1, W * 0.7);
      var bw = rand(W * 0.15, W * 0.5);
      c.beginPath();
      c.moveTo(bx2, by2);
      c.quadraticCurveTo(bx2 + bw * 0.5, by2 + rand(-14, 14), bx2 + bw, by2 + rand(-6, 6));
      c.strokeStyle = 'rgba(' + INK + ',' + rand(0.015, 0.042).toFixed(3) + ')';
      c.lineWidth = rand(1, 5);
      c.stroke();
    }
    c.restore();

    // 暗角：四周沉下去，中间留白，水看起来才有深度
    var vig = c.createRadialGradient(W * 0.5, H * 0.48, Math.min(W, H) * 0.16, W * 0.5, H * 0.5, Math.max(W, H) * 0.78);
    vig.addColorStop(0, 'rgba(' + PAPER + ',0)');
    vig.addColorStop(0.6, 'rgba(' + INK + ',0.035)');
    vig.addColorStop(1, 'rgba(' + INK + ',0.10)');
    c.fillStyle = vig;
    c.fillRect(0, 0, W, H);

    // 远处的水光：上下略亮
    var top = c.createLinearGradient(0, 0, 0, H);
    top.addColorStop(0, 'rgba(' + PAPER + ',0.60)');
    top.addColorStop(0.55, 'rgba(' + PAPER + ',0.04)');
    top.addColorStop(1, 'rgba(' + PAPER + ',0.22)');
    c.fillStyle = top;
    c.fillRect(0, 0, W, H);
  }

  // ---------------------------------------------------------------- 墨雾（预渲染小图）

  function buildMoteSprites() {
    moteSprites = [];
    for (var i = 0; i < 5; i++) {
      var size = 256;
      var cv = document.createElement('canvas');
      cv.width = cv.height = size;
      var c = cv.getContext('2d');
      var warm = (i === 4);
      var col = warm ? VERMILION : INK;
      var g = c.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
      g.addColorStop(0, 'rgba(' + col + ',' + (warm ? 0.16 : 0.26) + ')');
      g.addColorStop(0.45, 'rgba(' + col + ',' + (warm ? 0.10 : 0.15) + ')');
      g.addColorStop(1, 'rgba(' + col + ',0)');
      c.fillStyle = g;
      c.fillRect(0, 0, size, size);
      moteSprites.push(cv);
    }
  }

  function makeMotes() {
    motes = [];
    var count = Math.round(clamp(W * H / 330000, 5, 12));
    for (var i = 0; i < count; i++) {
      motes.push({
        x: rand(0, W), y: rand(0, H),
        r: rand(0.20, 0.44) * Math.max(W, H),
        a: rand(0.35, 0.95),
        vx: rand(-6, 6), vy: rand(-3, 3),
        phase: rand(0, Math.PI * 2),
        speed: rand(0.05, 0.13),
        sprite: moteSprites[i % moteSprites.length]
      });
    }
  }

  function drawMotes(dt, time, factor) {
    ctx.save();
    ctx.globalCompositeOperation = 'multiply';
    for (var i = 0; i < motes.length; i++) {
      var m = motes[i];
      m.x += m.vx * dt; m.y += m.vy * dt;
      if (m.x < -m.r) m.x = W + m.r;
      if (m.x > W + m.r) m.x = -m.r;
      if (m.y < -m.r) m.y = H + m.r;
      if (m.y > H + m.r) m.y = -m.r;
      var breathe = 0.7 + 0.3 * Math.sin(time * m.speed + m.phase);
      var cx = m.x + Math.sin(time * 0.06 + m.phase) * 26;
      var cy = m.y + Math.cos(time * 0.05 + m.phase) * 18;
      ctx.globalAlpha = clamp(m.a * breathe * factor, 0, 1);
      ctx.drawImage(m.sprite, cx - m.r, cy - m.r, m.r * 2, m.r * 2);
    }
    ctx.restore();
  }

  // ---------------------------------------------------------------- 鱼

  function createFish() {
    var red = Math.random() < 0.18;
    var depth = Math.random();
    return {
      size: rand(30, 76) * (0.62 + depth * 0.75),
      x: rand(W * 0.12, W * 0.88),
      y: rand(H * 0.14, H * 0.88),
      heading: rand(0, Math.PI * 2),
      cruise: rand(16, 34) * (0.75 + depth * 0.5),
      depth: depth,
      // 每条鱼墨色不同：有浓有淡，才有远近虚实
      ink: red ? VERMILION : INK,
      alpha: (red ? rand(0.13, 0.21) : rand(0.20, 0.46)) * (0.62 + depth * 0.58),
      phase: rand(0, Math.PI * 2),
      phaseSpeed: rand(2.2, 3.6),
      wander: rand(0, Math.PI * 2),
      wanderSpeed: rand(0.25, 0.6),
      full: 0,
      turnBias: rand(-1, 1) > 0 ? 1 : -1
    };
  }

  function spawnFish() {
    var count = Math.round(clamp(W * H / 165000, 5, 10));
    fish = [];
    for (var i = 0; i < count; i++) {
      var f = createFish();
      f.speed = f.cruise;
      fish.push(f);
    }
  }

  function steer(dt) {
    var margin = Math.min(W, H) * 0.12;
    var i, j, k;
    for (i = 0; i < fish.length; i++) {
      var f = fish[i];
      f.wander += f.wanderSpeed * dt;
      var desired = f.heading + Math.sin(f.wander) * 0.9;
      var targetSpeed = f.cruise;

      // 最近的食
      var best = null, bestD = 1e9;
      for (k = 0; k < foods.length; k++) {
        var d = Math.hypot(foods[k].x - f.x, foods[k].y - f.y);
        if (d < bestD) { bestD = d; best = foods[k]; }
      }
      if (best && bestD < 560) {
        var urgency = clamp(1 - bestD / 560, 0, 1);
        desired = Math.atan2(best.y - f.y, best.x - f.x);
        targetSpeed = f.cruise * (1 + urgency * 1.5);
        if (bestD < 46) targetSpeed = f.cruise * 0.35;   // 靠近时收势，像在啄食
      }

      // 避让：太挤就散开，避免叠在一起
      for (j = 0; j < fish.length; j++) {
        if (j === i) continue;
        var o = fish[j];
        var dd = Math.hypot(o.x - f.x, o.y - f.y);
        var minD = (f.size + o.size) * 0.85;
        if (dd < minD && dd > 0.01) {
          desired = angleLerp(desired, Math.atan2(f.y - o.y, f.x - o.x), clamp(1 - dd / minD, 0, 1) * 0.7);
        }
      }

      // 边界：柔和回身
      var ax = 0, ay = 0;
      if (f.x < margin) ax += 1;
      if (f.x > W - margin) ax -= 1;
      if (f.y < margin) ay += 1;
      if (f.y > H - margin) ay -= 1;
      if (ax || ay) desired = angleLerp(desired, Math.atan2(ay - 0.001, ax), 0.5);

      if (f.full > 0) {
        f.full -= dt;
        targetSpeed *= 0.55;
        desired += f.turnBias * 0.5;
      }

      f.heading = angleLerp(f.heading, desired, clamp(dt * ((ax || ay) ? 2.4 : 2.0), 0, 1));
      f.speed += (targetSpeed - f.speed) * clamp(dt * 2.2, 0, 1);
      f.x = clamp(f.x + Math.cos(f.heading) * f.speed * dt, -20, W + 20);
      f.y = clamp(f.y + Math.sin(f.heading) * f.speed * dt, -20, H + 20);
      f.phase += f.phaseSpeed * dt * (0.6 + f.speed / Math.max(1, f.cruise));

      // 吃食
      for (var m = foods.length - 1; m >= 0; m--) {
        var fd = foods[m];
        if (Math.hypot(fd.x - f.x, fd.y - f.y) < f.size * 0.45 + 8) {
          foods.splice(m, 1);
          f.full = rand(0.9, 2.0);
          addRipple(fd.x, fd.y, f.size * 0.7);
        }
      }
    }
  }

  /**
   * 画一条鱼。柔边只靠两件事：一次 shadowBlur 外晕 + 鳍部多铺一层淡墨。
   * 不做高斯模糊——形体必须认得出来，朦胧交给盖在上面的墨雾。
   */
  function drawFish(f) {
    var L = f.size * 2.0;
    var half = f.size * 0.40;
    var segs = 14;
    var amp = L * 0.055 * (0.6 + f.speed / Math.max(1, f.cruise) * 0.5);
    var cos = Math.cos(f.heading), sin = Math.sin(f.heading);
    var alpha = clamp(f.alpha, 0.06, 0.62);
    var i, t, tx, ty, tl, nx, ny, w;

    // 脊线（含摆动）
    var spine = [];
    for (i = 0; i <= segs; i++) {
      t = i / segs;
      var along = L * (t - 0.30);
      var sway = Math.sin(f.phase - t * 3.0) * amp * (0.25 + t * 1.05);
      spine.push({ x: f.x + cos * along - sin * sway, y: f.y + sin * along + cos * sway });
    }

    // 体宽：尾柄细 → 腹部最宽 → 吻端收尖
    function width(tt) {
      var base = Math.sin(Math.PI * Math.pow(clamp(tt, 0, 1), 0.6));
      return half * (0.12 + 0.88 * Math.pow(base, 0.9)) * (1 - 0.25 * tt);
    }

    function bodyPath() {
      var k, tt, pp, dx, dy, dl, mx, my, ww;
      ctx.beginPath();
      for (k = 0; k <= segs; k++) {
        tt = k / segs; pp = spine[k];
        dx = spine[Math.min(k + 1, segs)].x - spine[Math.max(k - 1, 0)].x;
        dy = spine[Math.min(k + 1, segs)].y - spine[Math.max(k - 1, 0)].y;
        dl = Math.hypot(dx, dy) || 1;
        mx = -dy / dl; my = dx / dl; ww = width(tt);
        if (k === 0) ctx.moveTo(pp.x + mx * ww, pp.y + my * ww);
        else ctx.lineTo(pp.x + mx * ww, pp.y + my * ww);
      }
      for (k = segs; k >= 0; k--) {
        tt = k / segs; pp = spine[k];
        dx = spine[Math.min(k + 1, segs)].x - spine[Math.max(k - 1, 0)].x;
        dy = spine[Math.min(k + 1, segs)].y - spine[Math.max(k - 1, 0)].y;
        dl = Math.hypot(dx, dy) || 1;
        mx = -dy / dl; my = dx / dl; ww = width(tt);
        ctx.lineTo(pp.x - mx * ww, pp.y - my * ww);
      }
      ctx.closePath();
    }

    // 尾鳍几何
    var tailBase = spine[1], tailTip = spine[0];
    var bx = tailTip.x - tailBase.x, by = tailTip.y - tailBase.y;
    var bl = Math.hypot(bx, by) || 1;
    var ux = bx / bl, uy = by / bl;                 // 向后
    var px = -uy, py = ux;                          // 侧向
    var tailLen = f.size * 0.88;
    var spread = f.size * (0.46 + Math.abs(Math.sin(f.phase)) * 0.12);
    function tp(back, side) {
      return {
        x: tailBase.x + ux * tailLen * back + px * spread * side,
        y: tailBase.y + uy * tailLen * back + py * spread * side
      };
    }
    var notch = tp(0.46, 0), up = tp(0.98, 1), down = tp(0.98, -1);

    function tailPath(scale) {
      var a1 = tp(0.30, 0.85 * scale), a2 = tp(0.62, 0.42 * scale);
      var a3 = tp(0.30, -0.85 * scale), a4 = tp(0.62, -0.42 * scale);
      ctx.beginPath();
      ctx.moveTo(tailBase.x, tailBase.y);
      ctx.quadraticCurveTo(a1.x, a1.y, up.x, up.y);
      ctx.quadraticCurveTo(a2.x, a2.y, notch.x, notch.y);
      ctx.quadraticCurveTo(a4.x, a4.y, down.x, down.y);
      ctx.quadraticCurveTo(a3.x, a3.y, tailBase.x, tailBase.y);
      ctx.closePath();
    }

    ctx.save();
    ctx.globalCompositeOperation = 'multiply';

    // 1) 外晕：边界化开
    ctx.save();
    ctx.shadowColor = 'rgba(' + f.ink + ',' + (alpha * 0.55).toFixed(3) + ')';
    ctx.shadowBlur = f.size * 0.50;
    ctx.fillStyle = 'rgba(' + f.ink + ',' + (alpha * 0.42).toFixed(3) + ')';
    bodyPath();
    ctx.fill();
    ctx.restore();

    // 2) 身体实心：形体读得出来
    ctx.fillStyle = 'rgba(' + f.ink + ',' + (alpha * 0.38).toFixed(3) + ')';
    bodyPath();
    ctx.fill();

    // 2b) 顺着脊背再压一层窄而浓的墨芯：墨会往中间聚，不是均匀一块
    ctx.save();
    ctx.translate(f.x, f.y);
    ctx.scale(1, 0.55);
    ctx.translate(-f.x, -f.y);
    ctx.fillStyle = 'rgba(' + f.ink + ',' + (alpha * 0.28).toFixed(3) + ')';
    bodyPath();
    ctx.fill();
    ctx.restore();

    // 3) 尾鳍：先铺一层更淡更大的墨，再画分叉
    tailPath(1.22);
    ctx.fillStyle = 'rgba(' + f.ink + ',' + (alpha * 0.16).toFixed(3) + ')';
    ctx.fill();
    tailPath(1);
    ctx.fillStyle = 'rgba(' + f.ink + ',' + (alpha * 0.38).toFixed(3) + ')';
    ctx.fill();

    // 4) 背鳍与胸鳍
    var mid = spine[Math.floor(segs * 0.55)];
    var dorsal = spine[Math.floor(segs * 0.78)];
    ctx.beginPath();
    ctx.moveTo(mid.x, mid.y);
    ctx.quadraticCurveTo(
      mid.x - sin * f.size * 0.36 + cos * f.size * 0.10,
      mid.y + cos * f.size * 0.36 + sin * f.size * 0.10,
      dorsal.x - sin * f.size * 0.06, dorsal.y + cos * f.size * 0.06);
    ctx.closePath();
    ctx.fillStyle = 'rgba(' + f.ink + ',' + (alpha * 0.30).toFixed(3) + ')';
    ctx.fill();
    ctx.beginPath();
    ctx.moveTo(dorsal.x, dorsal.y);
    ctx.quadraticCurveTo(
      dorsal.x + sin * f.size * 0.28 + cos * f.size * 0.12,
      dorsal.y - cos * f.size * 0.28 + sin * f.size * 0.12,
      dorsal.x + cos * f.size * 0.14 + sin * f.size * 0.05,
      dorsal.y + sin * f.size * 0.14 - cos * f.size * 0.05);
    ctx.closePath();
    ctx.fill();

    // 5) 脊上两笔浓墨：浓淡不均才有运笔感
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    for (var s = 0; s < 2; s++) {
      var i0 = Math.floor((0.30 + s * 0.30) * segs);
      ctx.beginPath();
      ctx.moveTo(spine[i0].x, spine[i0].y);
      for (var q = i0 + 1; q <= Math.min(i0 + 4, segs); q++) ctx.lineTo(spine[q].x, spine[q].y);
      ctx.strokeStyle = 'rgba(' + f.ink + ',' + (alpha * (0.24 - s * 0.08)).toFixed(3) + ')';
      ctx.lineWidth = f.size * (0.13 - s * 0.04);
      ctx.stroke();
    }

    // 6) 眼中一点浓墨
    var head = spine[segs - 1];
    ctx.beginPath();
    ctx.arc(head.x - sin * f.size * 0.13, head.y + cos * f.size * 0.13, Math.max(0.9, f.size * 0.045), 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(' + f.ink + ',' + clamp(alpha * 1.6, 0, 0.7).toFixed(3) + ')';
    ctx.fill();

    ctx.restore();
  }

  // ---------------------------------------------------------------- 食与涟漪

  function addRipple(x, y, r) {
    ripples.push({ x: x, y: y, r: r || 2, max: rand(40, 96), a: 0.22, speed: rand(26, 50), seed: rand(0, Math.PI * 2) });
    if (ripples.length > 40) ripples.shift();
  }

  function feed(x, y) {
    foods.push({
      x: x, y: y,
      vx: rand(-3, 3), vy: rand(3, 10),
      r: rand(1.6, 3.0),
      life: 1,
      fade: rand(0.035, 0.06)
    });
    addRipple(x, y, 3);
    if (foods.length > 60) foods.shift();
  }

  function drawFoods(dt) {
    ctx.save();
    ctx.globalCompositeOperation = 'multiply';
    for (var i = foods.length - 1; i >= 0; i--) {
      var f = foods[i];
      f.x += f.vx * dt;
      f.y += f.vy * dt;
      f.vy *= 0.995; f.vx *= 0.99;
      f.life -= f.fade * dt * 12;
      if (f.life <= 0) { foods.splice(i, 1); continue; }
      var rr = f.r * 5;
      var g = ctx.createRadialGradient(f.x, f.y, 0, f.x, f.y, rr);
      g.addColorStop(0, 'rgba(' + INK + ',' + (0.42 * f.life).toFixed(3) + ')');
      g.addColorStop(1, 'rgba(' + INK + ',0)');
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.arc(f.x, f.y, rr, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = 'rgba(' + INK + ',' + (0.5 * f.life).toFixed(3) + ')';
      ctx.beginPath();
      ctx.arc(f.x, f.y, f.r, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
  }

  function drawRipples(dt) {
    ctx.save();
    ctx.globalCompositeOperation = 'multiply';
    ctx.lineCap = 'round';
    for (var i = ripples.length - 1; i >= 0; i--) {
      var rp = ripples[i];
      rp.r += rp.speed * dt;
      rp.a -= dt * 0.13;
      if (rp.a <= 0 || rp.r > rp.max) { ripples.splice(i, 1); continue; }
      // 一段不闭合的弧：手绘感，不像几何圆
      ctx.beginPath();
      ctx.arc(rp.x, rp.y, rp.r, rp.seed, rp.seed + Math.PI * 1.45);
      ctx.strokeStyle = 'rgba(' + INK + ',' + (rp.a * 0.55).toFixed(3) + ')';
      ctx.lineWidth = 0.8;
      ctx.stroke();
      if (rp.r > 14) {
        ctx.beginPath();
        ctx.arc(rp.x, rp.y, rp.r * 0.58, rp.seed + 0.9, rp.seed + 0.9 + Math.PI * 1.15);
        ctx.strokeStyle = 'rgba(' + INK + ',' + (rp.a * 0.3).toFixed(3) + ')';
        ctx.lineWidth = 0.7;
        ctx.stroke();
      }
    }
    ctx.restore();
  }

  // ---------------------------------------------------------------- 主循环

  function resize() {
    // 上限 1.5：满屏 canvas 上更高的像素比只会拖慢帧率
    dpr = Math.min(window.devicePixelRatio || 1, 1.5);
    W = canvas.clientWidth || window.innerWidth;
    H = canvas.clientHeight || window.innerHeight;
    canvas.width = Math.floor(W * dpr);
    canvas.height = Math.floor(H * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    mistGradient = null;
    buildWash();
    makeMotes();
    spawnFish();
  }

  function frame(now) {
    frameId = requestAnimationFrame(frame);
    var dt = Math.min((now - lastTime) / 1000 || 0, 0.05);
    lastTime = now;
    var time = now / 1000;

    fpsAcc += dt; fpsCount++;
    if (fpsAcc >= 1) { fps = fpsCount / fpsAcc; fpsAcc = 0; fpsCount = 0; }

    ctx.clearRect(0, 0, W, H);
    if (washLayer) ctx.drawImage(washLayer, 0, 0, W, H);

    drawMotes(dt * 0.5, time, 0.6);          // 鱼身后

    steer(dt);
    drawFoods(dt);
    var order = fish.slice().sort(function (a, b) { return a.depth - b.depth; });
    for (var i = 0; i < order.length; i++) drawFish(order[i]);

    drawMotes(dt, time + 12, 1.35);          // 鱼身前：浑水让鱼时隐时现
    drawRipples(dt);

    // 顶层水汽：压低对比度，制造朦胧
    if (!mistGradient) {
      mistGradient = ctx.createLinearGradient(0, 0, 0, H);
      mistGradient.addColorStop(0, 'rgba(' + PAPER + ',0.26)');
      mistGradient.addColorStop(0.45, 'rgba(' + PAPER + ',0.09)');
      mistGradient.addColorStop(1, 'rgba(' + PAPER + ',0.20)');
    }
    ctx.fillStyle = mistGradient;
    ctx.fillRect(0, 0, W, H);
  }

  function start() {
    if (running) return;
    running = true;
    lastTime = performance.now();
    frameId = requestAnimationFrame(frame);
  }

  function stop() {
    running = false;
    cancelAnimationFrame(frameId);
  }

  window.Pond = {
    init: function (el) {
      canvas = el;
      ctx = canvas.getContext('2d');
      reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      buildMoteSprites();
      resize();
      var t = null;
      window.addEventListener('resize', function () {
        clearTimeout(t);
        t = setTimeout(resize, 180);
      });
      document.addEventListener('visibilitychange', function () {
        if (document.hidden) stop(); else if (!paused) start();
      });
      start();
    },
    feed: feed,
    ripple: addRipple,
    isRunning: function () { return running; },
    /** 静水：停住动画，画面留在最后一帧。 */
    setPaused: function (value) {
      paused = !!value;
      if (paused) stop(); else start();
      return paused;
    },
    isPaused: function () { return paused; },
    prefersReducedMotion: function () { return reduced; },
    stats: function () {
      return { fps: Math.round(fps), fish: fish.length, foods: foods.length, dpr: dpr, w: W, h: H };
    }
  };
})();
