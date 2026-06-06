"""HWPX report rendering while preserving a report template layout."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import copy
import zipfile
import xml.etree.ElementTree as ET

from han_auto.draft import ReportBulletGroup, ReportDraft, ReportSection, ReportTable
from han_auto.exceptions import HanAutoError
from han_auto.hwp2hwpx import prepared_hwpx_template


class HwpxRenderError(HanAutoError):
    """Raised when an HWPX report cannot be rendered."""


NS = {
    "ha": "http://www.hancom.co.kr/hwpml/2011/app",
    "hp": "http://www.hancom.co.kr/hwpml/2011/paragraph",
    "hp10": "http://www.hancom.co.kr/hwpml/2016/paragraph",
    "hs": "http://www.hancom.co.kr/hwpml/2011/section",
    "hc": "http://www.hancom.co.kr/hwpml/2011/core",
    "hh": "http://www.hancom.co.kr/hwpml/2011/head",
    "hhs": "http://www.hancom.co.kr/hwpml/2011/history",
    "hm": "http://www.hancom.co.kr/hwpml/2011/master-page",
    "hpf": "http://www.hancom.co.kr/schema/2011/hpf",
    "dc": "http://purl.org/dc/elements/1.1/",
    "opf": "http://www.idpf.org/2007/opf/",
    "ooxmlchart": "http://www.hancom.co.kr/hwpml/2016/ooxmlchart",
    "hwpunitchar": "http://www.hancom.co.kr/hwpml/2016/HwpUnitChar",
    "epub": "http://www.idpf.org/2007/ops",
    "config": "urn:oasis:names:tc:opendocument:xmlns:config:1.0",
}

for prefix, uri in NS.items():
    ET.register_namespace(prefix, uri)

HP = f"{{{NS['hp']}}}"
HH = f"{{{NS['hh']}}}"
HC = f"{{{NS['hc']}}}"
OPF = f"{{{NS['opf']}}}"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"

ROMAN_NUMERALS = ["Ⅰ", "Ⅱ", "Ⅲ", "Ⅳ"]
TABLE_WIDTH = 47688
TABLE_ROW_HEIGHT = 2200
TABLE_CELL_MARGIN = 141
TABLE_TITLE_CHAR_PR_ID = "36"
TABLE_HEADER_CHAR_PR_ID = "37"
TABLE_BODY_CHAR_PR_ID = "38"


def render_public_report_hwpx(
    *,
    template_path: str | Path,
    output_path: str | Path,
    draft: ReportDraft,
    logo_path: str | Path | None = None,
    resave_with_hwp: bool = True,
    register_security: bool = True,
    security_dll: str | Path | None = None,
    security_module_name: str = "FilePathCheckerModuleExample",
) -> Path:
    """Render a four-section public report HWPX from a structured draft."""

    template = Path(template_path).resolve()
    output = Path(output_path).resolve()
    if not template.exists():
        raise HwpxRenderError(f"HWPX template not found: {template}")

    with prepared_hwpx_template(template) as prepared_template, zipfile.ZipFile(prepared_template, "r") as zin:
        infos = zin.infolist()
        payloads = {info.filename: zin.read(info.filename) for info in infos}

    _require_parts(payloads, ["Contents/section0.xml", "Contents/header.xml", "Contents/content.hpf"])
    payloads["Contents/section0.xml"] = _update_section(payloads["Contents/section0.xml"], draft)
    payloads["Contents/header.xml"] = _update_header(payloads["Contents/header.xml"])
    payloads["Contents/content.hpf"] = _update_hpf(payloads["Contents/content.hpf"], draft)
    payloads["Preview/PrvText.txt"] = _preview_text(draft)

    if logo_path is not None:
        payloads["Contents/section0.xml"], payloads["BinData/image1.png"] = _replace_logo(
            payloads["Contents/section0.xml"],
            Path(logo_path).resolve(),
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w") as zout:
        for info in infos:
            data = payloads[info.filename]
            new_info = zipfile.ZipInfo(info.filename, date_time=info.date_time)
            new_info.compress_type = info.compress_type
            new_info.external_attr = info.external_attr
            new_info.comment = info.comment
            new_info.extra = info.extra
            zout.writestr(new_info, data)

    if resave_with_hwp:
        _resave_with_hwp(
            output,
            register_security=register_security,
            security_dll=security_dll,
            security_module_name=security_module_name,
        )
    return output


def _require_parts(payloads: dict[str, bytes], names: list[str]) -> None:
    missing = [name for name in names if name not in payloads]
    if missing:
        raise HwpxRenderError(f"Template is missing HWPX parts: {', '.join(missing)}")


def _xml_bytes(root: ET.Element) -> bytes:
    body = ET.tostring(root, encoding="utf-8", xml_declaration=False, short_empty_elements=True)
    return b'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>' + body


def _paragraph_text(paragraph: ET.Element) -> str:
    return "".join(node.text or "" for node in paragraph.findall(f".//{HP}t"))


def _replace_text_node(node: ET.Element, text: str) -> None:
    for child in list(node):
        node.remove(child)
    node.text = text
    if text:
        node.attrib[XML_SPACE] = "preserve"
    else:
        node.attrib.pop(XML_SPACE, None)


def _set_para_text(paragraphs: list[ET.Element], index: int, text: str) -> None:
    nodes = paragraphs[index].findall(f".//{HP}t")
    if not nodes:
        runs = paragraphs[index].findall(f"{HP}run")
        if not runs:
            return
        node = ET.SubElement(runs[0], f"{HP}t")
        _replace_text_node(node, text)
        return

    _replace_text_node(nodes[0], text)
    for node in nodes[1:]:
        _replace_text_node(node, "")


def _set_run_char_pr(paragraphs: list[ET.Element], index: int, char_pr_id: str) -> None:
    for run in paragraphs[index].findall(f"{HP}run"):
        run.attrib["charPrIDRef"] = char_pr_id


def _set_para_pr(paragraphs: list[ET.Element], index: int, para_pr_id: str) -> None:
    paragraphs[index].attrib["paraPrIDRef"] = para_pr_id


def _set_top_bullet(paragraphs: list[ET.Element], index: int, title: str) -> None:
    runs = paragraphs[index].findall(f"{HP}run")
    if len(runs) >= 2:
        first = runs[0].findall(f".//{HP}t")
        second = runs[1].findall(f".//{HP}t")
        if first:
            _replace_text_node(first[0], "□ ")
        if second:
            _replace_text_node(second[0], title)
            for node in second[1:]:
                _replace_text_node(node, "")
        return
    _set_para_text(paragraphs, index, f"□ {title}")


def _set_toc_line(paragraphs: list[ET.Element], index: int, number: str, title: str) -> None:
    if not number and not title:
        _set_para_text(paragraphs, index, "")
        return
    runs = paragraphs[index].findall(f"{HP}run")
    if len(runs) >= 2:
        first = runs[0].findall(f".//{HP}t")
        second = runs[1].findall(f".//{HP}t")
        if first:
            _replace_text_node(first[0], number)
        if second:
            _replace_text_node(second[0], f". {title}")
        for run in runs[2:]:
            for node in run.findall(f".//{HP}t"):
                _replace_text_node(node, "")
        return
    _set_para_text(paragraphs, index, f"{number}. {title}")


def _set_section_heading(
    paragraphs: list[ET.Element],
    combined_idx: int,
    number_idx: int,
    title_idx: int,
    number: str,
    title: str,
) -> None:
    _set_para_text(paragraphs, combined_idx, f"{number} {title}")
    _set_para_text(paragraphs, number_idx, number)
    _set_para_text(paragraphs, title_idx, f" {title}")


def _set_group(
    paragraphs: list[ET.Element],
    indexes: tuple[int, int, int, int],
    title: str,
    points: list[str],
    note: str | None,
) -> list[int]:
    top_idx, point_idx, detail_idx, note_idx = indexes
    removals: list[int] = []
    _set_top_bullet(paragraphs, top_idx, title)
    _set_para_text(paragraphs, point_idx, f"○ {points[0]}")
    if len(points) > 1:
        _set_para_text(paragraphs, detail_idx, f"― {points[1]}")
    else:
        _set_para_text(paragraphs, detail_idx, "")
        removals.append(detail_idx)

    if note_idx != detail_idx:
        note_text = note or (points[2] if len(points) > 2 else "")
        if note_text.strip():
            _set_para_text(paragraphs, note_idx, f"※ {note_text}")
        else:
            _set_para_text(paragraphs, note_idx, "")
            removals.append(note_idx)
    return removals


def _append_group(
    root: ET.Element,
    templates: tuple[ET.Element, ET.Element, ET.Element, ET.Element],
    title: str,
    points: list[str],
    note: str | None,
) -> list[ET.Element]:
    new_paragraphs = [copy.deepcopy(item) for item in templates]
    root_paragraphs = new_paragraphs
    for paragraph in root_paragraphs:
        root.append(paragraph)
    removal_indexes = _set_group(root_paragraphs, (0, 1, 2, 3), title, points, note)
    return [root_paragraphs[index] for index in removal_indexes]


def _remove_paragraphs(root: ET.Element, paragraphs: list[ET.Element]) -> None:
    parent_by_child = {child: parent for parent in root.iter() for child in parent}
    seen: set[int] = set()
    for paragraph in paragraphs:
        identity = id(paragraph)
        if identity in seen:
            continue
        seen.add(identity)
        parent = parent_by_child.get(paragraph)
        if parent is not None:
            parent.remove(paragraph)


def _update_section(section_xml: bytes, draft: ReportDraft) -> bytes:
    root = ET.fromstring(section_xml)
    paragraphs = root.findall(f".//{HP}p")
    if len(paragraphs) < 103:
        raise HwpxRenderError("This HWPX template does not match the supported public report layout.")

    sections = _four_sections(draft.sections)
    short_title = _short_title(draft.title, draft.company)

    _set_para_text(paragraphs, 6, f"{draft.company} {short_title}")
    _set_para_text(paragraphs, 9, draft.company)
    _set_para_text(paragraphs, 10, short_title)
    _set_run_char_pr(paragraphs, 10, "14")
    _set_para_text(paragraphs, 18, draft.date)
    _set_para_text(paragraphs, 48, short_title)
    _set_para_text(paragraphs, 51, short_title)
    _set_para_pr(paragraphs, 48, "23")
    _set_run_char_pr(paragraphs, 48, "14")
    _set_run_char_pr(paragraphs, 51, "14")

    toc_summary = "".join(f"{ROMAN_NUMERALS[i]}. {section.title}" for i, section in enumerate(sections))
    if draft.attachments:
        toc_summary += " [붙 임] " + "  ".join(f"{i}. {item}" for i, item in enumerate(draft.attachments, start=1))
    if draft.references:
        toc_summary += " [참 고] " + "  ".join(f"{i}. {item}" for i, item in enumerate(draft.references, start=1))
    _set_para_text(paragraphs, 37, toc_summary)
    for i, section in enumerate(sections):
        _set_toc_line(paragraphs, 38 + i, ROMAN_NUMERALS[i], section.title)
    _set_toc_line(paragraphs, 42, "", "")
    _set_para_text(paragraphs, 43, " [붙 임]")
    _set_para_text(paragraphs, 44, f"  1. {draft.attachments[0] if draft.attachments else '세부내용'}")
    _set_para_text(paragraphs, 45, f"  2. {draft.attachments[1] if len(draft.attachments) > 1 else '세부내용'}")
    _set_para_text(paragraphs, 46, " [참 고]")
    _set_para_text(paragraphs, 47, f"  1. {draft.references[0] if draft.references else '세부내용'}")

    heading_indexes = [(54, 55, 57), (62, 63, 65), (78, 79, 81), (95, 96, 98)]
    group_slots = [
        [(58, 59, 60, 60)],
        [(66, 67, 68, 69), (70, 71, 72, 73), (74, 75, 76, 77)],
        [(82, 83, 84, 85), (86, 87, 88, 89), (90, 91, 92, 93)],
        [(99, 100, 101, 102)],
    ]
    append_templates = (paragraphs[99], paragraphs[100], paragraphs[101], paragraphs[102])
    paragraphs_to_remove: list[ET.Element] = []

    for section_index, section in enumerate(sections):
        number = ROMAN_NUMERALS[section_index]
        _set_section_heading(paragraphs, *heading_indexes[section_index], number, section.title)
        slots = group_slots[section_index]
        for group_index, group in enumerate(section.groups):
            if group_index < len(slots):
                removal_indexes = _set_group(paragraphs, slots[group_index], group.title, group.points, group.note)
                paragraphs_to_remove.extend(paragraphs[index] for index in removal_indexes)
            elif section_index == 3:
                paragraphs_to_remove.extend(_append_group(root, append_templates, group.title, group.points, group.note))

        for unused_slot in slots[len(section.groups) :]:
            for index in dict.fromkeys(unused_slot):
                paragraphs_to_remove.append(paragraphs[index])

    _remove_paragraphs(root, paragraphs_to_remove)
    _append_report_tables(root, draft.tables)
    _preserve_text_spacing(root)
    return _xml_bytes(root)


def _four_sections(sections: list[ReportSection]) -> list[ReportSection]:
    if len(sections) >= 4:
        return sections[:4]
    defaults = [
        ReportSection(title="기획 개요", groups=[ReportBulletGroup(title="세부내용", points=["추후 작성한다."])]),
        ReportSection(title="추진 배경 및 과제", groups=[ReportBulletGroup(title="세부내용", points=["추후 작성한다."])]),
        ReportSection(title="AI 분석 설계", groups=[ReportBulletGroup(title="세부내용", points=["추후 작성한다."])]),
        ReportSection(title="추진 계획", groups=[ReportBulletGroup(title="세부내용", points=["추후 작성한다."])]),
    ]
    merged = sections + defaults[len(sections) :]
    for section in merged:
        if not section.groups:
            section.groups.append(ReportBulletGroup(title="세부내용", points=["추후 작성한다."]))
    return merged


def _short_title(title: str, company: str) -> str:
    stripped = title.replace(company, "").strip()
    return stripped or title


def _preserve_text_spacing(root: ET.Element) -> None:
    for node in root.findall(f".//{HP}t"):
        if node.text:
            node.attrib[XML_SPACE] = "preserve"


def _append_report_tables(root: ET.Element, tables: list[ReportTable]) -> None:
    if not tables:
        return

    table_id = _next_numeric_attr(root.findall(f".//{HP}tbl"), "id", default=1700000000)
    z_order = _next_numeric_attr(root.findall(f".//{HP}tbl"), "zOrder", default=0)
    for index, table in enumerate(tables, start=1):
        root.append(_make_text_paragraph(f"□ 표 {index}. {table.title}", para_pr_id="28", char_pr_id=TABLE_TITLE_CHAR_PR_ID))
        root.append(_make_table_paragraph(table, table_id=table_id, z_order=z_order))
        table_id += 1
        z_order += 1
        if table.note:
            root.append(_make_text_paragraph(f"※ {table.note}", para_pr_id="30", char_pr_id=TABLE_BODY_CHAR_PR_ID))


def _next_numeric_attr(elements: list[ET.Element], attr: str, *, default: int) -> int:
    values: list[int] = []
    for element in elements:
        raw = element.attrib.get(attr)
        if raw is None:
            continue
        try:
            values.append(int(raw))
        except ValueError:
            continue
    return (max(values) + 1) if values else default


def _make_text_paragraph(text: str, *, para_pr_id: str, char_pr_id: str) -> ET.Element:
    paragraph = ET.Element(
        f"{HP}p",
        {
            "id": "0",
            "paraPrIDRef": para_pr_id,
            "styleIDRef": "0",
            "pageBreak": "0",
            "columnBreak": "0",
            "merged": "0",
        },
    )
    run = ET.SubElement(paragraph, f"{HP}run", {"charPrIDRef": char_pr_id})
    text_node = ET.SubElement(run, f"{HP}t")
    _replace_text_node(text_node, text)
    _add_lineseg(paragraph, horz_size=TABLE_WIDTH)
    return paragraph


def _make_table_paragraph(table: ReportTable, *, table_id: int, z_order: int) -> ET.Element:
    rows = [table.columns, *table.rows]
    column_count = len(table.columns)
    row_count = len(rows)
    table_height = row_count * TABLE_ROW_HEIGHT
    widths = _column_widths(column_count, TABLE_WIDTH)

    paragraph = ET.Element(
        f"{HP}p",
        {
            "id": "0",
            "paraPrIDRef": "31",
            "styleIDRef": "0",
            "pageBreak": "0",
            "columnBreak": "0",
            "merged": "0",
        },
    )
    run = ET.SubElement(paragraph, f"{HP}run", {"charPrIDRef": "17"})
    table_node = ET.SubElement(
        run,
        f"{HP}tbl",
        {
            "id": str(table_id),
            "zOrder": str(z_order),
            "numberingType": "TABLE",
            "textWrap": "TOP_AND_BOTTOM",
            "textFlow": "BOTH_SIDES",
            "lock": "0",
            "dropcapstyle": "None",
            "pageBreak": "CELL",
            "repeatHeader": "1",
            "rowCnt": str(row_count),
            "colCnt": str(column_count),
            "cellSpacing": "0",
            "borderFillIDRef": "5",
            "noAdjust": "0",
        },
    )
    ET.SubElement(
        table_node,
        f"{HP}sz",
        {
            "width": str(TABLE_WIDTH),
            "widthRelTo": "ABSOLUTE",
            "height": str(table_height),
            "heightRelTo": "ABSOLUTE",
            "protect": "0",
        },
    )
    ET.SubElement(
        table_node,
        f"{HP}pos",
        {
            "treatAsChar": "1",
            "affectLSpacing": "0",
            "flowWithText": "1",
            "allowOverlap": "0",
            "holdAnchorAndSO": "0",
            "vertRelTo": "PARA",
            "horzRelTo": "PARA",
            "vertAlign": "TOP",
            "horzAlign": "LEFT",
            "vertOffset": "0",
            "horzOffset": "0",
        },
    )
    ET.SubElement(table_node, f"{HP}outMargin", {"left": "283", "right": "283", "top": "283", "bottom": "283"})
    ET.SubElement(
        table_node,
        f"{HP}inMargin",
        {
            "left": str(TABLE_CELL_MARGIN),
            "right": str(TABLE_CELL_MARGIN),
            "top": str(TABLE_CELL_MARGIN),
            "bottom": str(TABLE_CELL_MARGIN),
        },
    )

    for row_index, row in enumerate(rows):
        row_node = ET.SubElement(table_node, f"{HP}tr")
        for column_index, cell_text in enumerate(row):
            _append_cell(
                row_node,
                row_index=row_index,
                column_index=column_index,
                width=widths[column_index],
                text=cell_text,
                header=row_index == 0,
            )

    ET.SubElement(run, f"{HP}t")
    _add_lineseg(paragraph, vert_size=table_height, text_height="600", baseline="510", spacing="420")
    return paragraph


def _column_widths(column_count: int, total_width: int) -> list[int]:
    base = total_width // column_count
    widths = [base] * column_count
    widths[-1] += total_width - (base * column_count)
    return widths


def _append_cell(
    row_node: ET.Element,
    *,
    row_index: int,
    column_index: int,
    width: int,
    text: str,
    header: bool,
) -> None:
    cell = ET.SubElement(
        row_node,
        f"{HP}tc",
        {
            "name": "",
            "header": "1" if header else "0",
            "hasMargin": "0",
            "protect": "0",
            "editable": "0",
            "dirty": "0",
            "borderFillIDRef": "9" if header else "5",
        },
    )
    sub_list = ET.SubElement(
        cell,
        f"{HP}subList",
        {
            "id": "",
            "textDirection": "HORIZONTAL",
            "lineWrap": "BREAK",
            "vertAlign": "CENTER",
            "linkListIDRef": "0",
            "linkListNextIDRef": "0",
            "textWidth": "0",
            "textHeight": "0",
            "hasTextRef": "0",
            "hasNumRef": "0",
        },
    )
    paragraph = ET.SubElement(
        sub_list,
        f"{HP}p",
        {
            "id": "2147483648",
            "paraPrIDRef": "3" if header else "0",
            "styleIDRef": "0",
            "pageBreak": "0",
            "columnBreak": "0",
            "merged": "0",
        },
    )
    run = ET.SubElement(
        paragraph,
        f"{HP}run",
        {"charPrIDRef": TABLE_HEADER_CHAR_PR_ID if header else TABLE_BODY_CHAR_PR_ID},
    )
    text_node = ET.SubElement(run, f"{HP}t")
    _replace_text_node(text_node, _table_cell_text(text))
    inner_width = max(1, width - (TABLE_CELL_MARGIN * 2))
    if header:
        _add_lineseg(paragraph, horz_size=inner_width, vert_size=1200, text_height="1000", baseline="850", spacing="600")
    else:
        _add_lineseg(paragraph, horz_size=inner_width, vert_size=1100, text_height="900", baseline="765", spacing="540")
    ET.SubElement(cell, f"{HP}cellAddr", {"colAddr": str(column_index), "rowAddr": str(row_index)})
    ET.SubElement(cell, f"{HP}cellSpan", {"colSpan": "1", "rowSpan": "1"})
    ET.SubElement(cell, f"{HP}cellSz", {"width": str(width), "height": str(TABLE_ROW_HEIGHT)})
    ET.SubElement(
        cell,
        f"{HP}cellMargin",
        {
            "left": str(TABLE_CELL_MARGIN),
            "right": str(TABLE_CELL_MARGIN),
            "top": str(TABLE_CELL_MARGIN),
            "bottom": str(TABLE_CELL_MARGIN),
        },
    )


def _table_cell_text(text: str) -> str:
    return " ".join(text.split())


def _add_lineseg(
    element: ET.Element,
    *,
    horz_size: int = TABLE_WIDTH,
    vert_size: int | str = 1700,
    text_height: int | str = "1700",
    baseline: int | str = "1445",
    spacing: int | str = "1020",
) -> None:
    linesegarray = ET.SubElement(element, f"{HP}linesegarray")
    ET.SubElement(
        linesegarray,
        f"{HP}lineseg",
        {
            "textpos": "0",
            "vertpos": "0",
            "vertsize": str(vert_size),
            "textheight": str(text_height),
            "baseline": str(baseline),
            "spacing": str(spacing),
            "horzpos": "0",
            "horzsize": str(horz_size),
            "flags": "393216",
        },
    )


def _update_header(header_xml: bytes) -> bytes:
    root = ET.fromstring(header_xml)
    target_char_ids = {"17", "18", "19", "20", "21", "29"}
    for char_pr in root.findall(f".//{HH}charPr"):
        if char_pr.attrib.get("id") not in target_char_ids:
            continue
        char_pr.attrib["useFontSpace"] = "1"
        char_pr.attrib["useKerning"] = "1"
        spacing = char_pr.find(f"{HH}spacing")
        if spacing is not None:
            for key in spacing.attrib:
                spacing.attrib[key] = "0"

    for char_pr in root.findall(f".//{HH}charPr"):
        if char_pr.attrib.get("id") not in {"18", "19", "20"}:
            continue
        font_ref = char_pr.find(f"{HH}fontRef")
        if font_ref is not None:
            for key in font_ref.attrib:
                font_ref.attrib[key] = "1"

    long_title_char_sizes = {
        "14": "1500",
        "21": "2000",
    }
    for char_pr in root.findall(f".//{HH}charPr"):
        height = long_title_char_sizes.get(char_pr.attrib.get("id"))
        if height is None:
            continue
        char_pr.attrib["height"] = height
        char_pr.attrib["useFontSpace"] = "1"
        char_pr.attrib["useKerning"] = "1"
        spacing = char_pr.find(f"{HH}spacing")
        if spacing is not None:
            for key in spacing.attrib:
                spacing.attrib[key] = "0"
        ratio = char_pr.find(f"{HH}ratio")
        if ratio is not None:
            for key in ratio.attrib:
                ratio.attrib[key] = "100"
        strikeout = char_pr.find(f"{HH}strikeout")
        if strikeout is not None:
            strikeout.attrib["shape"] = "NONE"

    left_para_ids = {"0", "2", "22", "28", "29", "30", "35", "36", "40"}
    for para_pr in root.findall(f".//{HH}paraPr"):
        if para_pr.attrib.get("id") not in left_para_ids:
            continue
        align = para_pr.find(f"{HH}align")
        if align is not None:
            align.attrib["horizontal"] = "LEFT"

    for para_pr in root.findall(f".//{HH}paraPr"):
        if para_pr.attrib.get("id") != "23":
            continue
        break_setting = para_pr.find(f"{HH}breakSetting")
        if break_setting is not None:
            break_setting.attrib["lineWrap"] = "BREAK"
            break_setting.attrib["breakNonLatinWord"] = "KEEP_WORD"
        line_spacing = para_pr.find(f"{HH}lineSpacing")
        if line_spacing is not None:
            line_spacing.attrib["value"] = "160"

    indent_map = {
        "28": ("0", "0"),
        "29": ("850", "0"),
        "30": ("1700", "0"),
        "22": ("2550", "0"),
    }
    for para_pr in root.findall(f".//{HH}paraPr"):
        values = indent_map.get(para_pr.attrib.get("id"))
        if not values:
            continue
        left_value, intent_value = values
        for margin in para_pr.findall(f".//{HH}margin"):
            for child in margin:
                local_name = child.tag.split("}", 1)[-1]
                if local_name == "left":
                    child.attrib["value"] = left_value
                elif local_name == "intent":
                    child.attrib["value"] = intent_value
    _ensure_table_char_styles(root)
    return _xml_bytes(root)


def _ensure_table_char_styles(root: ET.Element) -> None:
    _upsert_char_pr(
        root,
        char_pr_id=TABLE_TITLE_CHAR_PR_ID,
        source_id="18",
        height="1300",
        text_color="#000000",
        bold=True,
    )
    _upsert_char_pr(
        root,
        char_pr_id=TABLE_HEADER_CHAR_PR_ID,
        source_id="24",
        height="1000",
        text_color="#FFFFFF",
        bold=True,
    )
    _upsert_char_pr(
        root,
        char_pr_id=TABLE_BODY_CHAR_PR_ID,
        source_id="21",
        height="900",
        text_color="#000000",
        bold=False,
    )


def _upsert_char_pr(
    root: ET.Element,
    *,
    char_pr_id: str,
    source_id: str,
    height: str,
    text_color: str,
    bold: bool,
) -> None:
    existing = root.find(f".//{HH}charPr[@id='{char_pr_id}']")
    source = root.find(f".//{HH}charPr[@id='{source_id}']")
    if existing is None and source is None:
        return

    char_pr = existing if existing is not None else copy.deepcopy(source)
    char_pr.attrib.update(
        {
            "id": char_pr_id,
            "height": height,
            "textColor": text_color,
            "useFontSpace": "1",
            "useKerning": "1",
        }
    )
    spacing = char_pr.find(f"{HH}spacing")
    if spacing is not None:
        for key in spacing.attrib:
            spacing.attrib[key] = "0"
    if bold and char_pr.find(f"{HH}bold") is None:
        ET.SubElement(char_pr, f"{HH}bold")
    if not bold:
        for node in list(char_pr.findall(f"{HH}bold")):
            char_pr.remove(node)

    if existing is not None:
        return
    char_properties = root.find(f".//{HH}charProperties")
    if char_properties is None:
        return
    char_properties.append(char_pr)
    char_properties.attrib["itemCnt"] = str(len(char_properties.findall(f"{HH}charPr")))


def _update_hpf(hpf_xml: bytes, draft: ReportDraft) -> bytes:
    root = ET.fromstring(hpf_xml)
    title_node = root.find(f".//{OPF}title")
    if title_node is not None:
        title_node.text = draft.title
    modified = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%dT%H:%M:%S+09:00")
    for meta in root.findall(f".//{OPF}meta"):
        name = meta.attrib.get("name")
        if name == "subject":
            meta.text = draft.title
        elif name == "description":
            meta.text = f"{draft.company} 자동 생성 기획안"
        elif name == "lastsaveby":
            meta.text = "han-auto"
        elif name == "ModifiedDate":
            meta.text = modified
    return _xml_bytes(root)


def _preview_text(draft: ReportDraft) -> bytes:
    lines = [f"<{draft.title}>", "", draft.date, "", "<목  차>", ""]
    sections = _four_sections(draft.sections)
    for index, section in enumerate(sections):
        lines.append(f"{ROMAN_NUMERALS[index]}. {section.title}")
    if draft.attachments:
        lines.append("[붙 임]")
        lines.extend(f"  {i}. {item}" for i, item in enumerate(draft.attachments, start=1))
    if draft.references:
        lines.append("[참 고]")
        lines.extend(f"  {i}. {item}" for i, item in enumerate(draft.references, start=1))
    lines.append("")
    for index, section in enumerate(sections):
        lines.append(f"{ROMAN_NUMERALS[index]} {section.title}")
        for group in section.groups:
            lines.append(f" □ {group.title}")
            for point_index, point in enumerate(group.points):
                prefix = "  ○" if point_index == 0 else "   ―"
                lines.append(f"{prefix} {point}")
            if group.note:
                lines.append(f"     ※ {group.note}")
        lines.append("")
    for index, table in enumerate(draft.tables, start=1):
        lines.append(f"□ 표 {index}. {table.title}")
        lines.append(" | ".join(table.columns))
        for row in table.rows:
            lines.append(" | ".join(row))
        if table.note:
            lines.append(f"※ {table.note}")
        lines.append("")
    return "\n".join(lines).encode("utf-16le")


def _replace_logo(section_xml: bytes, logo_path: Path) -> tuple[bytes, bytes]:
    if not logo_path.exists():
        raise HwpxRenderError(f"Logo image not found: {logo_path}")
    logo_bytes, width, height = _prepare_logo_png(logo_path)
    root = ET.fromstring(section_xml)
    pic = root.find(f".//{HP}pic")
    if pic is None:
        raise HwpxRenderError("Template has no logo picture to replace.")

    shape_w = 8196
    shape_h = round(shape_w * height / width)
    dim_w = 150000
    dim_h = round(dim_w * height / width)
    _set_attrs(pic.find(f"{HP}orgSz"), width=str(shape_w), height=str(shape_h))
    rotation = pic.find(f"{HP}rotationInfo")
    _set_attrs(rotation, centerX=str(round(shape_w / 2)), centerY=str(round(shape_h / 2)))
    img_rect = pic.find(f"{HP}imgRect")
    if img_rect is not None:
        _set_attrs(img_rect.find(f"{HC}pt0"), x="0", y="0")
        _set_attrs(img_rect.find(f"{HC}pt1"), x=str(shape_w), y="0")
        _set_attrs(img_rect.find(f"{HC}pt2"), x=str(shape_w), y=str(shape_h))
        _set_attrs(img_rect.find(f"{HC}pt3"), x="0", y=str(shape_h))
    _set_attrs(pic.find(f"{HP}imgClip"), left="0", right=str(dim_w), top="0", bottom=str(dim_h))
    _set_attrs(pic.find(f"{HP}imgDim"), dimwidth=str(dim_w), dimheight=str(dim_h))
    _set_attrs(pic.find(f"{HP}sz"), width=str(shape_w), height=str(shape_h))
    comment = pic.find(f"{HP}shapeComment")
    if comment is not None:
        comment.text = f"그림입니다.\n원본 그림의 이름: {logo_path.name}\n원본 그림의 크기: 가로 {width}pixel, 세로 {height}pixel"
    return _xml_bytes(root), logo_bytes


def _set_attrs(element: ET.Element | None, **attrs: str) -> None:
    if element is not None:
        element.attrib.update(attrs)


def _prepare_logo_png(path: Path) -> tuple[bytes, int, int]:
    try:
        from PIL import Image
    except ImportError as exc:
        raise HwpxRenderError("Pillow is required to crop and insert logo PNG files.") from exc

    image = Image.open(path).convert("RGBA")
    bbox = image.getbbox()
    if bbox:
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        pad_x = max(8, round(width * 0.025))
        pad_y = max(6, round(height * 0.08))
        bbox = (
            max(0, bbox[0] - pad_x),
            max(0, bbox[1] - pad_y),
            min(image.width, bbox[2] + pad_x),
            min(image.height, bbox[3] + pad_y),
        )
        image = image.crop(bbox)

    from io import BytesIO

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue(), image.width, image.height


def _resave_with_hwp(
    path: Path,
    *,
    register_security: bool,
    security_dll: str | Path | None,
    security_module_name: str,
) -> None:
    try:
        import win32com.client  # type: ignore[import-not-found]
    except ImportError:
        return
    try:
        from han_auto.hwp import register_file_path_check_module

        hwp = win32com.client.gencache.EnsureDispatch("HWPFrame.HwpObject")
        try:
            hwp.XHwpWindows.Item(0).Visible = False
        except Exception:
            pass
        if register_security:
            register_file_path_check_module(
                hwp,
                security_dll=security_dll,
                module_name=security_module_name,
            )
        if hwp.Open(str(path)) is False:
            raise HwpxRenderError(f"Hancom HWP refused to open generated file: {path}")
        if hwp.SaveAs(str(path), "HWPX", "") is False:
            raise HwpxRenderError(f"Hancom HWP refused to resave generated file: {path}")
    except HwpxRenderError:
        raise
    except Exception as exc:
        raise HwpxRenderError(f"Failed to resave HWPX with Hancom HWP: {exc}") from exc
    finally:
        try:
            hwp.Quit()  # type: ignore[name-defined]
        except Exception:
            pass
