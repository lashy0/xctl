import sys
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Generator, List
from contextlib import contextmanager

from .exceptions import ConfigNotFoundError, JsonDecodeError

if sys.platform != 'win32':
    import fcntl
else:
    fcntl = None


class ConfigRepository:
    """Handles reading and writing the Xray configuration file."""

    def __init__(self, file_path: Path):
        """Initializes the repository.

        Args:
            file_path: Path to the configuration file.
        """
        self.file_path = file_path
        self.lock_path = file_path.with_suffix('.lock')
        self.backup_dir = file_path.parent / "backups"

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
    
    def _create_backup(self) -> None:
        """Creates a timestamped backup and removes old ones."""
        if not self.file_path.exists():
            return
        
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_path = self.backup_dir / f"config.{timestamp}.json"

        shutil.copy2(self.file_path, backup_path)

        backups = sorted(self.backup_dir.glob("config.*.json"))
        
        while len(backups) > 10:
            oldest_backup = backups.pop(0)
            try:
                oldest_backup.unlink()
            except OSError:
                pass
    
    @contextmanager
    def atomic_write(self) -> Generator[Dict[str, Any], None, None]:
        """Context manager for safe read-modify-write operations.
        Acquires an exclusive lock before reading and releases it after saving.
        """
        if sys.platform == 'win32' or fcntl is None:
            self._create_backup()
            config = self.load()
            yield config
            self.save(config)
            return
        
        with open(self.lock_path, 'w') as lockfile:
            fcntl.flock(lockfile, fcntl.LOCK_EX)
            try:
                self._create_backup()
                config = self.load()
                yield config
                self.save(config)
            finally:
                fcntl.flock(lockfile, fcntl.LOCK_UN)
    
    def get_available_backups(self) -> List[Path]:
        """Returns a list of backup files sorted by newest first."""
        if not self.backup_dir.exists():
            return []
        return sorted(self.backup_dir.glob("config.*.json"), reverse=True)

    def restore_backup(self, backup_path: Path) -> None:
        """Overwrites the current config with the selected backup."""
        if not backup_path.exists():
            raise ConfigNotFoundError(f"Backup file not found: {backup_path}")
        
        shutil.copy2(backup_path, self.file_path)
