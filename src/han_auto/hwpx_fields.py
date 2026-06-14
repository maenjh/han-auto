"""Read and fill Hancom HWPX 누름틀(click-here) fields without COM automation.

Hancom Office COM automation (``inspect-fields`` / ``render``) only exists on Windows.
This module reproduces the field-reading and field-filling behaviour by editing the
HWPX package XML directly, so it works on macOS and Linux too. ``.hwp`` inputs are
converted to ``.hwpx`` first through :func:`han_auto.hwp2hwpx.prepared_hwpx_template`.

A 누름틀 field in section XML looks like::

    <hp:run><hp:ctrl><hp:fieldBegin id="A" type="CLICK_HERE" name="수신"/></hp:ctrl></hp:run>
    <hp:run charPrIDRef="N"><hp:t>field content</hp:t></hp:run>
    <hp:run><hp:ctrl><hp:fieldEnd beginIDRef="A"/></hp:ctrl></hp:run>

The field name is the ``name`` attribute of ``fieldBegin``; ``fieldEnd`` closes it via
``beginIDRef == fieldBegin/@id``. Field content is the ``hp:t`` text between the two.
"""

from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

from han_auto.exceptions import HanAutoError
from han_auto.hwp2hwpx import prepared_hwpx_template
from han_auto.hwpx_package import clear_paragraph_line_segments, write_payloads


class HwpxFieldError(HanAutoError):
    """Raised when HWPX field reading or filling fails."""


# Section XML namespaces. Registering keeps the hp:/hs: prefixes on serialization so the
# rewritten part stays byte-compatible with what Hancom expects.
_NS = {
    "ha": "http://www.hancom.co.kr/hwpml/2011/app",
    "hp": "http://www.hancom.co.kr/hwpml/2011/paragraph",
    "hp10": "http://www.hancom.co.kr/hwpml/2016/paragraph",
    "hs": "http://www.hancom.co.kr/hwpml/2011/section",
    "hc": "http://www.hancom.co.kr/hwpml/2011/core",
    "hh": "http://www.hancom.co.kr/hwpml/2011/head",
}
for _prefix, _uri in _NS.items():
    ET.register_namespace(_prefix, _uri)

HP = f"{{{_NS['hp']}}}"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"

_SECTION_PREFIX = "Contents/section"


def list_field_names(template_path: str | Path) -> list[str]:
    """Return the ordered, de-duplicated 누름틀 field names in a template.

    Accepts ``.hwpx`` or ``.hwp`` (converted first). Mirrors the names that Hancom's
    ``GetFieldList`` would report for click-here fields.
    """

    names: list[str] = []
    seen: set[str] = set()
    for xml_bytes in _iter_section_payloads(template_path):
        for name in _section_field_names(xml_bytes):
            if name not in seen:
                seen.add(name)
                names.append(name)
    return names


def fill_fields(
    template_path: str | Path,
    values: dict[str, str],
    output_path: str | Path,
    *,
    require_all: bool = True,
) -> Path:
    """Fill named 누름틀 fields with text and write an ``.hwpx`` output.

    ``values`` maps field name to replacement text. Every occurrence of a field is
    filled. With ``require_all`` set, a field name that is absent from the template
    raises :class:`HwpxFieldError` (parity with the COM renderer's field validation).
    The native engine always writes HWPX; writing binary ``.hwp`` needs Hancom on Windows.
    """

    output = Path(output_path).resolve()
    if output.suffix.lower() != ".hwpx":
        raise HwpxFieldError(
            f"The no-COM renderer writes .hwpx only; got output '{output.name}'. "
            "Use a .hwpx output path (binary .hwp output requires Hancom Office on Windows)."
        )

    template = Path(template_path)
    with prepared_hwpx_template(template) as prepared, zipfile.ZipFile(prepared, "r") as zin:
        infos = zin.infolist()
        payloads = {info.filename: zin.read(info.filename) for info in infos}

    filled: set[str] = set()
    for filename, data in list(payloads.items()):
        if _is_section_part(filename):
            payloads[filename], section_filled = _fill_section(data, values)
            filled |= section_filled

    if require_all:
        missing = sorted(set(values) - filled)
        if missing:
            raise HwpxFieldError(
                "Template is missing 누름틀 fields: " + ", ".join(missing) + ". "
                "Run `han-auto inspect-fields` to see the available field names."
            )

    write_payloads(output, infos, payloads)
    return output


# --- pure XML helpers (unit-tested directly on bytes) ---------------------------------


def _section_field_names(xml_bytes: bytes) -> list[str]:
    root = ET.fromstring(xml_bytes)
    names: list[str] = []
    for begin in root.iter(f"{HP}fieldBegin"):
        name = (begin.get("name") or "").strip()
        if name:
            names.append(name)
    return names


def _fill_section(xml_bytes: bytes, values: dict[str, str]) -> tuple[bytes, set[str]]:
    """Replace the content of every named, requested field in one section part."""

    root = ET.fromstring(xml_bytes)
    parents = {child: parent for parent in root.iter() for child in parent}

    # Walk in document order, tracking the fields we are currently inside.
    active: list[dict] = []
    filled: set[str] = set()
    for element in root.iter():
        tag = element.tag
        if tag == f"{HP}fieldBegin":
            name = (element.get("name") or "").strip()
            begin_id = element.get("id")
            if name and begin_id is not None and name in values:
                active.append(
                    {
                        "id": begin_id,
                        "name": name,
                        "t_nodes": [],
                        "run": _enclosing_run(element, parents),
                        "paragraph": _enclosing_paragraph(element, parents),
                    }
                )
        elif tag == f"{HP}fieldEnd":
            ref = element.get("beginIDRef")
            for index in range(len(active) - 1, -1, -1):
                if active[index]["id"] == ref:
                    context = active.pop(index)
                    _apply_field_text(context, values[context["name"]])
                    if context["paragraph"] is not None:
                        clear_paragraph_line_segments(context["paragraph"])
                    filled.add(context["name"])
                    break
        elif tag == f"{HP}t" and active:
            active[-1]["t_nodes"].append(element)

    return _serialize(root), filled


def _apply_field_text(context: dict, text: str) -> None:
    """Write ``text`` into a field: reuse the first text node, clear the rest."""

    t_nodes = context["t_nodes"]
    if t_nodes:
        _set_text(t_nodes[0], text)
        for node in t_nodes[1:]:
            _set_text(node, "")
        return

    # Empty field (placeholder only): add a text node to the field-begin run so the
    # content lands inside the begin/end region.
    run = context["run"]
    if run is None:
        return
    node = ET.SubElement(run, f"{HP}t")
    _set_text(node, text)


def _enclosing_run(field_begin: ET.Element, parents: dict) -> ET.Element | None:
    # fieldBegin -> hp:ctrl -> hp:run
    ctrl = parents.get(field_begin)
    if ctrl is None:
        return None
    return parents.get(ctrl)


def _enclosing_paragraph(element: ET.Element, parents: dict) -> ET.Element | None:
    current: ET.Element | None = element
    while current is not None:
        if current.tag == f"{HP}p":
            return current
        current = parents.get(current)
    return None


def _set_text(node: ET.Element, text: str) -> None:
    node.text = text
    if text:
        node.attrib[XML_SPACE] = "preserve"
    else:
        node.attrib.pop(XML_SPACE, None)


def _serialize(root: ET.Element) -> bytes:
    body = ET.tostring(root, encoding="utf-8", xml_declaration=False, short_empty_elements=True)
    return b'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>' + body


def _is_section_part(filename: str) -> bool:
    return filename.startswith(_SECTION_PREFIX) and filename.endswith(".xml")


def _iter_section_payloads(template_path: str | Path):
    template = Path(template_path)
    with prepared_hwpx_template(template) as prepared, zipfile.ZipFile(prepared, "r") as zin:
        for info in zin.infolist():
            if _is_section_part(info.filename):
                yield zin.read(info.filename)
