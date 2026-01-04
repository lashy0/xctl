import sys
from pathlib import Path
from ipaddress import IPv4Address

from pydantic import Field, field_validator, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict
from rich.console import Console
from rich.panel import Panel


BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_PATH = BASE_DIR / ".env"

class Settings(BaseSettings):
    """Manages application configuration loaded from environment variables.

    Attributes:
        SERVER_IP: The public IPv4 address of the server.
        XRAY_PORT: The port Xray listens on. Defaults to 443.
        XRAY_PUB_KEY: The Reality public key in Base64 format.
        CONFIG_PATH: Path to the Xray config JSON file.
        DOCKER_CONTAINER_NAME: Name of the Docker container.
    """
    SERVER_IP: IPv4Address
    XRAY_PORT: int = Field(default=453, ge=1, le=65535)
    XRAY_PUB_KEY: str
    CONFIG_PATH: Path = Path("./config/config.json")
    DOCKER_CONTAINER_NAME: str = "xray-core"

    model_config = SettingsConfigDict(
        env_file=ENV_PATH,
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @field_validator("XRAY_PUB_KEY")
    @classmethod
    def validate_key(cls, v: str) -> str:
        """Validates the format of the public key.

        Args:
            v: The public key string from the environment.

        Returns:
            The validated public key.

        Raises:
            ValueError: If the key is too short or doesn't end with '='.
        """
        v = v.strip()

        if len(v) not in (43, 44):
            raise ValueError(
                f"Invalid key length: {len(v)} characters. "
                "Public key must be exactly 43 or 44 characters."
            )
        
        return v
    
    @field_validator("CONFIG_PATH")
    @classmethod
    def validate_config_extension(cls, v: Path) -> Path:
        """Ensures the configuration file has a JSON extension.

        Args:
            v: The path object.

        Returns:
            The validated path.

        Raises:
            ValueError: If the file extension is not .json.
        """
        if v.suffix != ".json":
            raise ValueError(f"Configuration file must have a .json extension, got: {v}")
        
        return v


try:
    settings = Settings()
except ValidationError as e:

    if any(cmd in sys.argv for cmd in ["init", "--help", "-v", "--version"]):
        class DummySettings:
            SERVER_IP = "127.0.0.1"
            XRAY_PORT = 443
            XRAY_PUB_KEY = "dummy_key_for_init_process"
            CONFIG_PATH = Path("./config/config.json")
            DOCKER_CONTAINER_NAME = "xray-core"
        
        settings = DummySettings()
    else:
        console = Console(stderr=True)

        error_messages = []
        for error in e.errors():
            field_name = str(error['loc'][0])
            msg = error['msg']

            error_messages.append(f"[bold yellow]• {field_name}[/]: {msg}")
        
        error_text = "\n".join(error_messages)

        console.print(Panel(
            error_text,
            title="[bold red]Configuration Error (.env)[/]",
            border_style="red",
            padding=(1, 2)
        ))

        console.print(f"\n[dim]Please check your configuration file at: [/][blue]{ENV_PATH}[/]\n")

        sys.exit(1)
