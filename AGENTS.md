# Repository Guidelines

## Project Structure & Module Organization

This repository is currently minimal and contains only `LICENSE`. As code is added, keep the top-level layout predictable:

- `src/` for application source code.
- `tests/` for automated tests that mirror the source layout.
- `assets/` for static files such as images, fixtures, or sample data.
- `docs/` for design notes, API references, and longer contributor documentation.

Avoid placing implementation files at the repository root unless they are standard project entry points, such as `Makefile`, `package.json`, or `pyproject.toml`.

## Build, Test, and Development Commands

No project-specific build or test commands are defined yet. When adding tooling, document the canonical commands here and in `README.md` if one is introduced. Prefer a small, repeatable command set such as:

- `make test` or the ecosystem equivalent to run the full test suite.
- `make lint` to run format and static-analysis checks.
- `make dev` to start a local development server or watcher.

Until tooling exists, use `git status --short` before and after changes to confirm the working tree contains only intentional edits.

## Coding Style & Naming Conventions

Follow the conventions of the language or framework introduced by the first implementation. Keep formatting automated where possible, and commit the formatter or linter configuration with the code. Use descriptive file and directory names: lowercase with hyphens for documentation files, and the dominant ecosystem convention for source files.

## Testing Guidelines

Add tests alongside new functionality. Prefer test files that clearly identify the unit or behavior under test, such as `tests/test_parser.py`, `parser.test.ts`, or `parser.spec.ts`. Tests should be deterministic, isolated from external services by default, and runnable with one documented command.

## Commit & Pull Request Guidelines

The current history contains only `Initial commit`, so no detailed commit convention is established. Use concise, imperative commit subjects, for example `Add terminal command parser`. Pull requests should include a short summary, validation steps, linked issues when applicable, and screenshots or terminal output for user-visible changes.

## Security & Configuration Tips

Do not commit secrets, local credentials, or generated dependency caches. Add environment examples such as `.env.example` when configuration becomes necessary, and keep real local overrides ignored by Git.
