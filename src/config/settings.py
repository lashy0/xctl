import os
import sys
from functools import lru_cache
from pathlib import Path
from ipaddress import IPv4Address, AddressValueError
from typing import List, Optional

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel


BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_PATH = BASE_DIR / ".env"
DEFAULT_CONTAINER_NAME = "xray-core"

class Settings:
    """Manages application configuration loaded from environment variables."""
    def __init__(self):
        load_dotenv(ENV_PATH, override=True)

        self._errors: List[str] = []

        self.CONFIG_PATH = self._validate_path("CONFIG_PATH", "config/config.json")
        self.SERVER_IP = self._validate_ip("SERVER_IP")
        self.XRAY_PORT = self._validate_port("XRAY_PORT", 443)
        self.XRAY_PUB_KEY = self._validate_key("XRAY_PUB_KEY")

        self.XRAY_PROTOCOL = os.getenv("XRAY_PROTOCOL", "vless-reality")
        self.DOCKER_CONTAINER_NAME = os.getenv("DOCKER_CONTAINER_NAME", DEFAULT_CONTAINER_NAME)

        if self._errors:
            self._print_errors_and_exit()

    def _validate_ip(self, var_name: str) -> Optional[IPv4Address]:
        """Validates that the variable contains a valid IPv4 address."""
        val = os.getenv(var_name)
        if not val:
            if ENV_PATH.exists():
                self._errors.append(f"[bold yellow]• {var_name}[/]: Field required")
            return None
        try:
            return IPv4Address(val)
        except AddressValueError:
            self._errors.append(f"[bold yellow]• {var_name}[/]: Invalid IPv4 address: '{val}'")
            return None
    
    def _validate_port(self, var_name: str, default: int) -> int:
        """Validates that the port is an integer between 1 and 65535."""
        val = os.getenv(var_name, str(default))
        try:
            port = int(val)
            if not (1 <= port <= 65535):
                raise ValueError
            return port
        except ValueError:
            self._errors.append(f"[bold yellow]• {var_name}[/]: Port must be between 1 and 65535")
            return default
    
    def _validate_key(self, var_name: str) -> str:
        """Validates the length of the X25519 public key."""
        val = os.getenv(var_name, "").strip()
        if not val:
            if ENV_PATH.exists():
                self._errors.append(f"[bold yellow]• {var_name}[/]: Field required")
            return ""
        if len(val) not in (43, 44):
            self._errors.append(f"[bold yellow]• {var_name}[/]: Invalid key length ({len(val)}). Expected 43-44.")
        return val
    
    def _validate_path(self, var_name: str, default: str) -> Path:
        """Validates that the file path has a .json extension."""
        val = os.getenv(var_name, default)
        path = Path(val)
        if path.suffix != ".json":
            self._errors.append(f"[bold yellow]• {var_name}[/]: File must have .json extension")
        return path
    
    def _print_errors_and_exit(self):
        """Displays all validation errors in a Rich panel and exits the program."""
        console = Console(stderr=True)
        error_text = "\n".join(self._errors)
        console.print(Panel(
            error_text,
            title="[bold red]Configuration Error (.env)[/]",
            border_style="red",
            padding=(1, 2)
        ))
        console.print(f"\n[dim]Please check your configuration file at: [/][blue]{ENV_PATH}[/]")
        console.print("[dim]If this is a fresh install, run:[/][bold cyan] xctl init[/]\n")
        sys.exit(1)


@lru_cache
def load_settings() -> Settings:
    return Settings()
