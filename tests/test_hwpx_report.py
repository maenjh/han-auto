from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

from han_auto.draft import ReportBulletGroup, ReportDraft, ReportSection, ReportTable
from han_auto.hwpx_report import render_public_report_hwpx


NS = {"hp": "http://www.hancom.co.kr/hwpml/2011/paragraph"}


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
