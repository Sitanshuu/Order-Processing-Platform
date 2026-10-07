.PHONY: help install compile-proto test lint docker-up docker-down clean

help:
	@echo "Available commands:"
	@echo "  make install        Install project dependencies with uv"
	@echo "  make compile-proto  Compile Protocol Buffer definitions into shared/grpc_gen"
	@echo "  make test           Run full test suite with pytest"
	@echo "  make lint           Run ruff linting check"
	@echo "  make docker-up      Start all microservices & databases via docker compose"
	@echo "  make docker-down    Stop all containers and teardown networks"
	@echo "  make clean          Clean up python cache and temporary artifacts"

install:
	uv sync

compile-proto:
	uv run python scripts/compile_proto.py

test:
	uv run pytest -v

lint:
	uv run ruff check .

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down -v

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
