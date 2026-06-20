# Lloyd Voice ◈

**Open-source voice dictation with real-time transcription, voice editing commands, and a rainbow waveform UI.**

Lloyd Voice is a free, open-source alternative to Wispr Flow, SuperWhisper, and Monologue. It runs entirely on your machine using [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — no cloud, no subscription, no audio leaving your computer.

---

## Features

- **Real-time local transcription** using faster-whisper (GPU or CPU)
- **Rainbow waveform visualization** — live audio animation with particle effects
- **Voice editing commands** — say "delete that", "no / undo", "change X to Y" to edit on the fly
- **Long-form context management** — optimized for extended dictation sessions
- **Cross-platform UI** — responsive web interface works on desktop and mobile browsers
- **Push-to-talk** — hold Space to record, release to stop
- **Privacy-first** — 100% local, no internet required after model download
- **CLI mode** — use directly from the terminal

---

## Quick Start

### Install

```bash
pip install lloyd-voice
```

Or from source:

```bash
git clone https://github.com/lloyd-voice/lloyd-voice.git
cd lloyd-voice
pip install -e .
```

### Run

```bash
# Start the web server with rainbow waveform UI
lloyd-voice serve

# Or with a specific model
lloyd-voice serve --model small

# Open http://127.0.0.1:8765 in your browser
```

### CLI Transcription

```bash
# Transcribe from microphone
lloyd-voice transcribe

# Transcribe an audio file
lloyd-voice transcribe --file recording.wav

# CLI listening mode with level meter
lloyd-voice listen
```

---

## Model Sizes

| Model | Parameters | Disk | Speed | Accuracy |
|-------|-----------|------|-------|----------|
| `tiny` | 39M | ~75 MB | fastest | lowest |
| `base` | 74M | ~150 MB | fast | good |
| `small` | 244M | ~500 MB | medium | better |
| `medium` | 769M | ~1.5 GB | slow | high |
| `large-v3` | 1.5B | ~3 GB | slowest | best |

## Voice Commands

| Say | Effect |
|-----|--------|
| "delete that" | Remove the last utterance |
| "no" / "undo" | Undo last action |
| "redo" | Redo last undone action |
| "clear all" | Clear entire document |
| "change X to Y" | Find and replace text |
| "new line" | Insert line break |
| "new paragraph" | New paragraph |
| "period" / "comma" | Insert punctuation |
| "stop listening" | Pause transcription |

---

## Architecture

```
lloyd-voice/
├── src/lloyd_voice/
│   ├── core/
│   │   ├── audio.py          # Audio capture via sounddevice
│   │   ├── transcriber.py    # faster-whisper integration
│   │   └── commands.py       # Voice command parser & editor
│   ├── session/
│   │   └── context.py        # Long-form context management
│   ├── ui/
│   │   ├── app.py            # WebSocket server (aiohttp)
│   │   └── static/           # Web UI (rainbow waveform)
│   ├── platform/
│   │   └── text_injection.py # Cross-platform text injection
│   └── cli.py                # CLI entry point
├── pyproject.toml
└── README.md
```

## Requirements

- Python 3.10+
- Works on **Windows**, **macOS**, and **Linux**
- GPU acceleration via CUDA (optional, automatic CPU fallback)
- Mobile access via browser on same network

---

## License

MIT License — see [LICENSE](LICENSE).
