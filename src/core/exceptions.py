class XrayError(Exception):
    """Base class for all exceptions in this application."""
    pass


class ConfigNotFoundError(XrayError):
    """Raised when the config.json file does not exist."""
    pass


class JsonDecodeError(XrayError):
    """Raised when config.json contains invalid JSON."""
    pass


class DockerOperationError(XrayError):
    """Raised when a Docker command fails (e.g., restart failed)."""
    pass


class KeyGenerationError(XrayError):
    """Raised when Xray fails to generate keys."""
    pass
