ROUTE_PLANNER_DIR := services/ai/route-planner
FRONTEND_DIR := frontend
INFRA_DIR := infrastructure

ifeq ($(OS),Windows_NT)
    VENV_BIN := .venv/Scripts
else
    VENV_BIN := .venv/bin
endif

.PHONY: help install install-backend install-frontend train evaluate run-backend run-frontend validate clean \
        docker-up docker-up-db docker-down docker-build docker-logs docker-clean

help:
	@echo "install            - install backend (route-planner) + frontend dependencies"
	@echo "install-backend    - create venv and install route-planner Python dependencies"
	@echo "install-frontend   - npm install for frontend"
	@echo "train              - run the full route-planner training pipeline (corridors -> data -> train -> evaluate)"
	@echo "evaluate           - re-evaluate the trained model on the held-out test set"
	@echo "run-backend        - run the route-planner FastAPI server locally (http://localhost:8000, Swagger at /docs)"
	@echo "run-frontend       - run the Next.js dev server locally (http://localhost:3000)"
	@echo "validate           - run scenario validation against the route-planner pipeline"
	@echo "clean              - remove venvs, node_modules, caches, and build output"
	@echo ""
	@echo "docker-up          - build and run postgres + backend + frontend in Docker (detached)"
	@echo "docker-up-db       - run only the Postgres container (for local, non-Docker backend dev)"
	@echo "docker-down        - stop and remove the Docker containers"
	@echo "docker-build       - rebuild Docker images"
	@echo "docker-logs        - follow logs from all Docker containers"
	@echo "docker-clean       - stop containers and delete the Postgres data volume"

install: install-backend install-frontend

install-backend:
	cd $(ROUTE_PLANNER_DIR) && python -m venv .venv
	cd $(ROUTE_PLANNER_DIR) && $(VENV_BIN)/pip install --upgrade pip
	cd $(ROUTE_PLANNER_DIR) && $(VENV_BIN)/pip install -r requirements.txt
	cd $(ROUTE_PLANNER_DIR) && test -f .env || cp .env.example .env

install-frontend:
	cd $(FRONTEND_DIR) && npm install

train:
	cd $(ROUTE_PLANNER_DIR) && $(VENV_BIN)/python -m training.synthetic_corridors
	cd $(ROUTE_PLANNER_DIR) && $(VENV_BIN)/python -m training.generate_synthetic_data
	cd $(ROUTE_PLANNER_DIR) && $(VENV_BIN)/python -m training.train_model
	cd $(ROUTE_PLANNER_DIR) && $(VENV_BIN)/python -m training.evaluate_model

evaluate:
	cd $(ROUTE_PLANNER_DIR) && $(VENV_BIN)/python -m training.evaluate_model

run-backend:
	cd $(ROUTE_PLANNER_DIR) && $(VENV_BIN)/python -m uvicorn app.main:app --reload

run-frontend:
	cd $(FRONTEND_DIR) && npm run dev

validate:
	cd $(ROUTE_PLANNER_DIR) && $(VENV_BIN)/python -m scripts.validate_scenarios

clean:
	rm -rf $(ROUTE_PLANNER_DIR)/.venv $(ROUTE_PLANNER_DIR)/app_cache.db
	find $(ROUTE_PLANNER_DIR) -name "__pycache__" -type d -prune -exec rm -rf {} +
	rm -rf $(FRONTEND_DIR)/node_modules $(FRONTEND_DIR)/.next

docker-up:
	cd $(INFRA_DIR) && test -f .env || cp .env.example .env
	cd $(INFRA_DIR) && docker compose up --build -d

docker-up-db:
	cd $(INFRA_DIR) && test -f .env || cp .env.example .env
	cd $(INFRA_DIR) && docker compose up -d postgres

docker-down:
	cd $(INFRA_DIR) && docker compose down

docker-build:
	cd $(INFRA_DIR) && docker compose build

docker-logs:
	cd $(INFRA_DIR) && docker compose logs -f

docker-clean:
	cd $(INFRA_DIR) && docker compose down --volumes
