"""Hancom HWP COM automation."""

from __future__ import annotations

from contextlib import AbstractContextManager
from pathlib import Path
from typing import Protocol, Self

try:
    import winreg
except ImportError:  # pragma: no cover - Windows-only dependency.
    winreg = None  # type: ignore[assignment]

from han_auto.exceptions import (
    HwpAutomationError,
    HwpNotInstalledError,
    MissingFieldError,
    SecurityModuleError,
    TemplateNotFoundError,
)
from han_auto.formatter import MarkdownHwpFormatter
from han_auto.models import NoticeDocument, TemplateConfig


class HwpClient(Protocol):
    """Protocol shared by the COM client and tests."""

    def open(self, path: Path) -> None: ...

    def get_fields(self) -> list[str]: ...

    def put_field_text(self, field_name: str, text: str) -> None: ...

    def move_to_field(self, field_name: str) -> None: ...

    def insert_text(self, text: str) -> None: ...

    def run_action(self, action_name: str) -> None: ...

    def save_as(self, path: Path) -> None: ...

    def close(self) -> None: ...


class HwpComClient(AbstractContextManager["HwpComClient"]):
    """Thin wrapper around `HWPFrame.HwpObject`."""

    def __init__(self, hwp: object):
        self.hwp = hwp

    @classmethod
    def create(
        cls,
        *,
        visible: bool = False,
        register_security: bool = True,
        security_dll: str | Path | None = None,
        security_module_name: str = "FilePathCheckerModuleExample",
    ) -> Self:
        try:
            import win32com.client  # type: ignore[import-not-found]
        except ImportError as exc:
            raise HwpNotInstalledError("pywin32 is not installed for this Python environment.") from exc

        try:
            hwp = win32com.client.gencache.EnsureDispatch("HWPFrame.HwpObject")
        except Exception as exc:
            raise HwpNotInstalledError(
                "Could not create HWPFrame.HwpObject. Install Hancom Office and verify COM registration."
            ) from exc

        client = cls(hwp)
        client.set_visible(visible)
        if register_security:
            register_file_path_check_module(
                hwp,
                security_dll=security_dll,
                module_name=security_module_name,
            )
        return client

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.close()

    def set_visible(self, visible: bool) -> None:
        try:
            self.hwp.XHwpWindows.Item(0).Visible = visible
        except Exception:
            return

    def open(self, path: Path) -> None:
        try:
            result = self.hwp.Open(str(path))
        except Exception as exc:
            raise HwpAutomationError(f"Failed to open HWP template: {path}") from exc
        if result is False:
            raise HwpAutomationError(f"HWP refused to open template: {path}")

    def get_fields(self) -> list[str]:
        raw: object | None = None
        for args in ((0, 2), (), (0, 0)):
            try:
                raw = self.hwp.GetFieldList(*args)
                break
            except Exception:
                continue
        if raw is None:
            raise HwpAutomationError("Failed to read HWP field list.")
        return split_hwp_field_list(str(raw))

    def put_field_text(self, field_name: str, text: str) -> None:
        try:
            result = self.hwp.PutFieldText(field_name, text)
        except Exception as exc:
            raise HwpAutomationError(f"Failed to write HWP field: {field_name}") from exc
        if result is False:
            raise HwpAutomationError(f"HWP refused to write field: {field_name}")

    def move_to_field(self, field_name: str) -> None:
        try:
            result = self.hwp.MoveToField(field_name, True, True, False)
        except Exception as exc:
            raise HwpAutomationError(f"Failed to move to HWP field: {field_name}") from exc
        if result is False:
            raise HwpAutomationError(f"HWP refused to move to field: {field_name}")

    def insert_text(self, text: str) -> None:
        try:
            result = self.hwp.InsertText(text)
        except Exception:
            result = self._insert_text_with_action(text)
        if result is False:
            raise HwpAutomationError("HWP refused text insertion.")

    def run_action(self, action_name: str) -> None:
        try:
            result = self.hwp.HAction.Run(action_name)
        except Exception as exc:
            raise HwpAutomationError(f"Failed to run HWP action: {action_name}") from exc
        if result is False:
            raise HwpAutomationError(f"HWP refused action: {action_name}")

    def save_as(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            result = self.hwp.SaveAs(str(path))
        except Exception as exc:
            raise HwpAutomationError(f"Failed to save HWP file: {path}") from exc
        if result is False:
            raise HwpAutomationError(f"HWP refused to save file: {path}")

    def close(self) -> None:
        try:
            self.hwp.Quit()
        except Exception:
            return

    def _insert_text_with_action(self, text: str) -> object:
        try:
            hset = self.hwp.HParameterSet.HInsertText
            self.hwp.HAction.GetDefault("InsertText", hset.HSet)
            hset.Text = text
            return self.hwp.HAction.Execute("InsertText", hset.HSet)
        except Exception as exc:
            raise HwpAutomationError("Failed to insert text into HWP.") from exc


class HwpDocumentAutomation:
    """Render parsed documents into HWP templates."""

    def __init__(self, client: HwpClient, formatter: MarkdownHwpFormatter | None = None):
        self.client = client
        self.formatter = formatter or MarkdownHwpFormatter()

    def render(
        self,
        document: NoticeDocument,
        template_config: TemplateConfig,
        output_path: str | Path,
        *,
        rich_body: bool = True,
    ) -> Path:
        template_path = template_config.template_path
        if not template_path.exists():
            raise TemplateNotFoundError(f"HWP template not found: {template_path}")

        output = Path(output_path).resolve()
        self.client.open(template_path)
        self._validate_required_fields(template_config)

        values = document.field_values()
        body_target = template_config.field_mapping["body"]
        for source_name, target_field in template_config.field_mapping.items():
            if source_name == "body" and rich_body:
                continue
            self.client.put_field_text(target_field, values.get(source_name, ""))

        if rich_body:
            self.formatter.insert_body(
                self.client,
                body_target,
                document.blocks,
                template_config.style_mapping,
            )

        self.client.save_as(output)
        return output

    def _validate_required_fields(self, template_config: TemplateConfig) -> None:
        available = set(self.client.get_fields())
        required = set(template_config.field_mapping.values())
        missing = sorted(required - available)
        if missing:
            raise MissingFieldError(f"HWP template is missing fields: {', '.join(missing)}")


def inspect_fields(
    template_path: str | Path,
    *,
    visible: bool = False,
    register_security: bool = True,
    security_dll: str | Path | None = None,
    security_module_name: str = "FilePathCheckerModuleExample",
) -> list[str]:
    """Open a template and return its HWP field names."""

    path = Path(template_path).resolve()
    if not path.exists():
        raise TemplateNotFoundError(f"HWP template not found: {path}")
    with HwpComClient.create(
        visible=visible,
        register_security=register_security,
        security_dll=security_dll,
        security_module_name=security_module_name,
    ) as client:
        client.open(path)
        return client.get_fields()


def render_with_com(
    document: NoticeDocument,
    template_config: TemplateConfig,
    output_path: str | Path,
    *,
    visible: bool = False,
    register_security: bool = True,
    security_dll: str | Path | None = None,
    security_module_name: str = "FilePathCheckerModuleExample",
    rich_body: bool = True,
) -> Path:
    """Render a document using a real Hancom HWP COM instance."""

    with HwpComClient.create(
        visible=visible,
        register_security=register_security,
        security_dll=security_dll,
        security_module_name=security_module_name,
    ) as client:
        return HwpDocumentAutomation(client).render(
            document,
            template_config,
            output_path,
            rich_body=rich_body,
        )


def split_hwp_field_list(raw: str) -> list[str]:
    """Split the various separators returned by HWP GetFieldList."""

    if not raw:
        return []
    normalized = raw.replace("\x02", "\n").replace("\r", "\n").replace(";", "\n")
    return [part.strip() for part in normalized.split("\n") if part.strip()]


def register_file_path_check_module(
    hwp: object,
    *,
    security_dll: str | Path | None = None,
    module_name: str = "FilePathCheckerModuleExample",
) -> None:
    """Register and activate Hancom's FilePathCheckDLL automation module."""

    dll_path = Path(security_dll).resolve() if security_dll else find_file_path_check_dll()
    if dll_path is not None:
        _register_security_dll_path(dll_path, module_name=module_name)
    elif not _security_module_registered(module_name):
        raise SecurityModuleError(
            "HWP FilePathCheckDLL security module was not found. "
            "Download '보안모듈(Automation).zip' from Hancom Developer and pass "
            f"--security-dll with {module_name}.dll, or use --skip-security-register."
        )

    try:
        result = hwp.RegisterModule("FilePathCheckDLL", module_name)
    except Exception as exc:
        hint = " Pass --security-dll or --skip-security-register if your environment requires it."
        raise SecurityModuleError(f"Failed to register HWP FilePathCheckDLL.{hint}") from exc
    if result is False:
        raise SecurityModuleError("HWP refused FilePathCheckDLL registration.")


def find_file_path_check_dll() -> Path | None:
    """Search common Hancom Office install paths for FilePathCheckDLL.dll."""

    roots = [
        Path.cwd(),
        Path.home() / "Downloads",
        Path.home() / "Desktop",
        Path.home() / "Documents",
        Path.home() / "AppData/Local/Hancom/HwpAutomation",
        Path("C:/Program Files/HNC"),
        Path("C:/Program Files (x86)/HNC"),
        Path("C:/Program Files/Hancom"),
        Path("C:/Program Files (x86)/Hancom"),
    ]
    patterns = [
        "FilePathCheckerModuleExample.dll",
        "FilePathCheckerModule.dll",
        "FilePathCheckDLL.dll",
    ]
    for root in roots:
        if not root.exists():
            continue
        for pattern in patterns:
            matches = sorted(root.rglob(pattern))
            if matches:
                return matches[0].resolve()
        for archive in sorted(root.rglob("*.zip")):
            extracted = _extract_security_dll_from_zip(archive, patterns)
            if extracted is not None:
                return extracted
    return None


def _extract_security_dll_from_zip(archive: Path, patterns: list[str]) -> Path | None:
    try:
        import zipfile
    except ImportError:  # pragma: no cover - stdlib is expected.
        return None

    lowered = {pattern.lower() for pattern in patterns}
    try:
        with zipfile.ZipFile(archive) as zf:
            for name in zf.namelist():
                filename = Path(name).name
                if filename.lower() not in lowered:
                    continue
                target_dir = Path.home() / "AppData/Local/Hancom/HwpAutomation"
                target_dir.mkdir(parents=True, exist_ok=True)
                target = target_dir / filename
                if not target.exists():
                    target.write_bytes(zf.read(name))
                return target.resolve()
    except (OSError, zipfile.BadZipFile):
        return None
    return None


def _register_security_dll_path(dll_path: Path, *, module_name: str) -> None:
    if not dll_path.exists():
        raise SecurityModuleError(f"FilePathCheckDLL not found: {dll_path}")
    if winreg is None:
        raise SecurityModuleError("FilePathCheckDLL registry registration is only available on Windows.")
    key_path = r"Software\HNC\HwpAutomation\Modules"
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            winreg.SetValueEx(key, module_name, 0, winreg.REG_SZ, str(dll_path))
    except OSError as exc:
        raise SecurityModuleError(f"Failed to write HWP security module registry key: {dll_path}") from exc


def _security_module_registered(module_name: str) -> bool:
    if winreg is None:
        return False
    key_path = r"Software\HNC\HwpAutomation\Modules"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            value, _ = winreg.QueryValueEx(key, module_name)
    except OSError:
        return False
    return bool(str(value).strip())
