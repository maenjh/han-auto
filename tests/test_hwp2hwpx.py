from pathlib import Path
import tarfile

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


@pytest.mark.parametrize(
    ("name", "platform_name", "machine", "expected_os", "expected_arch"),
    [
        ("nt", "win32", "AMD64", "windows", "x64"),
        ("posix", "darwin", "arm64", "mac", "aarch64"),
        ("posix", "darwin", "x86_64", "mac", "x64"),
        ("posix", "linux", "aarch64", "linux", "aarch64"),
    ],
)
def test_adoptium_jdk_url_matches_os_and_arch(
    monkeypatch, name, platform_name, machine, expected_os, expected_arch
) -> None:
    monkeypatch.setattr(hwp2hwpx.os, "name", name)
    monkeypatch.setattr(hwp2hwpx.sys, "platform", platform_name)
    monkeypatch.setattr(hwp2hwpx.platform, "machine", lambda: machine)

    url = hwp2hwpx._adoptium_jdk_url()

    assert f"/{expected_os}/{expected_arch}/" in url


def test_jdk_archive_name_uses_tar_gz_off_windows(monkeypatch) -> None:
    monkeypatch.setattr(hwp2hwpx.os, "name", "posix")
    assert hwp2hwpx._jdk_archive_name().endswith(".tar.gz")

    monkeypatch.setattr(hwp2hwpx.os, "name", "nt")
    assert hwp2hwpx._jdk_archive_name().endswith(".zip")


def test_find_java_home_handles_macos_contents_home_layout(tmp_path: Path) -> None:
    home = tmp_path / "jdk-17" / "Contents" / "Home"
    bin_dir = home / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "java").write_text("stub")
    (bin_dir / "javac").write_text("stub")

    found = hwp2hwpx._find_java_home(tmp_path)

    assert found == home.resolve()


def test_extract_archive_unpacks_tar_gz(tmp_path: Path) -> None:
    payload = tmp_path / "jdk-17" / "bin" / "java"
    payload.parent.mkdir(parents=True)
    payload.write_text("binary")
    archive = tmp_path / "temurin-jdk17.tar.gz"
    with tarfile.open(archive, "w:gz") as tf:
        tf.add(payload, arcname="jdk-17/bin/java")

    dest = tmp_path / "out"
    hwp2hwpx._extract_archive(archive, dest)

    assert (dest / "jdk-17" / "bin" / "java").read_text() == "binary"


def test_is_working_jdk_rejects_failing_javac(tmp_path: Path) -> None:
    # A stub javac that exits non-zero (mirrors the macOS /usr/bin/javac placeholder).
    fake = tmp_path / "javac"
    assert hwp2hwpx._is_working_jdk(fake) is False
