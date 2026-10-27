import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from intract.cli import app
from intract.core.models import ContractRecord
from intract.parsers.inline import parse_contract_line
from intract.scan_artifacts import (
    INTENT_SCAN_SCHEMA,
    INTENT_SCAN_VERSION,
    build_intent_scan_artifact,
    build_intent_scan_row,
    discover_artifact_paths,
    golden_search_scan_fixtures,
    scan_all_artifacts,
)


def test_discover_dockerfile(tmp_path: Path):
    (tmp_path / "Dockerfile").write_text("FROM python:3.12-slim\nUSER app\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('x')\n", encoding="utf-8")

    paths = discover_artifact_paths(tmp_path)
    assert any(path.name == "Dockerfile" for path in paths)


def test_scan_all_artifacts_reports_violation(tmp_path: Path):
    (tmp_path / "Dockerfile").write_text("FROM python:latest\n", encoding="utf-8")
    report = scan_all_artifacts(tmp_path)
    assert report.artifacts == ["Dockerfile"]
    assert report.violations


def test_versioned_intent_scan_envelope_and_precise_bindings(tmp_path: Path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    auth_py = src_dir / "auth.py"
    auth_py.write_text(
        "# @intract.v1 scope:function intent:validate:permission !p1 domain:security "
        "in:user,token out:bool effect:read forbid:network,secret_leak require:authenticate:token "
        "validate:input_presence,return_value,no_forbidden_effect\n"
        "def verify_permission(user: str, token: str) -> bool:\n"
        "    if not user or not token:\n"
        "        return False\n"
        "    return token.startswith('ok_')\n\n"
        "def unannotated_helper(items: list[str]) -> int:\n"
        "    return len(items)\n",
        encoding="utf-8",
    )
    (src_dir / "other.py").write_text("def plain() -> int:\n    return 1\n", encoding="utf-8")

    artifact = build_intent_scan_artifact(tmp_path, include_inferred=True)
    envelope = artifact.to_dict()

    assert envelope["schema"] == INTENT_SCAN_SCHEMA
    assert envelope["version"] == INTENT_SCAN_VERSION
    assert envelope["status"] == "pass"
    assert envelope["failed_closed"] is False
    assert envelope["coverage"]["files_total"] == 2
    assert envelope["coverage"]["files_with_contracts"] == 1
    assert envelope["coverage"]["contracts_total"] == 1
    assert envelope["coverage"]["coverage_percent"] == 50.0
    assert envelope["coverage"]["missing_files"] == ["src/other.py"]

    declared = [r for r in envelope["rows"] if r["basis"] == "declared"]
    inferred = [r for r in envelope["rows"] if r["basis"] == "inferred"]
    assert len(declared) == 1
    assert len(inferred) >= 1

    row = declared[0]
    assert row["file"] == "src/auth.py"
    assert row["line"] == 1
    assert row["span"] == {"start_line": 1, "end_line": 6}
    assert row["scope"] == "function"
    assert row["intent"] == "validate.permission"
    assert row["priority"] == 1
    assert row["domain"] == "security"
    assert row["inputs"] == ["token", "user"]
    assert row["outputs"] == ["bool"]
    assert row["effects"] == ["read"]
    assert row["forbidden"] == ["network", "secret_leak"]
    assert row["preconditions"] == ["authenticate.token"]
    assert row["symbol"] == "verify_permission"
    assert row["symbol_kind"] == "function"
    assert row["symbol_id"] == "fn.src.auth.py.verify.permission"
    assert len(row["contract_hash"]) == 64
    assert len(row["source_hash"]) == 64
    assert row["source_verified"] is True
    assert row["source_binding"]["status"] == "verified"
    assert row["validation"]["status"] == "pass"
    assert row["validation"]["forbidden_effect_violated"] is False


def test_distinct_stale_missing_and_unknown_source_bindings(tmp_path: Path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "mod.py").write_text(
        "# @intract.v1 scope:function intent:parse:config !p2 domain:config\n"
        "CONFIG_VERSION = 1\n",
        encoding="utf-8",
    )
    contract = parse_contract_line(
        "# @intract.v1 scope:function intent:parse:config !p2 domain:config",
        default_scope="function",
    )
    assert contract is not None

    missing_rec = ContractRecord(contract=contract, file_path="src/missing.py", start_line=5, end_line=8)
    missing_row = build_intent_scan_row(missing_rec, source_text=None)
    assert missing_row["source_binding"]["status"] == "missing"
    assert missing_row["source_verified"] is False
    assert missing_row["source_hash"] is None

    artifact = build_intent_scan_artifact(
        tmp_path,
        expected_source_hashes={"src/mod.py:1": "f" * 64},
        extra_records=[missing_rec],
    )
    statuses = {r["file"]: r["source_binding"]["status"] for r in artifact.rows}
    assert statuses["src/mod.py"] == "stale"
    assert statuses["src/missing.py"] == "missing"

    artifact_unknown = build_intent_scan_artifact(tmp_path)
    assert artifact_unknown.rows[0]["source_binding"]["status"] == "unknown"
    assert artifact_unknown.rows[0]["source_verified"] is False


def test_fail_closed_on_forbidden_effects_and_cli_options(tmp_path: Path):
    (tmp_path / "bad.py").write_text(
        "# @intract.v1 scope:function intent:sync:remote !p1 domain:net "
        "in:data out:bool forbid:network validate:no_forbidden_effect\n"
        "def sync_remote(data: dict) -> bool:\n"
        "    import requests\n"
        "    requests.post('https://example.invalid', json=data)\n"
        "    return True\n",
        encoding="utf-8",
    )

    with pytest.raises(PermissionError, match="INTRACT-FORBIDDEN-EFFECT"):
        build_intent_scan_artifact(tmp_path, fail_on_forbidden_effects=True)

    runner = CliRunner()
    out_file = tmp_path / "intract-scan.json"
    res = runner.invoke(
        app,
        [
            "scan",
            str(tmp_path),
            "--json",
            "--envelope",
            "--fail-on-forbidden-effects",
            "--output",
            str(out_file),
        ],
    )
    assert res.exit_code == 1
    saved = json.loads(out_file.read_text(encoding="utf-8"))
    assert saved["schema"] == INTENT_SCAN_SCHEMA
    assert saved["failed_closed"] is True
    assert saved["summary"]["forbidden_effect_violations"] == 1


def test_golden_fixtures_for_search_and_todo2code():
    fixtures = golden_search_scan_fixtures()
    assert fixtures["schema"] == INTENT_SCAN_SCHEMA
    assert fixtures["version"] == INTENT_SCAN_VERSION

    verified = fixtures["verified_row"]
    inferred = fixtures["inferred_row"]
    stale = fixtures["stale_row"]
    missing = fixtures["missing_row"]
    unknown = fixtures["unknown_row"]
    violation = fixtures["forbidden_effect_violation_row"]

    assert verified["basis"] == "declared"
    assert verified["source_binding"]["status"] == "verified"
    assert inferred["basis"] == "inferred"
    assert stale["source_binding"]["status"] == "stale"
    assert missing["source_binding"]["status"] == "missing"
    assert unknown["source_binding"]["status"] == "unknown"
    assert violation["validation"]["forbidden_effect_violated"] is True

    for row in fixtures["search_compatible_rows"]:
        assert all(isinstance(row.get(k), str) and row[k] for k in ("file", "intent", "scope", "symbol_id", "contract_hash"))
        assert isinstance(row["inputs"], list)
        assert isinstance(row["outputs"], list)
        assert isinstance(row["effects"], list)
        assert isinstance(row["forbidden"], list)
        assert isinstance(row["preconditions"], list)

