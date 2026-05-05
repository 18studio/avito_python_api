"""Diff-aware interrogate coverage gate."""

from __future__ import annotations

import argparse
import json
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from interrogate.config import InterrogateConfig
from interrogate.coverage import InterrogateCoverage

DEFAULT_NEW_MODULE_BASELINE = 100.0


@dataclass(frozen=True, slots=True)
class CoverageRegression:
    """Docstring coverage regression for a changed module."""

    path: str
    baseline: float
    current: float


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(
        description="Проверить interrogate coverage только для измененных модулей.",
    )
    parser.add_argument(
        "--base-ref",
        default="origin/main",
        help="Git ref, относительно которого определяется список измененных файлов.",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=Path(".interrogate-baseline"),
        help="JSON-файл с baseline coverage по модулям.",
    )
    parser.add_argument(
        "--package",
        default="avito",
        help="Пакет, для которого применяется diff gate.",
    )
    return parser.parse_args()


def main() -> int:
    """Run interrogate diff gate CLI."""

    args = parse_args()
    root = Path.cwd()
    baseline = load_baseline(root / args.baseline)
    changed_modules = changed_python_modules(root, args.base_ref, args.package)

    if not changed_modules:
        print("Interrogate diff gate: changed modules=0, regressions=0")
        return 0

    current = measure_module_coverage(root, changed_modules)
    regressions = find_regressions(changed_modules, baseline, current)
    print(render_report(changed_modules, baseline, current, regressions), end="")
    return 1 if regressions else 0


def load_baseline(path: Path) -> Mapping[str, float]:
    """Load per-module interrogate baseline from JSON."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Некорректный baseline: {path}")
    modules = payload.get("modules")
    if not isinstance(modules, dict):
        raise ValueError(f"В baseline нет объекта modules: {path}")
    return {
        str(module_path): float(score)
        for module_path, score in cast(Mapping[object, object], modules).items()
    }


def changed_python_modules(root: Path, base_ref: str, package: str) -> tuple[str, ...]:
    """Return changed Python modules under package relative to repository root."""

    command = [
        "git",
        "diff",
        "--name-only",
        "--diff-filter=ACMR",
        f"{base_ref}...HEAD",
    ]
    result = subprocess.run(
        command,
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"Не удалось получить diff относительно {base_ref}: {message}")

    package_prefix = f"{package.rstrip('/')}/"
    modules = []
    for raw_path in result.stdout.splitlines():
        path = raw_path.strip()
        module_path = root / path
        if path.startswith(package_prefix) and path.endswith(".py") and module_path.is_file():
            modules.append(path)
    return tuple(sorted(set(modules)))


def measure_module_coverage(root: Path, modules: Sequence[str]) -> Mapping[str, float]:
    """Measure current interrogate coverage for selected modules."""

    paths = [str(root / module_path) for module_path in modules]
    coverage = InterrogateCoverage(
        paths=paths,
        conf=InterrogateConfig(fail_under=0.0),
    )
    results = coverage.get_coverage()

    scores: dict[str, float] = {}
    for file_result in results.file_results:
        module_path = _relative_path(Path(file_result.filename), root)
        scores[module_path] = round(file_result.perc_covered, 0)
    return scores


def find_regressions(
    changed_modules: Sequence[str],
    baseline: Mapping[str, float],
    current: Mapping[str, float],
) -> tuple[CoverageRegression, ...]:
    """Return modules whose current coverage is below baseline."""

    regressions: list[CoverageRegression] = []
    for module_path in changed_modules:
        baseline_score = baseline.get(module_path, DEFAULT_NEW_MODULE_BASELINE)
        current_score = current[module_path]
        if current_score < baseline_score:
            regressions.append(
                CoverageRegression(
                    path=module_path,
                    baseline=baseline_score,
                    current=current_score,
                )
            )
    return tuple(regressions)


def render_report(
    changed_modules: Sequence[str],
    baseline: Mapping[str, float],
    current: Mapping[str, float],
    regressions: Sequence[CoverageRegression],
) -> str:
    """Render human-readable gate report."""

    lines = [
        (
            "Interrogate diff gate: "
            f"changed modules={len(changed_modules)}, regressions={len(regressions)}"
        )
    ]
    for module_path in changed_modules:
        baseline_score = baseline.get(module_path, DEFAULT_NEW_MODULE_BASELINE)
        current_score = current[module_path]
        status = "FAIL" if current_score < baseline_score else "OK"
        lines.append(
            f"{status}: {module_path}: current={current_score:.0f}%, "
            f"baseline={baseline_score:.0f}%"
        )
    return "\n".join(lines) + "\n"


def _relative_path(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
