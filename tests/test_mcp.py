import json

from intract.mcp.handlers import TOOL_HANDLERS
from intract.mcp.schemas import TOOL_SCHEMA_INTRACT
from intract.mcp.server import handle_initialize, handle_tools_call, handle_tools_list


def test_tool_schema_lists_core_tools():
    assert "validate_project" in TOOL_SCHEMA_INTRACT
    assert "validate_staged" in TOOL_SCHEMA_INTRACT
    assert "scan_artifacts" in TOOL_SCHEMA_INTRACT


def test_initialize_response():
    payload = handle_initialize(1)
    assert payload["result"]["serverInfo"]["name"] == "intract"


def test_tools_list_response():
    payload = handle_tools_list(2)
    names = {tool["name"] for tool in payload["result"]["tools"]}
    assert "validate_intent_snippet" in names


def test_validate_intent_snippet_handler():
    raw = TOOL_HANDLERS["validate_intent_snippet"](
        {
            "code": (
                "# @intract.v1 scope:function intent:parse:extensions forbid:network\n"
                "def parse_extensions(raw):\n"
                "    return raw.split(',')\n"
            ),
            "filename": "parser.py",
        }
    )
    payload = json.loads(raw)
    assert payload["success"] is True


def test_validate_project_on_full_stack():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "examples" / "full-stack"
    raw = TOOL_HANDLERS["validate_project"](
        {"path": str(root), "manifest": str(root / "intract.yaml")}
    )
    payload = json.loads(raw)
    assert payload["success"] is True
    assert payload.get("empty") is False
    assert payload["report"]["status"] == "pass"


def test_validate_project_empty_is_not_success(tmp_path):
    raw = TOOL_HANDLERS["validate_project"]({"path": str(tmp_path)})
    payload = json.loads(raw)
    assert payload["success"] is False
    assert payload["empty"] is True
    assert payload["report"]["status"] == "unknown"
    assert payload["report"]["summary"]["total"] == 0
    assert "message" in payload


def test_validate_project_missing_path_is_not_success(tmp_path):
    missing = tmp_path / "does-not-exist"
    raw = TOOL_HANDLERS["validate_project"]({"path": str(missing)})
    payload = json.loads(raw)
    assert payload["success"] is False
    assert payload["empty"] is True
    assert payload["report"] is None


def test_tools_call_routes_handler():
    payload = handle_tools_call(
        3,
        {
            "name": "project_info",
            "arguments": {},
        },
    )
    text = payload["result"]["content"][0]["text"]
    info = json.loads(text)
    assert info["server"] == "intract"
