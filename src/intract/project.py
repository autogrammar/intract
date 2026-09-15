from __future__ import annotations

from collections.abc import Sequence
from fnmatch import fnmatchcase
from pathlib import Path

from intract.core.artifact import ArtifactKind, infer_artifact_kind

from .models import ProjectReport, ValidationResult, ValidationStatus
from .parser import extract_contract_records_from_text
from .parsers.toon import load_toon_records
from .signature import build_signatures
from .validation import validate_contract_against_source, validate_required_contracts
from .yaml_manifest import load_manifest_records

DEFAULT_EXTENSIONS = (
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".java",
    ".cs",
    ".go",
    ".rs",
    ".php",
    ".rb",
    ".sh",
    ".sql",
    ".html",
    ".css",
    ".yaml",
    ".yml",
)
EXTRA_ARTIFACT_KINDS = frozenset({ArtifactKind.DOCKERFILE})
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules", "dist", "build", ".worktrees", ".subactor"}


def is_ignored(rel_path: str, ignore: Sequence[str]) -> bool:
    """Return True when a project-relative POSIX path matches a configured ignore pattern.

    Patterns use ``fnmatch`` semantics on the whole relative path, so ``*`` also
    crosses directory separators (``examples/*/violation/*``). A pattern ending in
    ``/`` or ``/**`` ignores everything below that directory.
    """
    for pattern in ignore:
        normalized = pattern.strip()
        if not normalized:
            continue
        if normalized.endswith("/**"):
            normalized = normalized[:-3]
        if normalized.endswith("/"):
            normalized = normalized[:-1]
        if fnmatchcase(rel_path, normalized) or fnmatchcase(rel_path, f"{normalized}/*"):
            return True
    return False


def load_project_sources(
    root: Path,
    *,
    extensions: tuple[str, ...] = DEFAULT_EXTENSIONS,
    ignore: Sequence[str] = (),
) -> dict[str, str]:
    sources: dict[str, str] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        rel_path = str(rel)
        if ignore and is_ignored(rel.as_posix(), ignore):
            continue
        if path.suffix not in extensions:
            try:
                preview = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if infer_artifact_kind(rel_path, preview) not in EXTRA_ARTIFACT_KINDS:
                continue
        try:
            sources[rel_path] = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
    return sources


def extract_signatures_from_sources(sources: dict[str, str]):
    records = []
    for file_path, source in sources.items():
        records.extend(
            extract_contract_records_from_text(
                source,
                file_path=file_path,
                default_scope="block",
            )
        )
    return build_signatures(records)


def _validate_observed_signatures(
    observed_signatures,
    sources: dict[str, str],
) -> list[ValidationResult]:
    return [
        validate_contract_against_source(signature, sources.get(signature.file_path, ""))
        for signature in observed_signatures
    ]


def _validate_manifest_signature(required_signature, observed_signatures, sources: dict[str, str]):
    satisfied, missing = validate_required_contracts(required_signature, observed_signatures)
    result = validate_contract_against_source(
        required_signature,
        sources.get(required_signature.file_path, ""),
    )
    if missing:
        result.status = ValidationStatus.PARTIAL if satisfied else ValidationStatus.FAIL
        result.missing.extend(f"require:{item}" for item in missing)
    result.matched["satisfied_requirements"] = satisfied
    result.evidence["manifest_contract"] = True
    return result


def _validate_manifest_signatures(
    manifest_records,
    observed_signatures,
    sources: dict[str, str],
) -> list[ValidationResult]:
    return [
        _validate_manifest_signature(required_signature, observed_signatures, sources)
        for required_signature in build_signatures(manifest_records)
    ]


def _project_status(results: list[ValidationResult]) -> ValidationStatus:
    if any(item.status == ValidationStatus.VIOLATION for item in results):
        return ValidationStatus.VIOLATION
    if results and all(item.status == ValidationStatus.PASS for item in results):
        return ValidationStatus.PASS
    if any(item.status in {ValidationStatus.PASS, ValidationStatus.PARTIAL} for item in results):
        return ValidationStatus.PARTIAL
    if results:
        return ValidationStatus.FAIL
    return ValidationStatus.UNKNOWN


def validate_sources(sources: dict[str, str], *, manifest_records=None) -> ProjectReport:
    observed_signatures = extract_signatures_from_sources(sources)
    results = _validate_observed_signatures(observed_signatures, sources)

    if manifest_records:
        results.extend(
            _validate_manifest_signatures(manifest_records, observed_signatures, sources)
        )

    return ProjectReport(project_path="<sources>", status=_project_status(results), results=results)


def validate_project(
    root: Path | str,
    *,
    manifest_path: Path | str | None = None,
    ignore: Sequence[str] = (),
) -> ProjectReport:
    project_root = Path(root)
    sources = load_project_sources(project_root, ignore=ignore)
    manifest_records = []
    
    if manifest_path:
        path = Path(manifest_path)
        if path.suffix == ".toon":
            manifest_records = load_toon_records(path)
        else:
            manifest_records = load_manifest_records(path)
    else:
        # Search candidates
        candidates = [
            ("intract.toon", "toon"),
            ("intent.toon", "toon"),
            ("intract.toon.yaml", "yaml"),
            ("intract.yaml", "yaml"),
            ("intent.yaml", "yaml"),
            (".intract.yaml", "yaml"),
        ]
        for name, kind in candidates:
            path = project_root / name
            if path.exists():
                if kind == "toon":
                    manifest_records = load_toon_records(path)
                else:
                    manifest_records = load_manifest_records(path)
                break
                
    report = validate_sources(sources, manifest_records=manifest_records)
    report.project_path = str(project_root)
    return report
