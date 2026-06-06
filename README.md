# han-auto

`han-auto` converts a Markdown public notice draft into structured data and fills
Hancom HWP template fields through `win32com`.

## Requirements

- Windows is recommended for the full workflow. `parse` works anywhere, but
  `inspect-fields`, `render`, and the optional HWP resave step use Hancom Office
  COM automation on Windows.
- Python 3.11 or newer is required.
- `uv` is recommended for installing and running the project.
- Hancom Office for Windows is required when opening/resaving HWP/HWPX through
  the real HWP application.
- A Java JDK is required only when the input template is `.hwp` and must be
  converted to `.hwpx`. A JRE is not enough because the program compiles a small
  Java wrapper around `neolord0/hwp2hwpx`.
- Maven is not required. The program downloads the exact Java dependency jars
  directly.
- Git is optional. If `git` is available, the program clones `hwp2hwpx`; if not,
  it downloads the source ZIP instead.
- Network access is needed on the first `.hwp` conversion unless you provide a
  preinstalled JDK, local `hwp2hwpx` source, and local classpath through
  environment variables.
- The first automatic JDK download is roughly 180 MB, so allow enough disk space
  in the tool cache.
- External AI drafting is optional. Use `ANTHROPIC_API_KEY` for
  `--provider claude`, or `OPENAI_API_KEY` for `--provider codex`/`openai`.
  You can also use local CLI login sessions with `--provider claude-cli` or
  `--provider codex-cli`.

## Install

```powershell
uv sync
```

## Commands

```powershell
uv run han-auto parse examples/notice.md
uv run han-auto inspect-fields path\to\template.hwp
uv run han-auto render examples/notice.md --template configs/templates/default.yaml --output output.hwp
uv run han-auto draft-hwpx template.hwpx --topic "KBS AI 분석" --company "주식회사 스테이엑스" --logo logo.png --output output.hwpx
uv run han-auto draft-hwpx template.hwp --topic "KBS AI 분석" --provider codex-cli --output output.hwpx
uv run han-auto hwp-to-hwpx template.hwp --output template.hwpx
```

`parse` works without Hancom Office. `inspect-fields` and `render` require
Hancom Office for Windows and the `pywin32` COM bridge.

`draft-hwpx` generates a four-section public report draft and inserts it into an
HWPX report template while preserving the template layout. It also accepts an
HWP template; when the input ends with `.hwp`, it first converts the template to
HWPX with `neolord0/hwp2hwpx` and then runs the same HWPX rendering flow. By
default it uses a deterministic offline draft generator. Use `--provider claude` with
`ANTHROPIC_API_KEY`, or `--provider codex`/`--provider openai` with
`OPENAI_API_KEY`, to generate the draft through an external model. On Windows,
the command reopens and resaves the output through Hancom HWP when available so
the layout is recalculated. Before opening the file, it automatically registers
Hancom's FilePathCheckDLL security module when the DLL or the official
`보안모듈(Automation).zip` is found in common locations such as Downloads,
Desktop, Documents, or Hancom install folders.

```powershell
han-auto draft-hwpx `
  C:\path\to\template.hwpx `
  --topic "KBS AI 분석" `
  --company "주식회사 스테이엑스" `
  --logo C:\path\to\logo.png `
  --output C:\path\to\output.hwpx
```

For security-popup bypass, download Hancom's official `보안모듈(Automation).zip`
from Hancom Developer. `draft-hwpx` and `render` can auto-detect the extracted
DLL or ZIP in common folders. You can also pass the extracted DLL explicitly
when needed:

```powershell
uv run han-auto render examples/notice.md --template configs/templates/default.yaml --output output.hwp --security-dll path\to\FilePathCheckerModuleExample.dll
han-auto draft-hwpx template.hwpx --topic "KBS AI 분석" --output output.hwpx --security-dll path\to\FilePathCheckerModuleExample.dll
```

## AI Draft Providers

`draft-hwpx` can create the report draft in four ways:

- `--provider offline`: deterministic local draft, no external model.
- `--provider openai` or `--provider codex`: direct OpenAI API call. Requires
  `OPENAI_API_KEY`.
- `--provider anthropic` or `--provider claude`: direct Anthropic API call.
  Requires `ANTHROPIC_API_KEY`.
- `--provider codex-cli` or `--provider claude-cli`: run the installed local CLI
  and use its authenticated session.

API examples:

```powershell
$env:OPENAI_API_KEY = "sk-..."
han-auto draft-hwpx C:\path\to\template.hwpx `
  --topic "KBS AI 분석 기획" `
  --provider openai `
  --model gpt-4.1 `
  --output C:\path\to\output.hwpx

$env:ANTHROPIC_API_KEY = "sk-ant-..."
han-auto draft-hwpx C:\path\to\template.hwpx `
  --topic "KBS AI 분석 기획" `
  --provider anthropic `
  --model claude-sonnet-4-5 `
  --output C:\path\to\output.hwpx
```

Codex CLI mode:

1. Install and authenticate Codex CLI.
2. Confirm it is available:

```powershell
codex --version
codex login
```

3. Run `draft-hwpx` with `codex-cli`:

```powershell
han-auto draft-hwpx C:\path\to\template.hwp `
  --topic "KBS AI 분석 기획" `
  --provider codex-cli `
  --model gpt-5.4 `
  --output C:\path\to\output.hwpx
```

Internally, the program runs Codex non-interactively with `codex exec`,
`--sandbox read-only`, and a JSON schema. Codex writes only the structured draft;
`han-auto` still handles HWP/HWPX conversion and template rendering.

Claude CLI mode:

1. Install and authenticate Claude Code.
2. Confirm it is available:

```powershell
claude --version
claude auth
```

3. Run `draft-hwpx` with `claude-cli`:

```powershell
han-auto draft-hwpx C:\path\to\template.hwp `
  --topic "KBS AI 분석 기획" `
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

Use these when the CLI executable is not on `PATH`, or when a long document
needs more than the default 600-second timeout. CLI mode is convenient on a
personal workstation because it can reuse local CLI auth, but API mode is more
predictable for servers or shared automation.

## HWP to HWPX Conversion

HWP input support uses the Java library at `https://github.com/neolord0/hwp2hwpx`.
The first `.hwp` conversion prepares a local tool cache, clones/downloads the
library source, downloads the required `hwplib`/`hwpxlib` jars, and builds a
small CLI wrapper. If a JDK is not installed on Windows, `han-auto` downloads a
portable Temurin JDK into the same cache. You can override cache and Java paths
with `HAN_AUTO_TOOL_ROOT`, `HAN_AUTO_JAVA_HOME`, `HAN_AUTO_HWP2HWPX_SOURCE`, or
`HAN_AUTO_HWP2HWPX_CLASSPATH`.

First-run downloads for `.hwp` input:

- `neolord0/hwp2hwpx` source from GitHub:
  `https://github.com/neolord0/hwp2hwpx.git`
- fallback source ZIP:
  `https://github.com/neolord0/hwp2hwpx/archive/refs/heads/main.zip`
- `hwplib-1.1.10.jar` from Maven Central
- `hwpxlib-1.0.8.jar` from Maven Central
- portable Temurin/OpenJDK 17 for Windows x64 from Adoptium, only when no local
  JDK with both `java` and `javac` is found

Default tool cache:

- If the current project has `.tools`, conversion assets are stored there.
- Otherwise they are stored under
  `%LOCALAPPDATA%\han-auto\tools`.
- The cache contains `downloads`, `jdk`, `hwp2hwpx-src`, `hwp2hwpx-lib`, and
  `hwp2hwpx-build`.

Manual JDK setup:

1. Download and install Temurin/OpenJDK 17 or newer for Windows x64.
2. Set `JAVA_HOME` or `HAN_AUTO_JAVA_HOME` to the JDK folder.
3. Confirm both commands work:

```powershell
java -version
javac -version
```

Environment variables:

```powershell
$env:HAN_AUTO_TOOL_ROOT = "C:\path\to\han-auto-tools"
$env:HAN_AUTO_JAVA_HOME = "C:\path\to\jdk-17"
$env:HAN_AUTO_HWP2HWPX_SOURCE = "C:\path\to\hwp2hwpx"
$env:HAN_AUTO_HWP2HWPX_CLASSPATH = "C:\path\to\classes;C:\path\to\hwplib.jar;C:\path\to\hwpxlib.jar"
```

Use `HAN_AUTO_HWP2HWPX_SOURCE` when the PC cannot access GitHub but you already
copied the `hwp2hwpx` source locally. Use `HAN_AUTO_HWP2HWPX_CLASSPATH` only when
you want to manage the compiled Java classes and jars yourself.

Standalone conversion:

```powershell
han-auto hwp-to-hwpx C:\path\to\template.hwp --output C:\path\to\template.hwpx
```

Draft generation with an HWP template:

```powershell
han-auto draft-hwpx C:\path\to\template.hwp --topic "KBS AI 분석" --output C:\path\to\output.hwpx
```

If the first conversion fails because a company firewall blocks downloads, run
the command once on a network that allows GitHub, Maven Central, and Adoptium, or
prepare the JDK/source/classpath manually with the environment variables above.

## Markdown Input

The input file uses YAML front matter for document metadata and Markdown for the
body.

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

Template settings are YAML files. `field_mapping` maps source data names to HWP
field names.

```yaml
template_path: ../../templates/sample.hwp
field_mapping:
  recipient: "수신"
  title: "문서제목"
  body: "본문내용"
style_mapping:
  heading: {}
  bold: CharShapeBold
```
