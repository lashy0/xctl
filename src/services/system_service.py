from typing import List, Dict
from pathlib import Path

from ..config.settings import Settings
from ..core.config_repository import ConfigRepository
from ..core.docker_controller import DockerController


class SystemService:
    """Manages system-level operations: backups, restoration, server control."""

    def __init__(self, docker_controller: DockerController, settings: Settings):
        self.settings = settings
        self.repo = ConfigRepository(self.settings.CONFIG_PATH)
        self.docker = docker_controller

    def get_backups(self) -> List[Dict[str, str]]:
        """Returns a formatted list of available backups."""
        files = self.repo.get_available_backups()
        result = []
        for f in files:
            timestamp_str = f.stem.replace("config.", "").replace("_", " ")
            result.append({
                "path": f,
                "name": f.name,
                "date": timestamp_str
            })
        return result

    def restore_backup(self, backup_path: Path) -> None:
        """Restores a config backup and restarts the Xray server."""
        self.repo.restore_backup(backup_path)
        
        self.docker.restart()
