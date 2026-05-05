"""Static checks for reference-facing SDK docstrings."""

from __future__ import annotations

import argparse
import ast
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

GENERIC_DOCSTRING_FRAGMENTS = (
    "Выполняет публичную операцию",
    "Пустой результат возвращается",
)


@dataclass(frozen=True, slots=True)
class DocstringLintError:
    """Single docstring lint violation."""

    path: str
    line: int
    message: str


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(
        description="Проверить reference-facing docstrings SDK.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("."),
        help="Корень репозитория.",
    )
    return parser.parse_args()


def main() -> int:
    """Run docstring lint CLI."""

    args = parse_args()
    errors = lint_docstrings(args.root)
    print(render_report(errors), end="")
    return 1 if errors else 0


def lint_docstrings(root: Path = Path(".")) -> tuple[DocstringLintError, ...]:
    """Return docstring style violations for repository root."""

    normalized_root = root.resolve()
    errors: list[DocstringLintError] = []
    for path in sorted((normalized_root / "avito").glob("*/domain.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for class_node in (node for node in tree.body if isinstance(node, ast.ClassDef)):
            for function_node in (
                node for node in class_node.body if isinstance(node, ast.FunctionDef)
            ):
                docstring = ast.get_docstring(function_node) or ""
                for fragment in GENERIC_DOCSTRING_FRAGMENTS:
                    if fragment not in docstring:
                        continue
                    errors.append(
                        DocstringLintError(
                            path=_relative_path(path, normalized_root),
                            line=function_node.lineno,
                            message=(
                                f"`{class_node.name}.{function_node.name}` uses generic "
                                f"docstring fragment `{fragment}`."
                            ),
                        )
                    )
    return tuple(errors)


def render_report(errors: Sequence[DocstringLintError]) -> str:
    """Render human-readable lint report."""

    lines = [f"Docstring lint: errors={len(errors)}"]
    for error in errors:
        lines.append(f"{error.path}:{error.line}: {error.message}")
    return "\n".join(lines) + "\n"


def _relative_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
