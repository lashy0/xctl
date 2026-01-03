from .config.settings import settings
from .core.docker_controller import DockerController
from .services.user_service import UserService
from .services.system_service import SystemService


def get_docker_client() -> DockerController:
    """Creates and returns a configured DockerController instance."""
    return DockerController(settings.DOCKER_CONTAINER_NAME)


def get_user_service() -> UserService:
    """Creates and returns a configured UserService instance with all dependencies."""
    docker = get_docker_client()
    
    return UserService(docker_controller=docker)


def get_system_service() -> SystemService:
    """Creates and returns a configured SystemService instance."""
    docker = get_docker_client()
    
    return SystemService(docker_controller=docker)