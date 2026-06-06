from pathlib import Path

from han_auto.config import load_template_config


def test_load_template_config_resolves_template_relative_to_config(tmp_path: Path) -> None:
    config_path = tmp_path / "template.yaml"
    config_path.write_text(
        """
template_path: template.hwp
field_mapping:
  recipient: "수신"
  title: "문서제목"
  body: "본문내용"
style_mapping:
  heading:
    1: StyleHeading1
  bold: CharShapeBold
""",
        encoding="utf-8",
    )

    config = load_template_config(config_path)

    assert config.template_path == tmp_path / "template.hwp"
    assert config.field_mapping["body"] == "본문내용"
    assert config.style_mapping.heading[1] == "StyleHeading1"
