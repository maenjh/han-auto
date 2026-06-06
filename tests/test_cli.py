from pathlib import Path

from typer.testing import CliRunner

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
