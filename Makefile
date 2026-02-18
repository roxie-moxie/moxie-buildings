.PHONY: dev sync test

dev:
	uv run dev

sync:
	uv run sheets-sync

test:
	uv run pytest tests/ -v
