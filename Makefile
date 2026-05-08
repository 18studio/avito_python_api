-include $(PWD)/.env
export

REGISTRY=10.11.0.9:5000
MKDOCS_ENV=DISABLE_MKDOCS_2_WARNING=true NO_MKDOCS_2_WARNING=1

check: test quality

quality: typecheck lint python-guidelines-lint swagger-lint architecture-lint async-parity-lint docstring-lint build

build: clean
	poetry build

clean:
	rm -rf dist

lock:
	poetry lock

test: 
	poetry run pytest

typecheck:
	poetry run mypy avito

profile: 
	poetry run pytest --profile-svg

fmt:
	poetry run ruff format .

lint:
	poetry run ruff check .

python-guidelines-lint:
	poetry run python scripts/lint_python_guidelines.py

swagger-update:
	poetry run python scripts/download_avito_api_specs.py --clean

swagger-lint:
	poetry run python scripts/lint_swagger_bindings.py --strict

architecture-lint:
	poetry run python scripts/lint_architecture.py

async-parity-lint:
	poetry run python scripts/lint_async_parity.py

docstring-lint:
	poetry run python scripts/lint_docstrings.py

swagger-coverage: swagger-lint
	poetry run pytest tests/core/test_swagger_registry.py tests/contracts/test_swagger_contracts.py

minor: check
	poetry version minor

patch: check
	poetry version patch

major: check
	poetry version major

release:
	poetry publish --no-interaction

docs-serve:
	$(MKDOCS_ENV) poetry run mkdocs serve

docs-strict:
	$(MKDOCS_ENV) poetry run mkdocs build --strict
	poetry run python scripts/lint_swagger_bindings.py --strict
	poetry run python scripts/lint_docstrings.py

docs-build: docs-strict

docs-report:
	poetry run python scripts/lint_swagger_bindings.py --json --strict --output swagger-bindings-report.json

docs-check: docs-strict
	ln -sfn . site/avito_python_api
	lychee --root-dir "$(PWD)/site" --exclude "avito\.ru" --exclude "^https://18studio\.github\.io/avito_python_api/" --retry-wait-time 5 --max-retries 3 --timeout 30 site/

qa-docs:
	poetry run pydocstyle \
		avito/client.py avito/config.py \
		avito/core/exceptions.py avito/core/pagination.py \
		avito/*/domain.py \
		avito/testing/fake_transport.py
	poetry run interrogate avito/ --fail-under=0 --quiet
