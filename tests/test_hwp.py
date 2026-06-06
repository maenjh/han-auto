from pathlib import Path

import pytest

from han_auto.config import load_template_config
from han_auto.exceptions import MissingFieldError
from han_auto.hwp import HwpDocumentAutomation, split_hwp_field_list
from han_auto.parser import parse_markdown_text


class FakeHwpClient:
    def __init__(self, fields: list[str]):
        self.fields = fields
        self.opened: Path | None = None
        self.saved: Path | None = None
        self.put_calls: list[tuple[str, str]] = []
        self.inserted: list[str] = []
        self.actions: list[str] = []
        self.moved_to: list[str] = []

    def open(self, path: Path) -> None:
        self.opened = path

    def get_fields(self) -> list[str]:
        return self.fields

    def put_field_text(self, field_name: str, text: str) -> None:
        self.put_calls.append((field_name, text))

    def move_to_field(self, field_name: str) -> None:
        self.moved_to.append(field_name)

    def insert_text(self, text: str) -> None:
        self.inserted.append(text)

    def run_action(self, action_name: str) -> None:
        self.actions.append(action_name)

    def save_as(self, path: Path) -> None:
        self.saved = path

    def close(self) -> None:
        return None


def test_render_puts_fields_and_inserts_styled_body(tmp_path: Path) -> None:
    template_path = tmp_path / "template.hwp"
    template_path.write_bytes(b"fake")
    config_path = tmp_path / "template.yaml"
    config_path.write_text(
        """
template_path: template.hwp
field_mapping:
  recipient: "수신"
  title: "문서제목"
  body: "본문내용"
  sender: "발신"
style_mapping:
  heading:
    1: StyleHeading1
  bold: CharShapeBold
""",
        encoding="utf-8",
    )
    document = parse_markdown_text(
        """---
recipient: Office
title: Notice
fields:
  sender: Team
---

# Heading

Body with **bold**.
"""
    )
    client = FakeHwpClient(["수신", "문서제목", "본문내용", "발신"])

    output = HwpDocumentAutomation(client).render(document, load_template_config(config_path), tmp_path / "out.hwp")

    assert output == (tmp_path / "out.hwp").resolve()
    assert ("수신", "Office") in client.put_calls
    assert ("문서제목", "Notice") in client.put_calls
    assert ("발신", "Team") in client.put_calls
    assert ("본문내용", "") in client.put_calls
    assert "StyleHeading1" in client.actions
    assert "CharShapeBold" in client.actions
    assert client.saved == output


def test_render_raises_for_missing_hwp_field(tmp_path: Path) -> None:
    template_path = tmp_path / "template.hwp"
    template_path.write_bytes(b"fake")
    config_path = tmp_path / "template.yaml"
    config_path.write_text(
        """
template_path: template.hwp
field_mapping:
  recipient: "수신"
  title: "문서제목"
  body: "본문내용"
""",
        encoding="utf-8",
    )
    document = parse_markdown_text(
        """---
recipient: Office
title: Notice
---

Body.
"""
    )
    client = FakeHwpClient(["수신", "문서제목"])

    with pytest.raises(MissingFieldError):
        HwpDocumentAutomation(client).render(document, load_template_config(config_path), tmp_path / "out.hwp")


def test_split_hwp_field_list_handles_common_separators() -> None:
    assert split_hwp_field_list("수신\x02문서제목;본문내용\r\n발신") == ["수신", "문서제목", "본문내용", "발신"]
