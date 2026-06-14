import zipfile
from pathlib import Path

from han_auto.hwpx_package import clone_zip_info, write_payloads


def test_clone_zip_info_preserves_origin_metadata() -> None:
    original = zipfile.ZipInfo("Contents/section0.xml", date_time=(2026, 6, 14, 17, 30, 0))
    original.compress_type = zipfile.ZIP_DEFLATED
    original.create_system = 0
    original.create_version = 20
    original.extract_version = 20
    original.external_attr = 0
    original.internal_attr = 0
    original.extra = b"abc"
    original.comment = b"memo"

    cloned = clone_zip_info(original)

    assert cloned.filename == original.filename
    assert cloned.date_time == original.date_time
    assert cloned.compress_type == original.compress_type
    assert cloned.create_system == 0
    assert cloned.create_version == original.create_version
    assert cloned.extract_version == original.extract_version
    assert cloned.external_attr == original.external_attr
    assert cloned.internal_attr == original.internal_attr
    assert cloned.extra == original.extra
    assert cloned.comment == original.comment


def test_write_payloads_restores_zero_external_attrs(tmp_path: Path) -> None:
    original = zipfile.ZipInfo("Contents/section0.xml", date_time=(2026, 6, 14, 17, 30, 0))
    original.compress_type = zipfile.ZIP_DEFLATED
    original.create_system = 0
    original.external_attr = 0

    output = tmp_path / "out.hwpx"
    write_payloads(output, [original], {"Contents/section0.xml": b"<x/>"})

    with zipfile.ZipFile(output) as zf:
        written = zf.getinfo("Contents/section0.xml")

    assert written.create_system == 0
    assert written.external_attr == 0
