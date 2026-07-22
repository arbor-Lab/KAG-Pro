.PHONY: install install-dev test lint format check pre-commit clean run-notebook

install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"

install-all:
	pip install -e ".[all]"

test:
	pytest tests/ -v

test-cov:
	pytest tests/ -v --cov=src/kag_pro --cov-report=term-missing

lint:
	ruff check src/ tests/

format:
	ruff check --fix src/ tests/
	ruff format src/ tests/

pre-commit:
	pre-commit run --all-files

check: lint test

clean:
	rm -rf data/chroma_db/*
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

run-prototype:
	python -c "from kag_pro.core.pipeline import RAGPipeline; \
	pipeline = RAGPipeline(); \
	pipeline.index_documents('src/kag_pro/data/textbooks'); \
	questions = ['什么是分数？', '1/2 和 1/3 哪个更大？为什么？', '三角形的内角和是多少度？']; \
	[print(f'Q: {q}\nA: {pipeline.query(q)[\"answer\"]}\n---') for q in questions]"
