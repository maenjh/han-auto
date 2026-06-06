from pathlib import Path

from han_auto.source import extract_source_text


def test_extract_source_text_reads_utf8_text(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("  첫 줄  \n\n둘째   줄", encoding="utf-8")

    assert extract_source_text(source) == "첫 줄\n둘째 줄"


def test_extract_source_text_truncates_long_text(tmp_path: Path) -> None:
    source = tmp_path / "source.md"
    source.write_text("가" * 20, encoding="utf-8")

    assert extract_source_text(source, max_chars=5) == "가" * 5 + "\n\n[원문 일부 생략]"
