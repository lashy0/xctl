import re
from typing import Tuple

import docker
from docker.errors import DockerException, NotFound, APIError

from .exceptions import DockerOperationError, KeyGenerationError


class DockerController:
    """Manages Docker container operations."""

    def __init__(self, container_name: str):
        """Initializes the controller.

        Args:
            container_name: The name of the Docker container to control.
        """
        self.container_name = container_name
        try:
            self.client = docker.from_env()
        except DockerException as e:
            raise DockerOperationError(f"Failed to connect to Docker Daemon: {e}")

    def _get_container(self):
        """Helper to get the container object safely."""
        try:
            return self.client.containers.get(self.container_name)
        except NotFound:
            return None
        except APIError as e:
            raise DockerOperationError(f"Docker API Error: {e}")

    def restart(self) -> None:
        """Restarts the Docker container."""
        container = self._get_container()
        if not container:
            raise DockerOperationError(f"Container '{self.container_name}' not found.")
        
        try:
            container.restart()
        except APIError as e:
            raise DockerOperationError(f"Failed to restart container: {e}")

    def is_running(self) -> bool:
        """Checks if the container is currently running.
        Returns:
            True if the container status is 'running', False otherwise.
        """
        container = self._get_container()
        if not container:
            return False
        
        try:
            container.reload()
            return container.status == 'running'
        except APIError:
            return False

    def generate_x25519_keys(self) -> Tuple[str, str]:
        """Generates a new X25519 key pair."""
        image = "ghcr.io/xtls/xray-core:latest"
        output = ""

        try:
            container = self._get_container()
            
            if container and container.status == 'running':
                result = container.exec_run("xray x25519")
                if result.exit_code != 0:
                    raise KeyGenerationError(f"Xray command failed: {result.output.decode()}")
                output = result.output.decode('utf-8')
            
            else:
                output_bytes = self.client.containers.run(
                    image, 
                    "x25519", 
                    remove=True,
                    stderr=True
                )
                output = output_bytes.decode('utf-8')

        except (DockerException, APIError) as e:
            raise DockerOperationError(f"Docker failed during key generation: {e}")
        
        priv_match = re.search(r'Private\s*Key:?\s*(\S+)', output, re.IGNORECASE)
        pub_match = re.search(r'(?:Public\s*Key|Password):?\s*(\S+)', output, re.IGNORECASE)

        if priv_match and pub_match:
            return priv_match.group(1), pub_match.group(1)

        raise KeyGenerationError(f"Failed to parse output:\n{output}")
