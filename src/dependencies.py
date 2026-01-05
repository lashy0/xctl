from .config.settings import load_settings, ENV_PATH, DEFAULT_CONTAINER_NAME
from .core.docker_controller import DockerController
from .services.user_service import UserService
from .services.system_service import SystemService


def get_docker_client() -> DockerController:
    """Creates and returns a configured DockerController instance."""
    if ENV_PATH.exists():
        try:
            settings = load_settings()
            return DockerController(settings.DOCKER_CONTAINER_NAME)
        except SystemExit:
            pass
    
    return DockerController(DEFAULT_CONTAINER_NAME)


def get_user_service() -> UserService:
    """Creates and returns a configured UserService instance with all dependencies."""
    settings = load_settings()
    docker = get_docker_client()
    
    return UserService(docker_controller=docker, settings=settings)


def get_system_service() -> SystemService:
    """Creates and returns a configured SystemService instance."""
    settings = load_settings()
    docker = get_docker_client()
    
    return SystemService(docker_controller=docker, settings=settings)