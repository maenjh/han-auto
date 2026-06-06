from han_auto.draft import generate_report_draft, parse_report_draft_json


def test_offline_report_draft_has_four_sections() -> None:
    draft = generate_report_draft(
        topic="KBS AI 분석",
        company="주식회사 스테이엑스",
        provider="offline",
    )

    assert draft.title == "주식회사 스테이엑스 KBS AI 분석 기획(안)"
    assert len(draft.sections) == 4
    assert draft.sections[0].groups[0].points


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
