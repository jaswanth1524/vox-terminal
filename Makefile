PERFORMANCE_ITERATIONS ?= 100

.PHONY: setup lint test crash-check benchmark performance icon app install release-check verify release clean

setup:
	sh scripts/bootstrap.sh

lint:
	uv run --frozen --group dev ruff check .

test:
	uv run --frozen python -m unittest discover -s tests

crash-check:
	uv run --frozen python scripts/crash_feedback.py

benchmark:
	uv run --frozen python scripts/benchmark_latency.py

performance:
	uv run --frozen python scripts/performance_audit.py --iterations $(PERFORMANCE_ITERATIONS)

icon:
	sh scripts/build_icon.sh

app: icon
	uv run --frozen --group build pyinstaller --clean --noconfirm VoxTerminal.spec
	sh scripts/sign_app.sh

install: app
	sh scripts/install_app.sh

release-check:
	sh scripts/verify_app.sh

verify: lint test app release-check

release: app release-check
	sh scripts/package_release.sh

clean:
	rm -rf build dist
