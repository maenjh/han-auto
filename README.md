# han-auto

`han-auto`는 한컴 HWP/HWPX 양식을 유지한 상태로 보고서와 공문 초안을 자동 생성하는 도구입니다.
Markdown 문서를 HWP 필드에 넣거나, HWP/HWPX 양식과 PDF/TXT/Markdown 원문을 바탕으로 AI 초안을 만든 뒤 양식에 맞춰 HWPX 결과물을 생성할 수 있습니다.

## 개요

- Markdown 공문 초안을 구조화하고 HWP 템플릿 필드에 입력합니다.
- 공공기관 보고서형 HWPX 양식에 맞춰 4개 장 구성의 보고서 초안과 예산·일정·역할분담 표를 생성합니다.
- `.hwp` 양식이 들어오면 `neolord0/hwp2hwpx`를 이용해 `.hwpx`로 변환한 뒤 처리합니다.
- 참고 자료는 PDF/TXT/Markdown/HWP/HWPX에서 텍스트를 추출해 초안 생성에 반영합니다.
- 회사 로고 이미지를 HWPX 내부 이미지로 교체할 수 있습니다(`logo` extra 필요: `pip install 'han-auto[logo]'`).
- 초안 생성 방식은 로컬 오프라인, OpenAI/Anthropic API, Codex CLI, Claude CLI를 지원합니다.
- Windows 환경에서는 한컴 HWP COM 자동화를 이용해 생성된 HWPX를 다시 열고 저장하여 레이아웃을 재계산할 수 있습니다.

## 요구사항

- `parse`, `inspect-fields`, `render`, `hwp-to-hwpx`, `draft-hwpx`는 Windows·macOS·Linux에서 모두 동작합니다. `inspect-fields`와 `render`는 기본적으로 한컴오피스 없이 HWPX XML을 직접 다루는 `native` 엔진을 사용합니다. 한컴오피스 COM 자동화(`--engine com`, HWP 레이아웃 재저장, 바이너리 `.hwp` 저장)만 Windows + 한컴오피스가 필요합니다.
- Python 3.11 이상이 필요합니다.
- 설치와 실행에는 `uv` 사용을 권장합니다.
- 실제 한컴 HWP/HWPX 파일을 열거나 다시 저장하려면 Windows용 한컴오피스가 필요합니다.
- `.hwp` 양식을 `.hwpx`로 변환할 때만 Java JDK가 필요합니다. 프로그램이 `neolord0/hwp2hwpx`용 Java wrapper를 컴파일하므로 JRE만으로는 부족합니다.
- Maven은 필요하지 않습니다. 필요한 Java jar는 프로그램이 직접 다운로드합니다.
- Git은 선택사항입니다. Git이 있으면 `hwp2hwpx` 소스를 clone하고, 없으면 ZIP 파일을 다운로드합니다.
- 첫 `.hwp` 변환 시 JDK, `hwp2hwpx` 소스, jar 파일을 자동으로 받을 수 있어 네트워크가 필요합니다. 사내망에서 차단되는 경우 환경변수로 로컬 경로를 지정할 수 있습니다.
- 자동 JDK 다운로드는 약 180MB이므로 도구 캐시에 충분한 디스크 공간이 필요합니다.
- 외부 AI 초안 생성은 선택사항입니다. API 방식은 `OPENAI_API_KEY` 또는 `ANTHROPIC_API_KEY`가 필요하고, CLI 방식은 로컬 Codex/Claude CLI 설치와 로그인이 필요합니다.

### 명령별 환경 요구 매트릭스

| 명령 | Windows | 한컴오피스 | 보안모듈 DLL | Java JDK | 네트워크 | API 키 / CLI 로그인 |
|------|---------|-----------|-------------|----------|---------|---------------------|
| `parse` | 불필요 | 불필요 | 불필요 | 불필요 | 불필요 | 불필요 |
| `inspect-fields` (native, 기본) | 불필요 | 불필요 | 불필요 | `.hwp` 입력 시 필요 | `.hwp` 첫 변환 시 | 불필요 |
| `inspect-fields --engine com` | **필수** | **필수** | 권장 | 불필요 | 불필요 | 불필요 |
| `render` (native, 기본 → `.hwpx`) | 불필요 | 불필요 | 불필요 | `.hwp` 입력 시 필요 | `.hwp` 첫 변환 시 | 불필요 |
| `render --engine com` (→ `.hwp`) | **필수** | **필수** | 권장 | 불필요 | 불필요 | 불필요 |
| `draft-hwpx` (`.hwpx` 템플릿) | 불필요 | 불필요 | 불필요 | 불필요 | provider에 따라 | provider에 따라 |
| `draft-hwpx` (`.hwp` 템플릿) | 불필요* | 불필요 | 불필요 | **필수**(자동 설치 가능) | 첫 실행 시 필요 | provider에 따라 |
| `draft-hwpx` (HWP 재저장으로 레이아웃 재계산) | **필수** | **필수** | 권장 | 템플릿에 따라 | 첫 실행 시 필요 | provider에 따라 |
| `hwp-to-hwpx` | 불필요* | 불필요 | 불필요 | **필수**(자동 설치 가능) | 첫 실행 시 필요 | 불필요 |

\* `hwp-to-hwpx`와 `.hwp` 템플릿 변환은 Java만 사용하므로 Windows, macOS, Linux에서 모두 동작합니다. JDK 자동 다운로드도 세 OS를 지원하며, 현재 OS와 CPU 아키텍처에 맞는 Temurin/OpenJDK 17을 받습니다(macOS는 Apple Silicon arm64와 Intel x64 모두 지원). 자동 다운로드가 막히는 환경에서는 JDK를 직접 설치하고 `JAVA_HOME` 또는 `HAN_AUTO_JAVA_HOME`을 지정합니다.

`inspect-fields`와 `render`의 `--engine` 옵션은 `auto`(기본), `native`, `com` 중에서 고릅니다. `auto`는 Windows에 한컴오피스/`pywin32`가 있으면 `com`을, 그 외(macOS·Linux 포함)에는 `native`를 씁니다. `native` 엔진은 한컴오피스 없이 HWPX의 누름틀을 직접 읽고 채우며, `render`는 항상 `.hwpx`로 출력합니다(바이너리 `.hwp` 저장과 한컴 레이아웃 재계산은 Windows + 한컴오피스 전용). `draft-hwpx`의 HWP 재저장은 레이아웃을 다시 계산하는 선택 단계로, 한컴오피스가 없으면 자동으로 건너뜁니다(`--skip-hwp-resave`로 명시적으로 끌 수도 있음). 건너뛰어도 HWPX는 정상 생성되며, 한컴에서 파일을 열 때 레이아웃이 다시 계산됩니다.

### 한컴 보안모듈 DLL 준비 절차

한컴 COM 자동화(`inspect-fields`, `render`, HWP 재저장)는 첫 실행 시 한컴의 "보안 위험" 팝업으로 중단될 수 있습니다. 이를 우회하려면 한컴 공식 보안모듈을 등록해야 합니다.

1. 한컴 디벨로퍼(https://developer.hancom.com)에서 `보안모듈(Automation).zip`을 다운로드합니다.
2. ZIP을 그대로 `Downloads`, `Desktop`, `Documents` 중 한 곳에 두면 han-auto가 자동으로 찾아 `FilePathCheckerModuleExample.dll`을 추출·등록합니다. (탐색 순서: 현재 폴더 → Downloads → Desktop → Documents → 한컴 설치 폴더)
3. 자동 탐색에 실패하면 `--security-dll path\to\FilePathCheckerModuleExample.dll`로 직접 지정합니다.
4. 등록은 레지스트리 `HKEY_CURRENT_USER\Software\HNC\HwpAutomation\Modules`에 기록되며, 한 번 등록하면 이후 실행에서는 재등록이 필요 없습니다.
5. 회사 정책상 레지스트리 등록이 불가능하면 `--skip-security-register`로 건너뛸 수 있습니다(이 경우 팝업이 다시 나타날 수 있습니다).

### macOS 한컴오피스에서 HWPX 열기

macOS에서는 `han-auto`가 생성한 `.hwpx` 파일을 한컴오피스 한글로 직접 열 수 있습니다. 다만 HWP에서 변환한 양식을 XML로 다시 작성한 파일은 한컴오피스의 문서 보안 수준에 따라 다음 경고가 뜰 수 있습니다.

- "문서가 손상되었거나 변조되었을 가능성이 있습니다."
- "이 문서를 불러오려면 [문서 보안 설정]을 [낮음]으로 설정해야 합니다."

이 경우 한컴오피스 한글의 `보안 > 문서 보안 설정`에서 보안 수준을 `낮음`으로 바꾼 뒤 문서를 열어 확인합니다. 확인이 끝나면 보안 수준을 원래 값으로 되돌리는 것을 권장합니다. 자동화 테스트에서만 임시로 바꿔야 한다면 아래처럼 설정할 수 있습니다.

```bash
defaults write com.hancom.office.hwp12.mac.general 'Software\HNC\Hwp\12.0\HwpFrame\AppState\DocumentSecurityLevel' -int 0
open output.hwpx
defaults write com.hancom.office.hwp12.mac.general 'Software\HNC\Hwp\12.0\HwpFrame\AppState\DocumentSecurityLevel' -int 2
```

macOS에서 글자가 겹쳐 보이면 오래된 HWP 줄 배치 캐시가 남아 있는 경우가 많습니다. `han-auto`는 텍스트를 바꾼 문단의 줄 배치 캐시를 제거해 한컴오피스가 열 때 레이아웃을 다시 계산하도록 처리합니다.

## 설치

```powershell
uv sync
```

개발 환경에서 직접 설치하려면:

```powershell
python -m pip install -e .
```

## Homebrew 설치 (macOS)

macOS·Linux에서는 Homebrew로 설치할 수 있습니다. 이 저장소를 tap으로 추가한 뒤 설치합니다.

```bash
brew tap maenjh/han-auto https://github.com/maenjh/han-auto
brew install maenjh/han-auto/han-auto
han-auto --help
```

formula는 한컴오피스 없이 동작하는 기능을 제공합니다. 로고 삽입(`--logo`, Pillow)과 MCP 서버(`han-auto-mcp`, mcp)는 빌드를 가볍게 유지하기 위해 formula에 포함하지 않습니다. 두 기능까지 필요하면 extra와 함께 설치하세요.

```bash
pipx install 'han-auto[logo,mcp]'
```

설치·업그레이드·릴리스 갱신 절차는 [docs/homebrew.md](docs/homebrew.md)를 참고하세요.

## 패키지 빌드와 설치

배포용 wheel/sdist는 `uv build`로 생성합니다.

```bash
uv build --sdist --wheel
```

생성 결과:

- `dist/han_auto-0.1.0-py3-none-any.whl`
- `dist/han_auto-0.1.0.tar.gz`

로컬 wheel 설치:

```bash
python -m pip install dist/han_auto-0.1.0-py3-none-any.whl
han-auto --help
```

CLI 도구로 격리 설치:

```bash
uv tool install dist/han_auto-0.1.0-py3-none-any.whl
han-auto --help
```

패키지에는 기본 보고서 양식, 예제 설정, 예제 Markdown이 포함됩니다. 설치된 리소스 경로는 다음 명령으로 확인합니다.

```bash
han-auto resources
```

## MCP 서버

`han-auto`를 stdio MCP 서버(`han-auto-mcp`)로 실행하면 Claude Code, Codex CLI, Antigravity CLI 등 MCP 호스트에서 한컴 문서 생성·편집 도구를 바로 호출할 수 있습니다. 설치는 선택 의존성 `mcp`가 필요합니다.

```bash
uv sync --extra mcp                 # 로컬 실행
# 또는 전역 설치(PATH에 han-auto-mcp 등록)
uv build --sdist --wheel
uv tool install "dist/han_auto-0.1.0-py3-none-any.whl[mcp]"
```

Claude Code 등록 예:

```bash
claude mcp add han-auto -- han-auto-mcp
```

제공 도구(9개): `list_bundled_resources`, `inspect_fields`, `extract_source_text`, `parse_markdown`, `render_markdown_to_hwpx`, `hwp_to_hwpx`, `draft_report_hwpx`, `render_report_hwpx`, `fill_form_by_replacements`. 호스트가 직접 작성한 구조화 초안을 HWPX로 렌더링하는 `render_report_hwpx`와, 임의의 HWP/HWPX 문서를 양식으로 삼아 텍스트만 교체하는 `fill_form_by_replacements`가 핵심입니다.

Codex CLI(`~/.codex/config.toml`)·Antigravity CLI 등록 방법과 도구별 상세, `draft` 스키마는 [`docs/mcp.md`](docs/mcp.md)를 참고하세요.

## 주요 명령어

```powershell
uv run han-auto parse examples/notice.md
uv run han-auto inspect-fields path\to\template.hwp
uv run han-auto render examples/notice.md --template configs/templates/default.yaml --output output.hwp
uv run han-auto draft-hwpx template.hwpx --topic "KBS AI 분석" --company "주식회사 스테이엑스" --logo logo.png --output output.hwpx
uv run han-auto draft-hwpx templates/brother-public-report.hwpx --topic "KBS AI 분석" --company "주식회사 스테이엑스" --output output.hwpx
uv run han-auto draft-hwpx template.hwp --topic "KBS AI 분석" --provider codex-cli --output output.hwpx
uv run han-auto hwp-to-hwpx template.hwp --output template.hwpx
uv run han-auto resources
```

`parse`는 한컴오피스 없이 동작합니다. `inspect-fields`와 `render`는 기본 `native` 엔진으로 한컴오피스 없이 macOS·Linux·Windows에서 동작하며(`render`는 `.hwpx` 출력), `--engine com`을 쓸 때만 Windows용 한컴오피스와 `pywin32` COM bridge가 필요합니다.
`configs/templates/default.yaml`의 `template_path`는 실제 사용할 HWP 양식 경로로 수정한 뒤 사용합니다.
`templates/brother-public-report.hwpx`는 Brother Korea 네이버 블로그에서 받은 공공기관 보고서 양식입니다.
출처: https://blog.naver.com/brother_korea/223455020711?trackingCode=rss

## 보고서 초안 생성

`draft-hwpx`는 보고서 주제, 회사명, 참고 자료를 바탕으로 4개 장 구성의 보고서 초안을 만들고 HWPX 양식에 삽입합니다. 참고 자료는 PDF/TXT/Markdown/HWP/HWPX를 지원합니다. 예산, 추진 일정, 역할분담처럼 수치나 항목 비교가 필요한 내용은 JSON 초안의 `tables` 구조로 받고 실제 HWPX 표로 렌더링합니다. 입력 양식은 `.hwpx`와 `.hwp`를 모두 지원합니다. `.hwp`가 들어오면 먼저 `.hwpx`로 변환한 뒤 같은 렌더링 흐름을 사용합니다.

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

`.hwp` 입력 지원은 `https://github.com/neolord0/hwp2hwpx` Java 라이브러리를 사용합니다. 이 변환은 Java만 사용하므로 Windows, macOS, Linux에서 모두 동작합니다. 첫 `.hwp` 변환 시 프로그램은 로컬 도구 캐시를 준비하고, `hwp2hwpx` 소스와 필요한 jar를 받은 뒤 작은 Java CLI wrapper를 빌드합니다. JDK가 없으면 현재 OS와 아키텍처에 맞는 portable Temurin/OpenJDK 17을 같은 캐시에 다운로드합니다(Windows zip, macOS/Linux tar.gz). macOS는 `/usr/bin/java`·`/usr/bin/javac` 스텁만 있고 실제 JDK가 없는 상태도 감지해 자동 다운로드로 넘어갑니다.

첫 실행 시 받을 수 있는 항목:

- `neolord0/hwp2hwpx` 소스: `https://github.com/neolord0/hwp2hwpx.git`
- fallback source ZIP: `https://github.com/neolord0/hwp2hwpx/archive/refs/heads/main.zip`
- `hwplib-1.1.10.jar`
- `hwpxlib-1.0.8.jar`
- 로컬 JDK가 없을 때 현재 OS·아키텍처에 맞는 portable Temurin/OpenJDK 17 (Windows x64/aarch64, macOS x64/aarch64, Linux x64/aarch64)

기본 도구 캐시:

- 현재 프로젝트에 `.tools` 폴더가 있으면 그 안에 저장합니다.
- 그렇지 않으면 OS 표준 캐시 폴더 아래에 저장합니다: Windows `%LOCALAPPDATA%\han-auto\tools`, macOS `~/Library/Caches/han-auto/tools`, Linux `$XDG_CACHE_HOME/han-auto/tools` (없으면 `~/.cache/han-auto/tools`).
- 캐시에는 `downloads`, `jdk`, `hwp2hwpx-src`, `hwp2hwpx-lib`, `hwp2hwpx-build`가 포함됩니다.
- 실행 시점에 사용 중인 캐시 경로와 다운로드 진행 상황이 로그로 출력됩니다.
- 다운로드 중단·네트워크 오류로 변환이 계속 실패하면 캐시가 오염되었을 수 있습니다. 이 경우 도구 캐시 폴더(위 경로)를 통째로 삭제하고 다시 실행하면 처음부터 새로 준비합니다.

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
- Generate four-section public-report drafts, including budget, schedule, and role tables, and insert them into HWPX templates.
- Accept `.hwp` templates by converting them to `.hwpx` with `neolord0/hwp2hwpx`.
- Extract source text from PDF, TXT, Markdown, HWP, and HWPX files.
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

`parse` does not require Hancom Office. `inspect-fields` and `render` use a default `native` engine that reads/fills HWPX fields directly, so they run on macOS, Linux, and Windows without Hancom Office (`render` writes `.hwpx`). Only `--engine com` requires Hancom Office for Windows and the `pywin32` COM bridge.
Before using `configs/templates/default.yaml`, set `template_path` to the real HWP template path.
`templates/brother-public-report.hwpx` is a public-agency report template downloaded from the Brother Korea Naver Blog.
Source: https://blog.naver.com/brother_korea/223455020711?trackingCode=rss

## Report Draft Generation

`draft-hwpx` creates a structured four-section report draft and inserts it into an HWPX template. Source files can be PDF, TXT, Markdown, HWP, or HWPX. Numeric or comparison-heavy content such as budgets, schedules, and role assignments is accepted through the draft `tables` structure and rendered as real HWPX tables. It accepts both `.hwpx` and `.hwp` templates. When the template is `.hwp`, it is converted to `.hwpx` before rendering.

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

HWP input support uses the Java library at `https://github.com/neolord0/hwp2hwpx`. This conversion is pure Java, so it runs on Windows, macOS, and Linux. On first conversion, the program prepares a local tool cache, downloads or clones the source, downloads required jars, and builds a small Java CLI wrapper. If no working JDK is found, it downloads a portable Temurin/OpenJDK 17 matching the current OS and architecture into the cache (zip on Windows, tar.gz on macOS/Linux). On macOS it also detects the `/usr/bin/java` / `/usr/bin/javac` stubs that exist without a real JDK and falls back to the auto-download.

Possible first-run downloads:

- `neolord0/hwp2hwpx` source from GitHub
- fallback source ZIP
- `hwplib-1.1.10.jar`
- `hwpxlib-1.0.8.jar`
- portable Temurin/OpenJDK 17 for the current OS/arch (Windows, macOS, Linux) when no working JDK is found

Tool cache:

- If the current project has `.tools`, conversion assets are stored there.
- Otherwise they are stored under the OS cache dir: `%LOCALAPPDATA%\han-auto\tools` (Windows), `~/Library/Caches/han-auto/tools` (macOS), or `$XDG_CACHE_HOME/han-auto/tools` (Linux, defaulting to `~/.cache`).

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
