"""Model Context Protocol (MCP) server for han-auto.

Exposes han-auto's document automation as stdio MCP tools so MCP-capable hosts
(Claude Code, Codex CLI, Antigravity CLI, Claude Desktop, ...) can generate and
fill Hancom HWP/HWPX documents.

The tool functions are plain module-level functions so they can be unit-tested
without the ``mcp`` package installed. :func:`build_server` registers them on a
``FastMCP`` instance and :func:`main` runs that server over stdio.

Run the server with the packaged entry point::

    han-auto-mcp

or directly::

    python -m han_auto.mcp_server
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from han_auto.config import load_template_config
from han_auto.draft import ReportDraft, generate_report_draft
from han_auto.exceptions import HanAutoError
from han_auto.hwp import inspect_fields as inspect_hwp_fields
from han_auto.hwp2hwpx import convert_hwp_to_hwpx
from han_auto.hwpx_fields import fill_fields, list_field_names
from han_auto.hwpx_report import render_public_report_hwpx
from han_auto.hwpx_rewrite import replace_text_in_document
from han_auto.parser import parse_markdown_file
from han_auto.resources import list_resources, resource_path
from han_auto.source import extract_source_text as _extract_source_text

SERVER_NAME = "han-auto"

# The bundled public-report layout is the only template render_report_hwpx /
# draft_report_hwpx can fill, because the renderer rewrites paragraphs by index.
BUNDLED_REPORT_TEMPLATE = "templates/brother-public-report.hwpx"


# --- helpers -------------------------------------------------------------------------


def _today_korean_date() -> str:
    now = datetime.now(timezone(timedelta(hours=9)))
    return f"{now.year}. {now.month}. {now.day}."


def _existing_file(path: str, label: str) -> Path:
    resolved = Path(path).expanduser().resolve()
    if not resolved.exists():
        raise HanAutoError(f"{label} not found: {resolved}")
    if not resolved.is_file():
        raise HanAutoError(f"{label} is not a file: {resolved}")
    return resolved


def _resolve_template(template_path: str | None) -> Path:
    """Resolve a template path, defaulting to the bundled public-report template."""

    if template_path and template_path.strip():
        return _existing_file(template_path, "Template")
    return resource_path(BUNDLED_REPORT_TEMPLATE)


def _output_target(output_path: str) -> Path:
    target = Path(output_path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


# --- tool functions (registered in build_server) --------------------------------------


def list_bundled_resources() -> str:
    """List the templates, configs, and examples bundled inside the han-auto package.

    Returns a JSON array of objects with ``name`` (package-relative) and ``path``
    (absolute filesystem path). Use the absolute path of
    ``templates/brother-public-report.hwpx`` as the ``template_path`` for
    ``draft_report_hwpx`` / ``render_report_hwpx`` when you have no template of
    your own. That bundled public-report layout is the only template those two
    report tools can fill.
    """

    items = [{"name": name, "path": str(resource_path(name))} for name in list_resources()]
    return json.dumps(items, ensure_ascii=False, indent=2)


def inspect_fields(template_path: str, engine: str = "auto") -> str:
    """List the 누름틀 (click-here) field names in an HWP/HWPX template.

    Args:
        template_path: Path to a ``.hwpx`` or ``.hwp`` template. ``.hwp`` inputs are
            converted to ``.hwpx`` first (needs Java; downloaded on first use).
        engine: ``auto`` (default), ``native`` (HWPX XML, cross-platform, no Hancom
            Office), or ``com`` (Hancom Office automation, Windows only).

    Returns a JSON array of field-name strings in document order.
    """

    template = _existing_file(template_path, "Template")
    resolved_engine = engine
    if engine == "auto":
        resolved_engine = "native"
        import os

        if os.name == "nt":
            try:
                import win32com.client  # type: ignore[import-not-found]  # noqa: F401

                resolved_engine = "com"
            except ImportError:
                resolved_engine = "native"

    if resolved_engine == "com":
        names = inspect_hwp_fields(template)
    else:
        names = list_field_names(template)
    return json.dumps(list(names), ensure_ascii=False, indent=2)


def extract_source_text(path: str, max_chars: int = 12000) -> str:
    """Extract plain text from a reference document for drafting.

    Supports PDF, TXT, Markdown, HWP, and HWPX. Use this to read source material,
    then author a structured draft and render it with ``render_report_hwpx``.

    Args:
        path: Path to the source file.
        max_chars: Maximum number of characters to return (default 12000).
    """

    source = _existing_file(path, "Source file")
    return _extract_source_text(source, max_chars=max_chars)


def parse_markdown(input_path: str) -> str:
    """Parse a Markdown notice file (YAML front matter + body) into structured JSON.

    Returns the document as JSON: recipient, title, mapped fields, and body blocks.
    """

    source = _existing_file(input_path, "Markdown file")
    document = parse_markdown_file(source)
    return document.model_dump_json(indent=2)


def render_markdown_to_hwpx(
    input_path: str,
    template_config_path: str,
    output_path: str,
) -> str:
    """Fill an HWP/HWPX template's 누름틀 fields from a Markdown file and write HWPX.

    Uses the cross-platform native engine (no Hancom Office required) and always
    writes ``.hwpx``.

    Args:
        input_path: Markdown file with YAML front matter and body.
        template_config_path: YAML config mapping document fields to template field
            names (``template_path`` + ``field_mapping``). See the bundled
            ``configs/templates/default.yaml`` for the format.
        output_path: Destination ``.hwpx`` path (``.hwpx`` is enforced).
    """

    source = _existing_file(input_path, "Markdown file")
    config_file = _existing_file(template_config_path, "Template config")
    document = parse_markdown_file(source)
    template_config = load_template_config(config_file)

    target = _output_target(output_path)
    if target.suffix.lower() != ".hwpx":
        target = target.with_suffix(".hwpx")

    source_values = document.field_values()
    field_text = {
        target_field: source_values.get(source_field, "")
        for source_field, target_field in template_config.field_mapping.items()
    }
    written = fill_fields(template_config.template_path, field_text, target)
    return f"Saved {written}"


def hwp_to_hwpx(input_path: str, output_path: str, tool_root: str | None = None) -> str:
    """Convert an ``.hwp`` file to ``.hwpx`` via the neolord0/hwp2hwpx Java library.

    Pure Java, so it runs on Windows, macOS, and Linux. On first use it downloads
    the converter source, dependency jars, and (if no working JDK is found) a
    portable OpenJDK 17 into a tool cache. Network access is needed the first time.

    Args:
        input_path: Source ``.hwp`` file.
        output_path: Destination ``.hwpx`` file.
        tool_root: Optional tool-cache directory for the converter assets.
    """

    source = _existing_file(input_path, "HWP file")
    target = _output_target(output_path)
    written = convert_hwp_to_hwpx(source, target, tool_root=tool_root or None)
    return f"Saved {written}"


def draft_report_hwpx(
    topic: str,
    output_path: str,
    template_path: str | None = None,
    company: str = "주식회사 스테이엑스",
    audience: str = "공공기관 및 방송사 실무진",
    notes: str = "",
    source_path: str | None = None,
    logo_path: str | None = None,
    provider: str = "offline",
    model: str | None = None,
    skip_hwp_resave: bool = True,
) -> str:
    """Generate a 4-section public-report draft and render it into an HWPX template.

    This generates the draft *content* with a provider, then renders it. If you
    (the calling agent) want to author the Korean content yourself for higher
    quality, use ``render_report_hwpx`` instead and pass a structured draft.

    Args:
        topic: Report topic or request (Korean).
        output_path: Destination ``.hwpx`` path.
        template_path: HWP/HWPX template path. Defaults to the bundled
            public-report template when omitted. Only the bundled layout (or
            templates derived from it) is supported.
        company: Company / author name.
        audience: Target audience description.
        notes: Extra notes to fold into the draft.
        source_path: Optional reference file (PDF/TXT/MD/HWP/HWPX); its text is
            extracted and appended to the notes.
        logo_path: Optional PNG logo to insert into the template.
        provider: ``offline`` (default, no external model), ``openai``/``codex``
            (needs OPENAI_API_KEY), ``anthropic``/``claude`` (needs
            ANTHROPIC_API_KEY), ``codex-cli``, or ``claude-cli``.
        model: Provider model name (provider-specific).
        skip_hwp_resave: Skip reopening/resaving with Hancom HWP after generation
            (default True). Resave only runs on Windows with Hancom Office and is a
            layout-recalc convenience; the HWPX is valid without it.
    """

    template = _resolve_template(template_path)
    target = _output_target(output_path)

    source_text = ""
    if source_path and source_path.strip():
        source_text = _extract_source_text(_existing_file(source_path, "Source file"))
    combined_notes = "\n\n".join(part for part in [notes, source_text] if part.strip())

    draft = generate_report_draft(
        topic=topic,
        company=company,
        audience=audience,
        notes=combined_notes,
        provider=provider,  # type: ignore[arg-type]
        model=model,
    )
    written = render_public_report_hwpx(
        template_path=template,
        output_path=target,
        draft=draft,
        logo_path=_existing_file(logo_path, "Logo image") if logo_path else None,
        resave_with_hwp=not skip_hwp_resave,
    )
    return f"Saved {written}"


def render_report_hwpx(
    draft: dict[str, Any],
    output_path: str,
    template_path: str | None = None,
    logo_path: str | None = None,
    skip_hwp_resave: bool = True,
) -> str:
    """Render a structured report draft *you* authored into an HWPX template.

    This is the preferred tool for high-quality output: author the Korean content
    yourself as a structured ``draft`` object, and this renders it into the bundled
    public-report layout (title page, table of contents, four numbered sections,
    and any tables).

    The ``draft`` object schema (all text in Korean, public-report tone):

        {
          "title": "문서 제목",
          "date": "YYYY. M. D.",            # optional; defaults to today (KST)
          "company": "회사명",
          "sections": [                      # exactly 4 sections recommended
            {
              "title": "장 제목",
              "groups": [                    # 1-4 groups per section
                {
                  "title": "상위 불릿 제목",
                  "points": ["문장", "문장"], # 1-3 sentences
                  "note": "참고 문장 또는 생략"
                }
              ]
            }
          ],
          "tables": [                        # 0-3 tables (budget/schedule/roles)
            {
              "title": "표 제목",
              "columns": ["열1", "열2"],     # 2-5 columns
              "rows": [["셀", "셀"]],         # 1-12 rows, cells aligned to columns
              "note": "표 하단 참고 또는 생략"
            }
          ],
          "attachments": ["붙임 항목"],       # 0-3
          "references": ["참고 항목"]         # 0-3
        }

    Args:
        draft: The structured draft object described above.
        output_path: Destination ``.hwpx`` path.
        template_path: Template path; defaults to the bundled public-report
            template. Only that layout (or templates derived from it) is supported.
        logo_path: Optional PNG logo to insert.
        skip_hwp_resave: Skip the optional Hancom HWP resave (default True).
    """

    payload = dict(draft)
    payload.setdefault("date", _today_korean_date())
    report = ReportDraft.model_validate(payload)

    template = _resolve_template(template_path)
    target = _output_target(output_path)
    written = render_public_report_hwpx(
        template_path=template,
        output_path=target,
        draft=report,
        logo_path=_existing_file(logo_path, "Logo image") if logo_path else None,
        resave_with_hwp=not skip_hwp_resave,
    )
    return f"Saved {written}"


def fill_form_by_replacements(
    input_path: str,
    output_path: str,
    replacements: dict[str, str],
    update_preview: bool = True,
    update_metadata: bool = True,
) -> str:
    """Use any HWP/HWPX document as a 양식(form): substring-replace its text → HWPX.

    For documents that have no 누름틀 fields and do not match the report template
    (e.g. a 품의서/공문/보고서), this keeps the original layout, tables, and styling
    and only swaps the visible text. ``.hwp`` inputs are converted to ``.hwpx`` first.

    Workflow: call ``extract_source_text`` first to read the document, decide which
    exact strings to swap, then pass them here.

    Args:
        input_path: Source ``.hwp`` or ``.hwpx`` document used as the form.
        output_path: Destination ``.hwpx`` path.
        replacements: ``{old: new}`` map applied in order (JSON key order). Match the
            exact strings as they appear in the document. Put longer/more specific
            strings first so broader ones do not clobber them — e.g. replace the full
            title before a phrase contained inside it. A value that repeats (an amount,
            a name) is replaced everywhere consistently.
        update_preview: Also rewrite the file's text preview (default True).
        update_metadata: Also rewrite document metadata title/subject (default True).

    Returns a summary with the output path and how many text nodes/paragraphs changed.
    Replaced paragraphs have their cached line layout cleared so Hancom recomputes it.
    """

    source = _existing_file(input_path, "Source document")
    target = _output_target(output_path)
    if target.suffix.lower() != ".hwpx":
        target = target.with_suffix(".hwpx")
    summary = replace_text_in_document(
        source,
        target,
        replacements,
        update_preview=update_preview,
        update_metadata=update_metadata,
    )
    return json.dumps(summary, ensure_ascii=False, indent=2)


TOOLS = [
    list_bundled_resources,
    inspect_fields,
    extract_source_text,
    parse_markdown,
    render_markdown_to_hwpx,
    hwp_to_hwpx,
    draft_report_hwpx,
    render_report_hwpx,
    fill_form_by_replacements,
]


def build_server():
    """Construct the FastMCP server with all han-auto tools registered."""

    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise SystemExit(
            "The 'mcp' package is required to run the han-auto MCP server. "
            "Install it with:\n"
            "    uv pip install 'han-auto[mcp]'\n"
            "or\n"
            "    pip install 'han-auto[mcp]'"
        ) from exc

    server = FastMCP(
        SERVER_NAME,
        instructions=(
            "han-auto generates and fills Hancom HWP/HWPX documents. To produce a "
            "Korean public-report HWPX, author the content yourself as a structured "
            "draft and call render_report_hwpx (preferred), or call draft_report_hwpx "
            "to have a provider generate the content. Use list_bundled_resources to "
            "find the bundled report template, inspect_fields to discover template "
            "fields, extract_source_text to read reference files, and hwp_to_hwpx to "
            "convert .hwp inputs."
        ),
    )
    for tool in TOOLS:
        server.add_tool(tool)

    # Report han-auto's own version on the wire instead of the mcp SDK version.
    try:
        from han_auto import __version__

        server._mcp_server.version = __version__
    except Exception:  # pragma: no cover - cosmetic only; never block startup
        pass
    return server


def main() -> None:
    """Run the han-auto MCP server over stdio."""

    build_server().run()


if __name__ == "__main__":  # pragma: no cover
    main()
