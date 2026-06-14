"""Command line interface for han-auto."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Annotated

from rich.console import Console
import typer

from han_auto.config import load_template_config
from han_auto.draft import generate_report_draft
from han_auto.exceptions import HanAutoError
from han_auto.hwp import inspect_fields as inspect_hwp_fields
from han_auto.hwp import render_with_com
from han_auto.hwp2hwpx import convert_hwp_to_hwpx
from han_auto.hwpx_fields import fill_fields, list_field_names
from han_auto.hwpx_report import render_public_report_hwpx
from han_auto.parser import parse_markdown_file
from han_auto.resources import list_resources, resource_path
from han_auto.source import extract_source_text

app = typer.Typer(help="Generate Hancom HWP public notices from Markdown.")
console = Console()


def _resolve_engine(engine: str) -> str:
    """Pick the field engine. ``auto`` uses Hancom COM only where it can actually run."""

    if engine != "auto":
        return engine
    if os.name == "nt":
        try:
            import win32com.client  # type: ignore[import-not-found]  # noqa: F401

            return "com"
        except ImportError:
            return "native"
    return "native"

# Surface library progress logs (tool downloads, template style warnings) to CLI users.
logging.basicConfig(level=logging.INFO, format="%(message)s")


@app.command()
def parse(input_path: Annotated[Path, typer.Argument(exists=True, dir_okay=False)]) -> None:
    """Parse Markdown input and print structured JSON."""

    try:
        document = parse_markdown_file(input_path)
    except HanAutoError as exc:
        _fail(exc)
    console.print_json(document.model_dump_json(indent=2))


@app.command("inspect-fields")
def inspect_fields(
    template_path: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    engine: Annotated[
        str,
        typer.Option(
            "--engine",
            help="auto, native (HWPX XML, cross-platform), or com (Hancom Office on Windows).",
        ),
    ] = "auto",
    visible: Annotated[bool, typer.Option(help="Show the HWP window (com engine only).")] = False,
    skip_security_register: Annotated[
        bool,
        typer.Option(help="Do not call HWP FilePathCheckDLL registration (com engine only)."),
    ] = False,
    security_dll: Annotated[
        Path | None,
        typer.Option(help="Explicit FilePathCheckDLL.dll path (com engine only)."),
    ] = None,
    security_module_name: Annotated[
        str,
        typer.Option(help="Registry value/module name for the HWP FilePathCheckDLL (com engine only)."),
    ] = "FilePathCheckerModuleExample",
) -> None:
    """List 누름틀 field names from an HWP/HWPX template.

    The default `native` engine reads the HWPX XML directly and needs no Hancom Office,
    so it works on macOS and Linux. `.hwp` inputs are converted to `.hwpx` first.
    """

    try:
        if _resolve_engine(engine) == "com":
            fields = inspect_hwp_fields(
                template_path,
                visible=visible,
                register_security=not skip_security_register,
                security_dll=security_dll,
                security_module_name=security_module_name,
            )
        else:
            fields = list_field_names(template_path)
    except HanAutoError as exc:
        _fail(exc)
    for field in fields:
        console.print(field)


@app.command()
def render(
    input_path: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    template: Annotated[Path, typer.Option("--template", "-t", exists=True, dir_okay=False)],
    output: Annotated[Path, typer.Option("--output", "-o")],
    engine: Annotated[
        str,
        typer.Option(
            "--engine",
            help="auto, native (HWPX XML → .hwpx, cross-platform), or com (Hancom Office → .hwp on Windows).",
        ),
    ] = "auto",
    visible: Annotated[bool, typer.Option(help="Show the HWP window (com engine only).")] = False,
    skip_security_register: Annotated[
        bool,
        typer.Option(help="Do not call HWP FilePathCheckDLL registration (com engine only)."),
    ] = False,
    security_dll: Annotated[
        Path | None,
        typer.Option(help="Explicit FilePathCheckDLL.dll path (com engine only)."),
    ] = None,
    security_module_name: Annotated[
        str,
        typer.Option(help="Registry value/module name for the HWP FilePathCheckDLL (com engine only)."),
    ] = "FilePathCheckerModuleExample",
    plain_body: Annotated[
        bool,
        typer.Option(help="Use PutFieldText for body instead of styled insertion (com engine only)."),
    ] = False,
) -> None:
    """Render Markdown input into an HWP/HWPX output file.

    The default `native` engine fills 누름틀 fields directly in the HWPX XML and writes
    `.hwpx`, so it works on macOS and Linux without Hancom Office. The `com` engine uses
    Hancom on Windows to write `.hwp` with styled body insertion.
    """

    try:
        document = parse_markdown_file(input_path)
        template_config = load_template_config(template)
        if _resolve_engine(engine) == "com":
            output_path = render_with_com(
                document,
                template_config,
                output,
                visible=visible,
                register_security=not skip_security_register,
                security_dll=security_dll,
                security_module_name=security_module_name,
                rich_body=not plain_body,
            )
        else:
            output_path = _render_native(document, template_config, output)
    except HanAutoError as exc:
        _fail(exc)
    console.print(f"[green]Saved[/] {output_path}")


def _render_native(document, template_config, output: Path) -> Path:
    """Fill template fields with plain text and write HWPX (no Hancom Office)."""

    source_values = document.field_values()
    field_text = {
        target: source_values.get(source, "")
        for source, target in template_config.field_mapping.items()
    }
    target = output
    if target.suffix.lower() != ".hwpx":
        target = target.with_suffix(".hwpx")
        console.print(f"[yellow]native 엔진은 .hwpx만 출력합니다 → {target.name}[/]")
    return fill_fields(template_config.template_path, field_text, target)


@app.command("draft-hwpx")
def draft_hwpx(
    template_path: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    topic: Annotated[str, typer.Option("--topic", "-p", help="Report topic or request.")],
    output: Annotated[Path, typer.Option("--output", "-o")],
    company: Annotated[str, typer.Option("--company", "-c")] = "주식회사 스테이엑스",
    audience: Annotated[str, typer.Option("--audience", "-a")] = "공공기관 및 방송사 실무진",
    notes: Annotated[str, typer.Option("--notes", "-n")] = "",
    source: Annotated[
        Path | None,
        typer.Option("--source", "-s", exists=True, dir_okay=False, help="PDF, TXT, Markdown, HWP, or HWPX source file."),
    ] = None,
    logo: Annotated[Path | None, typer.Option("--logo", exists=True, dir_okay=False)] = None,
    provider: Annotated[
        str,
        typer.Option("--provider", help="offline, openai/codex, anthropic/claude, codex-cli, or claude-cli."),
    ] = "offline",
    model: Annotated[str | None, typer.Option("--model", help="Provider model name.")] = None,
    skip_hwp_resave: Annotated[
        bool,
        typer.Option(help="Do not reopen and resave with Hancom HWP after HWPX generation."),
    ] = False,
    skip_security_register: Annotated[
        bool,
        typer.Option(help="Do not auto-register Hancom HWP FilePathCheckDLL before resaving."),
    ] = False,
    security_dll: Annotated[
        Path | None,
        typer.Option(help="Explicit FilePathCheckDLL.dll path for automatic HWP security approval."),
    ] = None,
    security_module_name: Annotated[
        str,
        typer.Option(help="Registry value/module name for the HWP FilePathCheckDLL."),
    ] = "FilePathCheckerModuleExample",
) -> None:
    """Generate a report draft and render it into an HWPX template."""

    try:
        source_text = extract_source_text(source) if source is not None else ""
        combined_notes = "\n\n".join(part for part in [notes, source_text] if part.strip())
        draft = generate_report_draft(
            topic=topic,
            company=company,
            audience=audience,
            notes=combined_notes,
            provider=provider,  # type: ignore[arg-type]
            model=model,
        )
        output_path = render_public_report_hwpx(
            template_path=template_path,
            output_path=output,
            draft=draft,
            logo_path=logo,
            resave_with_hwp=not skip_hwp_resave,
            register_security=not skip_security_register,
            security_dll=security_dll,
            security_module_name=security_module_name,
        )
    except HanAutoError as exc:
        _fail(exc)
    console.print(f"[green]Saved[/] {output_path}")


@app.command("hwp-to-hwpx")
def hwp_to_hwpx(
    input_path: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    output: Annotated[Path, typer.Option("--output", "-o")],
    tool_root: Annotated[
        Path | None,
        typer.Option(help="Tool cache root for hwp2hwpx source, JDK, build, and dependency jars."),
    ] = None,
) -> None:
    """Convert an HWP file to HWPX through neolord0/hwp2hwpx."""

    try:
        output_path = convert_hwp_to_hwpx(input_path, output, tool_root=tool_root)
    except HanAutoError as exc:
        _fail(exc)
    console.print(f"[green]Saved[/] {output_path}")


@app.command("resources")
def resources() -> None:
    """Print packaged templates, configs, and examples."""

    for name in list_resources():
        console.print(f"{name}\t{resource_path(name)}")


def _fail(exc: HanAutoError) -> None:
    console.print(f"[red]Error:[/] {exc}")
    raise typer.Exit(1)
