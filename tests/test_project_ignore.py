from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from intract.cli import app
from intract.project import is_ignored, load_project_sources, validate_project

VIOLATION = (
    "# @intract.v1 scope:function intent:auth:check_permission priority:1 domain:security "
    "input:user,resource output:allowed effect:read forbid:network,write "
    "validate:input_presence,output_presence,return_value,no_forbidden_effect "
    'meaning:"Check permission locally without network or writes"\n'
    "import requests\n\n"
    "def check_permission(user, resource):\n"
    "    requests.post('https://example.invalid', json={'user': user})\n"
    "    return True\n"
)


def _project(tmp_path: Path) -> Path:
    fixture = tmp_path / "examples" / "negative" / "violation"
    fixture.mkdir(parents=True)
    (fixture / "auth.py").write_text(VIOLATION, encoding="utf-8")
    (tmp_path / "ok.py").write_text("def ok():\n    return 1\n", encoding="utf-8")
    return tmp_path


def test_is_ignored_matches_globs_and_directories() -> None:
    assert is_ignored("examples/negative/violation/auth.py", ["examples/*/violation/*"])
    assert is_ignored("examples/negative/violation/auth.py", ["examples/negative/"])
    assert is_ignored("examples/negative/violation/auth.py", ["examples/negative/**"])
    assert not is_ignored("src/intract/project.py", ["examples/**"])
    assert not is_ignored("examples/negative/violation/auth.py", ["", "   "])


def test_load_project_sources_skips_ignored_paths(tmp_path: Path) -> None:
    root = _project(tmp_path)
    sources = load_project_sources(root, ignore=["examples/**"])
    assert "ok.py" in sources
    assert not any(path.startswith("examples/") for path in sources)


def test_validate_project_excludes_ignored_violation(tmp_path: Path) -> None:
    root = _project(tmp_path)
    unfiltered = validate_project(root)
    filtered = validate_project(root, ignore=["examples/*/violation/**"])
    unfiltered_files = {result.file_path for result in unfiltered.results}
    filtered_files = {result.file_path for result in filtered.results}
    assert any("violation" in path for path in unfiltered_files if path)
    assert not any("violation" in path for path in filtered_files if path)


def test_load_project_sources_skips_agent_state_dirs(tmp_path: Path) -> None:
    root = _project(tmp_path)
    for state_dir in (".worktrees/ticket-001--x", ".subactor"):
        nested = root / state_dir
        nested.mkdir(parents=True)
        (nested / "auth.py").write_text(VIOLATION, encoding="utf-8")
    sources = load_project_sources(root)
    assert "ok.py" in sources
    assert not any(path.startswith((".worktrees/", ".subactor/")) for path in sources)


def test_load_project_sources_scans_checkout_nested_under_worktrees(tmp_path: Path) -> None:
    root = _project(tmp_path / ".worktrees" / "ticket-009--x" / "checkout")
    sources = load_project_sources(root)
    assert "ok.py" in sources
    assert "examples/negative/violation/auth.py" in sources


def test_check_command_honors_pyproject_ignore(tmp_path: Path) -> None:
    root = _project(tmp_path)
    runner = CliRunner()
    before = runner.invoke(app, ["check", str(root), "--format", "json"])
    (root / "pyproject.toml").write_text(
        "[tool.intract]\nignore = [\"examples/*/violation/**\"]\n", encoding="utf-8"
    )
    after = runner.invoke(app, ["check", str(root), "--format", "json"])
    assert "violation/auth.py" in before.output
    assert "violation/auth.py" not in after.output
