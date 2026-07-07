# Vox Terminal

Vox Terminal is a local macOS push-to-talk dictation tool. Hold Right Option anywhere, speak, release, and the transcript is pasted into the currently focused app. Audio stays on the machine. Runtime transcription is configured for offline mode; the Whisper model is downloaded only during installation.

Phase 0 through Phase 5 are implemented here.

## Requirements

- macOS on Apple Silicon
- Python 3.11+
- `uv`
- PortAudio, if `sounddevice` cannot find an input backend: `brew install portaudio`

## Install

```sh
./scripts/install.sh
```

The installer syncs Python dependencies, downloads the default model into the Hugging Face cache, writes a default config if needed, and runs permission diagnostics.

## macOS Permissions

Grant permissions to the binary that launches the app, usually the venv Python printed by `install.sh`, or the terminal app if you run through Terminal, iTerm2, Warp, or VS Code.

Open System Settings -> Privacy & Security and grant:

1. Microphone: required to record audio.
2. Accessibility: required to synthesize Cmd+V.
3. Input Monitoring: required for the global Right Option hotkey.

If the hotkey listener sees no keyboard events shortly after startup, Vox Terminal prints an Input Monitoring warning. Secure input fields, such as password prompts, may block synthetic paste events.

## Usage

Run the Phase 0 mic spike:

```sh
uv run python scripts/phase0_spike.py
```

Run the resident menu bar app:

```sh
uv run python -m dictate
```

Run without the menu bar for terminal debugging:

```sh
uv run python -m dictate --no-menubar
```

In hold mode, hold Right Option to record and release it to transcribe. In toggle mode, press Right Option once to start and again to stop. The transcript is pasted through the clipboard, then the previous text clipboard is restored after about 300 ms. Non-text clipboard content is not preserved.

The menu bar icon shows the current state:

- 🎙️ idle
- 🔴 recording
- ⏳ loading or transcribing
- ⚠️ needs attention

Use the menu's Start at Login item to install or remove `~/Library/LaunchAgents/com.user.dictate.plist`.

The History menu item shows recent pasted transcripts for the current process only. History is kept in memory, capped by `history_size`, and cleared when Vox Terminal quits or when you choose Clear History.

## Configuration

Create `~/.config/dictate/config.toml` to override defaults:

```toml
hotkey = "right_option"
mode = "hold"
model = "mlx-community/whisper-large-v3-turbo"
parakeet_model = "mlx-community/parakeet-tdt-0.6b-v2"
language = "en"
sounds = true
paste_mode = "clipboard"
restore_clipboard = true
min_recording_ms = 300
max_recording_seconds = 120
history_size = 20
custom_vocabulary = ["Claude Code", "Codex", "kubectl", "FastAPI"]
vad_auto_stop = true
vad_silence_seconds = 1.0
vad_min_speech_seconds = 0.25
vad_poll_seconds = 0.25
```

`paste_mode = "clipboard"` is the reliable default. `paste_mode = "keystroke"` is available as a fallback, but it can mangle Unicode or fast input in some terminals.

Recordings shorter than `min_recording_ms` are ignored. Recordings are capped at `max_recording_seconds`.

`custom_vocabulary` is appended to Whisper's `initial_prompt` as vocabulary hints. This improves recognition of project-specific terms without sending audio or prompts off-machine.

When `mode = "toggle"` and `vad_auto_stop = true`, Silero VAD watches the in-memory recording and stops automatically after speech is followed by `vad_silence_seconds` of silence.

## Benchmarking

Compare cached Whisper and Parakeet models on a local audio file:

```sh
uv run python scripts/benchmark_parakeet.py --audio tests/fixtures/hello_world.wav
```

Benchmarks run offline by default and fail if the configured models are not already cached. Use `./scripts/install.sh` once while online to pre-download the default Whisper and Parakeet models, or pass `--online` to the benchmark when intentionally allowing a model download.

## Testing

Run the default unit tests:

```sh
uv run python -m unittest discover -s tests
```

The MLX integration test is opt-in because it requires a cached model:

```sh
DICTATE_RUN_MLX_TESTS=1 uv run python -m unittest tests.test_transcriber
```

## Privacy Notes

Vox Terminal sets Hugging Face offline environment variables during normal runtime. If the model is missing from `~/.cache/huggingface`, runtime startup fails with installation instructions instead of attempting a network download. Audio is held in memory as NumPy arrays; Vox Terminal does not write utterances to disk.
