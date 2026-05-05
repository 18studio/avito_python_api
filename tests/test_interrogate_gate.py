"""Tests for interrogate diff gate helpers."""

from __future__ import annotations

from check_interrogate_gate import find_regressions, render_report


def test_find_regressions_reports_changed_module_below_baseline() -> None:
    """Changed modules below their baseline fail the gate."""

    regressions = find_regressions(
        changed_modules=("avito/client.py", "avito/config.py"),
        baseline={"avito/client.py": 92.0, "avito/config.py": 83.0},
        current={"avito/client.py": 91.0, "avito/config.py": 83.0},
    )

    assert len(regressions) == 1
    assert regressions[0].path == "avito/client.py"


def test_find_regressions_requires_new_modules_to_be_fully_documented() -> None:
    """New modules without a baseline use a full-coverage target."""

    regressions = find_regressions(
        changed_modules=("avito/new_domain/domain.py",),
        baseline={},
        current={"avito/new_domain/domain.py": 99.0},
    )

    assert len(regressions) == 1
    assert regressions[0].baseline == 100.0


def test_render_report_includes_ok_and_fail_statuses() -> None:
    """Gate report lists every changed module with status."""

    report = render_report(
        changed_modules=("avito/client.py", "avito/config.py"),
        baseline={"avito/client.py": 92.0, "avito/config.py": 83.0},
        current={"avito/client.py": 91.0, "avito/config.py": 83.0},
        regressions=(),
    )

    assert "Interrogate diff gate: changed modules=2" in report
    assert "FAIL: avito/client.py: current=91%, baseline=92%" in report
    assert "OK: avito/config.py: current=83%, baseline=83%" in report
