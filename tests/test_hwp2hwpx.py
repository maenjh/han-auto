from pathlib import Path

import pytest

from han_auto import hwp2hwpx
from han_auto.hwp2hwpx import Hwp2HwpxError, convert_hwp_to_hwpx, prepared_hwpx_template


def test_prepared_hwpx_template_keeps_hwpx_path(tmp_path: Path) -> None:
    template = tmp_path / "template.hwpx"
    template.write_bytes(b"hwpx")

    with prepared_hwpx_template(template) as prepared:
        assert prepared == template.resolve()


def test_prepared_hwpx_template_converts_hwp(monkeypatch, tmp_path: Path) -> None:
    template = tmp_path / "template.hwp"
    template.write_bytes(b"hwp")
    calls: list[tuple[Path, Path]] = []

    def fake_convert(input_path: Path, output_path: Path) -> Path:
        calls.append((input_path, output_path))
        output_path.write_bytes(b"hwpx")
        return output_path

    monkeypatch.setattr(hwp2hwpx, "convert_hwp_to_hwpx", fake_convert)

    with prepared_hwpx_template(template) as prepared:
        assert prepared.suffix == ".hwpx"
        assert prepared.read_bytes() == b"hwpx"
        assert calls == [(template.resolve(), prepared)]


def test_prepared_hwpx_template_rejects_unknown_extension(tmp_path: Path) -> None:
    template = tmp_path / "template.docx"
    template.write_bytes(b"docx")

    with pytest.raises(Hwp2HwpxError, match="Template must be"):
        with prepared_hwpx_template(template):
            pass


def test_convert_hwp_to_hwpx_invokes_converter(monkeypatch, tmp_path: Path) -> None:
    input_path = tmp_path / "template.hwp"
    output_path = tmp_path / "template.hwpx"
    input_path.write_bytes(b"hwp")
    calls: list[tuple[Path, Path, Path | None]] = []

    class FakeConverter:
        def __init__(self, *, tool_root: Path | None = None):
            self.tool_root = tool_root

        def convert(self, source: Path, output: Path) -> None:
            calls.append((source, output, self.tool_root))
            output.write_bytes(b"hwpx")

    monkeypatch.setattr(hwp2hwpx, "Hwp2HwpxConverter", FakeConverter)

    result = convert_hwp_to_hwpx(input_path, output_path, tool_root=tmp_path / "tools")

    assert result == output_path.resolve()
    assert calls == [(input_path.resolve(), output_path.resolve(), tmp_path / "tools")]
