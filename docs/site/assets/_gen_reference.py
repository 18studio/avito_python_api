from __future__ import annotations

import importlib
import inspect
from enum import Enum
from pathlib import Path
from urllib.parse import quote

import mkdocs_gen_files

from avito.core.domain import AsyncDomainObject, DomainObject
from avito.core.swagger_discovery import discover_swagger_bindings
from avito.core.swagger_linter import lint_swagger_bindings
from avito.core.swagger_registry import load_swagger_registry
from avito.core.swagger_report import build_swagger_binding_report

EXCLUDED_PACKAGES = {"auth", "core", "testing"}
PACKAGE_ROOT = Path("avito")
GITHUB_API_URL = "https://github.com/p141592/avito_python_api/blob/main/docs/avito/api"


def public_domain_packages() -> list[str]:
    return sorted(
        path.parent.name
        for path in (*PACKAGE_ROOT.glob("*/domain.py"), *PACKAGE_ROOT.glob("*/async_domain.py"))
        if path.parent.name not in EXCLUDED_PACKAGES
    )


def package_title(package: str) -> str:
    return package


def public_enums(package: str) -> list[type[Enum]]:
    module = importlib.import_module(f"avito.{package}")
    names = getattr(module, "__all__", ())
    enums: list[type[Enum]] = []
    for name in names:
        value = getattr(module, name, None)
        if inspect.isclass(value) and issubclass(value, Enum):
            enums.append(value)
    return enums


def public_domain_classes(package: str) -> list[type[DomainObject]]:
    modules = []
    for suffix in ("domain", "async_domain"):
        try:
            modules.append(importlib.import_module(f"avito.{package}.{suffix}"))
        except ModuleNotFoundError:
            continue
    classes: list[type[DomainObject]] = []
    for module in modules:
        for _, value in inspect.getmembers(module, inspect.isclass):
            if value.__module__ != module.__name__:
                continue
            if value in {DomainObject, AsyncDomainObject}:
                continue
            if issubclass(value, DomainObject | AsyncDomainObject):
                classes.append(value)
    return classes


def public_domain_methods(domain_class: type[DomainObject]) -> list[str]:
    methods: list[str] = []
    for name, value in inspect.getmembers(domain_class, predicate=inspect.isfunction):
        if name.startswith("_"):
            continue
        if value.__qualname__.startswith(f"{domain_class.__name__}."):
            methods.append(name)
    return methods


def write_domain_pages(packages: list[str]) -> list[str]:
    pages: list[str] = []
    for package in packages:
        page = f"reference/domains/{package}.md"
        pages.append(page)
        enums = public_enums(package)
        with mkdocs_gen_files.open(page, "w") as file:
            file.write(f"# {package}\n\n")
            file.write(f"Публичный доменный пакет SDK: `{package_title(package)}`.\n\n")
            if enums:
                file.write("## Enum\n\n")
                for enum_class in enums:
                    file.write(f"- [`{enum_class.__name__}`](../enums.md#{enum_class.__name__})\n")
                file.write("\n")
            for domain_class in public_domain_classes(package):
                file.write(f"::: {domain_class.__module__}.{domain_class.__name__}\n\n")
        mkdocs_gen_files.set_edit_path(page, Path(f"avito/{package}/__init__.py"))
    return pages


def write_operations(report: dict[str, object]) -> None:
    operations = report["operations"]
    if not isinstance(operations, list):
        raise TypeError("Swagger binding report operations must be a list.")

    with mkdocs_gen_files.open("reference/operations.md", "w") as file:
        file.write("# Методы API\n\n")
        file.write(
            "Страница строится из Swagger operation bindings и связывает каждую "
            "upstream-операцию с публичным SDK-методом. Подробные сигнатуры, модели "
            "и docstring-контракты находятся на страницах доменных пакетов.\n\n"
        )
        file.write("| Spec | HTTP | Path | SDK method | Deprecated |\n")
        file.write("|---|---|---|---|---|\n")
        for operation in operations:
            if not isinstance(operation, dict):
                raise TypeError("Swagger binding report operation entry must be an object.")
            binding = operation["binding"]
            sdk_method = ""
            if isinstance(binding, dict):
                sdk_method = str(binding["sdk_method"])
            file.write(
                f"| `{operation['spec']}` | `{operation['method']}` | "
                f"`{operation['path']}` | `{sdk_method}` | "
                f"{'yes' if operation['deprecated'] else 'no'} |\n"
            )


def write_coverage(report: dict[str, object]) -> None:
    summary = report["summary"]
    operations = report["operations"]
    if not isinstance(summary, dict):
        raise TypeError("Swagger binding report summary must be an object.")
    if not isinstance(operations, list):
        raise TypeError("Swagger binding report operations must be a list.")

    specs: dict[str, dict[str, int]] = {}
    for operation in operations:
        if not isinstance(operation, dict):
            raise TypeError("Swagger binding report operation entry must be an object.")
        spec = str(operation["spec"])
        spec_summary = specs.setdefault(spec, {"total": 0, "bound": 0, "deprecated": 0})
        spec_summary["total"] += 1
        if operation["status"] == "bound":
            spec_summary["bound"] += 1
        if operation["deprecated"]:
            spec_summary["deprecated"] += 1

    with mkdocs_gen_files.open("reference/coverage.md", "w") as file:
        file.write("# Покрытие API\n\n")
        file.write(
            "Swagger/OpenAPI-спецификации в `docs/avito/api/` остаются источником "
            "истины, а карта покрытия SDK строится из Swagger operation bindings "
            "на публичных SDK-методах.\n\n"
        )
        file.write(
            f"SDK покрывает {summary['bound']} из {summary['operations_total']} "
            f"операций Avito API. Deprecated operations: "
            f"{summary['deprecated_operations']}.\n\n"
        )
        file.write("!!! info \"Источник данных\"\n")
        file.write(
            "    Страница генерируется из JSON-compatible Swagger binding report, "
            "который строится из локальных specs и binding discovery.\n\n"
        )
        file.write("| Документ API | Операции | Bound | Deprecated | Swagger/OpenAPI |\n")
        file.write("|---|---:|---:|---:|---|\n")
        for spec, spec_summary in sorted(specs.items()):
            quoted_spec = quote(spec)
            file.write(
                f"| `{spec}` | {spec_summary['total']} | {spec_summary['bound']} | "
                f"{spec_summary['deprecated']} | "
                f"[{spec}]({GITHUB_API_URL}/{quoted_spec}) |\n"
            )
        file.write("\nПубличная карта операций: [Методы API](operations.md).\n")


def write_api_report(report: dict[str, object]) -> None:
    summary = report["summary"]
    operations = report["operations"]
    bindings = report["bindings"]
    errors = report["errors"]
    if not isinstance(summary, dict):
        raise TypeError("Swagger binding report summary must be an object.")
    if not isinstance(operations, list):
        raise TypeError("Swagger binding report operations must be a list.")
    if not isinstance(bindings, list):
        raise TypeError("Swagger binding report bindings must be a list.")
    if not isinstance(errors, list):
        raise TypeError("Swagger binding report errors must be a list.")

    specs: dict[str, dict[str, int]] = {}
    deprecated_operations: list[dict[str, object]] = []
    for operation in operations:
        if not isinstance(operation, dict):
            raise TypeError("Swagger binding report operation entry must be an object.")
        spec = str(operation["spec"])
        spec_summary = specs.setdefault(
            spec,
            {"total": 0, "bound": 0, "unbound": 0, "duplicate": 0, "deprecated": 0},
        )
        spec_summary["total"] += 1
        status = str(operation["status"])
        if status in {"bound", "unbound", "duplicate"}:
            spec_summary[status] += 1
        if operation["deprecated"]:
            spec_summary["deprecated"] += 1
            deprecated_operations.append(operation)

    operations_total = int(summary["operations_total"])
    bound = int(summary["bound"])
    coverage_percent = 100.0 if operations_total == 0 else bound / operations_total * 100
    strict_passed = (
        bound == operations_total
        and int(summary["unbound"]) == 0
        and int(summary["duplicate"]) == 0
        and int(summary["ambiguous"]) == 0
        and not errors
    )

    with mkdocs_gen_files.open("reference/api-report.md", "w") as file:
        file.write("# Отчёт покрытия API\n\n")
        file.write(
            "Страница строится при сборке документации из strict Swagger binding "
            "report. Она показывает полноту связи между upstream Swagger operations "
            "и публичными SDK methods.\n\n"
        )
        file.write("## Summary\n\n")
        file.write("| Метрика | Значение |\n")
        file.write("|---|---:|\n")
        file.write(f"| Swagger specs | {summary['specs']} |\n")
        file.write(f"| Operations total | {operations_total} |\n")
        file.write(f"| Bound operations | {bound} |\n")
        file.write(f"| Unbound operations | {summary['unbound']} |\n")
        file.write(f"| Duplicate operation bindings | {summary['duplicate']} |\n")
        file.write(f"| Ambiguous bindings | {summary['ambiguous']} |\n")
        file.write(f"| Deprecated operations | {summary['deprecated_operations']} |\n")
        file.write(f"| Validation errors | {len(errors)} |\n")
        file.write(f"| Coverage | {coverage_percent:.1f}% |\n")
        file.write(f"| Strict gate | {'passed' if strict_passed else 'failed'} |\n\n")

        file.write("## Локальная проверка\n\n")
        file.write("```bash\n")
        file.write("make swagger-coverage\n")
        file.write("poetry run python scripts/download_avito_api_specs.py --clean\n")
        file.write("poetry run python scripts/lint_swagger_bindings.py --json --strict\n")
        file.write("```\n\n")

        file.write("## Coverage By Spec\n\n")
        file.write("| Документ API | Operations | Bound | Unbound | Duplicate | Deprecated |\n")
        file.write("|---|---:|---:|---:|---:|---:|\n")
        for spec, spec_summary in sorted(specs.items()):
            file.write(
                f"| `{spec}` | {spec_summary['total']} | {spec_summary['bound']} | "
                f"{spec_summary['unbound']} | {spec_summary['duplicate']} | "
                f"{spec_summary['deprecated']} |\n"
            )

        file.write("\n## Deprecated Operations\n\n")
        if deprecated_operations:
            file.write("| Spec | HTTP | Path | SDK method |\n")
            file.write("|---|---|---|---|\n")
            for operation in deprecated_operations:
                binding = operation["binding"]
                sdk_method = ""
                if isinstance(binding, dict):
                    sdk_method = str(binding["sdk_method"])
                file.write(
                    f"| `{operation['spec']}` | `{operation['method']}` | "
                    f"`{operation['path']}` | `{sdk_method}` |\n"
                )
        else:
            file.write("Deprecated operations не найдены.\n")

        file.write("\n## Validation Errors\n\n")
        if errors:
            file.write("| Code | Operation | SDK method | Message |\n")
            file.write("|---|---|---|---|\n")
            for error in errors:
                if not isinstance(error, dict):
                    raise TypeError("Swagger binding report error entry must be an object.")
                file.write(
                    f"| `{error['code']}` | `{error['operation_key']}` | "
                    f"`{error['sdk_method']}` | {error['message']} |\n"
                )
        else:
            file.write("Ошибок strict validation нет.\n")


def write_enums(packages: list[str]) -> None:
    with mkdocs_gen_files.open("reference/enums.md", "w") as file:
        file.write("# Enum\n\n")
        file.write("Публичные перечисления из доменных пакетов SDK.\n\n")
        for package in packages:
            enums = public_enums(package)
            if not enums:
                continue
            file.write(f"## {package}\n\n")
            for enum_class in enums:
                file.write(f"### {enum_class.__name__} {{ #{enum_class.__name__} }}\n\n")
                file.write(f"::: avito.{package}.{enum_class.__name__}\n\n")


def write_summary(domain_pages: list[str]) -> None:
    with mkdocs_gen_files.open("reference/SUMMARY.md", "w") as file:
        file.write("* [Reference](index.md)\n")
        file.write("* [Покрытие API](coverage.md)\n")
        file.write("* [Отчёт покрытия API](api-report.md)\n")
        file.write("* [AvitoClient](client.md)\n")
        file.write("* [Конфигурация](config.md)\n")
        file.write("* [Операции API](operations.md)\n")
        file.write("* Домены\n")
        for page in domain_pages:
            name = Path(page).stem
            file.write(f"    * [{name}]({page.removeprefix('reference/')})\n")
        file.write("* [Enum](enums.md)\n")
        file.write("* [Модели](models.md)\n")
        file.write("* [Исключения](exceptions.md)\n")
        file.write("* [Пагинация](pagination.md)\n")
        file.write("* [Тестирование](testing.md)\n")


def ensure_debug_info_exists() -> None:
    from avito import AvitoClient

    debug_info = getattr(AvitoClient, "debug_info", None)
    if debug_info is None or not callable(debug_info):
        raise RuntimeError("AvitoClient.debug_info отсутствует в публичном reference-контракте.")


def main() -> None:
    ensure_debug_info_exists()
    registry = load_swagger_registry()
    discovery = discover_swagger_bindings(registry=registry)
    lint_errors = lint_swagger_bindings(registry, discovery, strict=True)
    if registry.errors or lint_errors:
        raise RuntimeError("Swagger binding report contains validation errors.")
    report = build_swagger_binding_report(registry, discovery).to_dict()

    packages = public_domain_packages()
    domain_pages = write_domain_pages(packages)
    write_coverage(report)
    write_api_report(report)
    write_operations(report)
    write_enums(packages)
    write_summary(domain_pages)


main()
