# ===========================
# backend/Makefile
# ===========================
"""
.PHONY: help install setup migrate test run celery clean docker-up docker-down

help:
	@echo "Available commands:"
	@echo "  make install    - Install dependencies"
	@echo "  make setup      - Complete setup"
	@echo "  make migrate    - Run database migrations"
	@echo "  make test       - Run tests"
	@echo "  make run        - Run development server"
	@echo "  make celery     - Run Celery worker"
	@echo "  make clean      - Clean temporary files"
	@echo "  make docker-up  - Start Docker services"
	@echo "  make docker-down- Stop Docker services"

install:
	pip install -r requirements.txt

setup:
	bash scripts/setup_complete.sh

migrate:
	alembic upgrade head

test:
	pytest tests/ -v --cov=app --cov-report=html

run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

celery:
	celery -A app.tasks worker --loglevel=info

celery-beat:
	celery -A app.tasks beat --loglevel=info

flower:
	celery -A app.tasks flower --port=5555

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name ".coverage" -delete
	rm -rf htmlcov/
	rm -rf .pytest_cache/

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

format:
	black app/ tests/
	isort app/ tests/

lint:
	flake8 app/ tests/
	mypy app/
"""