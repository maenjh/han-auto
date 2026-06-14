"""Use any HWP/HWPX document as a form: substring-replace its text and write HWPX.

Unlike :mod:`han_auto.hwpx_fields` (which fills named 누름틀 fields) and
:mod:`han_auto.hwpx_report` (which fills the bundled report layout by fixed index),
this rewrites the *visible text* of an arbitrary document by ordered substring
replacement, keeping the original layout, tables, and styling intact. It is the
"use this file as a 양식" path for documents that have no click-here fields and do
not match the report template.

``.hwp`` inputs are converted to ``.hwpx`` first. Output is always ``.hwpx``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

from han_auto.exceptions import HanAutoError
from han_auto.hwp2hwpx import prepared_hwpx_template
from han_auto.hwpx_package import clear_paragraph_line_segments, write_payloads


class HwpxRewriteError(HanAutoError):
    """Raised when a document cannot be rewritten."""


# Full HWPX namespace set so round-tripping section XML keeps Hancom's prefixes.
_NS = {
    "ha": "http://www.hancom.co.kr/hwpml/2011/app",
    "hp": "http://www.hancom.co.kr/hwpml/2011/paragraph",
    "hp10": "http://www.hancom.co.kr/hwpml/2016/paragraph",
    "hs": "http://www.hancom.co.kr/hwpml/2011/section",
    "hc": "http://www.hancom.co.kr/hwpml/2011/core",
    "hh": "http://www.hancom.co.kr/hwpml/2011/head",
    "hm": "http://www.hancom.co.kr/hwpml/2011/master-page",
}
for _prefix, _uri in _NS.items():
    ET.register_namespace(_prefix, _uri)

HP = f"{{{_NS['hp']}}}"
_SECTION_PREFIX = "Contents/section"


def replace_text_in_document(
    input_path: str | Path,
    output_path: str | Path,
    replacements: Mapping[str, str] | Sequence[tuple[str, str]],
    *,
    update_preview: bool = True,
    update_metadata: bool = True,
) -> dict[str, int | str]:
    """Substring-replace text throughout a document, preserving its layout.

    Args:
        input_path: Source ``.hwp`` or ``.hwpx`` document used as the form.
        output_path: Destination ``.hwpx`` path.
        replacements: ``{old: new}`` mapping (applied in insertion order) or an
            ordered sequence of ``(old, new)`` pairs. Put more specific/longer
            strings first so broader ones do not clobber them.
        update_preview: Also apply replacements to ``Preview/PrvText.txt``.
        update_metadata: Also apply replacements to ``Contents/content.hpf``.

    Returns a summary dict with the output path and counts. Every replaced
    paragraph's cached line layout is cleared so Hancom recomputes it on open.
    """

    pairs = _normalize_pairs(replacements)
    if not pairs:
        raise HwpxRewriteError("No replacements were provided.")

    output = Path(output_path).expanduser().resolve()
    if output.suffix.lower() != ".hwpx":
        raise HwpxRewriteError(
            f"Output must be a .hwpx file; got '{output.name}'. "
            "Binary .hwp output requires Hancom Office on Windows."
        )

    with prepared_hwpx_template(input_path) as prepared, zipfile.ZipFile(prepared, "r") as zin:
        infos = zin.infolist()
        payloads = {info.filename: zin.read(info.filename) for info in infos}

    section_parts = 0
    nodes_changed = 0
    paragraphs_cleared = 0
    for filename in list(payloads):
        if _is_section_part(filename):
            section_parts += 1
            payloads[filename], changed, cleared = _rewrite_section(payloads[filename], pairs)
            nodes_changed += changed
            paragraphs_cleared += cleared

    if section_parts == 0:
        raise HwpxRewriteError("Document has no Contents/sectionN.xml parts to rewrite.")

    if update_preview and "Preview/PrvText.txt" in payloads:
        text = payloads["Preview/PrvText.txt"].decode("utf-16le", errors="replace")
        payloads["Preview/PrvText.txt"] = _apply(text, pairs).encode("utf-16le")
    if update_metadata and "Contents/content.hpf" in payloads:
        hpf = payloads["Contents/content.hpf"].decode("utf-8", errors="replace")
        payloads["Contents/content.hpf"] = _apply(hpf, pairs).encode("utf-8")

    write_payloads(output, infos, payloads)
    return {
        "output": str(output),
        "section_parts": section_parts,
        "text_nodes_changed": nodes_changed,
        "paragraphs_relayout_cleared": paragraphs_cleared,
    }


def _normalize_pairs(replacements: Mapping[str, str] | Sequence[tuple[str, str]]) -> list[tuple[str, str]]:
    if isinstance(replacements, Mapping):
        return [(str(k), str(v)) for k, v in replacements.items()]
    pairs: list[tuple[str, str]] = []
    for item in replacements:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise HwpxRewriteError("Each replacement must be a [old, new] pair.")
        pairs.append((str(item[0]), str(item[1])))
    return pairs


def _apply(text: str, pairs: list[tuple[str, str]]) -> str:
    for old, new in pairs:
        if old and old in text:
            text = text.replace(old, new)
    return text


def _rewrite_section(section_xml: bytes, pairs: list[tuple[str, str]]) -> tuple[bytes, int, int]:
    root = ET.fromstring(section_xml)
    parents = {child: parent for parent in root.iter() for child in parent}
    changed_paragraphs: list[ET.Element] = []
    nodes_changed = 0
    for node in root.iter(f"{HP}t"):
        if not node.text:
            continue
        new_text = _apply(node.text, pairs)
        if new_text != node.text:
            node.text = new_text
            nodes_changed += 1
            paragraph = _enclosing_paragraph(node, parents)
            if paragraph is not None:
                changed_paragraphs.append(paragraph)

    seen: set[int] = set()
    cleared = 0
    for paragraph in changed_paragraphs:
        if id(paragraph) in seen:
            continue
        seen.add(id(paragraph))
        clear_paragraph_line_segments(paragraph)
        cleared += 1
    return _xml_bytes(root), nodes_changed, cleared


def _enclosing_paragraph(node: ET.Element, parents: dict[ET.Element, ET.Element]) -> ET.Element | None:
    current: ET.Element | None = node
    while current is not None and current.tag != f"{HP}p":
        current = parents.get(current)
    return current


def _xml_bytes(root: ET.Element) -> bytes:
    body = ET.tostring(root, encoding="utf-8", xml_declaration=False, short_empty_elements=True)
    return b'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>' + body


def _is_section_part(filename: str) -> bool:
    return filename.startswith(_SECTION_PREFIX) and filename.endswith(".xml")
