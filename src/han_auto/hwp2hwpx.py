"""Convert HWP files to HWPX through neolord0/hwp2hwpx."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import logging
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile

from han_auto.exceptions import HanAutoError


class Hwp2HwpxError(HanAutoError):
    """Raised when HWP to HWPX conversion fails."""


logger = logging.getLogger(__name__)


HWP2HWPX_REPO_URL = "https://github.com/neolord0/hwp2hwpx.git"
HWP2HWPX_ZIP_URL = "https://github.com/neolord0/hwp2hwpx/archive/refs/heads/main.zip"
# Adoptium serves a Temurin 17 JDK per OS/arch. The OS and architecture are filled in at
# runtime so the portable JDK download works on Windows, macOS, and Linux.
ADOPTIUM_JDK_URL_TEMPLATE = (
    "https://api.adoptium.net/v3/binary/latest/17/ga/{os}/{arch}/jdk/hotspot/normal/eclipse"
)

DEPENDENCIES = {
    "hwplib-1.1.10.jar": "https://repo.maven.apache.org/maven2/kr/dogfoot/hwplib/1.1.10/hwplib-1.1.10.jar",
    "hwpxlib-1.0.8.jar": "https://repo.maven.apache.org/maven2/kr/dogfoot/hwpxlib/1.0.8/hwpxlib-1.0.8.jar",
}

CLI_CLASS_NAME = "HanAutoHwp2HwpxCli"
CLI_SOURCE = """
import kr.dogfoot.hwp2hwpx.Hwp2Hwpx;
import kr.dogfoot.hwplib.object.HWPFile;
import kr.dogfoot.hwplib.reader.HWPReader;
import kr.dogfoot.hwpxlib.object.HWPXFile;
import kr.dogfoot.hwpxlib.writer.HWPXWriter;

public final class HanAutoHwp2HwpxCli {
    public static void main(String[] args) throws Exception {
        if (args.length != 2) {
            System.err.println("Usage: HanAutoHwp2HwpxCli <input.hwp> <output.hwpx>");
            System.exit(2);
        }
        HWPFile fromFile = HWPReader.fromFile(args[0]);
        HWPXFile toFile = Hwp2Hwpx.toHWPX(fromFile);
        HWPXWriter.toFilepath(toFile, args[1]);
    }
}
""".strip()


@contextmanager
def prepared_hwpx_template(template_path: str | Path):
    """Yield an HWPX template path, converting HWP templates into a temp HWPX."""

    template = Path(template_path).resolve()
    suffix = template.suffix.lower()
    if not template.exists():
        raise Hwp2HwpxError(f"Template not found: {template}")
    if suffix == ".hwpx":
        yield template
        return
    if suffix != ".hwp":
        raise Hwp2HwpxError(f"Template must be .hwpx or .hwp: {template}")

    with tempfile.TemporaryDirectory(prefix="han-auto-hwp2hwpx-") as temp_dir:
        converted = Path(temp_dir) / f"{template.stem}.hwpx"
        convert_hwp_to_hwpx(template, converted)
        yield converted


def convert_hwp_to_hwpx(
    input_path: str | Path,
    output_path: str | Path,
    *,
    tool_root: str | Path | None = None,
) -> Path:
    """Convert an HWP file into HWPX using the Java hwp2hwpx library."""

    source = Path(input_path).resolve()
    output = Path(output_path).resolve()
    if not source.exists():
        raise Hwp2HwpxError(f"HWP file not found: {source}")
    if source.suffix.lower() != ".hwp":
        raise Hwp2HwpxError(f"Input must be an .hwp file: {source}")
    if output.suffix.lower() != ".hwpx":
        raise Hwp2HwpxError(f"Output must be an .hwpx file: {output}")

    Hwp2HwpxConverter(tool_root=tool_root).convert(source, output)
    if not output.exists():
        raise Hwp2HwpxError(f"hwp2hwpx did not create output: {output}")
    return output


class Hwp2HwpxConverter:
    """Build and run a small CLI wrapper around neolord0/hwp2hwpx."""

    def __init__(self, *, tool_root: str | Path | None = None):
        self.tool_root = Path(tool_root).resolve() if tool_root else default_tool_root()
        self.source_dir = self.tool_root / "hwp2hwpx-src"
        self.lib_dir = self.tool_root / "hwp2hwpx-lib"
        self.build_dir = self.tool_root / "hwp2hwpx-build"
        self.classes_dir = self.build_dir / "classes"

    def convert(self, input_path: Path, output_path: Path) -> None:
        logger.info("Using hwp2hwpx tool cache: %s", self.tool_root)
        java, javac = self._ensure_java()
        classpath = self._prepare_classpath(javac)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            [str(java), "-cp", classpath, CLI_CLASS_NAME, str(input_path), str(output_path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            raise Hwp2HwpxError(_process_error("hwp2hwpx conversion failed", result))

    def _prepare_classpath(self, javac: Path) -> str:
        configured = os.environ.get("HAN_AUTO_HWP2HWPX_CLASSPATH")
        if configured:
            return configured
        source_dir = self._ensure_source()
        dependencies = self._ensure_dependencies()
        self._ensure_classes(javac, source_dir, dependencies)
        return os.pathsep.join(str(path) for path in [self.classes_dir, *dependencies])

    def _ensure_java(self) -> tuple[Path, Path]:
        java_home = os.environ.get("HAN_AUTO_JAVA_HOME") or os.environ.get("JAVA_HOME")
        if java_home:
            java, javac = _java_pair(Path(java_home))
            if java.exists() and javac.exists() and _is_working_jdk(javac):
                return java, javac

        java_name = _binary_name("java")
        javac_name = _binary_name("javac")
        java_path = shutil.which(java_name)
        javac_path = shutil.which(javac_name)
        if java_path and javac_path:
            java, javac = Path(java_path), Path(javac_path)
            if _is_working_jdk(javac):
                return java, javac

        return self._ensure_portable_jdk()

    def _ensure_portable_jdk(self) -> tuple[Path, Path]:
        jdk_root = self.tool_root / "jdk"
        existing = _find_java_home(jdk_root)
        if existing is not None:
            return _java_pair(existing)

        logger.warning(
            "No Java JDK found. Downloading portable Temurin/OpenJDK 17 (about 180 MB) into %s. "
            "This happens once; set HAN_AUTO_JAVA_HOME to use an existing JDK instead.",
            jdk_root,
        )
        archive = self.tool_root / "downloads" / _jdk_archive_name()
        _download_file(_adoptium_jdk_url(), archive)
        jdk_root.mkdir(parents=True, exist_ok=True)
        _extract_archive(archive, jdk_root)

        java_home = _find_java_home(jdk_root)
        if java_home is None:
            raise Hwp2HwpxError(f"Portable JDK did not contain java/javac: {jdk_root}")
        return _java_pair(java_home)

    def _ensure_source(self) -> Path:
        configured = os.environ.get("HAN_AUTO_HWP2HWPX_SOURCE")
        if configured:
            source_dir = Path(configured).resolve()
            _require_source_tree(source_dir)
            return source_dir

        if self.source_dir.exists():
            _require_source_tree(self.source_dir)
            return self.source_dir

        self.source_dir.parent.mkdir(parents=True, exist_ok=True)
        git = shutil.which("git")
        if git:
            result = subprocess.run(
                [git, "clone", "--depth", "1", HWP2HWPX_REPO_URL, str(self.source_dir)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if result.returncode == 0:
                return self.source_dir
            if self.source_dir.exists():
                shutil.rmtree(self.source_dir, ignore_errors=True)

        archive = self.tool_root / "downloads" / "hwp2hwpx-main.zip"
        _download_file(HWP2HWPX_ZIP_URL, archive)
        with tempfile.TemporaryDirectory(prefix="han-auto-hwp2hwpx-src-") as temp_dir:
            temp_path = Path(temp_dir)
            with zipfile.ZipFile(archive) as zf:
                zf.extractall(temp_path)
            extracted = next(temp_path.glob("hwp2hwpx-*"), None)
            if extracted is None:
                raise Hwp2HwpxError("Downloaded hwp2hwpx source archive had no source directory.")
            shutil.copytree(extracted, self.source_dir)
        _require_source_tree(self.source_dir)
        return self.source_dir

    def _ensure_dependencies(self) -> list[Path]:
        self.lib_dir.mkdir(parents=True, exist_ok=True)
        jars: list[Path] = []
        for filename, url in DEPENDENCIES.items():
            jar = self.lib_dir / filename
            if not jar.exists():
                _download_file(url, jar)
            jars.append(jar)
        return jars

    def _ensure_classes(self, javac: Path, source_dir: Path, dependencies: list[Path]) -> None:
        marker = self.build_dir / "built.marker"
        cli_class = self.classes_dir / f"{CLI_CLASS_NAME}.class"
        if marker.exists() and cli_class.exists():
            return

        if self.classes_dir.exists():
            shutil.rmtree(self.classes_dir)
        self.classes_dir.mkdir(parents=True, exist_ok=True)
        self.build_dir.mkdir(parents=True, exist_ok=True)

        cli_source = self.build_dir / f"{CLI_CLASS_NAME}.java"
        cli_source.write_text(CLI_SOURCE + "\n", encoding="utf-8")
        java_sources = sorted((source_dir / "src" / "main" / "java").rglob("*.java"))
        java_sources.append(cli_source)

        source_list = self.build_dir / "sources.txt"
        source_list.write_text(
            "\n".join(f'"{source.as_posix()}"' for source in java_sources) + "\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [
                str(javac),
                "-encoding",
                "UTF-8",
                "-cp",
                os.pathsep.join(str(path) for path in dependencies),
                "-d",
                str(self.classes_dir),
                f"@{source_list}",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            raise Hwp2HwpxError(_process_error("Failed to build hwp2hwpx Java wrapper", result))
        marker.write_text("built\n", encoding="utf-8")


def default_tool_root() -> Path:
    configured = os.environ.get("HAN_AUTO_TOOL_ROOT")
    if configured:
        return Path(configured).resolve()
    cwd_tools = Path.cwd() / ".tools"
    if cwd_tools.exists():
        return cwd_tools.resolve()
    return (_user_cache_dir() / "han-auto" / "tools").resolve()


def _user_cache_dir() -> Path:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA")
        return Path(base) if base else Path.home() / "AppData" / "Local"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches"
    return Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")


def _adoptium_os() -> str:
    if os.name == "nt":
        return "windows"
    if sys.platform == "darwin":
        return "mac"
    return "linux"


def _adoptium_arch() -> str:
    machine = platform.machine().lower()
    if machine in {"arm64", "aarch64"}:
        return "aarch64"
    if machine in {"x86_64", "amd64", "x64"}:
        return "x64"
    if machine in {"x86", "i386", "i686"}:
        return "x86"
    return "x64"


def _adoptium_jdk_url() -> str:
    return ADOPTIUM_JDK_URL_TEMPLATE.format(os=_adoptium_os(), arch=_adoptium_arch())


def _jdk_archive_name() -> str:
    # Adoptium ships Windows JDKs as .zip and macOS/Linux JDKs as .tar.gz.
    suffix = "zip" if os.name == "nt" else "tar.gz"
    return f"temurin-jdk17.{suffix}"


def _extract_archive(archive: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    name = archive.name.lower()
    if name.endswith(".zip"):
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(dest)
        return
    if name.endswith((".tar.gz", ".tgz")):
        with tarfile.open(archive, "r:gz") as tf:
            try:
                tf.extractall(dest, filter="data")
            except TypeError:  # pragma: no cover - Python without the tar filter argument.
                tf.extractall(dest)
        return
    raise Hwp2HwpxError(f"Unsupported JDK archive type: {archive}")


def _download_file(url: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + ".download")
    logger.info("Downloading %s -> %s", url, target)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "han-auto/0.1 hwp2hwpx bootstrap",
            "Accept": "application/octet-stream,application/zip,*/*",
        },
    )
    try:
        with urllib.request.urlopen(request) as response, partial.open("wb") as output:
            shutil.copyfileobj(response, output)
        partial.replace(target)
    except Exception as exc:
        partial.unlink(missing_ok=True)
        raise Hwp2HwpxError(
            f"Failed to download {url} (target: {target}): {exc}. "
            "If your network blocks this host, prepare the tool cache on an allowed network "
            "or point HAN_AUTO_JAVA_HOME / HAN_AUTO_HWP2HWPX_SOURCE / HAN_AUTO_HWP2HWPX_CLASSPATH "
            "at local copies. If a previous download was interrupted, delete the tool cache "
            f"directory ({target.parent.parent}) and retry."
        ) from exc


def _binary_name(name: str) -> str:
    return f"{name}.exe" if os.name == "nt" else name


def _java_pair(java_home: Path) -> tuple[Path, Path]:
    return java_home / "bin" / _binary_name("java"), java_home / "bin" / _binary_name("javac")


def _is_working_jdk(javac: Path) -> bool:
    """Return True only if javac actually runs.

    macOS ships /usr/bin/java and /usr/bin/javac stubs that exist on PATH but fail with
    "Unable to locate a Java Runtime" until a real JDK is installed. Probing javac avoids
    treating those stubs as a usable JDK and lets the portable download kick in instead.
    """

    try:
        result = subprocess.run(
            [str(javac), "-version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError:
        return False
    return result.returncode == 0


def _find_java_home(root: Path) -> Path | None:
    if not root.exists():
        return None
    candidates = [root, *root.glob("*")]
    for candidate in candidates:
        # macOS JDK archives nest the runtime under Contents/Home; Windows/Linux keep bin at the top.
        for home in (candidate, candidate / "Contents" / "Home"):
            java, javac = _java_pair(home)
            if java.exists() and javac.exists():
                return home.resolve()
    return None


def _require_source_tree(source_dir: Path) -> None:
    if not (source_dir / "src" / "main" / "java" / "kr" / "dogfoot" / "hwp2hwpx").exists():
        raise Hwp2HwpxError(f"hwp2hwpx source tree is invalid: {source_dir}")


def _process_error(message: str, result: subprocess.CompletedProcess[str]) -> str:
    details = "\n".join(part.strip() for part in [result.stdout, result.stderr] if part.strip())
    if details:
        # Keep the head and tail of long output: javac lists the first errors up
        # front, while runtime stack traces put the root cause at the end.
        limit = 4000
        if len(details) > limit:
            half = limit // 2
            details = f"{details[:half]}\n... ({len(details) - limit} characters omitted) ...\n{details[-half:]}"
        return f"{message}:\n{details}"
    return message
