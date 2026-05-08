"""Static checks for repository Python guideline rules."""

from __future__ import annotations

import argparse
import ast
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DIRECTORIES = ("avito", "scripts", "docs/site/assets", "tests")
BUILTIN_NAMES = frozenset(
    {
        "all",
        "any",
        "bool",
        "bytes",
        "dict",
        "enumerate",
        "filter",
        "float",
        "format",
        "hash",
        "id",
        "input",
        "int",
        "len",
        "list",
        "map",
        "max",
        "min",
        "next",
        "open",
        "range",
        "reversed",
        "set",
        "sorted",
        "str",
        "sum",
        "tuple",
        "type",
        "zip",
    }
)


@dataclass(slots=True, frozen=True)
class PythonGuidelineError:
    """Single Python guideline violation."""

    path: Path
    line: int
    code: str
    message: str


def main(argv: Sequence[str] | None = None) -> int:
    """Run Python guideline lint CLI."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("paths", nargs="*", type=Path)
    args = parser.parse_args(argv)

    errors = lint_python_guidelines(args.root, paths=args.paths)
    if not errors:
        print("Python guidelines lint: OK")
        return 0
    print(render_errors(errors))
    return 1


def lint_python_guidelines(
    root: Path = Path("."),
    *,
    paths: Sequence[Path] = (),
) -> tuple[PythonGuidelineError, ...]:
    """Return guideline lint violations for Python files."""

    normalized_root = root.resolve()
    errors: list[PythonGuidelineError] = []
    for path in _iter_python_files(normalized_root, paths):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            errors.append(
                PythonGuidelineError(
                    path=path.relative_to(normalized_root),
                    line=exc.lineno or 1,
                    code="PYGUIDE_SYNTAX_ERROR",
                    message=str(exc),
                )
            )
            continue
        visitor = _GuidelineVisitor(path.relative_to(normalized_root))
        visitor.visit(tree)
        errors.extend(visitor.errors)
    return tuple(sorted(errors, key=lambda error: (str(error.path), error.line, error.code)))


def render_errors(errors: Sequence[PythonGuidelineError]) -> str:
    """Render guideline lint errors."""

    lines = [f"Python guidelines lint: errors={len(errors)}"]
    for error in errors:
        lines.append(f"{error.path}:{error.line}: {error.code}: {error.message}")
    return "\n".join(lines)


class _GuidelineVisitor(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.errors: list[PythonGuidelineError] = []
        self._scope_depth = 0
        self._scope_stack: list[str] = []
        self._in_type_checking = 0
        self._loop_depth = 0
        self._with_context_calls: list[ast.Call] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._check_function_defaults(node)
        self._with_scope(node, "function")

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._check_function_defaults(node)
        self._with_scope(node, "function")

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._with_scope(node, "class")

    def visit_Import(self, node: ast.Import) -> None:
        if self._scope_depth > 0 and self._in_type_checking == 0:
            self._add(node, "PYGUIDE_LOCAL_IMPORT", "import должен быть на верхнем уровне модуля.")

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if self._scope_depth > 0 and self._in_type_checking == 0:
            self._add(node, "PYGUIDE_LOCAL_IMPORT", "import должен быть на верхнем уровне модуля.")

    def visit_Try(self, node: ast.Try) -> None:
        for handler in node.handlers:
            self._check_exception_handler(handler)
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        self.generic_visit(node)

    def visit_With(self, node: ast.With) -> None:
        saved_calls = list(self._with_context_calls)
        self._with_context_calls.extend(
            item.context_expr for item in node.items if isinstance(item.context_expr, ast.Call)
        )
        self.generic_visit(node)
        self._with_context_calls = saved_calls

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
        saved_calls = list(self._with_context_calls)
        self._with_context_calls.extend(
            item.context_expr for item in node.items if isinstance(item.context_expr, ast.Call)
        )
        self.generic_visit(node)
        self._with_context_calls = saved_calls

    def visit_Call(self, node: ast.Call) -> None:
        if _call_name(node.func) == "open" and not any(node is call for call in self._with_context_calls):
            self._add(node, "PYGUIDE_BARE_OPEN", "open() должен использоваться через with.")
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self._check_target_names(node.target, node)
        self._loop_depth += 1
        self.generic_visit(node)
        self._loop_depth -= 1

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self._check_target_names(node.target, node)
        self._loop_depth += 1
        self.generic_visit(node)
        self._loop_depth -= 1

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            self._check_target_names(target, node)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if self._current_scope_kind() != "class":
            self._check_target_names(node.target, node)
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self._check_target_names(node.target, node)
        if self._loop_depth > 0 and isinstance(node.op, ast.Add) and _is_stringish_node(node.value):
            self._add(
                node,
                "PYGUIDE_STRING_CONCAT_LOOP",
                "строки в цикле нужно собирать через list + ''.join(...).",
            )
        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare) -> None:
        singleton_names = {"None", "True", "False"}
        if any(_name_of(comparator) in singleton_names for comparator in node.comparators):
            if any(isinstance(operator, ast.Eq | ast.NotEq) for operator in node.ops):
                self._add(
                    node,
                    "PYGUIDE_SINGLETON_COMPARE",
                    "None/True/False нужно сравнивать через is или is not.",
                )
        self.generic_visit(node)

    def visit_Assert(self, node: ast.Assert) -> None:
        if self.path.parts and self.path.parts[0] != "tests":
            self._add(
                node,
                "PYGUIDE_RUNTIME_ASSERT",
                "assert нельзя использовать для runtime validation вне tests.",
            )
        self.generic_visit(node)

    def visit_If(self, node: ast.If) -> None:
        if _is_type_checking_test(node.test):
            self._in_type_checking += 1
            for child in node.body:
                self.visit(child)
            self._in_type_checking -= 1
            for child in node.orelse:
                self.visit(child)
            return
        self.generic_visit(node)

    def _with_scope(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
        kind: str,
    ) -> None:
        self._scope_depth += 1
        self._scope_stack.append(kind)
        self.generic_visit(node)
        self._scope_stack.pop()
        self._scope_depth -= 1

    def _current_scope_kind(self) -> str | None:
        if not self._scope_stack:
            return None
        return self._scope_stack[-1]

    def _check_function_defaults(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        arguments = (*node.args.posonlyargs, *node.args.args)
        defaults = node.args.defaults
        defaulted_args = arguments[len(arguments) - len(defaults) :]
        for argument, default in zip(defaulted_args, defaults, strict=True):
            self._check_default(argument, default)
        for argument, default in zip(node.args.kwonlyargs, node.args.kw_defaults, strict=True):
            if default is not None:
                self._check_default(argument, default)

    def _check_default(self, argument: ast.arg, default: ast.expr) -> None:
        if isinstance(default, ast.List | ast.Dict | ast.Set) or _call_name(default) == "set":
            self._add(
                argument,
                "PYGUIDE_MUTABLE_DEFAULT",
                f"`{argument.arg}` не должен иметь mutable default.",
            )

    def _check_exception_handler(self, handler: ast.ExceptHandler) -> None:
        if handler.type is None:
            self._add(handler, "PYGUIDE_BARE_EXCEPT", "bare except запрещен.")
            return
        exception_name = _exception_name(handler.type)
        if exception_name == "ImportError" and not _is_allowed_import_error_handler(handler):
            self._add(
                handler,
                "PYGUIDE_IMPORT_ERROR_FALLBACK",
                "try/except ImportError разрешен только для optional deps, pytest skip или stdlib fallback.",
            )
        if exception_name in {"Exception", "BaseException"} and not _handler_reraises(handler):
            self._add(
                handler,
                "PYGUIDE_BROAD_EXCEPT_NO_RAISE",
                "broad except должен re-raise после обработки.",
            )

    def _check_target_names(self, target: ast.AST, node: ast.AST) -> None:
        for name in _target_names(target):
            if name in BUILTIN_NAMES:
                self._add(
                    node,
                    "PYGUIDE_BUILTIN_SHADOW",
                    f"`{name}` shadow-ит built-in имя.",
                )

    def _add(self, node: ast.AST, code: str, message: str) -> None:
        self.errors.append(
            PythonGuidelineError(
                path=self.path,
                line=getattr(node, "lineno", 1),
                code=code,
                message=message,
            )
        )


def _iter_python_files(root: Path, paths: Sequence[Path]) -> Iterable[Path]:
    if paths:
        candidates = tuple(path if path.is_absolute() else root / path for path in paths)
    else:
        candidates = tuple(root / directory for directory in DEFAULT_DIRECTORIES)
    for candidate in candidates:
        if candidate.is_file() and candidate.suffix == ".py":
            yield candidate
        elif candidate.is_dir():
            yield from sorted(
                path
                for path in candidate.rglob("*.py")
                if "__pycache__" not in path.parts and ".venv" not in path.parts
            )


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _exception_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Tuple):
        names = {_exception_name(element) for element in node.elts}
        if "Exception" in names:
            return "Exception"
        if "BaseException" in names:
            return "BaseException"
        if "ImportError" in names:
            return "ImportError"
    return ""


def _handler_reraises(handler: ast.ExceptHandler) -> bool:
    return any(isinstance(node, ast.Raise) for node in ast.walk(handler))


def _is_allowed_import_error_handler(handler: ast.ExceptHandler) -> bool:
    body = handler.body
    return any(_assigns_none(node) or _imports_fallback(node) or _calls_pytest_skip(node) for node in body)


def _assigns_none(node: ast.AST) -> bool:
    if not isinstance(node, ast.Assign | ast.AnnAssign):
        return False
    value = node.value
    return isinstance(value, ast.Constant) and value.value is None


def _imports_fallback(node: ast.AST) -> bool:
    return isinstance(node, ast.Import | ast.ImportFrom)


def _calls_pytest_skip(node: ast.AST) -> bool:
    return any(
        isinstance(child, ast.Call)
        and isinstance(child.func, ast.Attribute)
        and isinstance(child.func.value, ast.Name)
        and child.func.value.id == "pytest"
        and child.func.attr == "skip"
        for child in ast.walk(node)
    )


def _target_names(target: ast.AST) -> Iterable[str]:
    if isinstance(target, ast.Name):
        yield target.id
    elif isinstance(target, ast.Tuple | ast.List):
        for element in target.elts:
            yield from _target_names(element)


def _is_stringish_node(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant):
        return isinstance(node.value, str)
    if isinstance(node, ast.JoinedStr):
        return True
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _is_stringish_node(node.left) or _is_stringish_node(node.right)
    return False


def _name_of(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant):
        if node.value is None:
            return "None"
        if node.value is True:
            return "True"
        if node.value is False:
            return "False"
    return None


def _is_type_checking_test(node: ast.AST) -> bool:
    return isinstance(node, ast.Name) and node.id == "TYPE_CHECKING"


if __name__ == "__main__":
    raise SystemExit(main())
