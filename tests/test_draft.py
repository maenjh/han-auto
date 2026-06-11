import json
import subprocess

from han_auto import draft as draft_module
from han_auto.draft import generate_report_draft, parse_report_draft_json


def _draft_payload() -> str:
    return json.dumps(
        {
            "title": "CLI draft",
            "date": "2026. 6. 6.",
            "company": "StayX",
            "sections": [
                {
                    "title": "Overview",
                    "groups": [{"title": "Purpose", "points": ["Draft with CLI."], "note": None}],
                }
            ],
            "attachments": [],
            "references": [],
        }
    )


def test_offline_report_draft_has_four_sections() -> None:
    draft = generate_report_draft(
        topic="KBS AI 분석",
        company="주식회사 스테이엑스",
        provider="offline",
    )

    assert draft.title == "주식회사 스테이엑스 KBS AI 분석 기획(안)"
    assert len(draft.sections) == 4
    assert draft.sections[0].groups[0].points
    assert len(draft.tables) == 3
    assert draft.tables[0].columns
    assert draft.tables[1].rows[0][1]


def test_offline_report_draft_uses_today_as_date() -> None:
    import re
    from datetime import datetime, timedelta, timezone

    draft = generate_report_draft(topic="주제", company="회사", provider="offline")

    assert re.fullmatch(r"\d{4}\. \d{1,2}\. \d{1,2}\.", draft.date)
    now = datetime.now(timezone(timedelta(hours=9)))
    assert draft.date == f"{now.year}. {now.month}. {now.day}."


def test_parse_report_draft_error_includes_response_snippet() -> None:
    import pytest

    from han_auto.draft import DraftGenerationError

    with pytest.raises(DraftGenerationError) as excinfo:
        parse_report_draft_json("Sorry, I cannot produce JSON right now.")

    assert "Sorry, I cannot produce JSON" in str(excinfo.value)


def test_parse_report_draft_json_accepts_fenced_json() -> None:
    draft = parse_report_draft_json(
        """```json
{
  "title": "테스트 기획(안)",
  "date": "2026. 6. 6.",
  "company": "테스트 회사",
  "sections": [
    {"title": "기획 개요", "groups": [{"title": "목적", "points": ["초안을 작성한다."]}]}
  ],
  "attachments": ["세부내용"],
  "references": ["검토사항"]
}
```"""
    )

    assert draft.company == "테스트 회사"
    assert draft.sections[0].groups[0].title == "목적"


def test_parse_report_draft_json_accepts_structured_tables() -> None:
    draft = parse_report_draft_json(
        """
{
  "title": "테스트 기획(안)",
  "date": "2026. 6. 6.",
  "company": "테스트 회사",
  "sections": [
    {"title": "기획 개요", "groups": [{"title": "목적", "points": ["초안을 작성한다."]}]}
  ],
  "tables": [
    {
      "title": "예산 산출 내역",
      "columns": ["항목", "금액"],
      "rows": [["분석", 3000000, "부가세 별도"]],
      "note": null
    }
  ],
  "attachments": [],
  "references": []
}
"""
    )

    assert draft.tables[0].rows == [["분석", "3000000 / 부가세 별도"]]


def test_codex_cli_provider_invokes_codex_exec(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_which(name: str) -> str | None:
        return "codex.exe" if name == "codex" else None

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout=_draft_payload(), stderr="")

    monkeypatch.setattr(draft_module.shutil, "which", fake_which)
    monkeypatch.setattr(draft_module.subprocess, "run", fake_run)

    result = generate_report_draft(topic="topic", company="StayX", provider="codex-cli", model="gpt-test")

    assert result.title == "CLI draft"
    assert calls[0][0] == "codex.exe"
    assert calls[0][1] == "exec"
    assert "--output-schema" in calls[0]
    assert "--model" in calls[0]


def test_claude_cli_provider_invokes_claude_print(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_which(name: str) -> str | None:
        return "claude.exe" if name == "claude" else None

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout=_draft_payload(), stderr="")

    monkeypatch.setattr(draft_module.shutil, "which", fake_which)
    monkeypatch.setattr(draft_module.subprocess, "run", fake_run)

    result = generate_report_draft(topic="topic", company="StayX", provider="claude-cli", model="sonnet")

    assert result.title == "CLI draft"
    assert calls[0][0] == "claude.exe"
    assert "--print" in calls[0]
    assert "--json-schema" in calls[0]
    assert "--model" in calls[0]
