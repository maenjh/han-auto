from pathlib import Path
import re
import zipfile

import pytest

from han_auto import hwpx_fields
from han_auto.hwpx_fields import HwpxFieldError, fill_fields, list_field_names

HP = "{http://www.hancom.co.kr/hwpml/2011/paragraph}"


def _section(*paragraphs: str) -> bytes:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
        '<hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
        'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">'
        + "".join(paragraphs)
        + "</hs:sec>"
    ).encode("utf-8")


def _field(begin_id: str, name: str, type_: str = "CLICK_HERE", content: str | None = None) -> str:
    body = (
        f'<hp:run charPrIDRef="0"><hp:ctrl>'
        f'<hp:fieldBegin id="{begin_id}" type="{type_}" name="{name}"/></hp:ctrl></hp:run>'
    )
    if content is not None:
        body += f'<hp:run charPrIDRef="1"><hp:t>{content}</hp:t></hp:run>'
    body += f'<hp:run><hp:ctrl><hp:fieldEnd beginIDRef="{begin_id}"/></hp:ctrl></hp:run>'
    return f"<hp:p>{body}</hp:p>"


def _texts(section_bytes: bytes) -> list[str]:
    return re.findall(r"<hp:t[^>]*>(.*?)</hp:t>", section_bytes.decode("utf-8"))


def _make_hwpx(tmp_path: Path, section: bytes) -> Path:
    path = tmp_path / "form.hwpx"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("mimetype", "application/hwp+zip")
        zf.writestr("Contents/section0.xml", section)
    return path


def test_section_field_names_lists_named_clickhere_only() -> None:
    section = _section(
        _field("1", "수신"),
        _field("2", "문서제목"),
        _field("3", "", type_="HYPERLINK"),  # unnamed → excluded
    )
    assert hwpx_fields._section_field_names(section) == ["수신", "문서제목"]


def test_list_field_names_dedupes_across_occurrences(tmp_path: Path) -> None:
    path = _make_hwpx(tmp_path, _section(_field("1", "수신"), _field("2", "수신")))
    assert list_field_names(path) == ["수신"]


def test_fill_replaces_existing_field_content(tmp_path: Path) -> None:
    section = _section(_field("1", "수신", content="옛 내용"))
    filled, names = hwpx_fields._fill_section(section, {"수신": "새 수신처"})
    assert names == {"수신"}
    assert _texts(filled) == ["새 수신처"]


def test_fill_empty_field_inserts_text_inside_region(tmp_path: Path) -> None:
    section = _section(_field("1", "제목"))  # no content node
    filled, names = hwpx_fields._fill_section(section, {"제목": "보고"})
    decoded = filled.decode("utf-8")
    assert names == {"제목"}
    # text must land before the fieldEnd so it is part of the field region
    assert decoded.index("보고") < decoded.index('beginIDRef="1"')


def test_fill_clears_extra_text_nodes() -> None:
    para = (
        "<hp:p>"
        '<hp:run charPrIDRef="0"><hp:ctrl><hp:fieldBegin id="1" type="CLICK_HERE" name="본문"/></hp:ctrl></hp:run>'
        '<hp:run charPrIDRef="1"><hp:t>첫째</hp:t></hp:run>'
        '<hp:run charPrIDRef="1"><hp:t>둘째</hp:t></hp:run>'
        '<hp:run><hp:ctrl><hp:fieldEnd beginIDRef="1"/></hp:ctrl></hp:run>'
        "</hp:p>"
    )
    filled, _ = hwpx_fields._fill_section(_section(para), {"본문": "교체"})
    # First node holds the new text; the extra node is emptied (serialized as <hp:t/>).
    assert _texts(filled) == ["교체"]
    assert filled.decode("utf-8").count("<hp:t") == 2


def test_fill_fields_writes_hwpx(tmp_path: Path) -> None:
    path = _make_hwpx(tmp_path, _section(_field("1", "수신", content="x")))
    out = fill_fields(path, {"수신": "제주도교육감"}, tmp_path / "out.hwpx")
    section = zipfile.ZipFile(out).read("Contents/section0.xml")
    assert "제주도교육감" in section.decode("utf-8")


def test_fill_fields_requires_hwpx_output(tmp_path: Path) -> None:
    path = _make_hwpx(tmp_path, _section(_field("1", "수신")))
    with pytest.raises(HwpxFieldError, match="writes .hwpx only"):
        fill_fields(path, {"수신": "x"}, tmp_path / "out.hwp")


def test_fill_fields_raises_for_missing_field(tmp_path: Path) -> None:
    path = _make_hwpx(tmp_path, _section(_field("1", "수신")))
    with pytest.raises(HwpxFieldError, match="missing 누름틀 fields"):
        fill_fields(path, {"없는필드": "x"}, tmp_path / "out.hwpx")
