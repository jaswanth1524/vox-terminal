# Vox Terminal

Vox Terminal is a local macOS menu-bar dictation app. Hold Right Option anywhere,
speak, release, and the transcript is pasted into the focused app. Audio remains in
memory, normal transcription is forced offline, and no transcript is uploaded.

## Requirements

- macOS on Apple Silicon
- Python 3.11+
- `uv`
- PortAudio, if `sounddevice` cannot find an input backend: `brew install portaudio`

## Install the Local App

```sh
make setup
make install
```

The build creates an arm64, ad-hoc-signed app at `dist/Vox Terminal.app` and copies
it to `~/Applications`. Launch it from Finder. On first launch, Vox Terminal checks
the local Hugging Face cache and offers to download the approximately 1.5 GB
Whisper model if needed. That explicit setup step is the only online app operation.

## macOS Permissions

Grant permissions to `Vox Terminal.app`. If you run the developer CLI, grant them
to the launching terminal and virtual-environment Python instead.

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

Use the menu's Start at Login item to register the installed app with macOS. The
app migrates an older repo-bound `com.user.dictate` LaunchAgent if one exists.

Settings opens a native window for recording mode, language, sounds, paste method,
clipboard restoration, and vocabulary hints. Save & Restart writes the existing
`~/.config/dictate/config.toml` atomically and restarts the internal service.

Run Diagnostics checks audio input and Accessibility access and can open Privacy
settings. Open Logs reveals rotating logs under `~/Library/Logs/Vox Terminal/`.

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

## Development

```sh
make lint       # Ruff static checks
make test       # deterministic unit suite
make app        # standalone .app bundle
make install    # build, sign, and copy to ~/Applications
```

`uv run python -m dictate --no-menubar` remains available for foreground debugging.
Use `uv run python -m dictate --doctor` for terminal diagnostics and
`uv run python -m dictate --download-model` for an explicit CLI model download.

## Benchmarking

Compare cached Whisper and Parakeet models on a local audio file:

```sh
make benchmark
```

Parakeet is an optional benchmark dependency and is not bundled in the daily-use
app. Benchmarks run offline by default; pass `--online` only when intentionally
allowing a benchmark-model download.

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
