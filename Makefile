# Shortcuts for common tasks. Windows users can run the commands inside each target directly.
PY ?= python

.PHONY: install frontend run dev-api dev-web test lint e2e desktop docker migration sample-data

install:          ## install backend (editable, with dev tools) and frontend dependencies
	cd backend && $(PY) -m pip install -e ".[dev]"
	cd frontend && npm ci

frontend:         ## build the web app into backend/mdos/static
	cd frontend && npm run build

run: frontend     ## run the desktop mode and open the browser
	cd backend && $(PY) -m mdos.desktop

dev-api:          ## API with auto-reload on :8000 (use with dev-web)
	cd backend && uvicorn mdos.main:create_app --factory --reload

dev-web:          ## Vite dev server on :5173, proxying /api to :8000
	cd frontend && npm run dev

test:             ## backend tests and frontend unit tests
	cd backend && $(PY) -m pytest -q
	cd frontend && npm test

lint:             ## ruff, migration drift check and the TypeScript typecheck
	cd backend && ruff check mdos tests
	cd backend && alembic -c alembic.ini upgrade head && alembic -c alembic.ini check && rm -f dev-migrations.db
	cd frontend && npm run typecheck

e2e: frontend     ## end-to-end tests in Chromium against the real server
	cd frontend && npx playwright test

desktop:          ## build the desktop executable for this operating system into dist/
	$(PY) scripts/build_desktop.py

docker:           ## run the cloud stack (app + PostgreSQL); needs .env
	docker compose up --build

migration:        ## create a migration after changing models: make migration m="add column x"
	cd backend && alembic -c alembic.ini revision --autogenerate -m "$(m)"

sample-data:      ## regenerate the synthetic Lake Toba data
	$(PY) scripts/generate_sample_data.py
