.PHONY: run test lint format dev-setup

run:
	uvicorn app.main:app --port 8000 --reload

test:
	python -m pytest tests -q

lint:
	python -m ruff check .

format:
	python -m ruff format .

dev-setup:
	pip install -r requirements-dev.txt
