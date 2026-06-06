"""Source document text extraction for draft generation."""

from __future__ import annotations

from pathlib import Path
import tempfile
import zipfile
import xml.etree.ElementTree as ET

from han_auto.exceptions import HanAutoError
from han_auto.hwp2hwpx import convert_hwp_to_hwpx


class SourceExtractionError(HanAutoError):
    """Raised when a source document cannot be read."""


def extract_source_text(path: str | Path, *, max_chars: int = 12000) -> str:
    """Extract plain text from a supported source file."""

    source = Path(path).resolve()
    if not source.exists():
        raise SourceExtractionError(f"Source file not found: {source}")
    suffix = source.suffix.lower()
    if suffix == ".pdf":
        text = _extract_pdf_text(source)
    elif suffix == ".hwpx":
        text = _extract_hwpx_text(source)
    elif suffix == ".hwp":
        text = _extract_hwp_text(source)
    elif suffix in {".txt", ".md"}:
        text = source.read_text(encoding="utf-8", errors="replace")
    else:
        raise SourceExtractionError(f"Unsupported source file type: {source.suffix}")
    text = _normalize_text(text)
    if len(text) > max_chars:
        return text[:max_chars].rstrip() + "\n\n[원문 일부 생략]"
    return text


def _extract_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise SourceExtractionError("pypdf is required to extract PDF text.") from exc

    try:
        reader = PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:
        raise SourceExtractionError(f"Failed to extract text from PDF: {path}") from exc
    return "\n\n".join(pages)


def _extract_hwp_text(path: Path) -> str:
    try:
        with tempfile.TemporaryDirectory(prefix="han-auto-source-hwp-") as temp_dir:
            converted = Path(temp_dir) / f"{path.stem}.hwpx"
            convert_hwp_to_hwpx(path, converted)
            return _extract_hwpx_text(converted)
    except HanAutoError:
        raise
    except Exception as exc:
        raise SourceExtractionError(f"Failed to extract text from HWP: {path}") from exc


def _extract_hwpx_text(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as zf:
            section_names = sorted(
                name for name in zf.namelist() if name.startswith("Contents/section") and name.endswith(".xml")
            )
            parts = [_extract_hwpx_section_text(zf.read(name)) for name in section_names]
    except zipfile.BadZipFile as exc:
        raise SourceExtractionError(f"Invalid HWPX file: {path}") from exc
    except Exception as exc:
        raise SourceExtractionError(f"Failed to extract text from HWPX: {path}") from exc
    return "\n".join(part for part in parts if part.strip())


def _extract_hwpx_section_text(section_xml: bytes) -> str:
    root = ET.fromstring(section_xml)
    hp = "{http://www.hancom.co.kr/hwpml/2011/paragraph}"
    lines: list[str] = []
    for paragraph in root.findall(f".//{hp}p"):
        text = "".join(node.text or "" for node in paragraph.findall(f".//{hp}t")).strip()
        if text:
            lines.append(text)
    return "\n".join(lines)


def _normalize_text(text: str) -> str:
    lines = [" ".join(line.split()) for line in text.replace("\r", "\n").split("\n")]
    return "\n".join(line for line in lines if line).strip()
