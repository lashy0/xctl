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
    
    def get_traffic_stats(self) -> dict:
        """Queries Xray API for user traffic statistics.
        
        Returns:
            Dict[email, {'up': bytes, 'down': bytes}]
        """
        container = self._get_container()
        if not container or container.status != 'running':
            raise DockerOperationError("Xray container is not running")

        try:
            cmd = "xray api statsquery --server=127.0.0.1:10085 --pattern ''"
            result = container.exec_run(cmd)
            
            if result.exit_code != 0:
                raise DockerOperationError(f"Failed to query stats: {result.output.decode()}")
                
            output = result.output.decode('utf-8')
            return self._parse_stats(output)
            
        except Exception as e:
            raise DockerOperationError(f"Error fetching stats: {e}")

    def _parse_stats(self, output: str) -> dict:
        """Parses the raw output from xray api statsquery."""
        stats = {}
        
        for line in output.strip().split('\n'):
            if ">>>traffic>>>" not in line:
                continue
                
            parts = line.split(">>>")
            if len(parts) < 4:
                continue
            
            email = parts[1]
            type_and_value = parts[3].split(":")
            direction = type_and_value[0].strip()
            try:
                value = int(type_and_value[1].strip())
            except ValueError:
                value = 0

            if email not in stats:
                stats[email] = {'up': 0, 'down': 0}
            
            if direction == 'uplink':
                stats[email]['up'] = value
            elif direction == 'downlink':
                stats[email]['down'] = value
                
        return stats
