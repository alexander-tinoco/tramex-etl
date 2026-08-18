# Atajos de desarrollo.
#
# Existe para que las mismas ordenes que corre la integracion continua se
# puedan ejecutar en local sin memorizarlas ni copiarlas del YAML.

PY := backend/.venv/bin/python
COMPOSE := docker compose

.DEFAULT_GOAL := ayuda

.PHONY: ayuda instalar arriba abajo logs migrar sembrar etl etl-simulacion \
        lint formato tipos test test-backend test-etl test-frontend cobertura \
        verificar limpiar

ayuda:  ## Muestra esta ayuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

instalar:  ## Instala dependencias de Python, Node y los hooks de Git
	python3 -m venv backend/.venv
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r backend/requirements.txt -r etl/requirements.txt
	$(PY) -m pip install -e ./shared
	npm install
	cd frontend && npm ci

arriba:  ## Levanta todo el stack de desarrollo
	$(COMPOSE) up -d

abajo:  ## Detiene el stack
	$(COMPOSE) down

logs:  ## Sigue los logs de la API
	$(COMPOSE) logs -f backend

migrar:  ## Aplica las migraciones pendientes
	cd backend && .venv/bin/alembic upgrade head

sembrar:  ## Crea el administrador inicial si no existe
	cd backend && .venv/bin/python -m scripts.sembrar_admin

etl:  ## Carga el archivo: make etl ARCHIVO=raw-data/TRAMEX.xlsx
	PYTHONPATH=. $(PY) -m etl.etl_tramex $(ARCHIVO)

etl-simulacion:  ## Informa que cambiaria la carga sin escribir nada
	PYTHONPATH=. $(PY) -m etl.etl_tramex $(ARCHIVO) --simulacion

lint:  ## Revisa el estilo de todo el codigo
	python3 -m ruff check backend etl shared
	python3 -m ruff format --check backend etl shared
	cd frontend && npm run lint

formato:  ## Aplica el formateador
	python3 -m ruff format backend etl shared
	python3 -m ruff check --fix backend etl shared

tipos:  ## Verifica los tipos de Python y TypeScript
	$(PY) -m mypy
	cd frontend && npm run typecheck

test-backend:  ## Pruebas de la API
	$(PY) -m pytest backend/tests -q

test-etl:  ## Pruebas del pipeline ETL
	PYTHONPATH=. $(PY) -m pytest etl/tests -q

test-frontend:  ## Pruebas del dashboard
	cd frontend && npm test

test: test-backend test-etl test-frontend  ## Todas las pruebas

cobertura:  ## Cobertura del codigo Python, con el umbral del proyecto
	PYTHONPATH=. $(PY) -m pytest --cov --cov-report=term-missing

verificar: lint tipos cobertura test-frontend  ## Todo lo que exige la CI

limpiar:  ## Borra cachés y artefactos de compilacion
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .ruff_cache .mypy_cache .pytest_cache htmlcov .coverage
	rm -rf frontend/dist frontend/.angular
