"""Tests for the han-auto MCP server tool layer.

These exercise the plain tool functions (no running server, no network) plus the
FastMCP registration. They are skipped automatically if the optional ``mcp``
extra is not installed.
"""

from __future__ import annotations

import json

import pytest

from han_auto import mcp_server as m
from han_auto.exceptions import HanAutoError
from han_auto.resources import resource_path

OFFLINE_DRAFT = {
    "title": "스테이엑스 테스트 기획(안)",
    "company": "주식회사 스테이엑스",
    "sections": [
        {"title": "기획 개요", "groups": [{"title": "목적", "points": ["AI로 고도화한다."]}]},
        {"title": "추진 배경", "groups": [{"title": "환경", "points": ["데이터가 분산되어 있다."]}]},
        {"title": "분석 설계", "groups": [{"title": "구조", "points": ["키워드와 감성을 결합한다."]}]},
        {"title": "추진 계획", "groups": [{"title": "일정", "points": ["4단계로 추진한다."]}]},
    ],
    "tables": [
        {
            "title": "예산",
            "columns": ["항목", "금액"],
            "rows": [["분석", "300만원"], ["운영", "200만원"]],
            "note": "부가세 별도",
        }
    ],
    "attachments": ["분석지표(안)"],
    "references": ["보안 검토사항"],
}


def test_tools_list_is_complete():
    names = {tool.__name__ for tool in m.TOOLS}
    assert names == {
        "list_bundled_resources",
        "inspect_fields",
        "extract_source_text",
        "parse_markdown",
        "render_markdown_to_hwpx",
        "hwp_to_hwpx",
        "draft_report_hwpx",
        "render_report_hwpx",
        "fill_form_by_replacements",
    }


def test_list_bundled_resources_includes_report_template():
    payload = json.loads(m.list_bundled_resources())
    names = {item["name"] for item in payload}
    assert m.BUNDLED_REPORT_TEMPLATE in names
    for item in payload:
        assert item["path"]


def test_inspect_fields_on_bundled_template_native():
    template = str(resource_path(m.BUNDLED_REPORT_TEMPLATE))
    names = json.loads(m.inspect_fields(template, engine="native"))
    assert isinstance(names, list)


def test_parse_markdown_on_bundled_example():
    example = str(resource_path("examples/notice.md"))
    document = json.loads(m.parse_markdown(example))
    assert "title" in document


def test_render_report_hwpx_writes_file(tmp_path):
    out = tmp_path / "report.hwpx"
    result = m.render_report_hwpx(draft=OFFLINE_DRAFT, output_path=str(out))
    assert out.exists() and out.stat().st_size > 0
    assert str(out) in result


def test_render_report_hwpx_defaults_date(tmp_path):
    draft = {k: v for k, v in OFFLINE_DRAFT.items()}
    draft.pop("date", None)
    out = tmp_path / "dated.hwpx"
    m.render_report_hwpx(draft=draft, output_path=str(out))
    assert out.exists()


def test_draft_report_hwpx_offline(tmp_path):
    out = tmp_path / "draft.hwpx"
    m.draft_report_hwpx(topic="KBS AI 분석", output_path=str(out), provider="offline")
    assert out.exists() and out.stat().st_size > 0


def test_fill_form_by_replacements(tmp_path):
    import json as _json

    form = tmp_path / "form.hwpx"
    m.render_report_hwpx(draft=OFFLINE_DRAFT, output_path=str(form))
    out = tmp_path / "filled.hwpx"
    result = m.fill_form_by_replacements(
        input_path=str(form),
        output_path=str(out),
        replacements={"주식회사 스테이엑스": "㈜교체됨"},
    )
    summary = _json.loads(result)
    assert summary["text_nodes_changed"] >= 1
    assert out.exists() and out.stat().st_size > 0


def test_missing_file_raises():
    with pytest.raises(HanAutoError):
        m.parse_markdown("/nonexistent/does-not-exist.md")


def test_build_server_registers_all_tools():
    mcp = pytest.importorskip("mcp")  # noqa: F841
    import asyncio

    server = m.build_server()
    tools = asyncio.run(server.list_tools())
    assert {t.name for t in tools} == {tool.__name__ for tool in m.TOOLS}
    assert server._mcp_server.version
