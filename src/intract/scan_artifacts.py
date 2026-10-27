from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from intract import __version__
from intract.core.artifact import ArtifactKind, infer_artifact_kind
from intract.core.models import ContractRecord, ValidationStatus
from intract.core.signatures import build_signature
from intract.coverage import calculate_coverage
from intract.engine.analyzer import analyze_source_units
from intract.engine.assigner import suggest_contract_for_fragment
from intract.engine.context import LogicalFragment
from intract.engine.scanner import SourceUnit
from intract.parsers.inline import extract_contract_records_from_text, parse_contract_line
from intract.plugins.base import infer_language
from intract.project import load_project_sources
from intract.validators.artifacts import ArtifactValidationReport, validate_artifact
from intract.validators.engine import validate_contract_against_source

SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules", "dist", "build", ".intract", ".pyqual", ".worktrees", ".subactor"}
ARTIFACT_KINDS = {
    ArtifactKind.OPENAPI,
    ArtifactKind.DOCKERFILE,
    ArtifactKind.GITHUB_ACTIONS,
    ArtifactKind.KUBERNETES,
}
INTENT_SCAN_SCHEMA = "intract.scan/v1"
INTENT_SCAN_VERSION = "1.0.0"
_SYMBOL_PREFIX = {
    "function": "fn",
    "method": "method",
    "class": "cls",
    "file": "file",
    "module": "mod",
    "block": "blk",
    "line": "line",
}


@dataclass
class ArtifactScanReport:
    root: str
    artifacts: list[str] = field(default_factory=list)
    reports: list[ArtifactValidationReport] = field(default_factory=list)

    @property
    def violations(self) -> list[ArtifactValidationReport]:
        return [
            report
            for report in self.reports
            if any(result.status.value == "violation" for result in report.results)
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "artifacts_scanned": len(self.artifacts),
            "violations": len(self.violations),
            "artifacts": self.artifacts,
            "reports": [report.to_dict() for report in self.reports],
        }


def _norm_token(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", ".", value.strip().replace("\\", "/")).strip(".")
    return cleaned.lower() or "root"


def make_symbol_id(
    file_path: str,
    scope: str,
    symbol: str | None,
    start_line: int,
    end_line: int,
    contract_id: str = "",
) -> str:
    if contract_id and contract_id.strip():
        return contract_id.strip()
    prefix = _SYMBOL_PREFIX.get(scope, "blk")
    file_token = _norm_token(file_path)
    if symbol and symbol.strip():
        return f"{prefix}.{file_token}.{_norm_token(symbol)}"
    digest = hashlib.sha1(f"{file_path}:{scope}:{start_line}:{end_line}".encode("utf-8")).hexdigest()[:12]
    return f"{prefix}.{file_token}.l{start_line}_{end_line}.{digest}"


def _match_fragment_for_line(
    line_no: int,
    fragments: Sequence[LogicalFragment],
    source_lines: Sequence[str],
) -> LogicalFragment | None:
    best: LogicalFragment | None = None
    for frag in fragments:
        if frag.start_line <= line_no <= frag.end_line:
            if best is None or (frag.end_line - frag.start_line) <= (best.end_line - best.start_line):
                best = frag
        elif line_no < frag.start_line <= line_no + 6:
            between = source_lines[line_no : frag.start_line - 1]
            if all(
                not ln.strip()
                or ln.lstrip().startswith(("#", "//", "/*", "*", "@", "--", ";", "#["))
                for ln in between
            ):
                if best is None or frag.start_line < best.start_line:
                    best = frag
    return best


def _slice_lines(source_lines: Sequence[str], start_line: int, end_line: int) -> str:
    if not source_lines or start_line < 1 or start_line > len(source_lines):
        return ""
    safe_end = max(start_line, min(end_line, len(source_lines)))
    return "\n".join(source_lines[start_line - 1 : safe_end])


def build_intent_scan_row(
    record: ContractRecord,
    *,
    source_text: str | None = None,
    fragments: Sequence[LogicalFragment] = (),
    basis: str = "declared",
    expected_source_hash: str | None = None,
) -> dict[str, Any]:
    sig = build_signature(record)
    scope = record.contract.scope
    file_frags = [f for f in fragments if f.file_path == record.file_path]

    if source_text is None:
        span = {"start_line": record.start_line, "end_line": record.end_line}
        symbol_name: str | None = None
        symbol_kind = scope
        symbol_id = make_symbol_id(
            record.file_path, scope, None, span["start_line"], span["end_line"], record.contract.contract_id
        )
        source_hash: str | None = None
        binding_status = "missing"
        source_verified = False
        val_dict = {
            "status": ValidationStatus.UNKNOWN.value,
            "score": 0.0,
            "missing": ["source_binding:missing"],
            "violations": [],
            "forbidden_effect_violated": False,
        }
    else:
        source_lines = source_text.splitlines()
        if record.start_line < 1 or record.start_line > max(1, len(source_lines)):
            span = {"start_line": record.start_line, "end_line": record.end_line}
            symbol_name = None
            symbol_kind = scope
            symbol_id = make_symbol_id(
                record.file_path, scope, None, span["start_line"], span["end_line"], record.contract.contract_id
            )
            source_hash = None
            binding_status = "missing"
            source_verified = False
            bound_source = ""
        else:
            frag = _match_fragment_for_line(record.start_line, file_frags, source_lines)
            if frag is not None:
                start_ln = min(record.start_line, frag.start_line)
                end_ln = max(record.end_line, frag.end_line)
                span = {"start_line": start_ln, "end_line": end_ln}
                symbol_name = frag.name
                symbol_kind = frag.kind
                bound_source = _slice_lines(source_lines, start_ln, end_ln)
                binding_status = "verified"
                source_verified = True
            elif scope in {"file", "module", "package", "project"}:
                span = {"start_line": 1, "end_line": max(1, len(source_lines))}
                symbol_name = Path(record.file_path).stem
                symbol_kind = scope
                bound_source = source_text
                binding_status = "verified"
                source_verified = True
            elif scope in {"line", "block", "ui"}:
                end_ln = min(len(source_lines), max(record.end_line, record.start_line + 15))
                span = {"start_line": record.start_line, "end_line": end_ln}
                symbol_name = None
                symbol_kind = scope
                bound_source = _slice_lines(source_lines, record.start_line, end_ln)
                binding_status = "verified"
                source_verified = True
            else:
                span = {"start_line": record.start_line, "end_line": record.end_line}
                symbol_name = None
                symbol_kind = scope
                bound_source = _slice_lines(source_lines, record.start_line, record.end_line)
                binding_status = "unknown"
                source_verified = False

            symbol_id = make_symbol_id(
                record.file_path,
                symbol_kind,
                symbol_name,
                span["start_line"],
                span["end_line"],
                record.contract.contract_id,
            )
            source_hash = hashlib.sha256(bound_source.encode("utf-8")).hexdigest()
            if expected_source_hash is not None and expected_source_hash != source_hash:
                binding_status = "stale"
                source_verified = False

        target_source = bound_source if bound_source else source_text
        val_res = validate_contract_against_source(sig, target_source)
        forbidden_violated = any(
            v.kind == "forbidden_effect" or "forbidden" in v.kind.lower() or "forbidden" in v.message.lower()
            for v in val_res.violations
        )
        val_dict = {
            "status": val_res.status.value,
            "score": val_res.score,
            "missing": list(val_res.missing),
            "violations": [
                {"kind": v.kind, "message": v.message, "severity": v.severity}
                for v in val_res.violations
            ],
            "forbidden_effect_violated": forbidden_violated,
        }

    return {
        "file": record.file_path,
        "line": record.start_line,
        "end_line": span["end_line"],
        "span": span,
        "scope": scope,
        "intent": sig.key,
        "priority": record.contract.priority,
        "domain": sig.domain or record.contract.domain,
        "inputs": sorted(sig.inputs),
        "outputs": sorted(sig.outputs),
        "effects": sorted(sig.effects),
        "forbidden": sorted(sig.forbidden),
        "preconditions": sorted(sig.required),
        "validators": sorted(sig.validators),
        "symbol_id": symbol_id,
        "symbol": symbol_name,
        "symbol_kind": symbol_kind,
        "contract_hash": sig.exact_hash,
        "source_hash": source_hash,
        "basis": basis,
        "source_verified": source_verified,
        "source_binding": {
            "status": binding_status,
            "verified": source_verified,
            "symbol": symbol_name,
            "symbol_id": symbol_id,
            "span": span,
            "source_hash": source_hash,
        },
        "validation": val_dict,
    }


@dataclass
class IntentScanArtifact:
    root: str
    rows: list[dict[str, Any]]
    coverage: dict[str, Any]
    summary: dict[str, Any]
    status: str
    failed_closed: bool
    schema: str = INTENT_SCAN_SCHEMA
    version: str = INTENT_SCAN_VERSION
    analyzer_version: str = __version__

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "version": self.version,
            "analyzer_version": self.analyzer_version,
            "root": self.root,
            "status": self.status,
            "failed_closed": self.failed_closed,
            "coverage": self.coverage,
            "summary": self.summary,
            "rows": self.rows,
        }


def build_intent_scan_artifact(
    root: str | Path,
    *,
    include_inferred: bool = False,
    fail_on_forbidden_effects: bool = False,
    expected_source_hashes: Mapping[str, str] | None = None,
    extra_records: Sequence[ContractRecord] = (),
) -> IntentScanArtifact:
    root_path = Path(root)
    if root_path.is_file():
        rel_name = root_path.name
        try:
            sources = {rel_name: root_path.read_text(encoding="utf-8")}
        except UnicodeDecodeError:
            sources = {}
        cov_dict = {
            "files_total": len(sources),
            "files_with_contracts": 0,
            "contracts_total": 0,
            "coverage_percent": 0.0,
            "missing_files": [],
        }
    else:
        sources = load_project_sources(root_path)
        cov_dict = calculate_coverage(root_path).to_dict()

    units = [
        SourceUnit(path=rel_path, language=infer_language(rel_path), text=text)
        for rel_path, text in sorted(sources.items())
    ]
    fragments = analyze_source_units(units)
    expected_map = dict(expected_source_hashes or {})

    rows: list[dict[str, Any]] = []
    bound_fragment_ids: set[str] = set()

    for rel_path, text in sorted(sources.items()):
        records = extract_contract_records_from_text(text, file_path=rel_path)
        for rec in records:
            exp_hash = expected_map.get(f"{rel_path}:{rec.start_line}") or expected_map.get(rel_path)
            row = build_intent_scan_row(
                rec,
                source_text=text,
                fragments=fragments,
                basis="declared",
                expected_source_hash=exp_hash,
            )
            rows.append(row)
            for frag in fragments:
                if (
                    frag.file_path == rel_path
                    and frag.name == row["symbol"]
                    and frag.start_line == row["span"]["start_line"]
                ):
                    bound_fragment_ids.add(frag.id)

    for rec in extra_records:
        text = sources.get(rec.file_path)
        exp_hash = expected_map.get(f"{rec.file_path}:{rec.start_line}") or expected_map.get(rec.file_path)
        rows.append(
            build_intent_scan_row(
                rec,
                source_text=text,
                fragments=fragments,
                basis="declared",
                expected_source_hash=exp_hash,
            )
        )

    if include_inferred:
        for frag in fragments:
            if frag.id in bound_fragment_ids:
                continue
            has_declared_in_span = any(
                r["file"] == frag.file_path
                and r["basis"] == "declared"
                and (
                    frag.start_line <= r["line"] <= frag.end_line
                    or (r["line"] < frag.start_line <= r["line"] + 6)
                )
                for r in rows
            )
            if has_declared_in_span:
                continue
            suggestion = suggest_contract_for_fragment(frag)
            inferred_contract = parse_contract_line(suggestion.contract_line, default_scope=frag.kind)
            if inferred_contract is None:
                continue
            inferred_rec = ContractRecord(
                contract=inferred_contract,
                file_path=frag.file_path,
                start_line=frag.start_line,
                end_line=frag.end_line,
            )
            exp_hash = expected_map.get(f"{frag.file_path}:{frag.start_line}") or expected_map.get(frag.file_path)
            rows.append(
                build_intent_scan_row(
                    inferred_rec,
                    source_text=sources.get(frag.file_path),
                    fragments=fragments,
                    basis="inferred",
                    expected_source_hash=exp_hash,
                )
            )

    if root_path.is_file():
        declared_files = {r["file"] for r in rows if r["basis"] == "declared"}
        cov_dict = {
            "files_total": len(sources),
            "files_with_contracts": len(declared_files),
            "contracts_total": sum(1 for r in rows if r["basis"] == "declared"),
            "coverage_percent": round((len(declared_files) / len(sources) * 100.0), 2) if sources else 0.0,
            "missing_files": sorted(set(sources) - declared_files),
        }

    declared_count = sum(1 for r in rows if r["basis"] == "declared")
    inferred_count = sum(1 for r in rows if r["basis"] == "inferred")
    verified_count = sum(1 for r in rows if r["source_binding"]["status"] == "verified")
    stale_count = sum(1 for r in rows if r["source_binding"]["status"] == "stale")
    missing_count = sum(1 for r in rows if r["source_binding"]["status"] == "missing")
    unknown_count = sum(1 for r in rows if r["source_binding"]["status"] == "unknown")
    forbidden_count = sum(1 for r in rows if r["validation"]["forbidden_effect_violated"])

    if forbidden_count > 0:
        status = ValidationStatus.VIOLATION.value
    elif missing_count > 0 or stale_count > 0:
        status = ValidationStatus.FAIL.value
    elif unknown_count > 0:
        status = ValidationStatus.PARTIAL.value
    elif rows:
        status = ValidationStatus.PASS.value
    else:
        status = ValidationStatus.UNKNOWN.value

    failed_closed = forbidden_count > 0 or (fail_on_forbidden_effects and status in {"violation", "fail"})
    summary = {
        "total_rows": len(rows),
        "declared_rows": declared_count,
        "inferred_rows": inferred_count,
        "verified_bindings": verified_count,
        "stale_bindings": stale_count,
        "missing_bindings": missing_count,
        "unknown_bindings": unknown_count,
        "forbidden_effect_violations": forbidden_count,
    }
    artifact = IntentScanArtifact(
        root=str(root_path),
        rows=rows,
        coverage=cov_dict,
        summary=summary,
        status=status,
        failed_closed=failed_closed,
    )
    if fail_on_forbidden_effects and forbidden_count > 0:
        raise PermissionError(
            f"INTRACT-FORBIDDEN-EFFECT: {forbidden_count} contract(s) violated forbidden effects in {root_path}"
        )
    return artifact


def golden_search_scan_fixtures() -> dict[str, Any]:
    """Return golden scan fixtures for Search and todo2code consumption."""
    sample_source = (
        "# @intract.v1 scope:function intent:validate:permission !p1 domain:security "
        "in:user,token out:bool effect:read forbid:network,secret_leak require:authenticate:token "
        "validate:input_presence,return_value,no_forbidden_effect\n"
        "def verify_permission(user: str, token: str) -> bool:\n"
        "    if not user or not token:\n"
        "        return False\n"
        "    return token.startswith('ok_')\n\n"
        "def helper_unannotated(items: list[str]) -> int:\n"
        "    return len(items)\n"
    )
    violation_source = (
        "# @intract.v1 scope:function intent:sync:remote_state !p1 domain:sync "
        "in:payload out:bool effect:none forbid:network validate:no_forbidden_effect\n"
        "def sync_remote_state(payload: dict) -> bool:\n"
        "    import requests\n"
        "    requests.post('https://example.invalid/sync', json=payload)\n"
        "    return True\n"
    )
    unit = SourceUnit(path="src/auth.py", language="python", text=sample_source)
    frags = analyze_source_units([unit])
    declared_rec = extract_contract_records_from_text(sample_source, file_path="src/auth.py")[0]
    verified_row = build_intent_scan_row(declared_rec, source_text=sample_source, fragments=frags, basis="declared")
    stale_row = build_intent_scan_row(
        declared_rec,
        source_text=sample_source,
        fragments=frags,
        basis="declared",
        expected_source_hash="0" * 64,
    )
    missing_rec = ContractRecord(
        contract=declared_rec.contract,
        file_path="src/deleted.py",
        start_line=10,
        end_line=12,
    )
    missing_row = build_intent_scan_row(missing_rec, source_text=None, fragments=(), basis="declared")
    unknown_rec = ContractRecord(
        contract=declared_rec.contract,
        file_path="src/config.py",
        start_line=1,
        end_line=1,
    )
    unknown_row = build_intent_scan_row(
        unknown_rec,
        source_text="# @intract.v1 scope:function intent:validate:permission\nCONST = 1\n",
        fragments=(),
        basis="declared",
    )
    inferred_frag = [f for f in frags if f.name == "helper_unannotated"][0]
    inferred_suggestion = suggest_contract_for_fragment(inferred_frag)
    inferred_contract = parse_contract_line(inferred_suggestion.contract_line, default_scope="function")
    assert inferred_contract is not None
    inferred_rec = ContractRecord(
        contract=inferred_contract,
        file_path="src/auth.py",
        start_line=inferred_frag.start_line,
        end_line=inferred_frag.end_line,
    )
    inferred_row = build_intent_scan_row(inferred_rec, source_text=sample_source, fragments=frags, basis="inferred")

    v_unit = SourceUnit(path="src/sync.py", language="python", text=violation_source)
    v_frags = analyze_source_units([v_unit])
    v_rec = extract_contract_records_from_text(violation_source, file_path="src/sync.py")[0]
    violation_row = build_intent_scan_row(v_rec, source_text=violation_source, fragments=v_frags, basis="declared")

    return {
        "schema": INTENT_SCAN_SCHEMA,
        "version": INTENT_SCAN_VERSION,
        "verified_row": verified_row,
        "inferred_row": inferred_row,
        "stale_row": stale_row,
        "missing_row": missing_row,
        "unknown_row": unknown_row,
        "forbidden_effect_violation_row": violation_row,
        "search_compatible_rows": [verified_row, inferred_row],
    }


def discover_artifact_paths(root: str | Path) -> list[Path]:
    root = Path(root)
    found: list[Path] = []

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        kind = infer_artifact_kind(str(rel), content)
        if kind in ARTIFACT_KINDS:
            found.append(path)

    return sorted(found, key=lambda item: str(item))


def scan_all_artifacts(root: str | Path) -> ArtifactScanReport:
    root = Path(root)
    artifacts = discover_artifact_paths(root)
    reports = [validate_artifact(path) for path in artifacts]
    return ArtifactScanReport(
        root=str(root),
        artifacts=[str(path.relative_to(root)) for path in artifacts],
        reports=reports,
    )
