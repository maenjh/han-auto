"""Pydantic models for parsed documents and template configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class InlineText(BaseModel):
    """A run of text with inline formatting flags."""

    text: str
    bold: bool = False


class ListItem(BaseModel):
    """A Markdown list item."""

    text: str
    runs: list[InlineText] = Field(default_factory=list)


class MarkdownBlock(BaseModel):
    """A block-level Markdown element after HTML normalization."""

    type: Literal["heading", "paragraph", "list"]
    text: str = ""
    level: int | None = None
    ordered: bool = False
    runs: list[InlineText] = Field(default_factory=list)
    items: list[ListItem] = Field(default_factory=list)


class NoticeDocument(BaseModel):
    """Structured data parsed from one Markdown notice input."""

    template: str | None = None
    recipient: str
    title: str
    fields: dict[str, str] = Field(default_factory=dict)
    body_markdown: str
    body_html: str
    blocks: list[MarkdownBlock] = Field(default_factory=list)

    @field_validator("recipient", "title")
    @classmethod
    def required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be empty")
        return value

    @field_validator("fields", mode="before")
    @classmethod
    def stringify_field_values(cls, value: Any) -> dict[str, str]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise TypeError("fields must be a mapping")
        return {str(key): "" if val is None else str(val) for key, val in value.items()}

    def field_values(self) -> dict[str, str]:
        """Return source field values that may be mapped into HWP fields."""

        values = {
            "recipient": self.recipient,
            "title": self.title,
            "body": self.plain_body(),
        }
        values.update(self.fields)
        return values

    def plain_body(self) -> str:
        """Render parsed Markdown blocks as plain text for HWP fields."""

        lines: list[str] = []
        for block in self.blocks:
            if block.type == "heading":
                lines.append(block.text)
                lines.append("")
            elif block.type == "paragraph":
                lines.append(block.text)
                lines.append("")
            elif block.type == "list":
                for index, item in enumerate(block.items, start=1):
                    prefix = f"{index}." if block.ordered else "-"
                    lines.append(f"{prefix} {item.text}")
                lines.append("")
        return "\n".join(lines).strip()


class StyleMapping(BaseModel):
    """HWP action/style names used for Markdown formatting."""

    heading: dict[int, str] = Field(default_factory=dict)
    paragraph: str | None = None
    unordered_list: str | None = None
    ordered_list: str | None = None
    bold: str | None = "CharShapeBold"

    @field_validator("heading", mode="before")
    @classmethod
    def normalize_heading_keys(cls, value: Any) -> dict[int, str]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise TypeError("heading style mapping must be a mapping")
        return {int(key): str(val) for key, val in value.items()}


class TemplateConfig(BaseModel):
    """Configuration for one HWP template."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    template_path: Path
    field_mapping: dict[str, str]
    style_mapping: StyleMapping = Field(default_factory=StyleMapping)

    @field_validator("field_mapping")
    @classmethod
    def validate_field_mapping(cls, value: dict[str, str]) -> dict[str, str]:
        if not value:
            raise ValueError("field_mapping must not be empty")
        normalized = {str(key): str(val).strip() for key, val in value.items()}
        empty_targets = [key for key, val in normalized.items() if not val]
        if empty_targets:
            joined = ", ".join(empty_targets)
            raise ValueError(f"field_mapping has empty target names: {joined}")
        return normalized

    @model_validator(mode="after")
    def require_body_mapping(self) -> "TemplateConfig":
        if "body" not in self.field_mapping:
            raise ValueError("field_mapping must include a body entry")
        return self
