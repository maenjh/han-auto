"""Draft generation for report-style HWPX documents."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
import urllib.error
import urllib.request
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from han_auto.exceptions import HanAutoError


class DraftGenerationError(HanAutoError):
    """Raised when an LLM draft cannot be generated or parsed."""


class ReportBulletGroup(BaseModel):
    """One top-level report bullet with supporting lines."""

    title: str
    points: list[str] = Field(default_factory=list, min_length=1, max_length=3)
    note: str | None = None

    @field_validator("title")
    @classmethod
    def title_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("bullet title must not be empty")
        return value

    @field_validator("points")
    @classmethod
    def clean_points(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item.strip()]
        if not cleaned:
            raise ValueError("bullet group must contain at least one point")
        return cleaned[:3]


class ReportSection(BaseModel):
    """One numbered report section."""

    title: str
    groups: list[ReportBulletGroup] = Field(default_factory=list, min_length=1, max_length=4)

    @field_validator("title")
    @classmethod
    def section_title_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("section title must not be empty")
        return value


class ReportTable(BaseModel):
    """One structured table to insert into the report body."""

    title: str
    columns: list[str] = Field(default_factory=list, min_length=2, max_length=5)
    rows: list[list[str]] = Field(default_factory=list, min_length=1, max_length=12)
    note: str | None = None

    @field_validator("title")
    @classmethod
    def table_title_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("table title must not be empty")
        return value

    @field_validator("columns", mode="before")
    @classmethod
    def clean_columns(cls, value: Any) -> list[str]:
        if not isinstance(value, list):
            raise TypeError("table columns must be a list")
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        if len(cleaned) < 2:
            raise ValueError("table must contain at least two columns")
        return cleaned[:5]

    @field_validator("rows", mode="before")
    @classmethod
    def stringify_rows(cls, value: Any) -> list[list[str]]:
        if not isinstance(value, list):
            raise TypeError("table rows must be a list")
        rows: list[list[str]] = []
        for row in value:
            if not isinstance(row, list):
                raise TypeError("each table row must be a list")
            rows.append(["" if cell is None else str(cell).strip() for cell in row])
        return rows

    @model_validator(mode="after")
    def align_row_cells(self) -> "ReportTable":
        column_count = len(self.columns)
        normalized: list[list[str]] = []
        for row in self.rows:
            if not any(cell.strip() for cell in row):
                continue
            if len(row) < column_count:
                row = [*row, *([""] * (column_count - len(row)))]
            elif len(row) > column_count:
                row = [*row[: column_count - 1], " / ".join(row[column_count - 1 :])]
            normalized.append(row)
        if not normalized:
            raise ValueError("table must contain at least one non-empty row")
        self.rows = normalized[:12]
        return self


class ReportDraft(BaseModel):
    """LLM-generated structured report draft."""

    title: str
    date: str
    company: str
    sections: list[ReportSection] = Field(default_factory=list, min_length=1, max_length=4)
    tables: list[ReportTable] = Field(default_factory=list, max_length=3)
    attachments: list[str] = Field(default_factory=list, max_length=3)
    references: list[str] = Field(default_factory=list, max_length=3)

    @field_validator("title", "date", "company")
    @classmethod
    def required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be empty")
        return value


ProviderName = Literal["offline", "openai", "codex", "anthropic", "claude", "codex-cli", "claude-cli"]


def generate_report_draft(
    *,
    topic: str,
    company: str,
    audience: str = "공공기관 및 방송사 실무진",
    notes: str = "",
    provider: ProviderName = "offline",
    model: str | None = None,
) -> ReportDraft:
    """Generate a structured draft using an LLM provider or deterministic fallback."""

    provider = _normalize_provider(provider)
    if provider == "offline":
        return offline_report_draft(topic=topic, company=company, audience=audience, notes=notes)

    prompt = build_report_prompt(topic=topic, company=company, audience=audience, notes=notes)
    if provider == "openai":
        raw = _call_openai(prompt, model=model)
    elif provider == "anthropic":
        raw = _call_anthropic(prompt, model=model)
    elif provider == "codex_cli":
        raw = _call_codex_cli(prompt, model=model)
    elif provider == "claude_cli":
        raw = _call_claude_cli(prompt, model=model)
    else:  # pragma: no cover - guarded by _normalize_provider
        raise DraftGenerationError(f"Unsupported draft provider: {provider}")
    return parse_report_draft_json(raw)


def offline_report_draft(*, topic: str, company: str, audience: str, notes: str = "") -> ReportDraft:
    """Create a usable draft without calling an external model."""

    title = f"{company} {topic} 기획(안)"
    facts = _source_facts(notes)
    has_facts = bool(facts)
    return ReportDraft(
        title=title,
        date="2026. 6. 6.",
        company=company,
        sections=[
            ReportSection(
                title="기획 개요",
                groups=[
                    ReportBulletGroup(
                        title="기획 목적",
                        points=[
                            facts.get(
                                "purpose",
                                f"{topic} 추진을 통해 {audience}의 의사결정 속도와 실행 품질을 높인다.",
                            ),
                            facts.get(
                                "collaboration",
                                f"{company}는 데이터 수집, 분석 설계, 리포팅 자동화 체계를 통합적으로 제안한다.",
                            ),
                        ],
                        note=facts.get("scope_note", "초기 범위는 제공 가능한 데이터와 현업 검증 가능성을 기준으로 설정한다."),
                    )
                ],
            ),
            ReportSection(
                title="추진 배경 및 과제",
                groups=[
                    ReportBulletGroup(
                        title="지역 선거보도 환경 변화" if has_facts else "업무 환경 변화",
                        points=[
                            facts.get(
                                "background",
                                "데이터와 이해관계자가 분산되어 반복 취합, 기준 불일치, 해석 편차가 발생한다.",
                            ),
                            facts.get(
                                "need",
                                "공통 지표와 표준 리포트 체계를 마련해 같은 기준으로 현황을 비교·추적할 필요가 있다.",
                            ),
                        ],
                        note=facts.get("background_note", "정량 지표와 정성 의견을 함께 반영하는 구조가 적합하다."),
                    ),
                    ReportBulletGroup(
                        title="AI 활용 기준 필요",
                        points=[
                            "AI 요약·분류·추천 기능은 효율성을 높이지만 보안, 개인정보, 편향 관리 기준이 함께 필요하다.",
                            "모델 검수, 로그 관리, 권한 통제, 근거 표시를 포함한 운영 원칙을 적용한다.",
                        ],
                    ),
                ],
            ),
            ReportSection(
                title="AI 분석 설계",
                groups=[
                    ReportBulletGroup(
                        title="AI 현안 보도 제작 지원" if has_facts else "통합 분석 구조",
                        points=[
                            facts.get("coverage_support", "업무 데이터, 성과 지표, 외부 반응 데이터를 분석 단위별로 연결한다."),
                            facts.get("coverage_method", "키워드, 감성, 변화 추이, 이상 징후를 결합해 개선 포인트를 도출한다."),
                        ],
                        note=facts.get("coverage_note", "PoC 단계에서는 대표 업무 2~3개를 중심으로 검증한다."),
                    ),
                    ReportBulletGroup(
                        title="인터랙티브 선거보도 페이지" if has_facts else "자동 리포팅",
                        points=[
                            facts.get(
                                "interactive_page",
                                "주간·월간 리포트의 지표 요약, 주요 변화, 원인 후보, 후속 액션을 자동 생성한다.",
                            ),
                            facts.get(
                                "interactive_ops",
                                "담당자는 초안 검토와 맥락 보정에 집중하고 반복 작성 시간을 줄인다.",
                            ),
                        ],
                        note=facts.get("interactive_note"),
                    ),
                ],
            ),
            ReportSection(
                title="추진 계획",
                groups=[
                    ReportBulletGroup(
                        title="단계별 일정",
                        points=[
                            facts.get(
                                "schedule",
                                "1단계 요구사항·데이터 진단, 2단계 PoC, 3단계 대시보드 구축, 4단계 운영 전환 순으로 추진한다.",
                            ),
                            facts.get(
                                "budget",
                                "일정은 데이터 제공 범위, 보안 검토, 관계부서 협의 결과에 따라 조정한다.",
                            ),
                        ],
                    ),
                    ReportBulletGroup(
                        title="산출물 및 역할분담",
                        points=[
                            facts.get("role_company", f"{company}는 분석 설계, 모델 구축, 자동 리포팅 구현을 담당한다."),
                            facts.get("role_partner", "고객사는 데이터 제공, 업무 검증, 현업 적용 기준 수립을 담당한다."),
                        ],
                        note=facts.get(
                            "role_note",
                            "운영 단계에서는 모델 오류·편향 모니터링과 정기 재학습 계획을 포함한다.",
                        ),
                    ),
                ],
            ),
        ],
        tables=_offline_report_tables(company=company, audience=audience, facts=facts),
        attachments=["분석 지표(안)", "산출물 및 역할분담"],
        references=["데이터·보안 검토사항"],
    )


def _offline_report_tables(*, company: str, audience: str, facts: dict[str, str]) -> list[ReportTable]:
    if "budget" in facts:
        scope_or_budget = ReportTable(
            title="예산 산출 내역",
            columns=["항목", "금액", "비고"],
            rows=[
                ["AI 현안 보도 제작 지원", "3,000,000원", "32개 선거구 현안·공약 초안 작성"],
                ["인터랙티브 페이지 개설", "2,000,000원", "선거정보 페이지 구축"],
                ["관리운영", "2,000,000원", "2026.5.6.~6.3. 운영"],
            ],
            note="부가세와 세부 정산 기준은 계약 협의 시 별도 확정한다.",
        )
    else:
        scope_or_budget = ReportTable(
            title="범위 산출 내역",
            columns=["구분", "수량/규모", "비고"],
            rows=[
                ["데이터 진단", "1식", "제공 자료 확인 및 품질 점검"],
                ["분석 모델 설계", "2~3개 업무", "대표 업무 중심 PoC"],
                ["리포트 자동화", "주간·월간", "검토용 초안 자동 생성"],
            ],
            note="금액은 데이터 범위와 보안 검토 결과에 따라 별도 산정한다.",
        )

    if "coverage_note" in facts:
        schedule_rows = [
            ["보도 제작 지원", "2026.3.6.~4.23.", "32개 선거구 현안·공약 초안 작성"],
            ["인터랙티브 페이지 개설", "2026.5.6.", "선거정보·후보 공약·질의답변 공개"],
            ["관리운영", "2026.5.6.~6.3.", "개표현황 및 운영 리포트 갱신"],
        ]
    else:
        schedule_rows = [
            ["1단계", "착수~2주", "요구사항 및 데이터 진단"],
            ["2단계", "3~6주", "PoC 및 분석 모델 검증"],
            ["3단계", "7~10주", "대시보드·리포트 자동화 구현"],
            ["4단계", "11~12주", "운영 전환 및 검수"],
        ]

    return [
        scope_or_budget,
        ReportTable(
            title="추진 일정",
            columns=["단계", "기간", "주요 내용"],
            rows=schedule_rows,
        ),
        ReportTable(
            title="역할분담",
            columns=["주체", "담당 역할", "산출물"],
            rows=[
                [company, "분석 설계·모델 구축·자동 리포팅", "초안 생성 체계 및 운영 가이드"],
                [audience, "자료 제공·업무 검증·적용 기준 수립", "검수 의견 및 운영 기준"],
                ["공동", "성과 검토·보안 점검", "정기 협의 결과 및 개선 과제"],
            ],
        ),
    ]


def _source_facts(notes: str) -> dict[str, str]:
    text = " ".join(notes.split())
    if not text:
        return {}
    facts: dict[str, str] = {}
    election_context = "전국동시지방선거" in text or "지방선거" in text
    kbs_jeju_context = "KBS제주" in text or "KBS 제주" in text
    halla_context = "한라대학교" in text or "한라대" in text
    if election_context:
        facts["purpose"] = (
            "전국동시지방선거 보도에 AI 기능을 접목해 유권자에게 공약, 지역현안, 개표현황을 새롭고 정확한 방식으로 전달한다."
        )
        facts["background"] = (
            "저출생과 청년유출 등 지역소멸 문제가 커지는 가운데 정책 중심 선거보도와 지역 미래 의제 발굴이 필요하다."
        )
        facts["need"] = "지역 언론, 지역 대학, 청년이 협업해 지역 의제를 해석하고 유권자에게 이해하기 쉬운 선거정보를 제공한다."
        facts["background_note"] = "정책선거 유도와 지역 미래 견인을 핵심 목표로 설정한다."
        facts["scope_note"] = "선거구별 현안, 후보별 공약, 질의응답, 개표현황을 우선 범위로 둔다."
    if kbs_jeju_context or halla_context:
        partners = []
        if kbs_jeju_context:
            partners.append("KBS제주방송총국")
        if halla_context:
            partners.append("한라대학교 AI인공지능학과")
        facts["collaboration"] = f"{'·'.join(partners)}와 협업해 AI 기반 선거보도 제작과 인터랙티브 서비스 운영 체계를 마련한다."
        facts["role_partner"] = f"{'·'.join(partners)}는 보도 기획, 현안 검증, 선거정보 운영, 학생·청년 참여 체계를 담당한다."
    if "32개" in text and "선거구" in text:
        facts["coverage_support"] = "32개 선거구를 대상으로 AI 현안 보도 제작을 지원하고 선거구별 지역 이슈를 체계화한다."
        facts["coverage_method"] = "지역현안, 후보 공약, 유권자 질문을 분석 단위로 구성해 기사·방송·웹페이지에 활용 가능한 초안을 만든다."
        facts["coverage_note"] = "보도 제작 지원 기간은 2026년 3월 6일부터 4월 23일까지로 설정한다."
        facts["interactive_ops"] = "사전투표, 투표주의사항, 개표방송 홍보와 32개 선거구별 개표 실시간 구현을 관리한다."
    if "인터랙티브" in text:
        facts["interactive_page"] = "KBS제주선거보도센터 인터랙티브 페이지를 개설해 선거정보, 후보별 공약, 질의답변 코너를 제공한다."
        facts["interactive_note"] = "개설 목표일은 2026년 5월 6일이며 선거일까지 운영·갱신한다."
    if "300만" in text or "200만" in text:
        facts["budget"] = "예산은 AI 현안 보도 제작 지원 300만 원, 인터랙티브 페이지 개설 200만 원, 관리운영 200만 원으로 구분한다."
    if "3월 6일" in text or "4월 23일" in text or "6월 3일" in text:
        facts["schedule"] = (
            "2026년 3월 6일~4월 23일 보도제작, 5월 6일 페이지 개설, 5월 6일~6월 3일 관리운영 순으로 추진한다."
        )
    if facts:
        facts["role_company"] = "주식회사 스테이엑스는 AI 분석 설계, 선거구별 현안 구조화, 인터랙티브 데이터 구성, 운영 리포팅 자동화를 지원한다."
        facts["role_note"] = "세금계산서는 과업별로 발행하고 부가세는 별도로 관리한다." if "부가세" in text else "세부 과업별 검수와 정산 기준을 별도로 관리한다."
    return facts


def build_report_prompt(*, topic: str, company: str, audience: str, notes: str = "") -> str:
    """Build a JSON-only prompt for external LLM providers."""

    return f"""
너는 한국 공공기관 보고서와 제안서 작성 전문가다.
아래 정보를 바탕으로 HWPX 공공기관 보고서 양식에 들어갈 초안을 작성하라.

작성 조건:
- 한국어로 작성한다.
- 과장된 마케팅 문구보다 공공기관 보고서 문체를 사용한다.
- 반드시 JSON 객체만 반환한다. Markdown 코드펜스는 쓰지 않는다.
- sections는 정확히 4개로 구성한다.
- 각 section.groups는 1~3개로 구성한다.
- 각 group.points는 1~3개 문장으로 구성한다.
- tables는 1~3개로 구성하고, 예산·일정·역할분담처럼 수치나 항목 비교가 필요한 내용을 실제 행과 열로 작성한다.
- 표 안의 금액, 건수, 기간, 비율은 단위를 붙인 문자열로 작성하고 본문 문장으로 풀어 쓰지 않는다.
- 제목, 목차, 본문에 바로 넣을 수 있도록 문장을 짧고 명료하게 작성한다.

JSON 스키마:
{{
  "title": "문서 제목",
  "date": "YYYY. M. D.",
  "company": "회사명",
  "sections": [
    {{
      "title": "장 제목",
      "groups": [
        {{
          "title": "상위 불릿 제목",
          "points": ["하위 문장", "하위 문장"],
          "note": "참고 문장 또는 null"
        }}
      ]
    }}
  ],
  "tables": [
    {{
      "title": "표 제목",
      "columns": ["열 이름", "열 이름"],
      "rows": [["셀 값", "셀 값"]],
      "note": "표 하단 참고 문장 또는 null"
    }}
  ],
  "attachments": ["붙임 항목"],
  "references": ["참고 항목"]
}}

회사명: {company}
주제: {topic}
대상 독자: {audience}
추가 메모: {notes or "없음"}
""".strip()


def parse_report_draft_json(text: str) -> ReportDraft:
    """Parse a provider response into a ReportDraft."""

    payload_text = _extract_json_object(text)
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError as exc:
        raise DraftGenerationError(f"LLM response was not valid JSON: {exc}") from exc
    try:
        return ReportDraft.model_validate(payload)
    except ValidationError as exc:
        raise DraftGenerationError(f"LLM response did not match the report schema: {exc}") from exc


def _normalize_provider(provider: str) -> Literal["offline", "openai", "anthropic", "codex_cli", "claude_cli"]:
    normalized = provider.strip().lower()
    if normalized in {"offline", "local", "none"}:
        return "offline"
    if normalized in {"openai", "codex"}:
        return "openai"
    if normalized in {"anthropic", "claude"}:
        return "anthropic"
    if normalized in {"codex-cli", "codex_cli", "codex-exec", "codexexec"}:
        return "codex_cli"
    if normalized in {"claude-cli", "claude_cli", "claude-code", "claudecode"}:
        return "claude_cli"
    raise DraftGenerationError(f"Unsupported draft provider: {provider}")


def _call_codex_cli(prompt: str, *, model: str | None) -> str:
    executable = os.getenv("HAN_AUTO_CODEX_CLI") or shutil.which("codex")
    if not executable:
        raise DraftGenerationError("Codex CLI was not found. Install it or set HAN_AUTO_CODEX_CLI.")

    schema_path = _write_temp_schema()
    cmd = [
        executable,
        "exec",
        "--ephemeral",
        "--sandbox",
        "read-only",
        "--output-schema",
        str(schema_path),
    ]
    if model:
        cmd.extend(["--model", model])
    cmd.append("-")
    try:
        return _run_cli_provider(cmd, input_text=prompt)
    finally:
        schema_path.unlink(missing_ok=True)


def _call_claude_cli(prompt: str, *, model: str | None) -> str:
    executable = os.getenv("HAN_AUTO_CLAUDE_CLI") or shutil.which("claude")
    if not executable:
        raise DraftGenerationError("Claude Code CLI was not found. Install it or set HAN_AUTO_CLAUDE_CLI.")

    cmd = [
        executable,
        "--print",
        "--no-session-persistence",
        "--permission-mode",
        "dontAsk",
        "--tools",
        "",
        "--output-format",
        "text",
        "--json-schema",
        _report_draft_schema_json(),
    ]
    if model:
        cmd.extend(["--model", model])
    return _run_cli_provider(cmd, input_text=prompt)


def _run_cli_provider(cmd: list[str], *, input_text: str | None = None) -> str:
    timeout = int(os.getenv("HAN_AUTO_CLI_TIMEOUT", "600"))
    try:
        result = subprocess.run(
            cmd,
            input=input_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise DraftGenerationError(f"CLI provider timed out after {timeout} seconds.") from exc
    if result.returncode != 0:
        details = "\n".join(part.strip() for part in [result.stdout, result.stderr] if part.strip())
        raise DraftGenerationError(f"CLI provider failed with exit code {result.returncode}: {details}")
    if not result.stdout.strip():
        raise DraftGenerationError("CLI provider did not return output.")
    return result.stdout


def _write_temp_schema() -> Path:
    handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False)
    with handle:
        handle.write(_report_draft_schema_json())
    return Path(handle.name)


def _report_draft_schema_json() -> str:
    schema = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "date": {"type": "string"},
            "company": {"type": "string"},
            "sections": {
                "type": "array",
                "minItems": 1,
                "maxItems": 4,
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "groups": {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": 4,
                            "items": {
                                "type": "object",
                                "properties": {
                                    "title": {"type": "string"},
                                    "points": {
                                        "type": "array",
                                        "minItems": 1,
                                        "maxItems": 3,
                                        "items": {"type": "string"},
                                    },
                                    "note": {"type": ["string", "null"]},
                                },
                                "required": ["title", "points", "note"],
                                "additionalProperties": False,
                            },
                        },
                    },
                    "required": ["title", "groups"],
                    "additionalProperties": False,
                },
            },
            "tables": {
                "type": "array",
                "minItems": 1,
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "columns": {
                            "type": "array",
                            "minItems": 2,
                            "maxItems": 5,
                            "items": {"type": "string"},
                        },
                        "rows": {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": 12,
                            "items": {
                                "type": "array",
                                "minItems": 2,
                                "maxItems": 5,
                                "items": {"type": ["string", "number", "integer", "null"]},
                            },
                        },
                        "note": {"type": ["string", "null"]},
                    },
                    "required": ["title", "columns", "rows", "note"],
                    "additionalProperties": False,
                },
            },
            "attachments": {"type": "array", "maxItems": 3, "items": {"type": "string"}},
            "references": {"type": "array", "maxItems": 3, "items": {"type": "string"}},
        },
        "required": ["title", "date", "company", "sections", "tables", "attachments", "references"],
        "additionalProperties": False,
    }
    return json.dumps(schema, ensure_ascii=False)


def _call_openai(prompt: str, *, model: str | None) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise DraftGenerationError("OPENAI_API_KEY is required for provider=openai/codex.")
    payload = {
        "model": model or os.getenv("OPENAI_MODEL", "gpt-4.1"),
        "input": prompt,
    }
    data = _post_json(
        "https://api.openai.com/v1/responses",
        payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    if isinstance(data.get("output_text"), str):
        return data["output_text"]

    chunks: list[str] = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and isinstance(content.get("text"), str):
                chunks.append(content["text"])
    if not chunks:
        raise DraftGenerationError("OpenAI response did not contain output text.")
    return "\n".join(chunks)


def _call_anthropic(prompt: str, *, model: str | None) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise DraftGenerationError("ANTHROPIC_API_KEY is required for provider=anthropic/claude.")
    payload = {
        "model": model or os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5"),
        "max_tokens": 4000,
        "messages": [{"role": "user", "content": prompt}],
    }
    data = _post_json(
        "https://api.anthropic.com/v1/messages",
        payload,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
    )
    chunks = [item.get("text", "") for item in data.get("content", []) if item.get("type") == "text"]
    text = "\n".join(chunk for chunk in chunks if chunk)
    if not text:
        raise DraftGenerationError("Anthropic response did not contain text.")
    return text


def _post_json(url: str, payload: dict[str, object], *, headers: dict[str, str]) -> dict[str, object]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise DraftGenerationError(f"Provider request failed with HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise DraftGenerationError(f"Provider request failed: {exc}") from exc


def _extract_json_object(text: str) -> str:
    stripped = text.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.DOTALL)
    if fenced:
        stripped = fenced.group(1).strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise DraftGenerationError("LLM response did not contain a JSON object.")
    return stripped[start : end + 1]
