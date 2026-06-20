class LloydVoiceClient {
  constructor() {
    this.ws = null;
    this.recording = false;
    this.paused = false;
    this.connected = false;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 10;
    this.reconnectDelay = 1000;
    this.sessionStart = null;
    this.sessionTimer = null;
    this.reconnectTimer = null;
    this.pingInterval = null;

    this.waveform = new RainbowWaveform('waveform');
    this.transcript = document.getElementById('transcript');
    this.recordBtn = document.getElementById('record-btn');
    this.statusDot = document.getElementById('status-dot');
    this.statusText = document.getElementById('status-text');
    this.connectionStatus = document.getElementById('connection-status');
    this.latencyEl = document.getElementById('latency');
    this.sessionDuration = document.getElementById('session-duration');
    this.wordCount = document.getElementById('word-count');
    this.modelInfo = document.getElementById('model-info');
    this.modelSelect = document.getElementById('model-select');
    this.toast = document.getElementById('toast');
    this.copyBtn = document.getElementById('copy-btn');
    this.clearBtn = document.getElementById('clear-btn');

    this._bindEvents();
    this._connect();
  }

  _bindEvents() {
    this.recordBtn.addEventListener('click', () => this._toggleRecording());
    this.copyBtn.addEventListener('click', () => this._copyText());
    this.clearBtn.addEventListener('click', () => this._clearText());
    this.modelSelect.addEventListener('change', () => this._setModel(this.modelSelect.value));

    document.addEventListener('keydown', (e) => {
      if (e.code === 'Space' && !e.repeat &&
          !e.target.closest('.transcript') &&
          !e.target.closest('.ctrl-btn')) {
        e.preventDefault();
        if (!this.recording) {
          this._startRecording();
        }
      }
    });

    document.addEventListener('keyup', (e) => {
      if (e.code === 'Space' && this.recording && !e.target.closest('.transcript')) {
        this._stopRecording();
      }
    });

    window.addEventListener('beforeunload', () => this._disconnect());
    window.addEventListener('resize', () => this.waveform.resize());
  }

  _connect() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${location.host}/ws`;

    try {
      this.ws = new WebSocket(wsUrl);
    } catch (e) {
      this._setConnectionStatus('Connection failed', false);
      this._scheduleReconnect();
      return;
    }

    this.ws.onopen = () => {
      this.connected = true;
      this.reconnectAttempts = 0;
      this.reconnectDelay = 1000;
      this._setConnectionStatus('Connected', true);
      this.waveform.setActive(true);

      this.pingInterval = setInterval(() => {
        if (this.ws.readyState === WebSocket.OPEN) {
          const start = performance.now();
          this.ws.send(JSON.stringify({ action: 'ping' }));
          this._lastPing = start;
        }
      }, 10000);
    };

    this.ws.onclose = () => {
      this.connected = false;
      this.waveform.setActive(false);
      if (this.pingInterval) {
        clearInterval(this.pingInterval);
        this.pingInterval = null;
      }
      this._setConnectionStatus('Disconnected', false);
      this._scheduleReconnect();
    };

    this.ws.onerror = () => {
      this.connected = false;
      this.waveform.setActive(false);
    };

    this.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        this._handleMessage(msg);
      } catch (e) {
        console.error('Failed to parse message:', e);
      }
    };
  }

  _scheduleReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) return;
    this.reconnectAttempts++;
    this.reconnectDelay = Math.min(this.reconnectDelay * 1.5, 30000);
    const jitter = Math.random() * 1000;
    this._setConnectionStatus(`Reconnecting in ${Math.round((this.reconnectDelay + jitter) / 1000)}s...`, false);
    this.reconnectTimer = setTimeout(() => this._connect(), this.reconnectDelay + jitter);
  }

  _disconnect() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
    if (this.ws) {
      this.ws.onclose = null;
      this.ws.close();
      this.ws = null;
    }
    if (this.sessionTimer) {
      clearInterval(this.sessionTimer);
      this.sessionTimer = null;
    }
  }

  _handleMessage(msg) {
    const { event, data } = msg;

    switch (event) {
      case 'audio_level':
        this.waveform.updateAudioLevel(data);
        break;

      case 'transcription':
        this._handleTranscription(data);
        break;

      case 'document':
        if (data.text) {
          this.transcript.textContent = data.text;
          this._updateWordCount(data.text);
        }
        break;

      case 'status':
        if (data.recording !== undefined) {
          this.recording = data.recording;
          this._updateRecordingUI();
        }
        if (data.paused !== undefined) {
          this.paused = data.paused;
          this._updateRecordingUI();
        }
    if (data.model) {
      this.modelInfo.textContent = data.model;
      this.modelSelect.value = data.model;
    }
        break;

      case 'error':
        this._showToast(data.message || 'An error occurred', 'error');
        break;

      case 'summary':
        this._showSummary(data);
        break;
    }
  }

  _handleTranscription(data) {
    if (data.is_command) {
      const span = document.createElement('span');
      span.className = 'command-highlight';
      span.textContent = data.text;
      this.transcript.appendChild(span);
      this.transcript.appendChild(document.createTextNode(' '));
      this._flashCommandItem(data.text);
    } else if (data.document) {
      this.transcript.textContent = data.document;
    }

    if (data.document) {
      this._updateWordCount(data.document);
    }
    this.transcript.scrollTop = this.transcript.scrollHeight;
  }

  _flashCommandItem(text) {
    const lower = text.toLowerCase();
    let cmd = '';
    if (/delete\s+(that|this|it)|remove\s+(that|this|it|the\s+last)/.test(lower)) cmd = 'delete_last';
    else if (/\b(undo|no\b|wait\s+no|scratch\s+that|never\s+mind)/.test(lower)) cmd = 'undo';
    else if (/\b(redo|remake)\b/.test(lower)) cmd = 'redo';
    else if (/clear\s+(all|everything)/.test(lower)) cmd = 'clear';
    else if (/\b(change|replace)\b/.test(lower)) cmd = 'replace';
    else if (/new\s+line/.test(lower)) cmd = 'new_line';
    else if (/\b(period|comma|question|exclamation)\b/.test(lower)) cmd = 'punctuation';
    else if (/\bstop\b/.test(lower)) cmd = 'stop_listening';

    if (!cmd) return;
    const el = document.querySelector(`.commands-panel [data-cmd="${cmd}"]`);
    if (!el) return;
    el.classList.add('flash');
    clearTimeout(el._flashTimer);
    el._flashTimer = setTimeout(() => el.classList.remove('flash'), 1200);
  }

  _updateWordCount(text) {
    const words = text.trim() ? text.trim().split(/\s+/).length : 0;
    this.wordCount.textContent = `${words} word${words !== 1 ? 's' : ''}`;
  }

  _toggleRecording() {
    if (this.recording) {
      this._stopRecording();
    } else {
      this._startRecording();
    }
  }

  _startRecording() {
    if (!this.connected || this.recording) return;
    this._send({ action: 'start_recording' });
    this.recording = true;
    this._updateRecordingUI();

    this.sessionStart = Date.now();
    this.sessionTimer = setInterval(() => {
      if (this.sessionStart) {
        const elapsed = Math.floor((Date.now() - this.sessionStart) / 1000);
        const m = String(Math.floor(elapsed / 60)).padStart(2, '0');
        const s = String(elapsed % 60).padStart(2, '0');
        this.sessionDuration.textContent = `${m}:${s}`;
      }
    }, 1000);
  }

  _stopRecording() {
    if (!this.recording) return;
    this._send({ action: 'stop_recording' });
    this.recording = false;
    this._updateRecordingUI();

    if (this.sessionTimer) {
      clearInterval(this.sessionTimer);
      this.sessionTimer = null;
    }
  }

  _updateRecordingUI() {
    this.recordBtn.classList.toggle('active', this.recording && !this.paused);
    this.recordBtn.classList.toggle('paused', this.paused);

    if (this.recording) {
      this.statusDot.className = 'status-dot recording';
      this.statusText.textContent = this.paused ? 'PAUSED' : 'RECORDING';
      this.waveform.setRecording(true);
      this.transcript.classList.add('recording');
    } else {
      this.statusDot.className = 'status-dot online';
      this.statusText.textContent = 'READY';
      this.waveform.setRecording(false);
      this.transcript.classList.remove('recording');
    }
  }

  _setConnectionStatus(text, connected) {
    this.connectionStatus.textContent = text;
    if (connected) {
      this.statusDot.className = 'status-dot online';
      this.statusText.textContent = this.recording ? 'RECORDING' : 'READY';
      this.modelInfo.textContent = '';
    } else {
      this.statusDot.className = 'status-dot offline';
      this.statusText.textContent = 'OFFLINE';
    }
  }

  _copyText() {
    const text = this.transcript.textContent;
    if (!text) return;

    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).catch(() => {
        this._fallbackCopy(text);
      });
    } else {
      this._fallbackCopy(text);
    }
  }

  _fallbackCopy(text) {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    try {
      document.execCommand('copy');
    } catch (e) {}
    document.body.removeChild(ta);
  }

  _clearText() {
    if (this.recording) {
      this._send({ action: 'reset_session' });
    }
    this.transcript.textContent = '';
    this._updateWordCount('');
  }

  _showSummary(data) {
    console.log('Session summary:', data);
  }

  _showToast(message, type) {
    this.toast.textContent = message;
    this.toast.className = 'toast visible ' + (type || 'info');
    clearTimeout(this._toastTimer);
    this._toastTimer = setTimeout(() => {
      this.toast.className = 'toast';
    }, 4000);
  }

  _setModel(model) {
    this._send({ action: 'set_model', model: model });
    this._showToast('Model: ' + model, 'info');
  }

  _send(data) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }
}


class RainbowWaveform {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    this.ctx = this.canvas.getContext('2d');
    this.active = false;
    this.recording = false;
    this.audioData = { rms: 0, peak: 0, waveform: [] };

    this._smoothRms = 0;
    this._smoothPeak = 0;
    this._displayRms = 0;
    this._history = [];
    this._maxHistory = 120;
    this._phase = 0;
    this._particles = [];
    this._sparkles = [];
    this._breath = 0;

    this._setupCanvas();
    this._animate();
  }

  _setupCanvas() {
    this.resize();
  }

  resize() {
    const rect = this.canvas.parentElement.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    this.canvas.width = rect.width * dpr;
    this.canvas.height = rect.height * dpr;
    this.canvas.style.width = rect.width + 'px';
    this.canvas.style.height = rect.height + 'px';
    this.ctx.scale(dpr, dpr);
    this._width = rect.width;
    this._height = rect.height;
  }

  setActive(active) {
    this.active = active;
    if (!active) {
      this._history = [];
      this._particles = [];
      this._sparkles = [];
      this._smoothRms = 0;
    }
  }

  setRecording(recording) {
    this.recording = recording;
  }

  updateAudioLevel(data) {
    if (!this.active) return;
    this._rawData = data;
    this._smoothRms = this._smoothRms * 0.7 + data.rms * 0.3;
    this._smoothPeak = this._smoothPeak * 0.7 + data.peak * 0.3;
    if (data.waveform && data.waveform.length > 0) {
      this._history.push({ rms: data.rms, waveform: [...data.waveform] });
      if (this._history.length > this._maxHistory) {
        this._history.shift();
      }
    }
  }

  _animate() {
    this._draw();
    requestAnimationFrame(() => this._animate());
  }

  _draw() {
    const ctx = this.ctx;
    const w = this._width || 300;
    const h = this._height || 100;
    const cx = w / 2;
    const cy = h / 2;

    ctx.clearRect(0, 0, w, h);

    if (!this.active) {
      this._drawInactive(ctx, w, h, cx, cy);
      return;
    }

    this._phase += 0.015;
    this._breath += 0.025;

    const targetRms = this.recording && this._rawData ? this._smoothRms : 0;
    this._displayRms += (targetRms - this._displayRms) * 0.12;

    if (this.recording && this._displayRms > 0.001) {
      this._drawBackgroundBars(ctx, w, h);
      this._drawActiveWaveform(ctx, w, h, cx, cy);
      this._drawParticles(ctx, w, h, cx, cy);
    } else {
      this._drawIdleWaveform(ctx, w, h, cx, cy);
    }

    this._drawCenterGlow(ctx, cx, cy, w);
  }

  _drawInactive(ctx, w, h, cx, cy) {
    const gradient = ctx.createLinearGradient(0, 0, w, 0);
    gradient.addColorStop(0, '#1a1a2e');
    gradient.addColorStop(0.5, '#2a2a3e');
    gradient.addColorStop(1, '#1a1a2e');

    ctx.strokeStyle = gradient;
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let x = 0; x < w; x += 2) {
      const y = cy + Math.sin(x * 0.02 + this._phase) * 4;
      x === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.stroke();

    ctx.fillStyle = 'rgba(42, 42, 62, 0.3)';
    ctx.font = '12px system-ui';
    ctx.textAlign = 'center';
    ctx.fillText('connect to start', cx, h - 16);
  }

  _drawIdleWaveform(ctx, w, h, cx, cy) {
    const breathe = 1 + Math.sin(this._breath) * 0.15;
    const gradient = ctx.createLinearGradient(0, 0, w, 0);
    gradient.addColorStop(0, '#2a2a3e');
    gradient.addColorStop(0.3, '#4dabf7');
    gradient.addColorStop(0.5, '#69db7c');
    gradient.addColorStop(0.7, '#ffd43b');
    gradient.addColorStop(1, '#2a2a3e');

    ctx.strokeStyle = gradient;
    ctx.lineWidth = 1.5;
    ctx.globalAlpha = 0.3 + Math.sin(this._breath * 0.7) * 0.1;

    ctx.beginPath();
    for (let x = 0; x < w; x += 2) {
      const envelope = this._getEnvelope(x, w);
      const wave = Math.sin(x * 0.03 + this._phase * 0.5);
      const y = cy + wave * 8 * envelope * breathe;
      x === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.stroke();

    ctx.globalAlpha = 0.08;
    ctx.lineWidth = 6;
    ctx.beginPath();
    for (let x = 0; x < w; x += 2) {
      const envelope = this._getEnvelope(x, w);
      const wave = Math.sin(x * 0.03 + this._phase * 0.5 + 0.3);
      const y = cy + wave * 10 * envelope * breathe;
      x === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.stroke();
    ctx.globalAlpha = 1;
  }

  _drawBackgroundBars(ctx, w, h) {
    const barCount = Math.floor(w / 12);
    const barWidth = 4;
    const gap = 8;
    ctx.globalAlpha = 0.06;
    for (let i = 0; i < barCount; i++) {
      const x = i * (barWidth + gap) + gap / 2;
      const barH = (0.3 + Math.sin(i * 0.5 + this._phase * 2) * 0.3) * h * 0.4;
      const hue = (i * 8 + this._phase * 30) % 360;
      ctx.fillStyle = `hsla(${hue}, 80%, 60%, 0.3)`;
      ctx.fillRect(x, h * 0.5 - barH / 2, barWidth, barH);
    }
    ctx.globalAlpha = 1;
  }

  _drawActiveWaveform(ctx, w, h, cx, cy) {
    const centerY = h * 0.45;
    const audio = this._rawData || this.audioData;
    const rms = Math.min(this._displayRms * 400, 1);
    const amplitude = Math.max(rms * h * 0.35, 6);
    const history = this._history;
    const len = history.length;

    const gradient = ctx.createLinearGradient(0, 0, w, 0);
    gradient.addColorStop(0, 'rgba(255, 107, 107, 0.1)');
    gradient.addColorStop(0.16, '#ff6b6b');
    gradient.addColorStop(0.33, '#ffa94d');
    gradient.addColorStop(0.5, '#ffd43b');
    gradient.addColorStop(0.66, '#69db7c');
    gradient.addColorStop(0.83, '#4dabf7');
    gradient.addColorStop(1, 'rgba(255, 107, 107, 0.1)');

    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';

    const samples = Math.min(audio.waveform.length, 200);
    if (samples > 0) {
      for (let pass = 0; pass < 2; pass++) {
        const lineWidth = pass === 0 ? 5 : 2.5;
        ctx.globalAlpha = pass === 0 ? 0.25 : 0.85;
        ctx.lineWidth = lineWidth;
        ctx.beginPath();

        for (let i = 0; i < samples; i++) {
          const x = (i / Math.max(samples - 1, 1)) * w;
          const sv = Math.abs(audio.waveform[i] || 0);
          const y = centerY - sv * amplitude * 1.5;

          if (pass === 0) {
            ctx.strokeStyle = `rgba(120, 120, 220, ${0.15 + sv * 0.35})`;
          } else {
            const t = i / Math.max(samples - 1, 1);
            ctx.strokeStyle = gradient;
          }

          if (i === 0) ctx.moveTo(x, y);
          else {
            const px = ((i - 1) / Math.max(samples - 1, 1)) * w;
            const py = centerY - Math.abs(audio.waveform[i - 1] || 0) * amplitude * 1.5;
            ctx.quadraticCurveTo((px + x) / 2, py, x, y);
          }
        }
        ctx.stroke();
      }

      ctx.globalAlpha = 0.5;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      for (let i = 0; i < samples; i++) {
        const x = (i / Math.max(samples - 1, 1)) * w;
        const sv = Math.abs(audio.waveform[i] || 0);
        const y = centerY + sv * amplitude * 1.5;
        if (i === 0) ctx.moveTo(x, y);
        else {
          const px = ((i - 1) / Math.max(samples - 1, 1)) * w;
          const py = centerY + Math.abs(audio.waveform[i - 1] || 0) * amplitude * 1.5;
          ctx.quadraticCurveTo((px + x) / 2, py, x, y);
        }
      }
      ctx.stroke();
    }

    if (len > 1) {
      const trailLen = Math.min(len, 50);
      ctx.lineWidth = 2;

      for (let t = 0; t < trailLen; t++) {
        const idx = len - trailLen + t;
        const entry = history[idx];
        if (!entry || !entry.waveform) continue;
        const progress = t / trailLen;
        const trailAmp = amplitude * Math.pow(progress, 0.6);

        ctx.globalAlpha = 0.08 * progress;
        const hue = (t * 4 + this._phase * 20) % 360;
        ctx.strokeStyle = `hsla(${hue}, 80%, 65%, 0.6)`;
        ctx.beginPath();

        const sw = entry.waveform.length;
        if (sw < 2) continue;
        for (let i = 0; i < sw; i++) {
          const x = (i / Math.max(sw - 1, 1)) * w;
          const sv = Math.abs(entry.waveform[i] || 0);
          const y = centerY - sv * trailAmp;
          i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
        }
        ctx.stroke();
      }
    }

    ctx.globalAlpha = 1;
  }

  _drawParticles(ctx, w, h, cx, cy) {
    if (!this.recording || this._displayRms < 0.003) {
      this._particles = [];
      this._sparkles = [];
      return;
    }

    const rms = this._displayRms;
    const count = Math.floor(rms * 200) + 3;

    while (this._particles.length < count) {
      const angle = -Math.PI / 2 + (Math.random() - 0.5) * Math.PI * 0.8;
      const speed = 0.4 + Math.random() * 1.2;
      this._particles.push({
        x: cx + (Math.random() - 0.5) * w * 0.5,
        y: cy + (Math.random() - 0.5) * h * 0.2,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed - Math.random() * 0.3,
        life: 0.6 + Math.random() * 0.6,
        maxLife: 1.0 + Math.random() * 0.2,
        size: 1.5 + Math.random() * 3,
        hue: (this._phase * 40 + Math.random() * 60) % 360,
      });
    }

    if (this._particles.length > count * 2) {
      this._particles = this._particles.slice(-count * 2);
    }

    if (Math.random() < rms * 0.5) {
      this._sparkles.push({
        x: cx + (Math.random() - 0.5) * w * 0.7,
        y: cy - h * 0.1 + Math.random() * h * 0.2,
        vx: (Math.random() - 0.5) * 3,
        vy: -Math.random() * 2 - 1,
        life: 0.3 + Math.random() * 0.3,
        maxLife: 0.6,
        size: 0.5 + Math.random() * 1.5,
        hue: (this._phase * 50 + Math.random() * 120) % 360,
      });
    }

    ctx.globalAlpha = 0.5;
    for (let i = this._particles.length - 1; i >= 0; i--) {
      const p = this._particles[i];
      p.x += p.vx;
      p.y += p.vy;
      p.vy += 0.015;
      p.life -= 0.006;

      if (p.life <= 0 || p.x < -30 || p.x > w + 30 || p.y > h + 30) {
        this._particles.splice(i, 1);
        continue;
      }

      const alpha = (p.life / p.maxLife) * 0.6;
      ctx.fillStyle = `hsla(${p.hue}, 90%, 65%, ${alpha})`;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.size * (p.life / p.maxLife), 0, Math.PI * 2);
      ctx.fill();
    }

    for (let i = this._sparkles.length - 1; i >= 0; i--) {
      const s = this._sparkles[i];
      s.x += s.vx;
      s.y += s.vy;
      s.vy += 0.02;
      s.life -= 0.02;

      if (s.life <= 0) {
        this._sparkles.splice(i, 1);
        continue;
      }

      const alpha = (s.life / s.maxLife) * 0.8;
      ctx.fillStyle = `hsla(${s.hue}, 100%, 80%, ${alpha})`;
      ctx.beginPath();
      ctx.arc(s.x, s.y, s.size * (s.life / s.maxLife), 0, Math.PI * 2);
      ctx.fill();
    }

    ctx.globalAlpha = 1;
  }

  _drawCenterGlow(ctx, cx, cy, w) {
    if (this._displayRms > 0.003) {
      const rms = Math.min(this._displayRms * 300, 1);
      const radius = 15 + rms * 50;
      const gradient = ctx.createRadialGradient(cx, cy, 0, cx, cy, radius);
      const hue = (this._phase * 40) % 360;
      const intensity = 0.12 + rms * 0.12;
      gradient.addColorStop(0, `hsla(${hue}, 100%, 70%, ${intensity})`);
      gradient.addColorStop(0.3, `hsla(${(hue + 90) % 360}, 90%, 60%, ${intensity * 0.6})`);
      gradient.addColorStop(0.6, `hsla(${(hue + 180) % 360}, 80%, 50%, ${intensity * 0.3})`);
      gradient.addColorStop(1, 'rgba(0,0,0,0)');
      ctx.fillStyle = gradient;
      ctx.beginPath();
      ctx.arc(cx, cy, radius, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  _getEnvelope(x, w) {
    const edgeWidth = w * 0.15;
    if (x < edgeWidth) return x / edgeWidth;
    if (x > w - edgeWidth) return (w - x) / edgeWidth;
    return 1;
  }
}


document.addEventListener('DOMContentLoaded', () => {
  const app = new LloydVoiceClient();
});
