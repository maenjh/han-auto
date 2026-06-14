# han-auto MCP 서버

`han-auto`를 **stdio MCP 서버**로 노출해 Claude Code, Codex CLI, Antigravity CLI 등
MCP를 지원하는 모든 호스트에서 한컴 HWP/HWPX 문서를 생성·편집할 수 있습니다.

엔트리포인트: `han-auto-mcp` (= `python -m han_auto.mcp_server`)

## 설치

MCP 서버는 선택 의존성(`mcp`)이 필요합니다. 다음 중 하나로 설치합니다.

```bash
# 1) 프로젝트에 동기화 (개발/로컬 실행)
uv sync --extra mcp

# 2) wheel에서 격리 설치 (PATH에 han-auto-mcp 등록 — 권장)
uv build --sdist --wheel
uv tool install "dist/han_auto-0.1.0-py3-none-any.whl[mcp]"

# 3) pip
pip install "han-auto[mcp]"
```

설치 후 동작 확인:

```bash
han-auto-mcp --help 2>/dev/null; echo "exit: $?"   # 서버는 stdio로 대기합니다
```

> `han-auto-mcp`는 인자 없이 실행하면 stdio로 클라이언트 연결을 기다립니다.
> 직접 터미널에서 실행하면 멈춘 것처럼 보이는 게 정상입니다(클라이언트가 붙어야 합니다).

## 실행 방식 두 가지

클라이언트에 등록할 `command`/`args`는 설치 방식에 따라 둘 중 하나를 씁니다.

**A. 전역 설치한 경우 (권장)** — `han-auto-mcp`가 PATH에 있음:

```text
command: han-auto-mcp
args:    []
```

**B. 설치 없이 프로젝트에서 실행** — `uv`가 프로젝트 가상환경을 해석:

```text
command: uv
args:    ["run", "--project", "/Users/moon/Desktop/개발프로젝트/han-auto", "han-auto-mcp"]
```

---

## Claude Code 등록

가장 간단한 방법은 CLI 명령입니다.

```bash
# 전역 설치한 경우
claude mcp add han-auto -- han-auto-mcp

# 설치 없이 프로젝트에서
claude mcp add han-auto -- uv run --project /Users/moon/Desktop/개발프로젝트/han-auto han-auto-mcp
```

`--scope`로 범위를 정할 수 있습니다: `local`(기본, 내 계정·이 프로젝트만), `project`(`.mcp.json`로 저장해 팀 공유), `user`(모든 프로젝트).

직접 파일로 등록하려면 프로젝트 루트 `.mcp.json`:

```json
{
  "mcpServers": {
    "han-auto": {
      "command": "han-auto-mcp",
      "args": [],
      "env": {}
    }
  }
}
```

등록 후 `/mcp` 명령으로 연결 상태와 도구 목록을 확인합니다.

## Codex CLI 등록

`~/.codex/config.toml`에 서버를 추가합니다.

```toml
[mcp_servers.han-auto]
command = "han-auto-mcp"
args = []

# 외부 provider를 쓸 때만 (offline 초안은 불필요)
# [mcp_servers.han-auto.env]
# ANTHROPIC_API_KEY = "sk-ant-..."
# OPENAI_API_KEY = "sk-..."
```

설치 없이 실행하려면:

```toml
[mcp_servers.han-auto]
command = "uv"
args = ["run", "--project", "/Users/moon/Desktop/개발프로젝트/han-auto", "han-auto-mcp"]
```

## Antigravity CLI 등록

Antigravity는 MCP 설정 패널(또는 MCP 설정 JSON)에서 표준 `mcpServers` 형식을 사용합니다.
"Add MCP server / Manage MCP servers"에서 아래 JSON을 추가합니다.

```json
{
  "mcpServers": {
    "han-auto": {
      "command": "han-auto-mcp",
      "args": []
    }
  }
}
```

설치 없이 실행하려면 `command`/`args`를 위 **실행 방식 B**로 바꿉니다.

---

## 제공 도구 (9개)

| 도구 | 설명 | 한컴오피스 | 네트워크 |
|------|------|-----------|----------|
| `list_bundled_resources` | 패키지에 내장된 양식·설정·예제 경로 목록(JSON) | 불필요 | 불필요 |
| `inspect_fields` | HWP/HWPX 양식의 누름틀 필드명 목록 | 불필요(native) | `.hwp` 첫 변환 시 |
| `extract_source_text` | PDF/TXT/MD/HWP/HWPX에서 본문 텍스트 추출 | 불필요 | `.hwp` 첫 변환 시 |
| `parse_markdown` | Markdown(YAML front matter+본문) → 구조화 JSON | 불필요 | 불필요 |
| `render_markdown_to_hwpx` | Markdown + YAML 매핑으로 누름틀 필드 채워 HWPX 출력 | 불필요 | `.hwp` 첫 변환 시 |
| `hwp_to_hwpx` | `.hwp` → `.hwpx` 변환 | 불필요 | 첫 변환 시(JDK 등) |
| `draft_report_hwpx` | provider로 4장 보고서 초안 생성 후 HWPX 렌더링 | 불필요 | provider에 따라 |
| `render_report_hwpx` | **에이전트가 작성한 구조화 초안**을 HWPX로 렌더링 | 불필요 | 불필요 |
| `fill_form_by_replacements` | **임의 HWP/HWPX 문서를 양식으로** 삼아 텍스트 치환 → HWPX | 불필요 | `.hwp` 첫 변환 시 |

### 임의 문서를 양식으로 채우기 (`fill_form_by_replacements`)

누름틀 필드가 없고 보고서 레이아웃과도 다른 문서(품의서·공문 등)를 양식으로 재사용할 때 씁니다.
원본의 표·결재선·서식은 그대로 두고 **보이는 텍스트만** 치환하며, 바뀐 문단의 줄배치 캐시를
비워 한컴이 열 때 레이아웃을 다시 계산하도록 합니다. `.hwp`는 먼저 `.hwpx`로 변환합니다.

권장 흐름:

1. `extract_source_text`로 원본 문서의 정확한 문자열을 읽는다.
2. 바꿀 문자열을 `{원본: 교체}` 형태로 정한다. **긴/구체적 문자열을 앞에** 둔다(제목 전체 → 제목 안의 구절 순). 반복되는 값(금액·이름)은 모든 위치에서 일관되게 바뀐다.
3. `fill_form_by_replacements(input_path, output_path, replacements={...})` 호출.

```jsonc
{
  "input_path": "/path/to/품의.hwp",
  "output_path": "/path/to/StayX_품의.hwpx",
  "replacements": {
    "제주한라대학교 산학협력단": "주식회사 스테이엑스 (STAIx)",
    "Agentic AI 기반 지능형 교육플랫폼 구축 용역": "생성형 AI 기반 지역현안 분석 플랫폼 구축 용역",
    "570,000,000": "120,000,000"
  }
}
```

### 권장 사용 흐름

호스트가 이미 LLM 에이전트이므로, **콘텐츠는 에이전트가 직접 작성하고 서버는 렌더링만** 하는 흐름이 품질이 가장 좋습니다.

1. (선택) `extract_source_text`로 참고 자료를 읽는다.
2. 한국어 공공기관 보고서 문체로 구조화 초안(`draft`)을 작성한다.
3. `render_report_hwpx(draft=..., output_path="out.hwpx")`로 렌더링한다.

외부 모델/규칙으로 초안 생성까지 위임하려면 `draft_report_hwpx`를 쓰고
`provider`를 `offline`/`openai`/`anthropic`/`codex-cli`/`claude-cli` 중에서 고릅니다.

### 양식 제약

`draft_report_hwpx`와 `render_report_hwpx`는 문단을 고정 인덱스로 채우므로
내장 양식 `templates/brother-public-report.hwpx`(또는 그 레이아웃에서 파생한 양식)만 지원합니다.
`template_path`를 비우면 내장 양식을 자동 사용합니다.
임의의 양식에 필드를 채우려면 `render_markdown_to_hwpx`(누름틀 기반)를 사용하세요.

### `draft` 객체 스키마 (render_report_hwpx)

```jsonc
{
  "title": "문서 제목",
  "date": "YYYY. M. D.",            // 생략 시 오늘 날짜(KST) 자동
  "company": "회사명",
  "sections": [                      // 4개 권장
    {
      "title": "장 제목",
      "groups": [                    // 1~4개
        { "title": "상위 불릿", "points": ["문장", "문장"], "note": "참고 또는 생략" }
      ]
    }
  ],
  "tables": [                        // 0~3개 (예산·일정·역할분담 등)
    { "title": "표 제목", "columns": ["열1","열2"], "rows": [["셀","셀"]], "note": "참고 또는 생략" }
  ],
  "attachments": ["붙임 항목"],       // 0~3개
  "references": ["참고 항목"]         // 0~3개
}
```

## 환경변수

| 변수 | 용도 |
|------|------|
| `OPENAI_API_KEY` | `draft_report_hwpx --provider openai` |
| `ANTHROPIC_API_KEY` | `draft_report_hwpx --provider anthropic` |
| `HAN_AUTO_TOOL_ROOT` | hwp2hwpx 도구 캐시 경로 |
| `HAN_AUTO_JAVA_HOME` | 직접 지정할 JDK 경로 |

CLI provider(`codex-cli`/`claude-cli`)는 로컬에 해당 CLI가 설치·로그인되어 있어야 합니다.

## 문제 해결

- **`The 'mcp' package is required`**: `uv sync --extra mcp` 또는 `pip install "han-auto[mcp]"`.
- **클라이언트가 서버를 못 찾음**: 전역 설치(`uv tool install`)로 `han-auto-mcp`를 PATH에 올리거나, 실행 방식 B(`uv run --project <절대경로>`)를 사용하세요.
- **`.hwp` 변환 실패**: 첫 변환 시 JDK/소스/jar 다운로드가 필요합니다. 사내망 차단 시 `HAN_AUTO_JAVA_HOME` 등으로 로컬 경로를 지정하세요(루트 README 참고).
