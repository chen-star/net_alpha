.PHONY: test lint format check release build-css

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff format .
	uv run ruff check --fix .

check: lint test

release:
	./scripts/release.sh

build-css:
	uv run tailwindcss \
		-c src/net_alpha/web/tailwind.config.js \
		-i src/net_alpha/web/static/app.src.css \
		-o src/net_alpha/web/static/app.css \
		--minify
