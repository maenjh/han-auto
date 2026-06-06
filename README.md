# han-auto

`han-auto` converts a Markdown public notice draft into structured data and fills
Hancom HWP template fields through `win32com`.

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
```

`parse` works without Hancom Office. `inspect-fields` and `render` require
Hancom Office for Windows and the `pywin32` COM bridge.

`draft-hwpx` generates a four-section public report draft and inserts it into an
HWPX report template while preserving the template layout. By default it uses a
deterministic offline draft generator. Use `--provider claude` with
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
