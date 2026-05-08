"""Enforce domain architecture v2 invariants during migration."""

from __future__ import annotations

import argparse
import ast
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

API_DOMAINS = (
    "accounts",
    "ads",
    "autoteka",
    "cpa",
    "jobs",
    "messenger",
    "orders",
    "promotion",
    "ratings",
    "realty",
    "tariffs",
)
LEGACY_FILENAMES = (
    "client.py",
    "mappers.py",
    "enums.py",
    "_client.py",
    "_mappers.py",
    "_mapping.py",
    "_enums.py",
)
LEGACY_USAGE_PATTERNS = ("request_public_model", "mapper=")
DEFAULT_MIGRATION_ALLOWLIST: frozenset[str] = frozenset()
APPROVED_PUBLIC_WRAPPERS = frozenset(
    {
        ("jobs", "Application", "list"),
    }
)
TEXT_FILE_SUFFIXES = frozenset({".py", ".md", ".txt"})
PRODUCTION_CHECK_DIRS = ("avito",)
SOURCE_CHECK_DIRS = ("avito", "tests", "docs")
DATE_LIKE_PARAMETER_MARKERS = frozenset(
    {
        "created_at_from",
        "date",
        "date_end",
        "date_from",
        "date_start",
        "date_time_from",
        "date_time_to",
        "date_to",
        "finish_time",
        "start_time",
        "updated_at_from",
        "updated_from",
        "updated_to",
    }
)
DATE_VALIDATION_CALLS = frozenset(
    {
        "serialize_iso_date",
        "serialize_iso_datetime",
        "validate_iso_date",
        "validate_iso_datetime",
    }
)
DATE_SAFE_ANNOTATION_NAMES = frozenset({"DateInput", "date", "datetime"})
FORBIDDEN_OFFICIAL_ENV_ALIASES = frozenset({"SECRET", "TOKEN", "AVITO_SECRET", "AVITO_TOKEN"})
REQUIRED_AVITO_ERROR_FIELDS = frozenset({"attempt", "method", "endpoint", "request_id"})


@dataclass(frozen=True, slots=True)
class ArchitectureLintError:
    """Single architecture lint violation."""

    code: str
    message: str
    path: str
    line: int = 1

    def to_dict(self) -> dict[str, object]:
        """Return JSON-compatible error data."""

        return {
            "code": self.code,
            "message": self.message,
            "path": self.path,
            "line": self.line,
        }


@dataclass(frozen=True, slots=True)
class OperationModelUse:
    """Model referenced by an OperationSpec field."""

    domain: str
    model_name: str
    field_name: str
    path: Path
    line: int


@dataclass(frozen=True, slots=True)
class ClassInfo:
    """Minimal AST information about a model class."""

    name: str
    bases: frozenset[str]
    methods: frozenset[str]
    path: Path
    line: int


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(
        description="Проверить соблюдение domain architecture v2.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("."),
        help="Корень репозитория.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_report",
        help="Вывести report в JSON.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Записать report в файл вместо stdout.",
    )
    parser.add_argument(
        "--allowlist-domain",
        action="append",
        choices=API_DOMAINS,
        dest="allowlisted_domains",
        help=(
            "API-домен, временно исключённый из migration checks. "
            "По умолчанию разрешены все ещё не переведённые Phase 0 домены."
        ),
    )
    parser.add_argument(
        "--no-default-allowlist",
        action="store_true",
        help="Отключить migration allowlist по умолчанию.",
    )
    return parser.parse_args()


def main() -> int:
    """Run architecture lint CLI."""

    args = parse_args()
    if args.no_default_allowlist:
        allowlisted_domains = frozenset(args.allowlisted_domains or ())
    else:
        allowlisted_domains = DEFAULT_MIGRATION_ALLOWLIST.union(
            frozenset(args.allowlisted_domains or ())
        )

    errors = lint_architecture(args.root, allowlisted_domains=allowlisted_domains)
    report = {
        "summary": {
            "error_count": len(errors),
            "allowlisted_domains": sorted(allowlisted_domains),
        },
        "errors": [error.to_dict() for error in errors],
    }

    if args.json_report:
        output = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    else:
        output = render_text_report(errors, allowlisted_domains=allowlisted_domains)

    if args.output is None:
        print(output, end="")
    else:
        args.output.write_text(output, encoding="utf-8")
    return 1 if errors else 0


def lint_architecture(
    root: Path = Path("."),
    *,
    allowlisted_domains: Iterable[str] = DEFAULT_MIGRATION_ALLOWLIST,
) -> tuple[ArchitectureLintError, ...]:
    """Return architecture lint violations for repository root."""

    normalized_root = root.resolve()
    allowlist = frozenset(allowlisted_domains)
    errors: list[ArchitectureLintError] = []
    errors.extend(_lint_legacy_files(normalized_root, allowlist))
    errors.extend(_lint_legacy_imports(normalized_root, allowlist))
    errors.extend(_lint_legacy_usage(normalized_root, allowlist))
    errors.extend(_lint_runtime_patching(normalized_root))
    errors.extend(_lint_official_env_aliases(normalized_root))
    errors.extend(_lint_public_exception_fields(normalized_root))
    errors.extend(_lint_public_domain_methods(normalized_root, allowlist))
    errors.extend(_lint_operation_models(normalized_root, allowlist))
    return tuple(sorted(errors, key=lambda error: (error.path, error.line, error.code)))


def render_text_report(
    errors: Sequence[ArchitectureLintError],
    *,
    allowlisted_domains: Iterable[str] = DEFAULT_MIGRATION_ALLOWLIST,
) -> str:
    """Render human-readable architecture lint report."""

    allowlist = sorted(allowlisted_domains)
    lines = [
        "Architecture lint: "
        f"errors={len(errors)}, allowlisted_domains={', '.join(allowlist) or '-'}"
    ]
    for error in errors:
        lines.append(f"{error.path}:{error.line}: [{error.code}] {error.message}")
    return "\n".join(lines) + "\n"


def _lint_legacy_files(
    root: Path,
    allowlisted_domains: frozenset[str],
) -> tuple[ArchitectureLintError, ...]:
    errors: list[ArchitectureLintError] = []
    for domain in API_DOMAINS:
        if domain in allowlisted_domains:
            continue
        for filename in LEGACY_FILENAMES:
            path = root / "avito" / domain / filename
            if not path.exists():
                continue
            errors.append(
                ArchitectureLintError(
                    code="ARCH_LEGACY_FILE",
                    message=(
                        f"API-домен `{domain}` не должен содержать legacy файл `{filename}`."
                    ),
                    path=_relative_path(path, root),
                )
            )
    return tuple(errors)


def _lint_legacy_imports(
    root: Path,
    allowlisted_domains: frozenset[str],
) -> tuple[ArchitectureLintError, ...]:
    errors: list[ArchitectureLintError] = []
    for path in _iter_python_files(root, SOURCE_CHECK_DIRS):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            modules: list[tuple[str, int]] = []
            if isinstance(node, ast.ImportFrom) and node.module is not None:
                modules.append((node.module, node.lineno))
            elif isinstance(node, ast.Import):
                modules.extend((alias.name, node.lineno) for alias in node.names)
            for module, line in modules:
                legacy_domain = _legacy_module_domain(module)
                if legacy_domain is None or legacy_domain in allowlisted_domains:
                    continue
                errors.append(
                    ArchitectureLintError(
                        code="ARCH_LEGACY_IMPORT",
                        message=f"Запрещён import legacy module `{module}`.",
                        path=_relative_path(path, root),
                        line=line,
                    )
                )
    return tuple(errors)


def _lint_legacy_usage(
    root: Path,
    allowlisted_domains: frozenset[str],
) -> tuple[ArchitectureLintError, ...]:
    errors: list[ArchitectureLintError] = []
    for path in _iter_text_files(root, SOURCE_CHECK_DIRS):
        relative_path = _relative_path(path, root)
        if _path_domain(path, root) in allowlisted_domains:
            continue
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for pattern in LEGACY_USAGE_PATTERNS:
                if pattern not in line:
                    continue
                errors.append(
                    ArchitectureLintError(
                        code="ARCH_LEGACY_USAGE",
                        message=f"Запрещено legacy usage `{pattern}`.",
                        path=relative_path,
                        line=line_number,
                    )
                )
    return tuple(errors)


def _lint_runtime_patching(root: Path) -> tuple[ArchitectureLintError, ...]:
    errors: list[ArchitectureLintError] = []
    for path in _iter_python_files(root, PRODUCTION_CHECK_DIRS):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = _call_name(node.func)
            if name not in {"setattr", "globals"}:
                continue
            errors.append(
                ArchitectureLintError(
                    code="ARCH_RUNTIME_PATCHING",
                    message=f"Запрещён runtime patching через `{name}(...)`.",
                    path=_relative_path(path, root),
                    line=node.lineno,
                )
            )
    return tuple(errors)


def _lint_official_env_aliases(root: Path) -> tuple[ArchitectureLintError, ...]:
    errors: list[ArchitectureLintError] = []
    for path in _iter_python_files(root, PRODUCTION_CHECK_DIRS):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for class_node in (node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)):
            for assignment in class_node.body:
                if not _is_class_alias_assignment(assignment, "ENV_ALIASES"):
                    continue
                for alias_node in _string_constants(assignment.value):
                    alias = alias_node.value
                    if alias not in FORBIDDEN_OFFICIAL_ENV_ALIASES:
                        continue
                    errors.append(
                        ArchitectureLintError(
                            code="ARCH_FORBIDDEN_ENV_ALIAS",
                            message=(
                                f"Официальный env alias `{alias}` слишком общий; "
                                "используйте доменное имя вроде `AVITO_CLIENT_SECRET`."
                            ),
                            path=_relative_path(path, root),
                            line=alias_node.lineno,
                        )
                    )
    return tuple(errors)


def _lint_public_exception_fields(root: Path) -> tuple[ArchitectureLintError, ...]:
    path = root / "avito" / "core" / "exceptions.py"
    if not path.exists():
        return ()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for class_node in (node for node in tree.body if isinstance(node, ast.ClassDef)):
        if class_node.name != "AvitoError":
            continue
        fields = {
            statement.target.id
            for statement in class_node.body
            if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name)
        }
        errors: list[ArchitectureLintError] = []
        for field_name in sorted(REQUIRED_AVITO_ERROR_FIELDS - fields):
            errors.append(
                ArchitectureLintError(
                    code="ARCH_AVITO_ERROR_FIELD_MISSING",
                    message=f"`AvitoError` должен явно объявлять поле `{field_name}`.",
                    path=_relative_path(path, root),
                    line=class_node.lineno,
                )
            )
        return tuple(errors)
    return (
        ArchitectureLintError(
            code="ARCH_AVITO_ERROR_MISSING",
            message="Не найден базовый public exception `AvitoError`.",
            path=_relative_path(path, root),
        ),
    )


def _lint_public_domain_methods(
    root: Path,
    allowlisted_domains: frozenset[str],
) -> tuple[ArchitectureLintError, ...]:
    errors: list[ArchitectureLintError] = []
    for domain in API_DOMAINS:
        if domain in allowlisted_domains:
            continue
        for path in (
            root / "avito" / domain / "domain.py",
            root / "avito" / domain / "async_domain.py",
        ):
            if not path.exists():
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for class_node in _public_classes(tree):
                for method_node in _public_methods(class_node):
                    if (domain, class_node.name, method_node.name) in APPROVED_PUBLIC_WRAPPERS:
                        continue
                    method_label = f"{class_node.name}.{method_node.name}"
                    for parameter in _optional_positional_parameters(method_node):
                        errors.append(
                            ArchitectureLintError(
                                code="ARCH_PUBLIC_OPTIONAL_POSITIONAL",
                                message=(
                                    f"Public API method `{method_label}` содержит optional "
                                    f"positional parameter `{parameter.arg}`; сделайте его keyword-only."
                                ),
                                path=_relative_path(path, root),
                                line=parameter.lineno,
                            )
                        )
                    for parameter in _date_like_string_parameters(method_node):
                        errors.append(
                            ArchitectureLintError(
                                code="ARCH_PUBLIC_DATE_STRING_UNVALIDATED",
                                message=(
                                    f"Public API method `{method_label}` принимает date-like string "
                                    f"parameter `{parameter.arg}` без явного validation/serialization helper."
                                ),
                                path=_relative_path(path, root),
                                line=parameter.lineno,
                            )
                        )
                    if not _has_swagger_operation(method_node):
                        errors.append(
                            ArchitectureLintError(
                                code="ARCH_PUBLIC_METHOD_UNBOUND",
                                message=f"Public API method `{method_label}` без swagger_operation.",
                                path=_relative_path(path, root),
                                line=method_node.lineno,
                            )
                        )
                    if not _method_uses_operation_executor(method_node):
                        errors.append(
                            ArchitectureLintError(
                                code="ARCH_PUBLIC_METHOD_NO_OPERATION_SPEC",
                                message=f"Public API method `{method_label}` не исполняется через OperationSpec.",
                                path=_relative_path(path, root),
                                line=method_node.lineno,
                            )
                        )
                    if _annotation_is_forbidden_public_return(method_node.returns):
                        errors.append(
                            ArchitectureLintError(
                                code="ARCH_PUBLIC_RETURN_RAW",
                                message=f"Public API method `{method_label}` возвращает dict или Any.",
                                path=_relative_path(path, root),
                                line=method_node.lineno,
                            )
                        )
    return tuple(errors)


def _optional_positional_parameters(
    method_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> tuple[ast.arg, ...]:
    positional_args = tuple(method_node.args.posonlyargs + method_node.args.args)
    positional_args = tuple(arg for arg in positional_args if arg.arg != "self")
    default_count = len(method_node.args.defaults)
    if default_count == 0:
        return ()
    return positional_args[-default_count:]


def _date_like_string_parameters(
    method_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> tuple[ast.arg, ...]:
    if _method_uses_date_validation_helper(method_node):
        return ()
    parameters = tuple(
        arg
        for arg in (
            method_node.args.posonlyargs + method_node.args.args + method_node.args.kwonlyargs
        )
        if arg.arg != "self"
    )
    return tuple(parameter for parameter in parameters if _is_unvalidated_date_string(parameter))


def _method_uses_date_validation_helper(method_node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for node in ast.walk(method_node):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node.func)
        if name in DATE_VALIDATION_CALLS or name.rsplit(".", maxsplit=1)[-1] in DATE_VALIDATION_CALLS:
            return True
    return False


def _is_unvalidated_date_string(parameter: ast.arg) -> bool:
    if parameter.arg not in DATE_LIKE_PARAMETER_MARKERS:
        return False
    if parameter.annotation is None:
        return False
    annotation_names = _annotation_names(parameter.annotation)
    if "str" not in annotation_names:
        return False
    return not bool(annotation_names & DATE_SAFE_ANNOTATION_NAMES)


def _lint_operation_models(
    root: Path,
    allowlisted_domains: frozenset[str],
) -> tuple[ArchitectureLintError, ...]:
    errors: list[ArchitectureLintError] = []
    for domain in API_DOMAINS:
        if domain in allowlisted_domains:
            continue
        classes = _collect_domain_classes(root, domain)
        for use in _collect_operation_model_uses(root, domain):
            class_info = classes.get(use.model_name)
            if class_info is None:
                continue
            if use.field_name == "response_model":
                if "from_payload" not in class_info.methods:
                    errors.append(
                        ArchitectureLintError(
                            code="ARCH_RESPONSE_MODEL_NO_FROM_PAYLOAD",
                            message=(
                                f"Response model `{use.model_name}` из OperationSpec "
                                "не реализует from_payload()."
                            ),
                            path=_relative_path(class_info.path, root),
                            line=class_info.line,
                        )
                    )
                continue
            required_method = "to_params" if use.field_name == "query_model" else "to_payload"
            if required_method in class_info.methods or "RequestModel" in class_info.bases:
                continue
            errors.append(
                ArchitectureLintError(
                    code="ARCH_REQUEST_MODEL_NO_SERIALIZER",
                    message=(
                        f"Request/query model `{use.model_name}` из OperationSpec "
                        f"не реализует {required_method}() и не наследует RequestModel."
                    ),
                    path=_relative_path(class_info.path, root),
                    line=class_info.line,
                )
            )
    return tuple(errors)


def _collect_operation_model_uses(root: Path, domain: str) -> tuple[OperationModelUse, ...]:
    uses: list[OperationModelUse] = []
    for path in _domain_operation_files(root, domain):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not _is_operation_spec_call(node):
                continue
            for keyword in node.keywords:
                if keyword.arg not in {"query_model", "request_model", "response_model"}:
                    continue
                model_name = _model_name(keyword.value)
                if model_name is None:
                    continue
                uses.append(
                    OperationModelUse(
                        domain=domain,
                        model_name=model_name,
                        field_name=keyword.arg,
                        path=path,
                        line=keyword.value.lineno,
                    )
                )
    return tuple(uses)


def _collect_domain_classes(root: Path, domain: str) -> Mapping[str, ClassInfo]:
    classes: dict[str, ClassInfo] = {}
    domain_path = root / "avito" / domain
    if not domain_path.exists():
        return classes
    for path in sorted(domain_path.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            classes[node.name] = ClassInfo(
                name=node.name,
                bases=frozenset(_base_name(base) for base in node.bases),
                methods=frozenset(
                    item.name
                    for item in node.body
                    if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef)
                ),
                path=path,
                line=node.lineno,
            )
    return classes


def _domain_operation_files(root: Path, domain: str) -> tuple[Path, ...]:
    domain_path = root / "avito" / domain
    candidates = [domain_path / "operations.py"]
    operations_dir = domain_path / "operations"
    if operations_dir.exists():
        candidates.extend(sorted(operations_dir.rglob("*.py")))
    return tuple(path for path in candidates if path.exists())


def _public_classes(tree: ast.Module) -> Iterable[ast.ClassDef]:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            yield node


def _public_methods(class_node: ast.ClassDef) -> Iterable[ast.FunctionDef | ast.AsyncFunctionDef]:
    for node in class_node.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and not node.name.startswith("_"):
            yield node


def _has_swagger_operation(method_node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return any(_decorator_name(decorator) == "swagger_operation" for decorator in method_node.decorator_list)


def _method_uses_operation_executor(method_node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for node in ast.walk(method_node):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node.func)
        if name in {"self._execute", "_execute", "OperationExecutor.execute"}:
            return True
        if name.endswith("._execute") or name.endswith(".execute"):
            return True
    return False


def _annotation_is_forbidden_public_return(annotation: ast.expr | None) -> bool:
    if annotation is None:
        return False
    names = _annotation_names(annotation)
    return "dict" in names or "Dict" in names or "Any" in names or "typing.Any" in names


def _annotation_names(annotation: ast.expr) -> frozenset[str]:
    names: set[str] = set()
    for node in ast.walk(annotation):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(_attribute_name(node))
    return frozenset(names)


def _is_operation_spec_call(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and _call_name(node.func).endswith("OperationSpec")


def _model_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _decorator_name(node: ast.AST) -> str:
    if isinstance(node, ast.Call):
        return _call_name(node.func)
    return _call_name(node)


def _is_class_alias_assignment(node: ast.AST, name: str) -> bool:
    if isinstance(node, ast.Assign):
        return any(isinstance(target, ast.Name) and target.id == name for target in node.targets)
    if isinstance(node, ast.AnnAssign):
        return isinstance(node.target, ast.Name) and node.target.id == name
    return False


def _string_constants(node: ast.AST | None) -> Iterable[ast.Constant]:
    if node is None:
        return ()
    return (
        child
        for child in ast.walk(node)
        if isinstance(child, ast.Constant) and isinstance(child.value, str)
    )


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return _attribute_name(node)
    return ""


def _attribute_name(node: ast.Attribute) -> str:
    parts = [node.attr]
    value = node.value
    while isinstance(value, ast.Attribute):
        parts.append(value.attr)
        value = value.value
    if isinstance(value, ast.Name):
        parts.append(value.id)
    return ".".join(reversed(parts))


def _base_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Subscript):
        return _base_name(node.value)
    return ""


def _legacy_module_domain(module: str) -> str | None:
    parts = module.split(".")
    if len(parts) != 3:
        return None
    package, domain, name = parts
    if package != "avito" or domain not in API_DOMAINS:
        return None
    if f"{name}.py" not in LEGACY_FILENAMES:
        return None
    return domain


def _path_domain(path: Path, root: Path) -> str | None:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return None
    parts = relative.parts
    if len(parts) < 3 or parts[0] != "avito":
        return None
    domain = parts[1]
    if domain not in API_DOMAINS:
        return None
    return domain


def _iter_python_files(root: Path, directories: Iterable[str]) -> Iterable[Path]:
    for path in _iter_text_files(root, directories):
        if path.suffix == ".py":
            yield path


def _iter_text_files(root: Path, directories: Iterable[str]) -> Iterable[Path]:
    for directory in directories:
        base = root / directory
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file() and path.suffix in TEXT_FILE_SUFFIXES:
                yield path


def _relative_path(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
