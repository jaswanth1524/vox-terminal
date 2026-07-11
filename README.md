# Vox Terminal

Vox Terminal is a local macOS menu-bar dictation app. Hold Right Option anywhere,
speak, release, and the transcript is pasted into the focused app. Audio remains in
memory, normal transcription is forced offline, and no transcript is uploaded.

## Requirements

- macOS 13 or newer on Apple Silicon (arm64)
- Python 3.11+ and [`uv`](https://docs.astral.sh/uv/) 0.8.11+ when building from source
- PortAudio, if `sounddevice` cannot find an input backend: `brew install portaudio`

Intel Macs, Linux, and Windows are not supported. Speech models are intentionally
not included in the app or release archive.

## Download a Release

Download the arm64 ZIP and matching `.sha256` file from the repository's Releases
page. Keep both files in the same directory, then verify and extract them:

```sh
shasum -a 256 -c Vox-Terminal-*-macOS-arm64.sha256
ditto -x -k Vox-Terminal-*-macOS-arm64.zip .
mkdir -p "$HOME/Applications"
mv "Vox Terminal.app" "$HOME/Applications/"
```

Notarized releases open normally. An ad-hoc-signed beta may be blocked by
Gatekeeper: control-click the app and choose Open, then confirm it under System
Settings -> Privacy & Security -> Open Anyway. Verify the checksum before doing
this; never bypass Gatekeeper for an unverified archive.

## Build from a Clean Clone

```sh
git clone https://github.com/jaswanth1524/vox-terminal.git
cd vox-terminal
make setup
make verify
make install
```

`make setup` validates macOS and arm64, then synchronizes a Python 3.11 environment
from the exact `uv.lock` in frozen mode. `make verify` runs lint, tests, a production build,
the frozen-app self-test, architecture and signature checks, and the 300 MB bundle
limit. `make install` copies the ad-hoc-signed app to your personal Applications
folder at `~/Applications`, not the system-wide `/Applications` folder. Run
`open -R "$HOME/Applications/Vox Terminal.app"` to reveal it in Finder.

The lock intentionally omits Torch, SciPy, Numba, Librosa, and scikit-learn.
The pinned speech engines declare those optional stacks unconditionally, while Vox
Terminal provides the small mel-filter and disabled word-timing APIs it actually uses.
When upgrading either engine pin, update its dependency metadata in `pyproject.toml`
and verify both engine imports before regenerating `uv.lock`.

Launch from Finder. On first launch, Vox Terminal checks the local Hugging Face
cache and asks before starting the selected model download. That single-use
provisioning process is the only component allowed to connect externally. After
the model is cached, startup, recording, transcription, paste, diagnostics, and
performance reporting remain offline.

## macOS Permissions

Grant permissions to `Vox Terminal.app`. If you run the developer CLI, grant them
to the launching terminal and virtual-environment Python instead.

Open System Settings -> Privacy & Security and grant:

1. Microphone: required to record audio.
2. Accessibility: required to synthesize Cmd+V.
3. Input Monitoring: required for the global Right Option hotkey.

If the hotkey listener sees no keyboard events shortly after startup, Vox Terminal
prints an Input Monitoring warning. Grant permissions to the exact installed app at
`~/Applications/Vox Terminal.app`; grant Terminal and virtual-environment Python
only when running the developer CLI. Secure input fields, such as password prompts,
may block synthetic paste events.

Replacing an ad-hoc-signed local build can change its macOS code identity and leave
privacy toggles looking enabled while no longer matching the executable. Quit the
app, remove and re-add the exact installed bundle under Accessibility and Input
Monitoring, then relaunch it. If macOS retains stale entries, reset only this app:

```sh
tccutil reset Accessibility com.jaswanth.voxterminal
tccutil reset ListenEvent com.jaswanth.voxterminal
tccutil reset Microphone com.jaswanth.voxterminal
```

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

In hold mode, hold Right Option to record and release it to transcribe. In toggle
mode, press Right Option once to start and again to stop. The transcript is pasted
through the clipboard immediately; text clipboard restoration runs in the
background after about 300 ms and does not overwrite newer user-copied text.
Non-text clipboard content is not preserved.

The menu bar icon shows the current state:

- 🎙️ idle
- 🔴 recording
- ⏳ loading or transcribing
- ⚠️ needs attention

Use the menu's Start at Login item to register the installed app with macOS. The
app migrates an older repo-bound `com.user.dictate` LaunchAgent if one exists.

Settings opens a native window for speech engine, recording mode, language,
sounds, paste method, clipboard restoration, and vocabulary hints. Save & Restart writes the existing
`~/.config/dictate/config.toml` atomically and restarts the internal service.

Run Diagnostics checks audio input and Accessibility access and can open Privacy
settings. Open Logs reveals rotating logs under `~/Library/Logs/Vox Terminal/`.
Performance Report shows local p50/p95 release-to-paste and inference latency. It
keeps the latest 100 samples across launches, includes per-engine comparisons, and
contains timings only—never audio or transcript text. Use Reset Performance Data
to remove the saved samples at any time. The data file is stored at
`~/Library/Application Support/Vox Terminal/latency.json`.

The History menu item shows recent pasted transcripts for the current process only. History is kept in memory, capped by `history_size`, and cleared when Vox Terminal quits or when you choose Clear History.

## Configuration

Create `~/.config/dictate/config.toml` to override defaults:

```toml
engine = "parakeet"
hotkey = "right_option"
mode = "hold"
model = "mlx-community/whisper-large-v3-turbo"
parakeet_model = "mlx-community/parakeet-tdt-0.6b-v2"
parakeet_beam_size = 2
parakeet_quantization_bits = 3
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

Parakeet two-beam decoding is the new-install default for fast, accurate English dictation.
Set `engine = "whisper"` or select Whisper in Settings for multilingual and
accuracy-first use. An existing explicit engine setting is preserved. Only the
selected engine is loaded into memory. Parakeet uses local 3-bit MLX weight
quantization by default to reduce GPU memory and improve inference speed; set
`parakeet_quantization_bits = 0` to disable it, or choose `4` or `8` for a
different accuracy/memory tradeoff. Two-bit mode is rejected because it causes
severe accuracy loss on the repository corpus.

When `mode = "toggle"` and `vad_auto_stop = true`, a bounded streaming energy
detector adapts to the local noise floor and stops after speech is followed by
`vad_silence_seconds` of silence. It retains counters and one partial analysis
frame, not a second copy of the recording.

## Development

```sh
make lint       # Ruff static checks
make test       # deterministic unit suite
make app        # standalone .app bundle
make install    # build, sign, and copy to ~/Applications
make verify     # all source and release bundle gates
make performance PERFORMANCE_ITERATIONS=100  # cached-model latency/memory audit
make release    # versioned ZIP, checksum, and dependency report
```

`uv run python -m dictate --no-menubar` remains available for foreground debugging.
Use `uv run python -m dictate --doctor` for terminal diagnostics and
`uv run python -m dictate --download-model` for an explicit CLI model download.
The performance audit reports cold load time, warm p50/p95 inference from the
first 20 utterances, macOS physical footprint including GPU allocations,
100-dictation memory growth, and bundle size. It
requires the Parakeet model to be cached and returns a nonzero status when a
budget fails. The release limits are 500/750 ms p50/p95, 1.5 GiB physical
footprint, 100 MiB soak growth, and a 300 MiB app bundle.

## Publishing Releases

`pyproject.toml` is the single version source for package metadata, the app bundle,
and release filenames. A `v<version>` tag runs the arm64 release workflow. It
publishes a versioned ZIP, SHA-256 checksum, locked dependency report, SPDX 2.3 JSON
SBOM derived from the frozen bundle analysis, and GitHub provenance attestation.
With no Apple secrets it produces an ad-hoc-signed
beta. For Developer ID signing and notarization, configure all six repository
secrets: `MACOS_CERTIFICATE_BASE64`, `MACOS_CERTIFICATE_PASSWORD`,
`MACOS_SIGNING_IDENTITY`, `APPLE_ID`, `APPLE_TEAM_ID`, and
`APPLE_APP_SPECIFIC_PASSWORD`. Partial configuration fails instead of silently
publishing a misleading build; see `.github/workflows/release.yml` for the exact flow.

## Benchmarking

Run the deterministic 20-phrase release latency and accuracy gate:

```sh
make benchmark
```

The benchmark synthesizes temporary English audio, runs cached models offline, and
reports p50, p95, WER, the latency-first fast-default gate, and the release gate that
allows at most two percentage points of WER regression from Whisper. The command
exits successfully only when that stricter release gate passes. Temporary audio is
deleted when the command exits. Use
`--parakeet-only` to test Parakeet without re-running Whisper. Run
`uv run python scripts/benchmark_latency.py --interactive` for ten prompted,
user-spoken comparisons; captured audio remains in memory and is discarded.

## Testing

Run the default unit tests:

```sh
uv run python -m unittest discover -s tests
```

The MLX integration test is opt-in because it requires a cached model:

```sh
DICTATE_RUN_MLX_TESTS=1 uv run python -m unittest tests.test_transcriber
```

## Privacy and Offline Operation

Normal runtime installs a process-wide outbound socket guard before model libraries
are imported and sets Hugging Face offline mode. If the selected model is missing
from `~/.cache/huggingface`, the app requests consent and launches a separate,
single-use provisioning subprocess; it never silently falls back to the network.
There is no telemetry, analytics, update check, remote transcription API, or crash
reporting. Dictation audio stays in memory and is never written to disk. Performance
history contains only engine names and numeric stage timings—never recordings,
transcripts, prompts, or target-app details.
