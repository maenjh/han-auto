from pathlib import Path

from typer.testing import CliRunner

from han_auto import cli
from han_auto.cli import app


def test_parse_command_works_without_hwp(tmp_path: Path) -> None:
    input_path = tmp_path / "notice.md"
    input_path.write_text(
        """---
recipient: Office
title: Notice
---

Body.
""",
        encoding="utf-8",
    )

    result = CliRunner().invoke(app, ["parse", str(input_path)])

    assert result.exit_code == 0
    assert '"recipient": "Office"' in result.output
    assert '"title": "Notice"' in result.output


def test_hwp_to_hwpx_command_invokes_converter(monkeypatch, tmp_path: Path) -> None:
    input_path = tmp_path / "template.hwp"
    output_path = tmp_path / "template.hwpx"
    input_path.write_bytes(b"hwp")

    def fake_convert_hwp_to_hwpx(input_arg: Path, output_arg: Path, *, tool_root: Path | None = None) -> Path:
        assert input_arg == input_path
        assert output_arg == output_path
        assert tool_root is None
        output_path.write_bytes(b"hwpx")
        return output_path

    monkeypatch.setattr(cli, "convert_hwp_to_hwpx", fake_convert_hwp_to_hwpx)

    result = CliRunner().invoke(app, ["hwp-to-hwpx", str(input_path), "--output", str(output_path)])

    assert result.exit_code == 0
    assert output_path.read_bytes() == b"hwpx"


def test_resources_command_lists_packaged_files() -> None:
    result = CliRunner().invoke(app, ["resources"])

    assert result.exit_code == 0
    assert "templates/brother-public-report.hwpx" in result.output
    assert "configs/templates/default.yaml" in result.output
    assert "examples/notice.md" in result.output
