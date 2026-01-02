import subprocess
import re
from typing import Tuple

from .exceptions import DockerOperationError, KeyGenerationError


class DockerController:
    """Manages Docker container operations via subprocess commands."""

    def __init__(self, container_name: str):
        """Initializes the controller.

        Args:
            container_name: The name of the Docker container to control.
        """
        self.container_name = container_name

    def _run_cmd(self, cmd: str) -> str:
        """Executes a shell command and returns the output.

        Args:
            cmd: The command string to execute.

        Returns:
            The standard output of the command.

        Raises:
            DockerOperationError: If the command returns a non-zero exit code.
        """
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() or "Unknown error"
            raise DockerOperationError(f"Command failed: {cmd}\nError: {error_msg}")

    def restart(self) -> None:
        """Restarts the Docker container."""
        self._run_cmd(f"docker restart {self.container_name}")

    def is_running(self) -> bool:
        """Checks if the container is currently running.

        Returns:
            True if the container status is 'running', False otherwise.
        """
        try:
            cmd = f"docker inspect -f '{{{{.State.Running}}}}' {self.container_name}"
            output = self._run_cmd(cmd)
            return output.lower() == 'true'
        except DockerOperationError:
            return False

    def generate_x25519_keys(self) -> Tuple[str, str]:
        """Generates a new X25519 key pair.

        Smart logic:
        1. If Xray is running, use 'docker exec' (fast).
        2. If Xray is stopped, use 'docker run' (temporary container).
        """
        if self.is_running():
            cmd = f"docker exec {self.container_name} xray x25519"
        else:
            image = "ghcr.io/xtls/xray-core:latest"
            cmd = f"docker run --rm {image} x25519"
        
        try:
            output = self._run_cmd(cmd)
        except DockerOperationError as e:
            raise DockerOperationError(f"Failed to generate keys: {e}")
        
        priv_match = re.search(r'Private\s*Key:?\s*(\S+)', output, re.IGNORECASE)
        pub_match = re.search(r'(?:Public\s*Key|Password):?\s*(\S+)', output, re.IGNORECASE)

        if priv_match and pub_match:
            return priv_match.group(1), pub_match.group(1)
        
        raise KeyGenerationError(f"Failed to parse output:\n{output}")
