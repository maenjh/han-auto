"""Domain exceptions raised by han-auto."""


class HanAutoError(Exception):
    """Base exception for expected han-auto failures."""


class DocumentParseError(HanAutoError):
    """Raised when Markdown input cannot be parsed into a document."""


class TemplateConfigError(HanAutoError):
    """Raised when a template configuration file is invalid."""


class TemplateNotFoundError(HanAutoError):
    """Raised when the configured HWP template path does not exist."""


class HwpNotInstalledError(HanAutoError):
    """Raised when Hancom HWP or pywin32 cannot be loaded."""


class MissingFieldError(HanAutoError):
    """Raised when an HWP template is missing a required field."""


class SecurityModuleError(HanAutoError):
    """Raised when the HWP security module cannot be registered."""


class HwpAutomationError(HanAutoError):
    """Raised for generic HWP COM automation failures."""
