"""MCP tool handlers for Intract."""

from __future__ import annotations

import json
import platform
from pathlib import Path
from typing import Any

from intract.mcp.schemas import TOOL_SCHEMA_INTRACT
from intract import __version__
from intract.check import staged_check
from intract.config import load_config
from intract.duplicates import find_duplicate_contracts
from intract.graph import build_graph
from intract.integrations.vallm import validate_proposal
from intract.policy import decide_policy
from intract.project import validate_project
from intract.scan_artifacts import scan_all_artifacts


def _resolve_path(params: dict[str, Any]) -> Path:
    return Path(str(params.get("path", "."))).resolve()


def _resolve_manifest(root: Path, params: dict[str, Any]) -> Path | None:
    manifest = params.get("manifest")
    if manifest:
        path = Path(str(manifest))
        return path if path.is_absolute() else root / path
    config = load_config(root)
    candidate = root / config.manifest
    return candidate if candidate.exists() else None


def handle_validate_project(params: dict[str, Any]) -> str:
    root = _resolve_path(params)
    if not root.exists():
        return json.dumps(
            {
                "success": False,
                "empty": True,
                "message": f"Project path does not exist: {root}",
                "report": None,
            },
            indent=2,
            ensure_ascii=False,
        )
    manifest = _resolve_manifest(root, params)
    report = validate_project(root, manifest_path=manifest)
    report_dict = report.to_dict()
    status = str(report_dict.get("status") or "unknown")
    total = int((report_dict.get("summary") or {}).get("total") or 0)
    empty = total == 0 or status == "unknown"
    # Fail closed: do not advertise success when no contracts were found/validated.
    success = (not empty) and status == "pass"
    payload: dict[str, Any] = {
        "success": success,
        "empty": empty,
        "report": report_dict,
    }
    if empty:
        payload["message"] = (
            "No Intract contracts found or validation status is unknown"
        )
    elif status != "pass":
        payload["message"] = f"Project validation status is {status}"
    return json.dumps(payload, indent=2, ensure_ascii=False)


def handle_validate_staged(params: dict[str, Any]) -> str:
    root = _resolve_path(params)
    manifest = _resolve_manifest(root, params)
    hunk_filter = bool(params.get("hunks", True))
    report, files, hunks = staged_check(root, manifest=manifest, hunk_filter=hunk_filter)
    config = load_config(root)
    graph = None
    if manifest and "missing_required_p1" in config.fail_on:
        graph = build_graph(root, manifest=manifest)
    decision = decide_policy(
        report,
        fail_on=config.fail_on,
        warn_on=config.warn_on,
        graph=graph,
        manifest_path=manifest,
    )
    payload = {
        "success": not decision.should_fail,
        "report": report.to_dict(),
        "policy": {
            "should_fail": decision.should_fail,
            "reasons": decision.reasons,
            "warnings": decision.warnings,
        },
        "changed_files": files,
        "hunks": [item.to_dict() for item in hunks],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def handle_validate_intent_snippet(params: dict[str, Any]) -> str:
    mapped = validate_proposal(params.get("code", ""), filename=params.get("filename"))
    return json.dumps({"success": mapped.status != "violation", **mapped.to_dict()}, indent=2, ensure_ascii=False)


def handle_find_duplicates(params: dict[str, Any]) -> str:
    root = _resolve_path(params)
    threshold = float(params.get("threshold", 0.84))
    matches = find_duplicate_contracts(root, threshold=threshold)
    payload = {
        "success": True,
        "count": len(matches),
        "duplicates": [item.to_dict() for item in matches],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def handle_build_graph(params: dict[str, Any]) -> str:
    root = _resolve_path(params)
    manifest = _resolve_manifest(root, params)
    graph = build_graph(root, manifest=manifest)
    return json.dumps({"success": True, "graph": graph.to_dict()}, indent=2, ensure_ascii=False)


def handle_scan_artifacts(params: dict[str, Any]) -> str:
    root = _resolve_path(params)
    report = scan_all_artifacts(root)
    payload = report.to_dict()
    payload["success"] = not report.violations
    return json.dumps(payload, indent=2, ensure_ascii=False)


def handle_project_info(_: dict[str, Any]) -> str:
    payload = {
        "server": "intract",
        "version": __version__,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "tools": sorted(TOOL_SCHEMA_INTRACT.keys()),
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


TOOL_HANDLERS = {
    "validate_project": handle_validate_project,
    "validate_staged": handle_validate_staged,
    "validate_intent_snippet": handle_validate_intent_snippet,
    "find_duplicates": handle_find_duplicates,
    "build_graph": handle_build_graph,
    "scan_artifacts": handle_scan_artifacts,
    "project_info": handle_project_info,
}
