from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .config import load_config
from .coverage import calculate_coverage
from .duplicates import find_duplicate_contracts
from .engine import EngineConfig, scan_suggest_and_validate
from .check import changed_check, staged_check
from .graph import build_graph
from .integrations.planfile import PlanfileExporter, tickets_from_report
from .parser import extract_contract_records_from_text
from .policy import decide_policy
from .project import validate_project
from .reporters.sarif import report_to_sarif
from .watch import WatchConfig, changes_to_paths, watch_tree
from .yaml_manifest import create_sample_manifest

app = typer.Typer(help="Intract — intent contracts for codebases.")
engine_app = typer.Typer(help="Intract engine: scan, suggest contracts and detect logic drift.")
planfile_app = typer.Typer(help="Planfile ticket export and API sync.")
propose_app = typer.Typer(help="Propose @intract.v1 contracts from deltas or LLM.")
manifest_app = typer.Typer(help="intract.yaml manifest operations.")
app.add_typer(engine_app, name="engine")
app.add_typer(planfile_app, name="planfile")
app.add_typer(propose_app, name="propose")
app.add_typer(manifest_app, name="manifest")
console = Console()


@app.callback(invoke_without_command=True)
def main(version: bool = typer.Option(False, "--version", help="Show version.")):
    if version:
        console.print(f"intract {__version__}")
        raise typer.Exit()


@app.command()
def init(path: Path = typer.Argument(Path(".")), force: bool = typer.Option(False, "--force")):
    """Create a sample intract.yaml manifest."""
    target = path / "intract.yaml"
    if target.exists() and not force:
        console.print(f"[red]File already exists:[/] {target}")
        raise typer.Exit(1)
    target.write_text(create_sample_manifest(), encoding="utf-8")
    console.print(f"[green]Created[/] {target}")


SCAN_SUFFIXES = {
    ".py",
    ".js",
    ".ts",
    ".cs",
    ".java",
    ".go",
    ".rs",
    ".yaml",
    ".yml",
    ".json",
    ".toml",
    ".sh",
    ".sql",
    ".html",
    ".css",
}


def _print_artifact_scan_report(artifact_report) -> None:
    console.print(f"[bold]Artifacts scanned:[/] {len(artifact_report.artifacts)}")
    console.print(f"[bold]Violations:[/] {len(artifact_report.violations)}")
    for report in artifact_report.reports:
        for result in report.results:
            console.print(f"- {report.path}: {result.status.value} {result.contract}")


def _scan_artifacts(path: Path, *, json_output: bool) -> None:
    from .scan_artifacts import scan_all_artifacts

    artifact_report = scan_all_artifacts(path)
    if json_output:
        console.print_json(json.dumps(artifact_report.to_dict(), ensure_ascii=False))
        return
    _print_artifact_scan_report(artifact_report)
    if artifact_report.violations:
        raise typer.Exit(1)


def _is_scan_candidate(path: Path) -> bool:
    return path.suffix in SCAN_SUFFIXES or path.name.lower() == "dockerfile"


def _scan_contract_file(path: Path, *, file_path: str):
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []
    return extract_contract_records_from_text(text, file_path=file_path)


def _scan_inline_records(path: Path):
    if path.is_file():
        return _scan_contract_file(path, file_path=str(path))

    records = []
    for file_path in path.rglob("*"):
        if file_path.is_file() and _is_scan_candidate(file_path):
            records.extend(
                _scan_contract_file(file_path, file_path=str(file_path.relative_to(path)))
            )
    return records


def _scan_row(record) -> dict[str, object]:
    return {
        "file": record.file_path,
        "line": record.start_line,
        "scope": record.contract.scope,
        "intent": record.contract.key,
        "priority": record.contract.priority,
        "domain": record.contract.domain,
    }


def _print_scan_table(data: list[dict[str, object]]) -> None:
    table = Table(title="Intract contracts")
    table.add_column("File")
    table.add_column("Line")
    table.add_column("Scope")
    table.add_column("Intent")
    table.add_column("Priority")
    table.add_column("Domain")
    for item in data:
        table.add_row(
            str(item["file"]),
            str(item["line"]),
            str(item["scope"]),
            str(item["intent"]),
            str(item["priority"]),
            str(item["domain"]),
        )
    console.print(table)


@app.command()
def scan(
    path: Path = typer.Argument(Path(".")),
    json_output: bool = typer.Option(False, "--json"),
    all_artifacts: bool = typer.Option(False, "--all-artifacts", help="Also scan and validate non-code artifacts."),
):
    """Scan files for inline @intract contracts."""
    if all_artifacts:
        _scan_artifacts(path, json_output=json_output)
        return

    data = [_scan_row(record) for record in _scan_inline_records(path)]
    if json_output:
        console.print_json(json.dumps(data, ensure_ascii=False))
        return

    _print_scan_table(data)


@app.command()
def validate(
    path: Path = typer.Argument(Path(".")),
    manifest: Path | None = typer.Option(None, "--manifest"),
    json_output: bool = typer.Option(False, "--json"),
    planfile: bool = typer.Option(False, "--planfile"),
):
    """Validate project contracts."""
    report = validate_project(path, manifest_path=manifest)
    if planfile:
        _export_tickets(path, report)
    if json_output:
        console.print_json(json.dumps(report.to_dict(), ensure_ascii=False))
        return
    _print_validation_report(report)


@app.command()
def check(
    path: Path = typer.Argument(Path(".")),
    staged: bool = typer.Option(False, "--staged", help="Check staged files. Falls back to project if not in git."),
    changed: bool = typer.Option(False, "--changed", help="Check branch diff. Falls back to project if not in git."),
    base: str = typer.Option("main", "--base", help="Base ref for --changed."),
    hunks: bool = typer.Option(False, "--hunks", help="With --staged, validate only contracts touched by hunks."),
    manifest: Path | None = typer.Option(None, "--manifest"),
    fmt: str = typer.Option("text", "--format", help="text|json|sarif"),
    output: Path | None = typer.Option(None, "--output"),
    planfile: bool = typer.Option(False, "--planfile"),
):
    """Policy-aware validation for pre-commit/CI."""
    config = load_config(path)
    manifest_path = manifest
    if manifest_path is None and (Path(path) / config.manifest).exists():
        manifest_path = Path(path) / config.manifest

    files: list[str] = []
    if staged:
        report, files, _hunks = staged_check(path, manifest=manifest_path, hunk_filter=hunks)
        report.project_path = str(path)
    elif changed:
        report, files = changed_check(path, base_ref=base, manifest=manifest_path)
        report.project_path = str(path)
    else:
        report = validate_project(path, manifest_path=manifest_path, ignore=tuple(config.ignore))

    graph = None
    if manifest_path and any(token in config.fail_on for token in ("missing_required_p1",)):
        graph = build_graph(path, manifest=manifest_path)

    decision = decide_policy(
        report,
        fail_on=config.fail_on,
        warn_on=config.warn_on,
        graph=graph,
        manifest_path=manifest_path,
    )

    if planfile:
        _export_tickets(path, report)

    if fmt == "json":
        payload = {"report": report.to_dict(), "policy": decision.__dict__, "changed_files": files}
        text = json.dumps(payload, indent=2, ensure_ascii=False)
    elif fmt == "sarif":
        text = json.dumps(report_to_sarif(report), indent=2, ensure_ascii=False)
    else:
        text = _format_check_text(report, decision, files)

    if output:
        output.write_text(text, encoding="utf-8")
    else:
        console.print(text)

    if decision.should_fail:
        raise typer.Exit(1)


@app.command()
def coverage(path: Path = typer.Argument(Path(".")), json_output: bool = typer.Option(False, "--json")):
    """Show contract coverage for project files."""
    report = calculate_coverage(path)
    if json_output:
        console.print_json(json.dumps(report.to_dict(), ensure_ascii=False))
        return
    console.print(f"Files: {report.files_total}")
    console.print(f"Files with contracts: {report.files_with_contracts}")
    console.print(f"Contracts: {report.contracts_total}")
    console.print(f"Coverage: {report.coverage_percent}%")


@app.command()
def duplicates(
    path: Path = typer.Argument(Path(".")),
    threshold: float = typer.Option(0.84, "--threshold"),
    json_output: bool = typer.Option(False, "--json"),
):
    """Find duplicate/similar intent contracts."""
    duplicates_ = find_duplicate_contracts(path, threshold=threshold)
    data = [d.to_dict() for d in duplicates_]
    if json_output:
        console.print_json(json.dumps(data, ensure_ascii=False))
        return
    table = Table(title="Duplicate intent contracts")
    table.add_column("Score")
    table.add_column("Left")
    table.add_column("Right")
    table.add_column("Files")
    for d in duplicates_:
        table.add_row(str(d.score), d.left_contract, d.right_contract, f"{d.left_file} ↔ {d.right_file}")
    console.print(table)


@app.command()
def graph(
    path: Path = typer.Argument(Path(".")),
    manifest: Path | None = typer.Option(None, "--manifest"),
    fmt: str = typer.Option("text", "--format", help="text|json|mermaid"),
    output: Path | None = typer.Option(None, "--output"),
):
    """Build require/provide graph from contracts."""
    g = build_graph(path, manifest=manifest)
    if fmt == "json":
        text = json.dumps(g.to_dict(), indent=2, ensure_ascii=False)
    elif fmt == "mermaid":
        text = g.to_mermaid()
    else:
        text = f"nodes={len(g.nodes)} edges={len(g.edges)} missing={len(g.missing)}\\n" + "\\n".join(f"- missing: {m}" for m in g.missing)
    if output:
        output.write_text(text, encoding="utf-8")
    else:
        console.print(text)


@app.command()
def tickets(path: Path = typer.Argument(Path(".")), manifest: Path | None = typer.Option(None, "--manifest")):
    """Validate and export failed/partial/violating results as planfile-style tickets."""
    report = validate_project(path, manifest_path=manifest)
    paths = _export_tickets(path, report)
    console.print(f"[bold]Ticket files:[/] {paths}")


@planfile_app.command("push")
def planfile_push(
    path: Path = typer.Argument(Path(".")),
    manifest: Path | None = typer.Option(None, "--manifest"),
    api_url: str | None = typer.Option(None, "--url", envvar="PLANFILE_URL"),
    token: str | None = typer.Option(None, "--token", envvar="PLANFILE_TOKEN"),
    project: str | None = typer.Option(None, "--project", envvar="PLANFILE_PROJECT"),
):
    """Export validation tickets locally and optionally push to a planfile API."""
    from .integrations.planfile_adapter import PlanfileApiAdapter, PlanfileConfig

    report = validate_project(path, manifest_path=manifest)
    adapter = PlanfileApiAdapter(
        PlanfileConfig(url=api_url, token=token, project=project, output_dir=Path(path) / ".intract")
    )
    result = adapter.sync_from_report(report)
    console.print(f"[bold]Pushed:[/] {result.pushed} tickets ({result.remote_status})")
    console.print(f"[bold]Files:[/] {result.local_files}")


@planfile_app.command("pull")
def planfile_pull(
    path: Path = typer.Argument(Path(".")),
    api_url: str | None = typer.Option(None, "--url", envvar="PLANFILE_URL"),
    token: str | None = typer.Option(None, "--token", envvar="PLANFILE_TOKEN"),
    project: str | None = typer.Option(None, "--project", envvar="PLANFILE_PROJECT"),
    json_output: bool = typer.Option(False, "--json"),
):
    """Pull planfile tickets from API or local .intract export."""
    from .integrations.planfile_adapter import PlanfileApiAdapter, PlanfileConfig

    adapter = PlanfileApiAdapter(
        PlanfileConfig(url=api_url, token=token, project=project, output_dir=Path(path) / ".intract")
    )
    tickets_ = adapter.pull()
    if json_output:
        console.print_json(json.dumps([ticket.__dict__ for ticket in tickets_], ensure_ascii=False))
        return
    console.print(f"[bold]Tickets:[/] {len(tickets_)}")


@planfile_app.command("sync")
def planfile_sync(
    path: Path = typer.Argument(Path(".")),
    manifest: Path | None = typer.Option(None, "--manifest"),
    api_url: str | None = typer.Option(None, "--url", envvar="PLANFILE_URL"),
    token: str | None = typer.Option(None, "--token", envvar="PLANFILE_TOKEN"),
    project: str | None = typer.Option(None, "--project", envvar="PLANFILE_PROJECT"),
):
    """Validate project, export tickets, and push to planfile API when configured."""
    from .integrations.planfile_adapter import PlanfileApiAdapter, PlanfileConfig

    report = validate_project(path, manifest_path=manifest)
    adapter = PlanfileApiAdapter(
        PlanfileConfig(url=api_url, token=token, project=project, output_dir=Path(path) / ".intract")
    )
    result = adapter.sync_from_report(report)
    console.print(
        f"[bold]Sync complete:[/] pushed={result.pushed} pulled={result.pulled} "
        f"status={result.remote_status} webhook={result.webhook_status}"
    )


@planfile_app.command("webhook-test")
def planfile_webhook_test(
    webhook_url: str = typer.Option(..., "--url", envvar="PLANFILE_WEBHOOK_URL"),
    secret: str | None = typer.Option(None, "--secret", envvar="PLANFILE_WEBHOOK_SECRET"),
):
    """Send a test webhook payload to verify connectivity."""
    from .integrations.planfile_adapter import PlanfileApiAdapter, PlanfileConfig

    adapter = PlanfileApiAdapter(PlanfileConfig(webhook_url=webhook_url, webhook_secret=secret))
    result = adapter.emit_webhook("ping", {"message": "intract webhook test"})
    console.print(f"[green]Webhook delivered[/] event={result.event} status={result.status_code}")


@planfile_app.command("webhook-apply")
def planfile_webhook_apply(
    path: Path = typer.Argument(Path(".")),
    event_file: Path = typer.Argument(..., help="JSON file with inbound planfile webhook payload"),
):
    """Apply inbound planfile ticket status updates to local .intract export."""
    from .integrations.planfile_adapter import PlanfileApiAdapter, PlanfileConfig

    payload = json.loads(event_file.read_text(encoding="utf-8"))
    adapter = PlanfileApiAdapter(PlanfileConfig(output_dir=Path(path) / ".intract"))
    changed = adapter.apply_webhook_event(payload)
    console.print(f"[bold]Updated tickets:[/] {changed}")


@app.command()
def watch(
    path: Path = typer.Argument(Path(".")),
    manifest: Path | None = typer.Option(None, "--manifest"),
    interval: float = typer.Option(1.0, "--interval"),
    planfile: bool = typer.Option(False, "--planfile"),
    once: bool = typer.Option(False, "--once"),
    json_output: bool = typer.Option(False, "--json"),
):
    """Watch folder and re-validate Intract contracts when logical files change."""
    def run_validation(changed_paths: list[str] | None = None) -> None:
        if changed_paths:
            console.print(f"[cyan]Changed:[/] {', '.join(changed_paths)}")
        report = validate_project(path, manifest_path=manifest)
        if planfile:
            _export_tickets(path, report)
        if json_output:
            console.print_json(json.dumps(report.to_dict(), ensure_ascii=False))
        else:
            console.print(f"[bold]Status:[/] {report.status.value} pass={len(report.passed)} partial={len(report.partial)} fail={len(report.failed)} violations={len(report.violations)}")

    if once:
        run_validation()
        return

    console.print(f"[green]Watching[/] {path} interval={interval}s")
    run_validation()
    try:
        watch_tree(path, lambda changes: run_validation(changes_to_paths(changes)), config=WatchConfig(interval=interval))
    except KeyboardInterrupt:
        console.print("[yellow]Stopped.[/]")


@engine_app.command("suggest")
def engine_suggest(path: Path = typer.Argument(Path(".")), json_output: bool = typer.Option(False, "--json")):
    result = scan_suggest_and_validate(EngineConfig(root=path))
    suggestions = result["suggestions"]
    if json_output:
        console.print_json(json.dumps({"suggestions": suggestions}, ensure_ascii=False))
        return
    table = Table(title="Suggested Intract contracts")
    table.add_column("File")
    table.add_column("Line")
    table.add_column("Confidence")
    table.add_column("Contract")
    for item in suggestions:
        table.add_row(item["file_path"], str(item["line"]), str(round(item["confidence"], 2)), item["contract_line"])
    console.print(table)


@engine_app.command("drift")
def engine_drift(path: Path = typer.Argument(Path(".")), manifest: Path | None = typer.Option(None, "--manifest"), json_output: bool = typer.Option(False, "--json")):
    result = scan_suggest_and_validate(EngineConfig(root=path, manifest=str(manifest) if manifest else None))
    if json_output:
        console.print_json(json.dumps(result, ensure_ascii=False))
        return
    drift = result["drift"]
    console.print(f"Files: {result['files']}")
    console.print(f"Fragments: {result['fragments']}")
    console.print(f"Drift issues: {len(drift)}")
    table = Table(title="Logic drift")
    table.add_column("Severity")
    table.add_column("Kind")
    table.add_column("File")
    table.add_column("Message")
    for item in drift:
        table.add_row(item["severity"], item["kind"], item["file_path"], item["message"])
    console.print(table)


@engine_app.command("run")
def engine_run(path: Path = typer.Argument(Path(".")), manifest: Path | None = typer.Option(None, "--manifest"), planfile: bool = typer.Option(False, "--planfile"), json_output: bool = typer.Option(False, "--json")):
    result = scan_suggest_and_validate(EngineConfig(root=path, manifest=str(manifest) if manifest else None))
    if planfile:
        report = validate_project(path, manifest_path=manifest)
        _export_tickets(path, report)
    if json_output:
        console.print_json(json.dumps(result, ensure_ascii=False))
        return
    console.print(f"Files: {result['files']}")
    console.print(f"Fragments: {result['fragments']}")
    console.print(f"Suggestions: {len(result['suggestions'])}")
    console.print(f"Drift: {len(result['drift'])}")
    console.print(f"Validation: {result['validation']['status']}")


def _export_tickets(path: Path, report):
    tickets_ = tickets_from_report(report)
    paths = PlanfileExporter(Path(path) / ".intract").export(tickets_)
    console.print(f"[yellow]Generated {len(tickets_)} ticket(s) in .intract/[/]")
    return paths


def _print_validation_report(report) -> None:
    console.print(f"[bold]Project:[/] {report.project_path}")
    console.print(f"[bold]Status:[/] {report.status.value}")
    table = Table(title="Validation results")
    table.add_column("Status")
    table.add_column("Scope")
    table.add_column("Contract")
    table.add_column("Score")
    table.add_column("File")
    table.add_column("Missing / Violations")
    for result in report.results:
        issues = []
        issues.extend(result.missing)
        issues.extend(issue.message for issue in result.violations)
        table.add_row(result.status.value, result.scope, result.contract, str(result.score), result.file_path or "", "\\n".join(issues))
    console.print(table)


def _format_check_text(report, decision, files: list[str]) -> str:
    lines = ["INTRACT CHECK", ""]
    if files:
        lines.append("Changed files:")
        lines.extend(f"- {f}" for f in files)
        lines.append("")
    lines.append(f"Status: {report.status.value}")
    lines.append(f"Passed: {len(report.passed)}")
    lines.append(f"Partial: {len(report.partial)}")
    lines.append(f"Failed: {len(report.failed)}")
    lines.append(f"Violations: {len(report.violations)}")
    if decision.reasons:
        lines.append("")
        lines.append("FAIL REASONS:")
        lines.extend(f"- {r}" for r in decision.reasons)
    if decision.warnings:
        lines.append("")
        lines.append("WARNINGS:")
        lines.extend(f"- {w}" for w in decision.warnings)
    return "\\n".join(lines)


@app.command("check-manifest")
def check_manifest(
    manifest: Path = typer.Argument(Path("intract.yaml"), help="Manifest path."),
    json_output: bool = typer.Option(False, "--json", help="Print JSON."),
):
    """Validate intract.yaml against the Intract schema."""
    from .manifest_schema import validate_manifest

    report = validate_manifest(manifest)
    if json_output:
        console.print_json(json.dumps(report.to_dict(), ensure_ascii=False))
        return

    if report.valid:
        console.print(f"[green]Manifest valid:[/] {manifest}")
    else:
        console.print(f"[red]Manifest invalid:[/] {manifest}")
        for issue in report.issues:
            console.print(f"- {issue.path}: {issue.message}")
        raise typer.Exit(1)


@app.command("artifact")
def artifact_validate(
    path: Path = typer.Argument(..., help="Artifact path: OpenAPI, Dockerfile, GitHub Actions, Kubernetes."),
    json_output: bool = typer.Option(False, "--json", help="Print JSON."),
):
    """Validate a non-code artifact: OpenAPI, Dockerfile, GitHub Actions or Kubernetes."""
    from .artifacts import validate_artifact

    report = validate_artifact(path)
    if json_output:
        console.print_json(json.dumps(report.to_dict(), ensure_ascii=False))
        return

    console.print(f"[bold]Artifact:[/] {report.path}")
    console.print(f"[bold]Kind:[/] {report.kind}")
    for result in report.results:
        console.print(f"- {result.status.value}: {result.contract}")
        for issue in result.violations:
            console.print(f"  - {issue.severity}: {issue.kind}: {issue.message}")


@propose_app.command("delta")
def propose_delta(
    keep: list[str] = typer.Option([], "--keep", help="Element ids to KEEP."),
    delete: list[str] = typer.Option([], "--delete", help="Element ids to DELETE."),
    stage: int = typer.Option(0, "--stage", help="Cinema stage number."),
    capsule: str = typer.Option("capsule", "--capsule", help="Capsule name."),
    json_output: bool = typer.Option(False, "--json"),
):
    """Propose @intract.v1 lines from cinema-style KEEP/DELETE feedback."""
    from .proposals import propose_ui_delta_contracts

    proposals = propose_ui_delta_contracts(
        stage=stage, keep=keep, delete=delete, capsule=capsule, domain="ui"
    )
    if json_output:
        console.print_json(json.dumps([p.to_dict() for p in proposals], ensure_ascii=False))
        return
    for item in proposals:
        console.print(item.line)


@propose_app.command("llm")
def propose_llm_cmd(
    file: Path | None = typer.Option(None, "--file", "-f", help="Artifact file to analyze."),
    goal: str = typer.Option("", "--goal", "-g", help="Goal/context for the LLM."),
    model: str | None = typer.Option(None, "--model", "-m", help="LLM model override."),
    json_output: bool = typer.Option(False, "--json"),
):
    """Propose @intract.v1 lines using an LLM (requires intract[llm])."""
    from .propose_llm import propose_contracts_llm

    if file is None:
        console.print("[red]--file is required[/]")
        raise typer.Exit(1)
    source = file.read_text(encoding="utf-8")
    try:
        proposals = propose_contracts_llm(
            source, goal=goal, fragment_name=str(file), model=model
        )
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1) from exc

    if json_output:
        console.print_json(json.dumps([p.to_dict() for p in proposals], ensure_ascii=False))
        return
    for item in proposals:
        console.print(item.line)


@manifest_app.command("apply-ledger")
def manifest_apply_ledger(
    manifest: Path = typer.Option(Path("intract.yaml"), "--manifest", "-m", help="Target intract.yaml."),
    ledger: Path = typer.Option(..., "--ledger", "-l", help="Cinema intract_policy_ledger.json."),
    workspace: Path | None = typer.Option(
        None, "--workspace", "-w", help="Workspace root (with --capsule for multi-target apply)."
    ),
    capsule: str = typer.Option("", "--capsule", "-c", help="Capsule name for --target capsule|both."),
    target: str = typer.Option(
        "project",
        "--target",
        "-t",
        help="project | capsule | both (requires -w and -c for capsule/both).",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show changes without writing."),
    json_output: bool = typer.Option(False, "--json"),
):
    """Merge evolved cinema ledger contracts into intract.yaml (by id)."""
    from .manifest_ops import apply_ledger_to_manifest, apply_ledger_to_manifests

    normalized_target = target.strip().lower()
    if normalized_target not in {"project", "capsule", "both"}:
        console.print("[red]--target must be project, capsule, or both[/]")
        raise typer.Exit(1)

    if workspace and capsule:
        batch = apply_ledger_to_manifests(
            workspace_root=workspace,
            capsule_name=capsule,
            ledger_path=ledger,
            target=normalized_target,  # type: ignore[arg-type]
            dry_run=dry_run,
        )
        if json_output:
            console.print_json(json.dumps(batch.to_dict(), ensure_ascii=False))
            return
        console.print(f"[bold]Target:[/] {normalized_target} · added total: {batch.added_total}")
        for result in batch.results:
            console.print(f"  [cyan]{result.target}[/] {result.manifest_path}")
            for contract_id in result.added:
                console.print(f"    + {contract_id}")
        return

    result = apply_ledger_to_manifest(
        manifest,
        ledger,
        dry_run=dry_run,
        target="project",
    )
    if json_output:
        console.print_json(json.dumps(result.to_dict(), ensure_ascii=False))
        return
    console.print(f"[bold]Manifest:[/] {result.manifest_path}")
    console.print(f"[green]Added:[/] {len(result.added)}")
    for contract_id in result.added:
        console.print(f"  + {contract_id}")
    if result.skipped:
        console.print(f"[yellow]Skipped:[/] {len(result.skipped)}")
