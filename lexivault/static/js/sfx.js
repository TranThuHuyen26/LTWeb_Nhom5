/**
 * LexiVault Sound Engine
 * Pure Web Audio API - no external files needed
 */
const SFX = (() => {
  let ctx = null;
  let enabled = localStorage.getItem('lv_sfx') !== 'off';

  function getCtx() {
    if (!ctx) ctx = new (window.AudioContext || window.webkitAudioContext)();
    if (ctx.state === 'suspended') ctx.resume();
    return ctx;
  }

  function tone(freq, type, dur, vol = 0.3, delay = 0) {
    if (!enabled) return;
    try {
      const c = getCtx();
      const osc = c.createOscillator();
      const gain = c.createGain();
      osc.connect(gain);
      gain.connect(c.destination);
      osc.type = type;
      osc.frequency.setValueAtTime(freq, c.currentTime + delay);
      gain.gain.setValueAtTime(0, c.currentTime + delay);
      gain.gain.linearRampToValueAtTime(vol, c.currentTime + delay + 0.01);
      gain.gain.exponentialRampToValueAtTime(0.001, c.currentTime + delay + dur);
      osc.start(c.currentTime + delay);
      osc.stop(c.currentTime + delay + dur + 0.05);
    } catch(e) {}
  }

  function noise(dur, vol = 0.1, delay = 0) {
    if (!enabled) return;
    try {
      const c = getCtx();
      const bufSize = c.sampleRate * dur;
      const buf = c.createBuffer(1, bufSize, c.sampleRate);
      const data = buf.getChannelData(0);
      for (let i = 0; i < bufSize; i++) data[i] = Math.random() * 2 - 1;
      const src = c.createBufferSource();
      src.buffer = buf;
      const gain = c.createGain();
      gain.gain.setValueAtTime(vol, c.currentTime + delay);
      gain.gain.exponentialRampToValueAtTime(0.001, c.currentTime + delay + dur);
      src.connect(gain);
      gain.connect(c.destination);
      src.start(c.currentTime + delay);
    } catch(e) {}
  }

  const sounds = {
    // ✅ Correct answer — happy ascending arpeggio
    correct() {
      tone(523.25, 'sine', 0.12, 0.25, 0.00); // C5
      tone(659.25, 'sine', 0.12, 0.25, 0.08); // E5
      tone(783.99, 'sine', 0.15, 0.28, 0.16); // G5
      tone(1046.5, 'sine', 0.18, 0.22, 0.24); // C6
    },

    // ❌ Wrong answer — sad descending
    wrong() {
      tone(311.13, 'sawtooth', 0.10, 0.18, 0.00); // Eb4
      tone(261.63, 'sawtooth', 0.12, 0.20, 0.10); // C4
      tone(220.00, 'sawtooth', 0.20, 0.22, 0.20); // A3
    },

    // 🎉 Perfect / Level complete — fanfare
    perfect() {
      tone(523.25, 'sine', 0.10, 0.22, 0.00);
      tone(659.25, 'sine', 0.10, 0.22, 0.07);
      tone(783.99, 'sine', 0.10, 0.22, 0.14);
      tone(1046.5, 'sine', 0.22, 0.28, 0.21);
      tone(1318.5, 'sine', 0.30, 0.32, 0.32); // E6 high note
    },

    // 🃏 Card flip
    flip() {
      tone(880, 'sine', 0.06, 0.12, 0.00);
      tone(1100, 'sine', 0.05, 0.10, 0.04);
    },

    // ⏰ Tick (Word Bomb timer)
    tick() {
      tone(1200, 'square', 0.04, 0.08);
    },

    // 💣 Explosion (Word Bomb game over)
    explode() {
      noise(0.6, 0.35, 0.00);
      tone(80,  'sawtooth', 0.40, 0.30, 0.00);
      tone(60,  'sawtooth', 0.30, 0.20, 0.10);
      tone(40,  'sawtooth', 0.20, 0.15, 0.20);
    },

    // 🎯 Daily challenge correct
    daily() {
      tone(523.25, 'sine', 0.10, 0.20, 0.00);
      tone(659.25, 'sine', 0.10, 0.20, 0.06);
      tone(783.99, 'sine', 0.10, 0.20, 0.12);
      tone(1046.5, 'sine', 0.12, 0.25, 0.18);
      tone(1318.5, 'triangle', 0.40, 0.30, 0.28);
    },

    // 🏆 Achievement unlocked
    achievement() {
      tone(659.25, 'sine', 0.12, 0.18, 0.00);
      tone(880.00, 'sine', 0.12, 0.20, 0.10);
      tone(1046.5, 'sine', 0.12, 0.22, 0.20);
      tone(1318.5, 'sine', 0.25, 0.30, 0.30);
      tone(1567.0, 'sine', 0.35, 0.28, 0.42); // G6
    },

    // 🔀 Letter pick (Scramble)
    pick() {
      tone(660, 'sine', 0.05, 0.15);
    },

    // ✨ Streak milestone
    streak() {
      [523, 587, 659, 698, 783, 880, 988].forEach((f, i) => {
        tone(f, 'sine', 0.10, 0.18, i * 0.06);
      });
    },

    // 🖱️ Button click (subtle)
    click() {
      tone(440, 'sine', 0.04, 0.08);
    },

    // ⏩ Speed match: MATCH
    match() {
      tone(700, 'sine', 0.08, 0.18, 0.00);
      tone(900, 'sine', 0.08, 0.20, 0.06);
    },

    // ✗ Speed match: NO MATCH wrong
    noMatch() {
      tone(350, 'sawtooth', 0.10, 0.16, 0.00);
      tone(280, 'sawtooth', 0.12, 0.18, 0.08);
    },

    // 🃏 Memory pair found
    pairFound() {
      tone(523, 'sine', 0.08, 0.18, 0.00);
      tone(784, 'sine', 0.08, 0.20, 0.08);
      tone(1047,'sine', 0.12, 0.22, 0.16);
    },
  };

  return {
    play(name) {
      if (sounds[name]) sounds[name]();
    },
    toggle() {
      enabled = !enabled;
      localStorage.setItem('lv_sfx', enabled ? 'on' : 'off');
      return enabled;
    },
    isEnabled() { return enabled; },
  };
})();

// Global sound toggle button helper
function initSoundToggle(btnId) {
  const btn = document.getElementById(btnId);
  if (!btn) return;
  btn.textContent = SFX.isEnabled() ? '🔊' : '🔇';
  btn.onclick = () => {
    const on = SFX.toggle();
    btn.textContent = on ? '🔊' : '🔇';
    if (on) SFX.play('click');
  };
}
