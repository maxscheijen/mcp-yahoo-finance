UV ?= uv
VERSION ?=

.PHONY: sync test lint format-check build check-dist verify-release bump-patch bump-minor bump-major tag-release

sync:
	$(UV) sync --locked --dev

test:
	$(UV) run pytest

lint:
	$(UV) run ruff check .

format-check:
	$(UV) run ruff format --check .

build:
	$(UV) build

check-dist:
	$(UV)x twine check dist/*

verify-release: sync lint format-check test build check-dist

bump-patch:
	$(UV) version --bump patch

bump-minor:
	$(UV) version --bump minor

bump-major:
	$(UV) version --bump major

tag-release:
	@if [ -z "$(VERSION)" ]; then echo "Usage: make tag-release VERSION=x.y.z"; exit 1; fi
	@if [ "$$($(UV) version --short)" != "$(VERSION)" ]; then echo "pyproject.toml version does not match VERSION=$(VERSION)"; exit 1; fi
	git tag "v$(VERSION)"
