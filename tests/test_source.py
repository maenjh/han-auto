from pathlib import Path
import zipfile

from han_auto import source as source_module
from han_auto.source import extract_source_text


def test_extract_source_text_reads_utf8_text(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("  첫 줄  \n\n둘째   줄", encoding="utf-8")

    assert extract_source_text(source) == "첫 줄\n둘째 줄"


def test_extract_source_text_truncates_long_text(tmp_path: Path) -> None:
    source = tmp_path / "source.md"
    source.write_text("가" * 20, encoding="utf-8")

    assert extract_source_text(source, max_chars=5) == "가" * 5 + "\n\n[원문 일부 생략]"


def test_extract_source_text_reads_hwpx_sections(tmp_path: Path) -> None:
    source = tmp_path / "source.hwpx"
    section_xml = """<?xml version="1.0" encoding="UTF-8"?>
<hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section"
        xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">
  <hp:p><hp:run><hp:t>첫 문단</hp:t></hp:run></hp:p>
  <hp:p><hp:run><hp:t>둘째</hp:t><hp:t> 문단</hp:t></hp:run></hp:p>
</hs:sec>
""".encode()
    with zipfile.ZipFile(source, "w") as zf:
        zf.writestr("Contents/section0.xml", section_xml)

    assert extract_source_text(source) == "첫 문단\n둘째 문단"


def test_extract_source_text_converts_hwp_before_reading(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "source.hwp"
    source.write_bytes(b"hwp")

    def fake_convert(input_path: Path, output_path: Path) -> Path:
        assert input_path == source.resolve()
        section_xml = """<?xml version="1.0" encoding="UTF-8"?>
<hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section"
        xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">
  <hp:p><hp:run><hp:t>변환된 원문</hp:t></hp:run></hp:p>
</hs:sec>
""".encode()
        with zipfile.ZipFile(output_path, "w") as zf:
            zf.writestr("Contents/section0.xml", section_xml)
        return output_path

    monkeypatch.setattr(source_module, "convert_hwp_to_hwpx", fake_convert, raising=False)

    assert extract_source_text(source) == "변환된 원문"
