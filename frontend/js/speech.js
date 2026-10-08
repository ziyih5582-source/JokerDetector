/** AI 长文朗读：使用设备/浏览器语音，不调用项目的云端 API。 */
(function () {
  'use strict';

  var synth = window.speechSynthesis;
  var supported = !!(synth && typeof synth.speak === 'function' &&
    typeof window.SpeechSynthesisUtterance === 'function');
  var button, status, controls;
  var text = '', chunks = [], index = 0, generation = 0;
  var active = false, busy = false, currentUtterance = null;

  function readable(value) {
    return String(value || '')
      .replace(/```[\s\S]*?```/g, '')
      .replace(/!\[([^\]]*)\]\([^)]*\)/g, '$1')
      .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
      .replace(/^\s{0,3}(?:#{1,6}\s+|>\s*|[-*+]\s+|\d+[.)、]\s*)/gm, '')
      .replace(/[*`]/g, '')
      .replace(/\s+/g, ' ').trim();
  }

  // 按句子优先切短段，避免一次提交上千字在部分设备上被截断。
  function splitText(value) {
    var chars = Array.from(value), result = [];
    while (chars.length) {
      var end = Math.min(180, chars.length);
      if (end < chars.length) {
        for (var i = end - 1; i >= 80; i--) {
          if (/[。！？!?；;，,：:]/.test(chars[i])) { end = i + 1; break; }
        }
      }
      result.push(chars.splice(0, end).join(''));
    }
    return result;
  }

  function sync(nextBusy) {
    if (typeof nextBusy === 'boolean') busy = nextBusy;
    if (!button) return;
    controls.hidden = !text;
    button.disabled = !supported || !text || busy;
    button.textContent = active ? '停止朗读' : '播放朗读';
    button.setAttribute('aria-pressed', String(active));
  }

  function stop(message) {
    // cancel() 可能延后触发旧 utterance 的事件，先让那些回调失效。
    generation += 1;
    var wasActive = active;
    active = false;
    currentUtterance = null;
    chunks = [];
    index = 0;
    if (supported && wasActive) synth.cancel();
    if (status && wasActive) status.textContent = message || '已停止，再次播放将从头开始。';
    sync();
  }

  function setText(value) {
    stop();
    text = readable(value);
    if (status) status.textContent = supported
      ? '使用设备或浏览器语音，音色因设备而异；部分语音可能需要联网。'
      : '当前浏览器不支持语音朗读，请换用支持此功能的浏览器。';
    sync();
  }

  function chineseVoice() {
    var voices = synth.getVoices ? synth.getVoices() : [];
    var chinese = voices.filter(function (voice) { return /^zh(?:[-_]|$)/i.test(voice.lang); });
    chinese.sort(function (a, b) {
      function rank(v) {
        return (v.localService ? 10 : 0) + (/^zh[-_](CN|Hans)(?:[-_]|$)/i.test(v.lang) ? 2 : 0);
      }
      return rank(b) - rank(a);
    });
    return chinese[0] || null;
  }

  function speakNext(token, voice) {
    if (!active || token !== generation) return;
    if (index >= chunks.length) {
      active = false;
      currentUtterance = null;
      status.textContent = '朗读完毕。';
      sync();
      return;
    }
    var utterance = new window.SpeechSynthesisUtterance(chunks[index]);
    currentUtterance = utterance; // 持有引用，避免长文播放时被垃圾回收。
    utterance.lang = voice ? voice.lang : 'zh-CN';
    if (voice) utterance.voice = voice;
    utterance.rate = 1;
    utterance.onstart = function () {
      if (token !== generation || !active) return;
      status.textContent = '正在朗读（' + (index + 1) + '/' + chunks.length + ' 段）…';
    };
    utterance.onend = function () {
      if (token !== generation || !active || currentUtterance !== utterance) return;
      index += 1;
      speakNext(token, voice);
    };
    utterance.onerror = function () {
      if (token !== generation || !active) return;
      stop('暂时无法朗读，请检查设备的中文语音或换个浏览器后重试。');
    };
    try {
      synth.speak(utterance);
    } catch (error) {
      stop('暂时无法朗读，请检查设备的中文语音或换个浏览器后重试。');
    }
  }

  function play() {
    if (!supported || !text || busy || !button) return;
    stop();
    chunks = splitText(text);
    index = 0;
    active = true;
    status.textContent = '正在启动朗读…';
    sync();
    try {
      synth.cancel();
      // 一些浏览器在之前的语音被暂停后仍保留 paused 状态。
      if (synth.paused && synth.resume) synth.resume();
      var music = document.getElementById('music-audio');
      if (music && !music.paused) music.pause();
      speakNext(generation, chineseVoice());
    } catch (error) {
      stop('暂时无法朗读，请检查设备的中文语音或换个浏览器后重试。');
    }
  }

  function init() {
    button = document.getElementById('guidance-speech-toggle');
    status = document.getElementById('guidance-speech-status');
    controls = document.getElementById('guidance-speech');
    if (!button || !status || !controls) { button = null; return; }
    button.addEventListener('click', function () { if (active) stop(); else play(); });
    window.addEventListener('pagehide', function () { stop(); });
    document.addEventListener('visibilitychange', function () { if (document.hidden) stop(); });
    setText(text);
  }

  window.AnalysisSpeech = { setText: setText, stop: stop, sync: sync };
  document.addEventListener('DOMContentLoaded', init);
})();
