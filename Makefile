.PHONY: setup lint test benchmark icon app install clean

setup:
	uv sync --group dev --group build

lint:
	uv run --group dev ruff check .

test:
	uv run python -m unittest discover -s tests

benchmark:
	uv run python scripts/benchmark_latency.py

icon:
	sh scripts/build_icon.sh

app: icon
	uv run --group build pyinstaller --clean --noconfirm VoxTerminal.spec

install: app
	sh scripts/install_app.sh

clean:
	rm -rf build dist
