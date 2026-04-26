.PHONY: test lint format check release build-css vendor-fonts vendor-apex

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

vendor-fonts:
	@mkdir -p src/net_alpha/web/static/fonts
	curl -sSL -o src/net_alpha/web/static/fonts/Inter-Regular.woff2  https://rsms.me/inter/font-files/Inter-Regular.woff2
	curl -sSL -o src/net_alpha/web/static/fonts/Inter-Medium.woff2   https://rsms.me/inter/font-files/Inter-Medium.woff2
	curl -sSL -o src/net_alpha/web/static/fonts/Inter-SemiBold.woff2 https://rsms.me/inter/font-files/Inter-SemiBold.woff2
	curl -sSL -o src/net_alpha/web/static/fonts/Inter-Bold.woff2     https://rsms.me/inter/font-files/Inter-Bold.woff2
	curl -sSL -o src/net_alpha/web/static/fonts/JetBrainsMono-Regular.woff2 https://github.com/JetBrains/JetBrainsMono/raw/master/fonts/webfonts/JetBrainsMono-Regular.woff2
	curl -sSL -o src/net_alpha/web/static/fonts/JetBrainsMono-Medium.woff2  https://github.com/JetBrains/JetBrainsMono/raw/master/fonts/webfonts/JetBrainsMono-Medium.woff2
