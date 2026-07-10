.PHONY: setup lint test benchmark icon app install clean

setup:
	uv sync --group dev --group build

lint:
	uv run --group dev ruff check .

test:
	uv run python -m unittest discover -s tests

benchmark:
	uv run --extra benchmark python scripts/benchmark_parakeet.py --audio tests/fixtures/hello_world.wav

icon:
	sh scripts/build_icon.sh

app: icon
	uv run --group build pyinstaller --clean --noconfirm VoxTerminal.spec

install: app
	sh scripts/install_app.sh

clean:
	rm -rf build dist
