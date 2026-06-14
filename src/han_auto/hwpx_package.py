"""Helpers for rewriting HWPX zip packages without changing zip metadata."""

from __future__ import annotations

from pathlib import Path
import struct
import xml.etree.ElementTree as ET
import zipfile

HP = "{http://www.hancom.co.kr/hwpml/2011/paragraph}"


def clone_zip_info(info: zipfile.ZipInfo) -> zipfile.ZipInfo:
    """Return a ZipInfo suitable for rewriting an existing HWPX package entry.

    Hancom is sensitive to package metadata. Python's default ZipInfo marks entries
    as Unix-origin files on macOS/Linux, while HWPX files converted from HWP often
    use FAT/MS-DOS-origin entries. Preserve the original metadata so changing XML
    content does not make the package look unnecessarily different.
    """

    cloned = zipfile.ZipInfo(info.filename, date_time=info.date_time)
    cloned.compress_type = info.compress_type
    cloned.comment = info.comment
    cloned.extra = info.extra
    cloned.internal_attr = info.internal_attr
    cloned.external_attr = info.external_attr
    cloned.create_system = info.create_system
    cloned.create_version = info.create_version
    cloned.extract_version = info.extract_version
    return cloned


def write_payloads(output: str | Path, infos: list[zipfile.ZipInfo], payloads: dict[str, bytes]) -> None:
    """Write HWPX payloads using the original zip entry order and metadata."""

    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w") as zout:
        for info in infos:
            zout.writestr(clone_zip_info(info), payloads[info.filename])
    _restore_external_attrs(target, {info.filename: info.external_attr for info in infos})


def clear_paragraph_line_segments(paragraph: ET.Element) -> None:
    """Remove stale line layout data so Hancom recalculates changed paragraphs.

    HWPX paragraphs may carry ``hp:linesegarray`` records converted from the original
    HWP. After direct XML text replacement those records still describe the old text,
    and Hancom Office for Mac can render the new text with overlapping glyphs. Dropping
    the paragraph's cached line segments lets Hancom rebuild them when opening the file.
    """

    for child in list(paragraph):
        if child.tag == f"{HP}linesegarray":
            paragraph.remove(child)


def _restore_external_attrs(target: Path, external_attrs: dict[str, int]) -> None:
    """Patch central-directory external attributes back to the source values.

    ``zipfile`` rewrites a zero external attribute as Unix ``0600`` permissions even
    when ``create_system`` is set to FAT/MS-DOS. HWPX files produced by Java-based
    converters often use zero attributes, so patch the central directory explicitly.
    """

    data = bytearray(target.read_bytes())
    cursor = 0
    signature = b"PK\x01\x02"
    while True:
        index = data.find(signature, cursor)
        if index == -1:
            break
        name_length = struct.unpack_from("<H", data, index + 28)[0]
        extra_length = struct.unpack_from("<H", data, index + 30)[0]
        comment_length = struct.unpack_from("<H", data, index + 32)[0]
        name_start = index + 46
        name_end = name_start + name_length
        name = data[name_start:name_end].decode("utf-8")
        if name in external_attrs:
            struct.pack_into("<I", data, index + 38, external_attrs[name])
        cursor = name_end + extra_length + comment_length
    target.write_bytes(data)
