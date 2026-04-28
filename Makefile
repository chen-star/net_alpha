.PHONY: test lint format check release build-css vendor-fonts vendor-apex vendor-lucide snapshot-test snapshot-update

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

vendor-apex:
	@mkdir -p src/net_alpha/web/static/vendor/apexcharts
	curl -sSL -o src/net_alpha/web/static/vendor/apexcharts/apexcharts.min.js  https://cdn.jsdelivr.net/npm/apexcharts@3.51.0/dist/apexcharts.min.js
	curl -sSL -o src/net_alpha/web/static/vendor/apexcharts/apexcharts.min.css https://cdn.jsdelivr.net/npm/apexcharts@3.51.0/dist/apexcharts.min.css

# UI/UX redesign §5.4 — Lucide v0.469.0 pinned for reproducibility.
# `more-horizontal` was renamed to `ellipsis` in Lucide v0.292; we use the new name.
LUCIDE_VERSION := 0.469.0
LUCIDE_BASE := https://cdn.jsdelivr.net/npm/lucide-static@$(LUCIDE_VERSION)/icons
LUCIDE_ICONS := \
	gauge wallet landmark flask-conical \
	settings \
	arrow-up-right play pencil trash-2 \
	triangle-alert info check lock \
	arrow-up arrow-down move-vertical \
	search chevron-down x ellipsis \
	refresh-cw database download

vendor-lucide:
	@mkdir -p src/net_alpha/web/static/icons
	@for icon in $(LUCIDE_ICONS); do \
		echo "fetching $$icon.svg"; \
		curl -fsSL -o src/net_alpha/web/static/icons/$$icon.svg \
			$(LUCIDE_BASE)/$$icon.svg; \
	done
	@echo "✓ vendored $(words $(LUCIDE_ICONS)) icons to src/net_alpha/web/static/icons/"

snapshot-test:
	uv run pytest tests/web/snapshots -v

snapshot-update:
	uv run pytest tests/web/snapshots --update-snapshots -v
