.PHONY: install test lint smoke clean

install:
	pip install -e ".[dev]"

test:
	pytest tests/ -v

lint:
	ruff check src/ tests/
	ruff format --check src/ tests/

format:
	ruff format src/ tests/

smoke:
	pytest tests/ -v -k smoke --run-smoke

clean:
	rm -rf .pytest_cache __pycache__ src/*.egg-info .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} +