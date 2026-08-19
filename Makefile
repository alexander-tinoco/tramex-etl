# Development shortcuts.
#
# Exists so the same commands CI runs can be run locally without memorizing
# or copying them out of the YAML.

PY := backend/.venv/bin/python
COMPOSE := docker compose

.DEFAULT_GOAL := ayuda

.PHONY: ayuda instalar arriba abajo logs migrar sembrar etl etl-simulacion \
        lint formato tipos test test-backend test-etl test-frontend cobertura \
        verificar limpiar

ayuda:  ## Shows this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

instalar:  ## Installs Python and Node dependencies and the Git hooks
	python3 -m venv backend/.venv
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r backend/requirements.txt -r etl/requirements.txt
	$(PY) -m pip install -e ./shared
	npm install
	cd frontend && npm ci

arriba:  ## Brings up the full development stack
	$(COMPOSE) up -d

abajo:  ## Stops the stack
	$(COMPOSE) down

logs:  ## Follows the API logs
	$(COMPOSE) logs -f backend

migrar:  ## Applies pending migrations
	cd backend && .venv/bin/alembic upgrade head

sembrar:  ## Creates the initial administrator if it doesn't exist
	cd backend && .venv/bin/python -m scripts.sembrar_admin

etl:  ## Loads the file: make etl ARCHIVO=raw-data/TRAMEX.xlsx
	PYTHONPATH=. $(PY) -m etl.etl_tramex $(ARCHIVO)

etl-simulacion:  ## Reports what the load would change without writing anything
	PYTHONPATH=. $(PY) -m etl.etl_tramex $(ARCHIVO) --simulacion

lint:  ## Checks the style of all the code
	python3 -m ruff check backend etl shared
	python3 -m ruff format --check backend etl shared
	cd frontend && npm run lint

formato:  ## Applies the formatter
	python3 -m ruff format backend etl shared
	python3 -m ruff check --fix backend etl shared

tipos:  ## Checks Python and TypeScript types
	$(PY) -m mypy
	cd frontend && npm run typecheck

test-backend:  ## API tests
	$(PY) -m pytest backend/tests -q

test-etl:  ## ETL pipeline tests
	PYTHONPATH=. $(PY) -m pytest etl/tests -q

test-frontend:  ## Dashboard tests
	cd frontend && npm test

test: test-backend test-etl test-frontend  ## All tests

cobertura:  ## Python code coverage, against the project threshold
	PYTHONPATH=. $(PY) -m pytest --cov --cov-report=term-missing

verificar: lint tipos cobertura test-frontend  ## Everything CI requires

limpiar:  ## Deletes caches and build artifacts
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .ruff_cache .mypy_cache .pytest_cache htmlcov .coverage
	rm -rf frontend/dist frontend/.angular
