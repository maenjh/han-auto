"""Map parsed Markdown blocks onto HWP text insertion and actions."""

from __future__ import annotations

from typing import Protocol

from han_auto.models import InlineText, MarkdownBlock, StyleMapping


class HwpTextClient(Protocol):
    """Small HWP client surface used by the formatter."""

    def put_field_text(self, field_name: str, text: str) -> None: ...

    def move_to_field(self, field_name: str) -> None: ...

    def insert_text(self, text: str) -> None: ...

    def run_action(self, action_name: str) -> None: ...


class MarkdownHwpFormatter:
    """Insert Markdown body content and apply configured HWP actions."""

    def plain_text(self, blocks: list[MarkdownBlock]) -> str:
        lines: list[str] = []
        for block in blocks:
            if block.type == "heading":
                lines.append(block.text)
                lines.append("")
            elif block.type == "paragraph":
                lines.append(block.text)
                lines.append("")
            elif block.type == "list":
                for index, item in enumerate(block.items, start=1):
                    marker = f"{index}." if block.ordered else "-"
                    lines.append(f"{marker} {item.text}")
                lines.append("")
        return "\n".join(lines).strip()

    def insert_body(
        self,
        client: HwpTextClient,
        field_name: str,
        blocks: list[MarkdownBlock],
        style_mapping: StyleMapping,
    ) -> None:
        """Replace a body field and insert block content with best-effort styles."""

        client.put_field_text(field_name, "")
        client.move_to_field(field_name)

        for block_index, block in enumerate(blocks):
            if block.type == "heading":
                action = style_mapping.heading.get(block.level or 0)
                if action:
                    client.run_action(action)
                self._insert_runs(client, block.runs, style_mapping)
                self._insert_paragraph_break(client)
            elif block.type == "paragraph":
                if style_mapping.paragraph:
                    client.run_action(style_mapping.paragraph)
                self._insert_runs(client, block.runs, style_mapping)
                self._insert_paragraph_break(client)
            elif block.type == "list":
                action = style_mapping.ordered_list if block.ordered else style_mapping.unordered_list
                for index, item in enumerate(block.items, start=1):
                    if action:
                        client.run_action(action)
                    marker = f"{index}. " if block.ordered else "- "
                    client.insert_text(marker)
                    self._insert_runs(client, item.runs, style_mapping)
                    self._insert_paragraph_break(client)

            if block_index < len(blocks) - 1:
                self._insert_paragraph_break(client)

    def _insert_runs(
        self,
        client: HwpTextClient,
        runs: list[InlineText],
        style_mapping: StyleMapping,
    ) -> None:
        for run in runs:
            if run.bold and style_mapping.bold:
                client.run_action(style_mapping.bold)
            client.insert_text(run.text)
            if run.bold and style_mapping.bold:
                client.run_action(style_mapping.bold)

    def _insert_paragraph_break(self, client: HwpTextClient) -> None:
        client.insert_text("\r\n")
