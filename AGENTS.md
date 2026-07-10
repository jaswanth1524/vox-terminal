# Repository Guidelines

## Project Structure & Module Organization

Vox Terminal is a Python 3.11, Apple-Silicon macOS menu-bar app. Keep the layout predictable:

- `dictate/` contains the app controller, audio, transcription, injection, configuration, and UI modules.
- `tests/` mirrors behavior with deterministic `unittest` coverage; audio fixtures live in `tests/fixtures/`.
- `assets/` contains app artwork, while `scripts/` contains setup, packaging, and benchmark helpers.

Keep implementation out of the repository root except for standard entry points such as `Makefile`, `pyproject.toml`, and the app bundle spec.

## Build, Test, and Development Commands

- `make setup` synchronizes runtime, lint, and app-build dependencies with `uv`.
- `make lint` runs Ruff without rewriting files.
- `make test` runs the complete unit suite.
- `make app` builds `dist/Vox Terminal.app`; `make install` copies and ad-hoc signs it in `~/Applications`.
- `uv run python -m dictate --no-menubar` runs the foreground debugging service.

## Coding Style & Naming Conventions

Use four-space indentation, Python type hints, `snake_case` functions/modules, and `PascalCase` classes. Keep UI code on the macOS main thread and isolate system/ML dependencies behind injectable interfaces. Run Ruff before submitting changes.

## Testing Guidelines

Name tests `tests/test_<behavior>.py`. Mock microphones, keyboard listeners, model backends, network calls, and macOS services. The default suite must remain offline and deterministic; MLX integration is opt-in with `DICTATE_RUN_MLX_TESTS=1`.

## Commit & Pull Request Guidelines

History uses Conventional Commit-style subjects such as `feat: add VAD auto-stop`. Keep subjects concise and imperative. Pull requests need a summary, validation commands, linked issues when relevant, and screenshots or terminal evidence for user-visible changes.

## Security & Configuration Tips

Never commit recordings, transcripts, credentials, model caches, `.venv`, `build/`, or `dist/`. Normal runtime must stay offline; network access is allowed only after explicit user action for model provisioning or benchmarking. Preserve the existing config path and migration behavior.
