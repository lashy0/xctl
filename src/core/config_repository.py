import json
from pathlib import Path
from typing import Dict, Any

from .exceptions import ConfigNotFoundError, JsonDecodeError


class ConfigRepository:
    """Handles reading and writing the Xray configuration file."""

    def __init__(self, file_path: Path):
        """Initializes the repository.

        Args:
            file_path: Path to the configuration file.
        """
        self.file_path = file_path

    def load(self) -> Dict[str, Any]:
        """Reads the configuration from the JSON file.

        Returns:
            A dictionary containing the configuration.

        Raises:
            ConfigNotFoundError: If the file does not exist.
            JsonDecodeError: If the file content is not valid JSON.
        """
        if not self.file_path.exists():
            raise ConfigNotFoundError(f"File not found: {self.file_path}")

        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise JsonDecodeError(f"Invalid JSON: {e}")

    def save(self, data: Dict[str, Any]) -> None:
        """Writes the configuration to the JSON file.

        Args:
            data: The configuration dictionary to save.
        """
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
