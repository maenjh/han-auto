"""Tests for han_auto.hwpx_rewrite — using any document as a 양식 via text replacement."""

from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile

import pytest

from han_auto.draft import offline_report_draft
from han_auto.hwpx_report import render_public_report_hwpx
from han_auto.hwpx_rewrite import HwpxRewriteError, replace_text_in_document
from han_auto.resources import resource_path

HP = "{http://www.hancom.co.kr/hwpml/2011/paragraph}"


def _section_text(path) -> str:
    with zipfile.ZipFile(path) as z:
        parts = [n for n in z.namelist() if n.startswith("Contents/section") and n.endswith(".xml")]
        text = []
        for part in parts:
            root = ET.fromstring(z.read(part))
            text.append("".join(t.text or "" for t in root.iter(f"{HP}t")))
    return "".join(text)


def _known_hwpx(tmp_path):
    """Render a report HWPX with a known company string to use as a form."""
    draft = offline_report_draft(topic="테스트 주제", company="주식회사 스테이엑스", audience="실무진")
    src = tmp_path / "form.hwpx"
    render_public_report_hwpx(
        template_path=resource_path("templates/brother-public-report.hwpx"),
        output_path=src,
        draft=draft,
        resave_with_hwp=False,
    )
    return src


def test_replace_text_round_trip(tmp_path):
    src = _known_hwpx(tmp_path)
    assert "주식회사 스테이엑스" in _section_text(src)

    out = tmp_path / "out.hwpx"
    summary = replace_text_in_document(src, out, {"주식회사 스테이엑스": "㈜테스트컴퍼니"})

    assert summary["section_parts"] >= 1
    assert summary["text_nodes_changed"] >= 1
    assert summary["paragraphs_relayout_cleared"] >= 1
    text = _section_text(out)
    assert "주식회사 스테이엑스" not in text
    assert "㈜테스트컴퍼니" in text


def test_replace_accepts_ordered_pairs(tmp_path):
    src = _known_hwpx(tmp_path)
    out = tmp_path / "out.hwpx"
    replace_text_in_document(src, out, [("주식회사 스테이엑스", "에이"), ("에이", "비")])
    text = _section_text(out)
    # ordered application: 스테이엑스 -> 에이 -> 비
    assert "비" in text
    assert "주식회사 스테이엑스" not in text


def test_line_segments_cleared_on_changed_paragraph(tmp_path):
    src = _known_hwpx(tmp_path)
    out = tmp_path / "out.hwpx"
    replace_text_in_document(src, out, {"주식회사 스테이엑스": "㈜테스트"})
    # Changed paragraphs must drop their cached linesegarray so Hancom relayouts.
    with zipfile.ZipFile(out) as z:
        root = ET.fromstring(z.read("Contents/section0.xml"))
    parents = {c: p for p in root.iter() for c in p}
    for t in root.iter(f"{HP}t"):
        if t.text and "㈜테스트" in t.text:
            para = t
            while para is not None and para.tag != f"{HP}p":
                para = parents.get(para)
            assert para is not None
            assert para.find(f"{HP}linesegarray") is None
            break
    else:
        pytest.fail("replacement text not found in output")


def test_non_hwpx_output_rejected(tmp_path):
    src = _known_hwpx(tmp_path)
    with pytest.raises(HwpxRewriteError):
        replace_text_in_document(src, tmp_path / "out.hwp", {"a": "b"})


def test_empty_replacements_rejected(tmp_path):
    src = _known_hwpx(tmp_path)
    with pytest.raises(HwpxRewriteError):
        replace_text_in_document(src, tmp_path / "out.hwpx", {})
