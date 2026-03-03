.PHONY: help build up down logs ps test migrate shell clean

# Default target
help:
	@echo "SIMPA MCP Service - Available commands:"
	@echo "  make build        - Build Docker images"
	@echo "  make up           - Start all services"
	@echo "  make down         - Stop all services"
	@echo "  make logs         - View service logs"
	@echo "  make ps           - Show running containers"
	@echo "  make test         - Run tests"
	@echo "  make migrate      - Run database migrations"
	@echo "  make shell        - Open shell in simpa container"
	@echo "  make clean        - Remove containers and volumes"
	@echo "  make init-db      - Initialize database (run migrations)"
	@echo "  make pull-models  - Pull Ollama models"

# Build Docker images
build:
	docker-compose build

# Start services
up:
	docker-compose up -d

# Stop services
down:
	docker-compose down

# View logs
logs:
	docker-compose logs -f

# Show running containers
ps:
	docker-compose ps

# Run tests
test:
	docker-compose --profile test run --rm testrunner

# Run migrations
migrate:
	docker-compose exec simpa alembic upgrade head

# Initialize database
init-db:
	docker-compose exec simpa python -m src.main --init-db

# Open shell in simpa container
shell:
	docker-compose exec simpa bash

# Open shell in postgres container
db-shell:
	docker-compose exec postgres psql -U simpa -d simpa

# Pull Ollama models
pull-models:
	docker-compose exec ollama ollama pull nomic-embed-text
	docker-compose exec ollama ollama pull llama3.2

# Clean everything
clean:
	docker-compose down -v
	docker system prune -f

# Development setup (build + up + migrate)
dev-setup: build up
	@echo "Waiting for services to be healthy..."
	@sleep 10
	@make migrate
	@echo "SIMPA is ready!"

# Production build
prod-build:
	docker build --target production -t simpa-mcp:prod .

# Run production container
prod-run:
	docker run -d \
		--name simpa-mcp-prod \
		-e DATABASE_URL=$${DATABASE_URL} \
		-e EMBEDDING_PROVIDER=$${EMBEDDING_PROVIDER:-ollama} \
		-e EMBEDDING_MODEL=$${EMBEDDING_MODEL:-nomic-embed-text} \
		-e OLLAMA_BASE_URL=$${OLLAMA_BASE_URL:-http://host.docker.internal:11434} \
		-e LLM_PROVIDER=$${LLM_PROVIDER:-ollama} \
		-e LLM_MODEL=$${LLM_MODEL:-llama3.2} \
		-p 8000:8000 \
		simpa-mcp:prod
