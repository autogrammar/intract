from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from intract.core.artifact import ArtifactKind, infer_artifact_kind
from intract.validators.artifacts import ArtifactValidationReport, validate_artifact

SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules", "dist", "build", ".intract", ".pyqual", ".worktrees", ".subactor"}
ARTIFACT_KINDS = {
    ArtifactKind.OPENAPI,
    ArtifactKind.DOCKERFILE,
    ArtifactKind.GITHUB_ACTIONS,
    ArtifactKind.KUBERNETES,
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

    def to_dict(self) -> dict:
        return {
            "root": self.root,
            "artifacts_scanned": len(self.artifacts),
            "violations": len(self.violations),
            "artifacts": self.artifacts,
            "reports": [report.to_dict() for report in self.reports],
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
