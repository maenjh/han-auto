"""Source document text extraction for draft generation."""

from __future__ import annotations

from pathlib import Path

from han_auto.exceptions import HanAutoError


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


def _normalize_text(text: str) -> str:
    lines = [" ".join(line.split()) for line in text.replace("\r", "\n").split("\n")]
    return "\n".join(line for line in lines if line).strip()
