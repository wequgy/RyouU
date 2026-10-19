.PHONY: run test lint format dev-setup

run:
	uvicorn app.main:app --port 8000 --reload

test:
	pytest services/api/tests tests -q

lint:
	python -m ruff check .

format:
	python -m ruff format .

dev-setup:
	pip install -e "services/api[all]"
