from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

from ..docker_controller import DockerController


class ProtocolHandler(ABC):
    """Abstract base class for Xray protocol handling strategies.
    
    This class defines the interface that all specific protocol implementations
    (e.g., VLESS-Reality, VLESS-WS, Trojan) must adhere to.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Returns the unique identifier for this protocol."""
        pass

    @abstractmethod
    def find_inbound(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Locates the specific inbound configuration object in the config.

        Args:
            config: The full Xray configuration dictionary.

        Returns:
            The inbound dictionary reference.

        Raises:
            XrayError: If the inbound cannot be found.
        """
        pass

        
    @property
    @abstractmethod
    def requires_domain(self) -> bool:
        """Does this protocol require a valid SNI/Domain?"""
        pass

    @abstractmethod
    def create_client(self, email: str, user_id: str) -> Dict[str, Any]:
        """Creates the client dictionary structure for the config.

        Args:
            email: The user's email/identifier.
            user_id: The generated UUID.

        Returns:
            A dictionary representing the client object in Xray config.
        """
        pass

    @abstractmethod
    def generate_link(
        self, 
        inbound: Dict[str, Any], 
        user_id: str, 
        email: str, 
        host: str, 
        **kwargs
    ) -> str:
        """Generates the connection share link (e.g., vless://...).

        Args:
            inbound: The inbound configuration dictionary.
            user_id: The user's UUID.
            email: The user's email/identifier.
            host: The server's IP address or domain.
            **kwargs: Additional protocol-specific arguments (e.g., pub_key).

        Returns:
            The formatted connection string.
        """
        pass

    @abstractmethod
    def on_initialize(
        self, 
        config: Dict[str, Any], 
        docker: DockerController,
        domain: Optional[str] = None
    ) -> Dict[str, str]:
        """Performs protocol-specific setup during the 'init' command.

        For example, generating keys, setting SNI, or configuring paths.

        Args:
            config: The Xray configuration dictionary (to be modified in place).
            docker: The docker controller for executing generation commands.
            domain: The selected SNI domain (if applicable).

        Returns:
            A dictionary of environment variables to save to .env (e.g., PUB_KEY).
        """
        pass
