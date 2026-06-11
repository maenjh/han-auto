"""Command line interface for han-auto."""

from __future__ import annotations

import logging
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
from han_auto.hwpx_report import render_public_report_hwpx
from han_auto.parser import parse_markdown_file
from han_auto.source import extract_source_text

app = typer.Typer(help="Generate Hancom HWP public notices from Markdown.")
console = Console()

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
    visible: Annotated[bool, typer.Option(help="Show the HWP window.")] = False,
    skip_security_register: Annotated[
        bool,
        typer.Option(help="Do not call HWP FilePathCheckDLL registration."),
    ] = False,
    security_dll: Annotated[
        Path | None,
        typer.Option(help="Explicit FilePathCheckDLL.dll path."),
    ] = None,
    security_module_name: Annotated[
        str,
        typer.Option(help="Registry value/module name for the HWP FilePathCheckDLL."),
    ] = "FilePathCheckerModuleExample",
) -> None:
    """List field names from an HWP template."""

    try:
        fields = inspect_hwp_fields(
            template_path,
            visible=visible,
            register_security=not skip_security_register,
            security_dll=security_dll,
            security_module_name=security_module_name,
        )
    except HanAutoError as exc:
        _fail(exc)
    for field in fields:
        console.print(field)


@app.command()
def render(
    input_path: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    template: Annotated[Path, typer.Option("--template", "-t", exists=True, dir_okay=False)],
    output: Annotated[Path, typer.Option("--output", "-o")],
    visible: Annotated[bool, typer.Option(help="Show the HWP window.")] = False,
    skip_security_register: Annotated[
        bool,
        typer.Option(help="Do not call HWP FilePathCheckDLL registration."),
    ] = False,
    security_dll: Annotated[
        Path | None,
        typer.Option(help="Explicit FilePathCheckDLL.dll path."),
    ] = None,
    security_module_name: Annotated[
        str,
        typer.Option(help="Registry value/module name for the HWP FilePathCheckDLL."),
    ] = "FilePathCheckerModuleExample",
    plain_body: Annotated[
        bool,
        typer.Option(help="Use PutFieldText for body instead of styled insertion."),
    ] = False,
) -> None:
    """Render Markdown input into an HWP output file."""

    try:
        document = parse_markdown_file(input_path)
        template_config = load_template_config(template)
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
    except HanAutoError as exc:
        _fail(exc)
    console.print(f"[green]Saved[/] {output_path}")


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


def _fail(exc: HanAutoError) -> None:
    console.print(f"[red]Error:[/] {exc}")
    raise typer.Exit(1)
