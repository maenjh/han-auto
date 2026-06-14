"""Access packaged han-auto templates, configs, and examples."""

from __future__ import annotations

from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path, PurePosixPath

from han_auto.exceptions import HanAutoError


class ResourceError(HanAutoError):
    """Raised when a packaged resource cannot be found."""


def resource(name: str) -> Traversable:
    """Return a packaged resource by POSIX-style relative path."""

    parts = _resource_parts(name)
    item = files("han_auto").joinpath("resources", *parts)
    if not item.is_file():
        raise ResourceError(f"Packaged resource not found: {name}")
    return item


def resource_path(name: str) -> Path:
    """Return the filesystem path for a packaged resource.

    Wheels are installed unpacked in normal Python environments, so packaged HWPX
    templates can be passed directly to CLI commands that expect a real file path.
    """

    return Path(str(resource(name)))


def list_resources() -> list[str]:
    """List packaged resource names relative to ``han_auto/resources``."""

    root = files("han_auto").joinpath("resources")
    if not root.is_dir():
        return []
    names: list[str] = []
    _walk(root, PurePosixPath(), names)
    return sorted(names)


def _walk(node: Traversable, prefix: PurePosixPath, names: list[str]) -> None:
    for child in node.iterdir():
        child_name = prefix / child.name
        if child.is_dir():
            _walk(child, child_name, names)
        elif child.is_file():
            names.append(child_name.as_posix())


def _resource_parts(name: str) -> tuple[str, ...]:
    path = PurePosixPath(name)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise ResourceError(f"Resource name must be a relative path inside the package: {name}")
    return path.parts
