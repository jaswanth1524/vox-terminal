# Vox Terminal

Vox Terminal is a fast, local dictation app for Apple-Silicon Macs. Hold the
**Right Option** key, speak, release it, and the transcript is pasted into the
focused terminal, editor, browser, or text field.

- Local MLX speech recognition; no remote transcription API
- About 400 ms warm inference on the repository benchmark
- Menu-bar controls, settings, diagnostics, history, and performance reports
- English-first Parakeet default with optional multilingual Whisper
- Audio and transcript history remain in memory

Normal use is forced offline. The only network operation is the model download
that you explicitly approve during setup.

## Requirements

- macOS 13 or newer
- Apple Silicon (`arm64`)
- Approximately 3 GB of free disk space for the app and selected speech model

Intel Macs, Linux, and Windows are not supported. Speech models are not bundled
inside the app or release archive.

## Install Vox Terminal

### Option 1: Download a release

Download the macOS arm64 ZIP and matching `.sha256` file from
[GitHub Releases](https://github.com/jaswanth1524/vox-terminal/releases). Keep
both files in the same directory.

Verify the archive before extracting it. Replace `<version>` with the downloaded
version:

```sh
cd ~/Downloads
shasum -a 256 -c Vox-Terminal-<version>-macOS-arm64.sha256
ditto -x -k Vox-Terminal-<version>-macOS-arm64.zip .
```

Install it in your personal Applications folder:

```sh
mkdir -p "$HOME/Applications"
ditto "Vox Terminal.app" "$HOME/Applications/Vox Terminal.app"
open "$HOME/Applications/Vox Terminal.app"
```

This project uses `~/Applications`, which is different from the system-wide
`/Applications` folder shown in Finder's sidebar. Reveal the installed app with:

```sh
open -R "$HOME/Applications/Vox Terminal.app"
```

### Option 2: Build from source

Building requires Python 3.11+, [`uv`](https://docs.astral.sh/uv/) 0.8.11+,
and `librsvg` for the app icon. PortAudio is only needed if `sounddevice` cannot
open an input device.

```sh
git clone https://github.com/jaswanth1524/vox-terminal.git
cd vox-terminal
brew install librsvg
make setup
make verify
make install
```

If setup reports an audio-backend error, run `brew install portaudio` and retry.
`make install` builds and ad-hoc signs the app, then copies it to
`~/Applications/Vox Terminal.app`.

## First Launch

1. Launch `~/Applications/Vox Terminal.app`.
2. If Gatekeeper blocks an ad-hoc-signed build, control-click the app, choose
   **Open**, and confirm it under **System Settings → Privacy & Security**.
3. Approve the one-time speech-model download when prompted.
4. Grant the app the three macOS permissions below.
5. Quit and reopen Vox Terminal after changing permissions.

The model may take several minutes to download. Later launches load only the
cached local model and do not contact external services.

## Required macOS Permissions

Open **System Settings → Privacy & Security** and grant the exact installed app:

| Permission | Why it is required |
| --- | --- |
| Microphone | Records audio while dictation is active |
| Accessibility | Pastes the finished transcript with Command-V |
| Input Monitoring | Detects the global Right Option hotkey |

The permission target must be:

```text
/Users/<your-user>/Applications/Vox Terminal.app
```

When using the installed app, do not grant permissions to the repository's
`dist/` copy, Terminal, or `.venv` Python. Those are only relevant when running
the developer CLI.

## Using the App

Vox Terminal runs in the menu bar and does not open a Dock window.

1. Focus the field where text should appear.
2. Hold **Right Option**; the icon changes to 🔴.
3. Speak normally.
4. Release **Right Option**; the icon changes to ⏳ while transcribing.
5. The transcript is pasted and the icon returns to 🎙️.

Menu-bar states:

- 🎙️ Ready
- 🔴 Recording
- ⏳ Loading or transcribing
- ⚠️ Setup or permission problem

The menu also provides Settings, Diagnostics, Logs, transcript History,
Performance Report, Start at Login, and Quit. History is kept only for the
current process and is cleared when the app quits.

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| App is not visible in Applications | It is in the personal folder | Run `open -R "$HOME/Applications/Vox Terminal.app"` |
| Right Option does nothing | Input Monitoring or Accessibility is stale | Remove and re-add the exact installed app, enable both permissions, then relaunch |
| Recording starts but audio fails | Microphone permission is missing | Enable Microphone and relaunch |
| Transcription finishes but text is not pasted | Accessibility is missing | Enable Accessibility for the installed app |
| ⚠️ remains after launch | Model or configuration needs attention | Choose **Run Diagnostics** and **Open Logs** from the menu |
| Hotkey fails in a password field | macOS Secure Input is active | Focus a normal text field and retry |

Local ad-hoc builds receive a new macOS code identity when rebuilt. Old privacy
toggles may still look enabled even though they no longer match the executable.
Quit the app, remove its old Accessibility and Input Monitoring entries, and
re-add `~/Applications/Vox Terminal.app`.

If macOS retains stale permission records, reset only Vox Terminal, then re-add
the permissions and restart the Mac:

```sh
tccutil reset Accessibility com.jaswanth.voxterminal
tccutil reset ListenEvent com.jaswanth.voxterminal
tccutil reset Microphone com.jaswanth.voxterminal
```

Logs are stored under `~/Library/Logs/Vox Terminal/`. The app's **Open Logs**
menu item opens the correct folder.

## Settings and Configuration

Use **Settings…** in the menu bar for common options. Advanced settings live at
`~/.config/dictate/config.toml`:

```toml
engine = "parakeet"
mode = "hold"
parakeet_model = "mlx-community/parakeet-tdt-0.6b-v2"
parakeet_beam_size = 2
parakeet_quantization_bits = 3
language = "en"
sounds = true
paste_mode = "clipboard"
restore_clipboard = true
custom_vocabulary = ["Codex", "kubectl", "FastAPI"]
vad_auto_stop = true
vad_silence_seconds = 1.0
```

Parakeet is the fast English default. Select Whisper for multilingual or
accuracy-first dictation. Only the selected engine is loaded into memory.

`mode = "hold"` records while Right Option is held. With `mode = "toggle"`,
press once to start and again to stop; streaming voice activity detection can
also stop after trailing silence.

## Privacy and Offline Operation

- Audio stays in memory and is never written to disk.
- Transcript history is process-local and is never uploaded.
- Performance history contains numeric timings, not audio or transcript text.
- Normal runtime installs a process-wide outbound socket guard.
- There is no telemetry, analytics, update check, remote transcription API, or
  crash-reporting service.
- A separate, single-use provisioning process is allowed online only after you
  approve a missing-model download.

## Development

Common commands:

```sh
make setup       # validate the Mac and synchronize uv.lock
make lint        # run Ruff
make test        # run deterministic unit tests
make benchmark   # compare cached Whisper and Parakeet models offline
make performance # audit latency, memory growth, and bundle size
make app         # build and ad-hoc sign dist/Vox Terminal.app
make verify      # run all source and frozen-bundle gates
make install     # copy the app to ~/Applications
make release     # create ZIP, checksum, dependency report, and SPDX SBOM
```

Developer CLI commands:

```sh
uv run python -m dictate --no-menubar
uv run python -m dictate --doctor
uv run python -m dictate --download-model
```

The default suite must remain deterministic and offline:

```sh
uv run python -m unittest discover -s tests
```

The real MLX integration is opt-in and requires a cached model:

```sh
DICTATE_RUN_MLX_TESTS=1 uv run python -m unittest tests.test_transcriber
```

The release gates are 500/750 ms p50/p95 inference, 1.5 GiB physical memory,
100 MiB memory growth over 100 dictations, and a 300 MiB app bundle. CI builds
on a hosted macOS arm64 runner from the frozen `uv.lock`.

## Publishing Releases

`pyproject.toml` is the single version source. A `v<version>` tag runs the release
workflow and produces a versioned ZIP, SHA-256 checksum, dependency report, SPDX
2.3 SBOM, and GitHub provenance attestation.

Without Apple credentials, the workflow produces an ad-hoc-signed beta. Developer
ID signing and notarization require all Apple secrets documented in
`.github/workflows/release.yml`; partial configuration fails the release instead
of publishing an ambiguously signed build.
