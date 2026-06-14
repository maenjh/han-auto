import logging
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

import pytest

from han_auto.draft import ReportBulletGroup, ReportDraft, ReportSection, ReportTable
from han_auto.hwpx_report import (
    HwpxRenderError,
    _ensure_table_char_styles,
    _set_para_text,
    render_public_report_hwpx,
)


NS = {"hp": "http://www.hancom.co.kr/hwpml/2011/paragraph"}


def _minimal_draft() -> ReportDraft:
    return ReportDraft(
        title="StayX AI Plan",
        date="2026. 6. 6.",
        company="StayX",
        sections=[
            ReportSection(
                title="Overview",
                groups=[ReportBulletGroup(title="Purpose", points=["Create a report draft."])],
            )
        ],
        attachments=[],
        references=[],
    )


def test_render_public_report_hwpx_inserts_structured_tables(tmp_path: Path) -> None:
    template = Path(__file__).parents[1] / "templates" / "brother-public-report.hwpx"
    output = tmp_path / "report.hwpx"
    draft = ReportDraft(
        title="StayX AI Plan",
        date="2026. 6. 6.",
        company="StayX",
        sections=[
            ReportSection(
                title="Overview",
                groups=[ReportBulletGroup(title="Purpose", points=["Create a report draft."])],
            )
        ],
        tables=[
            ReportTable(
                title="Budget",
                columns=["Item", "Amount", "Memo"],
                rows=[
                    ["Analysis", "3,000,000 KRW", "32 districts"],
                    ["Page", "2,000,000 KRW", "Launch"],
                ],
                note="VAT excluded.",
            )
        ],
        attachments=[],
        references=[],
    )

    render_public_report_hwpx(
        template_path=template,
        output_path=output,
        draft=draft,
        resave_with_hwp=False,
    )

    with zipfile.ZipFile(output) as zf:
        section = ET.fromstring(zf.read("Contents/section0.xml"))
        header = ET.fromstring(zf.read("Contents/header.xml"))
        preview = zf.read("Preview/PrvText.txt").decode("utf-16le")

    tables = section.findall(".//hp:tbl", NS)
    inserted = tables[-1]
    inserted_text = "".join(node.text or "" for node in inserted.findall(".//hp:t", NS))
    document_text = "".join(node.text or "" for node in section.findall(".//hp:t", NS))
    char_prs = {node.attrib["id"]: node.attrib for node in header.findall(".//{http://www.hancom.co.kr/hwpml/2011/head}charPr")}

    assert len(tables) == 9
    assert inserted.attrib["rowCnt"] == "3"
    assert inserted.attrib["colCnt"] == "3"
    assert inserted.find(".//hp:cellSz", NS).attrib["height"] == "2200"
    assert char_prs["37"]["height"] == "1000"
    assert char_prs["37"]["textColor"] == "#FFFFFF"
    assert char_prs["38"]["height"] == "900"
    assert "ItemAmountMemo" in inserted_text
    assert "3,000,000 KRW" in inserted_text
    assert "□ 표 1. Budget" in document_text
    assert "VAT excluded." in document_text
    assert "Budget" in preview


def test_set_para_text_clears_stale_line_segments() -> None:
    paragraph = ET.fromstring(
        '<hp:p xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">'
        '<hp:run><hp:t>old</hp:t></hp:run>'
        '<hp:linesegarray><hp:lineseg textpos="0" vertpos="0" vertsize="1000" '
        'textheight="1000" baseline="850" spacing="600" horzpos="0" '
        'horzsize="1000" flags="393216"/></hp:linesegarray>'
        "</hp:p>"
    )

    _set_para_text([paragraph], 0, "new")

    assert paragraph.find("hp:linesegarray", NS) is None
    assert "".join(node.text or "" for node in paragraph.findall(".//hp:t", NS)) == "new"


def test_render_rejects_template_with_unexpected_layout(tmp_path: Path) -> None:
    section_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
        '<hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
        'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">'
        "<hp:p><hp:run><hp:t>x</hp:t></hp:run></hp:p>"
        "</hs:sec>"
    )
    template = tmp_path / "other-form.hwpx"
    with zipfile.ZipFile(template, "w") as zf:
        zf.writestr("Contents/section0.xml", section_xml)
        zf.writestr("Contents/header.xml", "<x/>")
        zf.writestr("Contents/content.hpf", "<x/>")

    with pytest.raises(HwpxRenderError) as excinfo:
        render_public_report_hwpx(
            template_path=template,
            output_path=tmp_path / "out.hwpx",
            draft=_minimal_draft(),
            resave_with_hwp=False,
        )

    message = str(excinfo.value)
    assert "103" in message
    assert "found 1" in message
    assert "brother-public-report" in message


def test_render_rejects_template_missing_required_parts(tmp_path: Path) -> None:
    template = tmp_path / "broken.hwpx"
    with zipfile.ZipFile(template, "w") as zf:
        zf.writestr("Contents/section0.xml", "<x/>")

    with pytest.raises(HwpxRenderError) as excinfo:
        render_public_report_hwpx(
            template_path=template,
            output_path=tmp_path / "out.hwpx",
            draft=_minimal_draft(),
            resave_with_hwp=False,
        )

    message = str(excinfo.value)
    assert "Contents/header.xml" in message
    assert "Contents/content.hpf" in message


def test_missing_table_char_styles_logs_warning(caplog: pytest.LogCaptureFixture) -> None:
    root = ET.fromstring('<hh:head xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head"/>')

    with caplog.at_level(logging.WARNING, logger="han_auto.hwpx_report"):
        _ensure_table_char_styles(root)

    assert any("charPr" in record.message for record in caplog.records)
