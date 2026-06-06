# han-auto

`han-auto`는 한컴 HWP/HWPX 양식을 유지한 상태로 보고서와 공문 초안을 자동 생성하는 도구입니다.
Markdown 문서를 HWP 필드에 넣거나, HWP/HWPX 양식과 PDF/TXT/Markdown 원문을 바탕으로 AI 초안을 만든 뒤 양식에 맞춰 HWPX 결과물을 생성할 수 있습니다.

## 개요

- Markdown 공문 초안을 구조화하고 HWP 템플릿 필드에 입력합니다.
- 공공기관 보고서형 HWPX 양식에 맞춰 4개 장 구성의 보고서 초안을 생성합니다.
- `.hwp` 양식이 들어오면 `neolord0/hwp2hwpx`를 이용해 `.hwpx`로 변환한 뒤 처리합니다.
- 회사 로고 이미지를 HWPX 내부 이미지로 교체할 수 있습니다.
- 초안 생성 방식은 로컬 오프라인, OpenAI/Anthropic API, Codex CLI, Claude CLI를 지원합니다.
- Windows 환경에서는 한컴 HWP COM 자동화를 이용해 생성된 HWPX를 다시 열고 저장하여 레이아웃을 재계산할 수 있습니다.

## 요구사항

- 전체 워크플로에는 Windows를 권장합니다. `parse`는 어느 환경에서나 동작하지만, `inspect-fields`, `render`, HWP 재저장은 Windows용 한컴오피스 COM 자동화가 필요합니다.
- Python 3.11 이상이 필요합니다.
- 설치와 실행에는 `uv` 사용을 권장합니다.
- 실제 한컴 HWP/HWPX 파일을 열거나 다시 저장하려면 Windows용 한컴오피스가 필요합니다.
- `.hwp` 양식을 `.hwpx`로 변환할 때만 Java JDK가 필요합니다. 프로그램이 `neolord0/hwp2hwpx`용 Java wrapper를 컴파일하므로 JRE만으로는 부족합니다.
- Maven은 필요하지 않습니다. 필요한 Java jar는 프로그램이 직접 다운로드합니다.
- Git은 선택사항입니다. Git이 있으면 `hwp2hwpx` 소스를 clone하고, 없으면 ZIP 파일을 다운로드합니다.
- 첫 `.hwp` 변환 시 JDK, `hwp2hwpx` 소스, jar 파일을 자동으로 받을 수 있어 네트워크가 필요합니다. 사내망에서 차단되는 경우 환경변수로 로컬 경로를 지정할 수 있습니다.
- 자동 JDK 다운로드는 약 180MB이므로 도구 캐시에 충분한 디스크 공간이 필요합니다.
- 외부 AI 초안 생성은 선택사항입니다. API 방식은 `OPENAI_API_KEY` 또는 `ANTHROPIC_API_KEY`가 필요하고, CLI 방식은 로컬 Codex/Claude CLI 설치와 로그인이 필요합니다.

## 설치

```powershell
uv sync
```

개발 환경에서 직접 설치하려면:

```powershell
python -m pip install -e .
```

## 주요 명령어

```powershell
uv run han-auto parse examples/notice.md
uv run han-auto inspect-fields path\to\template.hwp
uv run han-auto render examples/notice.md --template configs/templates/default.yaml --output output.hwp
uv run han-auto draft-hwpx template.hwpx --topic "KBS AI 분석" --company "주식회사 스테이엑스" --logo logo.png --output output.hwpx
uv run han-auto draft-hwpx templates/brother-public-report.hwpx --topic "KBS AI 분석" --company "주식회사 스테이엑스" --output output.hwpx
uv run han-auto draft-hwpx template.hwp --topic "KBS AI 분석" --provider codex-cli --output output.hwpx
uv run han-auto hwp-to-hwpx template.hwp --output template.hwpx
```

`parse`는 한컴오피스 없이 동작합니다. `inspect-fields`와 `render`는 Windows용 한컴오피스와 `pywin32` COM bridge가 필요합니다.
`configs/templates/default.yaml`의 `template_path`는 실제 사용할 HWP 양식 경로로 수정한 뒤 사용합니다.
`templates/brother-public-report.hwpx`는 Brother Korea 네이버 블로그에서 받은 공공기관 보고서 양식입니다.
출처: https://blog.naver.com/brother_korea/223455020711?trackingCode=rss

## 보고서 초안 생성

`draft-hwpx`는 보고서 주제, 회사명, 참고 자료를 바탕으로 4개 장 구성의 보고서 초안을 만들고 HWPX 양식에 삽입합니다. 입력 양식은 `.hwpx`와 `.hwp`를 모두 지원합니다. `.hwp`가 들어오면 먼저 `.hwpx`로 변환한 뒤 같은 렌더링 흐름을 사용합니다.

내장 예시 양식:

- `templates/brother-public-report.hwpx`
- 원본 파일명: `브라더 공공기관 보고서 양식.hwpx`
- 출처: Brother Korea 네이버 블로그, https://blog.naver.com/brother_korea/223455020711?trackingCode=rss

```powershell
han-auto draft-hwpx `
  C:\path\to\template.hwpx `
  --topic "KBS AI 분석 기획" `
  --company "주식회사 스테이엑스" `
  --logo C:\path\to\logo.png `
  --source C:\path\to\source.pdf `
  --output C:\path\to\output.hwpx
```

`.hwp` 양식을 바로 넣는 예:

```powershell
han-auto draft-hwpx `
  C:\path\to\template.hwp `
  --topic "KBS AI 분석 기획" `
  --company "주식회사 스테이엑스" `
  --source C:\path\to\source.hwp `
  --provider offline `
  --output C:\path\to\output.hwpx
```

한컴 보안 팝업을 줄이려면 한컴 개발자 자료의 공식 `보안모듈(Automation).zip`을 다운로드해 둡니다. `draft-hwpx`와 `render`는 Downloads, Desktop, Documents, 한컴 설치 폴더 등에서 DLL 또는 ZIP을 자동 탐색합니다. 필요하면 DLL 경로를 직접 지정할 수 있습니다.

```powershell
han-auto draft-hwpx template.hwpx `
  --topic "KBS AI 분석" `
  --output output.hwpx `
  --security-dll path\to\FilePathCheckerModuleExample.dll
```

## AI 초안 생성 방식

`draft-hwpx`의 `--provider` 옵션은 다음 방식을 지원합니다.

- `offline`: 외부 모델 없이 로컬 규칙 기반 초안을 생성합니다.
- `openai` 또는 `codex`: OpenAI API를 직접 호출합니다. `OPENAI_API_KEY`가 필요합니다.
- `anthropic` 또는 `claude`: Anthropic API를 직접 호출합니다. `ANTHROPIC_API_KEY`가 필요합니다.
- `codex-cli`: 설치된 Codex CLI를 비대화형으로 실행하고, 로컬 로그인 세션을 사용합니다.
- `claude-cli`: 설치된 Claude Code CLI를 비대화형으로 실행하고, 로컬 로그인 세션을 사용합니다.

### OpenAI API 방식

```powershell
$env:OPENAI_API_KEY = "sk-..."
han-auto draft-hwpx C:\path\to\template.hwpx `
  --topic "KBS AI 분석 기획" `
  --provider openai `
  --model gpt-4.1 `
  --output C:\path\to\output.hwpx
```

### Anthropic API 방식

```powershell
$env:ANTHROPIC_API_KEY = "sk-ant-..."
han-auto draft-hwpx C:\path\to\template.hwpx `
  --topic "KBS AI 분석 기획" `
  --provider anthropic `
  --model claude-sonnet-4-5 `
  --output C:\path\to\output.hwpx
```

### Codex CLI 방식

1. Codex CLI를 설치하고 로그인합니다.
2. 실행 가능 여부를 확인합니다.

```powershell
codex --version
codex login
```

3. `codex-cli` provider로 실행합니다.

```powershell
han-auto draft-hwpx C:\path\to\template.hwp `
  --topic "KBS AI 분석 기획" `
  --provider codex-cli `
  --model gpt-5.4 `
  --output C:\path\to\output.hwpx
```

내부적으로 프로그램은 `codex exec`, `--sandbox read-only`, JSON schema를 사용합니다. Codex CLI는 구조화된 초안 JSON만 작성하고, HWP/HWPX 변환과 양식 렌더링은 `han-auto`가 처리합니다.

### Claude CLI 방식

1. Claude Code CLI를 설치하고 로그인합니다.
2. 실행 가능 여부를 확인합니다.

```powershell
claude --version
claude auth
```

3. `claude-cli` provider로 실행합니다.

```powershell
han-auto draft-hwpx C:\path\to\template.hwp `
  --topic "KBS AI 분석 기획" `
  --provider claude-cli `
  --model sonnet `
  --output C:\path\to\output.hwpx
```

CLI 실행 파일이 PATH에 없거나 긴 문서 처리 시간이 더 필요하면 다음 환경변수를 사용합니다.

```powershell
$env:HAN_AUTO_CODEX_CLI = "C:\path\to\codex.cmd"
$env:HAN_AUTO_CLAUDE_CLI = "C:\path\to\claude.exe"
$env:HAN_AUTO_CLI_TIMEOUT = "900"
```

개인 PC에서는 CLI 방식이 로컬 로그인 세션을 재사용할 수 있어 편합니다. 서버나 공유 자동화 환경에서는 API 방식이 더 예측 가능합니다.

## HWP to HWPX 변환

`.hwp` 입력 지원은 `https://github.com/neolord0/hwp2hwpx` Java 라이브러리를 사용합니다. 첫 `.hwp` 변환 시 프로그램은 로컬 도구 캐시를 준비하고, `hwp2hwpx` 소스와 필요한 jar를 받은 뒤 작은 Java CLI wrapper를 빌드합니다. Windows에서 JDK가 없으면 portable Temurin/OpenJDK 17을 같은 캐시에 다운로드합니다.

첫 실행 시 받을 수 있는 항목:

- `neolord0/hwp2hwpx` 소스: `https://github.com/neolord0/hwp2hwpx.git`
- fallback source ZIP: `https://github.com/neolord0/hwp2hwpx/archive/refs/heads/main.zip`
- `hwplib-1.1.10.jar`
- `hwpxlib-1.0.8.jar`
- 로컬 JDK가 없을 때 Windows x64용 portable Temurin/OpenJDK 17

기본 도구 캐시:

- 현재 프로젝트에 `.tools` 폴더가 있으면 그 안에 저장합니다.
- 그렇지 않으면 `%LOCALAPPDATA%\han-auto\tools` 아래에 저장합니다.
- 캐시에는 `downloads`, `jdk`, `hwp2hwpx-src`, `hwp2hwpx-lib`, `hwp2hwpx-build`가 포함됩니다.

수동 JDK 설정:

```powershell
java -version
javac -version
```

환경변수:

```powershell
$env:HAN_AUTO_TOOL_ROOT = "C:\path\to\han-auto-tools"
$env:HAN_AUTO_JAVA_HOME = "C:\path\to\jdk-17"
$env:HAN_AUTO_HWP2HWPX_SOURCE = "C:\path\to\hwp2hwpx"
$env:HAN_AUTO_HWP2HWPX_CLASSPATH = "C:\path\to\classes;C:\path\to\hwplib.jar;C:\path\to\hwpxlib.jar"
```

사내망에서 GitHub, Maven Central, Adoptium 다운로드가 막히면 한 번 허용된 네트워크에서 캐시를 준비하거나, 위 환경변수로 JDK/source/classpath를 직접 지정합니다.

단독 변환:

```powershell
han-auto hwp-to-hwpx C:\path\to\template.hwp --output C:\path\to\template.hwpx
```

## Markdown 입력

Markdown 입력은 YAML front matter와 본문으로 구성합니다.

```markdown
---
recipient: Sample recipient
title: Sample title
fields:
  sender: Sample sender
---

# Body heading

Body text with **bold text**.
```

## 템플릿 설정

템플릿 설정은 YAML 파일입니다. `field_mapping`은 입력 데이터 이름과 HWP 필드명을 연결합니다.

```yaml
template_path: C:/path/to/template.hwp
field_mapping:
  recipient: "수신"
  title: "문서제목"
  body: "본문내용"
style_mapping:
  heading: {}
  bold: CharShapeBold
```

---

# English

`han-auto` generates report and notice drafts while preserving Hancom HWP/HWPX templates. It can fill HWP fields from Markdown, generate a structured report draft from a topic and source files, convert HWP templates to HWPX, and render the result into the original layout.

## Overview

- Parse Markdown notice drafts and fill HWP template fields.
- Generate four-section public-report drafts and insert them into HWPX templates.
- Accept `.hwp` templates by converting them to `.hwpx` with `neolord0/hwp2hwpx`.
- Replace the company logo image inside the HWPX package.
- Support offline, OpenAI API, Anthropic API, Codex CLI, and Claude CLI draft providers.
- On Windows, reopen and resave generated files through Hancom HWP COM automation when available.

## Requirements

- Windows is recommended for the full workflow. `parse` works anywhere, but HWP field inspection, rendering, and optional resave require Hancom Office COM automation on Windows.
- Python 3.11 or newer is required.
- `uv` is recommended for installation and execution.
- Hancom Office for Windows is required when opening or resaving HWP/HWPX files through the real HWP application.
- A Java JDK is required only when a `.hwp` template must be converted to `.hwpx`. A JRE is not enough because the program compiles a small Java wrapper.
- Maven is not required. The program downloads the required Java jars directly.
- Git is optional. If Git is available, the program clones `hwp2hwpx`; otherwise it downloads the source ZIP.
- First `.hwp` conversion may require network access for JDK, source, and jar downloads.
- External AI drafting is optional. API providers require API keys; CLI providers require installed and authenticated local CLIs.

## Install

```powershell
uv sync
```

For editable development installation:

```powershell
python -m pip install -e .
```

## Commands

```powershell
uv run han-auto parse examples/notice.md
uv run han-auto inspect-fields path\to\template.hwp
uv run han-auto render examples/notice.md --template configs/templates/default.yaml --output output.hwp
uv run han-auto draft-hwpx template.hwpx --topic "KBS AI analysis" --company "StayX Inc." --logo logo.png --output output.hwpx
uv run han-auto draft-hwpx templates/brother-public-report.hwpx --topic "KBS AI analysis" --company "StayX Inc." --output output.hwpx
uv run han-auto draft-hwpx template.hwp --topic "KBS AI analysis" --provider codex-cli --output output.hwpx
uv run han-auto hwp-to-hwpx template.hwp --output template.hwpx
```

`parse` does not require Hancom Office. `inspect-fields` and `render` require Hancom Office for Windows and the `pywin32` COM bridge.
Before using `configs/templates/default.yaml`, set `template_path` to the real HWP template path.
`templates/brother-public-report.hwpx` is a public-agency report template downloaded from the Brother Korea Naver Blog.
Source: https://blog.naver.com/brother_korea/223455020711?trackingCode=rss

## Report Draft Generation

`draft-hwpx` creates a structured four-section report draft and inserts it into an HWPX template. It accepts both `.hwpx` and `.hwp` templates. When the template is `.hwp`, it is converted to `.hwpx` before rendering.

Bundled example template:

- `templates/brother-public-report.hwpx`
- Original filename: `브라더 공공기관 보고서 양식.hwpx`
- Source: Brother Korea Naver Blog, https://blog.naver.com/brother_korea/223455020711?trackingCode=rss

```powershell
han-auto draft-hwpx `
  C:\path\to\template.hwpx `
  --topic "KBS AI analysis plan" `
  --company "StayX Inc." `
  --logo C:\path\to\logo.png `
  --source C:\path\to\source.pdf `
  --output C:\path\to\output.hwpx
```

To reduce Hancom security popups, download Hancom's official `보안모듈(Automation).zip`. The program searches common folders for the DLL or ZIP, and you can also pass the DLL explicitly.

```powershell
han-auto draft-hwpx template.hwpx `
  --topic "KBS AI analysis" `
  --output output.hwpx `
  --security-dll path\to\FilePathCheckerModuleExample.dll
```

## AI Draft Providers

`draft-hwpx` supports these providers:

- `offline`: deterministic local draft, no external model.
- `openai` or `codex`: direct OpenAI API call. Requires `OPENAI_API_KEY`.
- `anthropic` or `claude`: direct Anthropic API call. Requires `ANTHROPIC_API_KEY`.
- `codex-cli`: runs local Codex CLI non-interactively.
- `claude-cli`: runs local Claude Code CLI non-interactively.

OpenAI API:

```powershell
$env:OPENAI_API_KEY = "sk-..."
han-auto draft-hwpx C:\path\to\template.hwpx `
  --topic "KBS AI analysis plan" `
  --provider openai `
  --model gpt-4.1 `
  --output C:\path\to\output.hwpx
```

Anthropic API:

```powershell
$env:ANTHROPIC_API_KEY = "sk-ant-..."
han-auto draft-hwpx C:\path\to\template.hwpx `
  --topic "KBS AI analysis plan" `
  --provider anthropic `
  --model claude-sonnet-4-5 `
  --output C:\path\to\output.hwpx
```

Codex CLI:

```powershell
codex --version
codex login

han-auto draft-hwpx C:\path\to\template.hwp `
  --topic "KBS AI analysis plan" `
  --provider codex-cli `
  --model gpt-5.4 `
  --output C:\path\to\output.hwpx
```

Claude CLI:

```powershell
claude --version
claude auth

han-auto draft-hwpx C:\path\to\template.hwp `
  --topic "KBS AI analysis plan" `
  --provider claude-cli `
  --model sonnet `
  --output C:\path\to\output.hwpx
```

CLI provider environment variables:

```powershell
$env:HAN_AUTO_CODEX_CLI = "C:\path\to\codex.cmd"
$env:HAN_AUTO_CLAUDE_CLI = "C:\path\to\claude.exe"
$env:HAN_AUTO_CLI_TIMEOUT = "900"
```

CLI mode is convenient on a personal workstation because it can reuse local CLI authentication. API mode is more predictable for servers and shared automation.

## HWP to HWPX Conversion

HWP input support uses the Java library at `https://github.com/neolord0/hwp2hwpx`. On first conversion, the program prepares a local tool cache, downloads or clones the source, downloads required jars, and builds a small Java CLI wrapper. If no local JDK is found on Windows, it downloads a portable Temurin/OpenJDK 17 into the cache.

Possible first-run downloads:

- `neolord0/hwp2hwpx` source from GitHub
- fallback source ZIP
- `hwplib-1.1.10.jar`
- `hwpxlib-1.0.8.jar`
- portable Temurin/OpenJDK 17 for Windows x64 when no local JDK is found

Tool cache:

- If the current project has `.tools`, conversion assets are stored there.
- Otherwise they are stored under `%LOCALAPPDATA%\han-auto\tools`.

Environment variables:

```powershell
$env:HAN_AUTO_TOOL_ROOT = "C:\path\to\han-auto-tools"
$env:HAN_AUTO_JAVA_HOME = "C:\path\to\jdk-17"
$env:HAN_AUTO_HWP2HWPX_SOURCE = "C:\path\to\hwp2hwpx"
$env:HAN_AUTO_HWP2HWPX_CLASSPATH = "C:\path\to\classes;C:\path\to\hwplib.jar;C:\path\to\hwpxlib.jar"
```

Standalone conversion:

```powershell
han-auto hwp-to-hwpx C:\path\to\template.hwp --output C:\path\to\template.hwpx
```

## Markdown Input

Markdown input uses YAML front matter plus a body.

```markdown
---
recipient: Sample recipient
title: Sample title
fields:
  sender: Sample sender
---

# Body heading

Body text with **bold text**.
```

## Template Config

Template settings are YAML files. `field_mapping` maps source data names to HWP field names.

```yaml
template_path: C:/path/to/template.hwp
field_mapping:
  recipient: "recipient"
  title: "document_title"
  body: "body"
style_mapping:
  heading: {}
  bold: CharShapeBold
```
