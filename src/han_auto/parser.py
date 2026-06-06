"""Markdown and YAML front matter parsing."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, NavigableString, Tag
import markdown
from pydantic import ValidationError
import yaml

from han_auto.exceptions import DocumentParseError
from han_auto.models import InlineText, ListItem, MarkdownBlock, NoticeDocument

FRONT_MATTER_RE = re.compile(r"\A---\s*\r?\n(.*?)\r?\n---\s*(?:\r?\n)?(.*)\Z", re.DOTALL)


def parse_markdown_file(path: str | Path) -> NoticeDocument:
    """Parse a Markdown file from disk."""

    input_path = Path(path)
    return parse_markdown_text(input_path.read_text(encoding="utf-8"), source=str(input_path))


def parse_markdown_text(text: str, *, source: str = "<memory>") -> NoticeDocument:
    """Parse YAML front matter plus Markdown body into a notice document."""

    metadata, body = _split_front_matter(text, source=source)
    html = markdown.markdown(body, extensions=["extra", "sane_lists"])
    blocks = parse_markdown_blocks(html)

    payload: dict[str, Any] = {
        **metadata,
        "body_markdown": body.strip(),
        "body_html": html,
        "blocks": blocks,
    }
    try:
        return NoticeDocument.model_validate(payload)
    except ValidationError as exc:
        raise DocumentParseError(f"Invalid front matter in {source}: {exc}") from exc


def parse_markdown_blocks(html: str) -> list[MarkdownBlock]:
    """Convert normalized Markdown HTML into block models."""

    soup = BeautifulSoup(html, "html.parser")
    blocks: list[MarkdownBlock] = []
    for node in soup.children:
        if not isinstance(node, Tag):
            continue
        if node.name and re.fullmatch(r"h[1-6]", node.name):
            runs = _inline_runs(node)
            text = _join_runs(runs)
            blocks.append(
                MarkdownBlock(
                    type="heading",
                    level=int(node.name[1]),
                    text=text,
                    runs=runs,
                )
            )
        elif node.name == "p":
            runs = _inline_runs(node)
            blocks.append(MarkdownBlock(type="paragraph", text=_join_runs(runs), runs=runs))
        elif node.name in {"ul", "ol"}:
            ordered = node.name == "ol"
            items: list[ListItem] = []
            for item_node in node.find_all("li", recursive=False):
                runs = _inline_runs(item_node)
                items.append(ListItem(text=_join_runs(runs), runs=runs))
            blocks.append(MarkdownBlock(type="list", ordered=ordered, items=items))
    return blocks


def _split_front_matter(text: str, *, source: str) -> tuple[dict[str, Any], str]:
    match = FRONT_MATTER_RE.match(text)
    if not match:
        raise DocumentParseError(f"{source} must start with YAML front matter delimited by ---")

    raw_yaml, body = match.groups()
    try:
        metadata = yaml.safe_load(raw_yaml) or {}
    except yaml.YAMLError as exc:
        raise DocumentParseError(f"Invalid YAML front matter in {source}: {exc}") from exc
    if not isinstance(metadata, dict):
        raise DocumentParseError(f"YAML front matter in {source} must be a mapping")
    return metadata, body


def _inline_runs(node: Tag) -> list[InlineText]:
    runs: list[InlineText] = []

    def visit(child: Tag | NavigableString, *, bold: bool) -> None:
        if isinstance(child, NavigableString):
            text = str(child)
            if text:
                _append_run(runs, text, bold=bold)
            return
        child_bold = bold or child.name in {"strong", "b"}
        for nested in child.children:
            visit(nested, bold=child_bold)

    for child in node.children:
        visit(child, bold=False)
    return runs


def _append_run(runs: list[InlineText], text: str, *, bold: bool) -> None:
    if not runs or runs[-1].bold != bold:
        runs.append(InlineText(text=text, bold=bold))
        return
    runs[-1].text += text


def _join_runs(runs: list[InlineText]) -> str:
    return "".join(run.text for run in runs).strip()
