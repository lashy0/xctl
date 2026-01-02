import uuid
from typing import List, Dict

from ..config.settings import settings
from ..core.config_repository import ConfigRepository
from ..core.docker_controller import DockerController
from ..core.exceptions import XrayError


class UserService:
    """Manages Xray users, configuration updates, and service restarts."""

    def __init__(self):
        """Initializes the service with repository and docker controller."""
        self.repo = ConfigRepository(settings.CONFIG_PATH)
        self.docker = DockerController(settings.DOCKER_CONTAINER_NAME)

    def add_user(self, email: str) -> str:
        """Adds a new user, restarts Xray, and returns the connection link.

        Args:
            email: Unique identifier for the user (e.g., device name).

        Returns:
            The generated VLESS connection link.

        Raises:
            ValueError: If a user with the same email already exists.
            XrayError: If configuration parsing or docker operations fail.
        """
        config = self.repo.load()
        inbound = self._find_vless_inbound(config)
        clients = inbound['settings']['clients']

        if any(c.get('email') == email for c in clients):
            raise ValueError(f"User '{email}' already exists.")
        
        new_uuid = str(uuid.uuid4())
        new_client = {
            "id": new_uuid,
            "flow": "xtls-rprx-vision",
            "email": email
        }
        clients.append(new_client)

        self.repo.save(config)
        self.docker.restart()

        return self._generate_link(new_uuid, email, inbound)

    def remove_user(self, email: str) -> bool:
        """Removes a user by email and restarts Xray.

        Args:
            email: The identifier of the user to remove.

        Returns:
            True if the user was removed, False if not found.
        """
        config = self.repo.load()
        inbound = self._find_vless_inbound(config)
        clients = inbound['settings']['clients']

        initial_count = len(clients)
        inbound['settings']['clients'] = [c for c in clients if c.get('email') != email]

        if len(inbound['settings']['clients']) < initial_count:
            self.repo.save(config)
            self.docker.restart()
            return True
        
        return False

    def get_users(self) -> List[Dict[str, str]]:
        """Retrieves a list of all active users.

        Returns:
            A list of dictionaries with user details (email, id, flow).
        """
        config = self.repo.load()
        inbound = self._find_vless_inbound(config)
        return inbound['settings']['clients']
    
    def get_user_link(self, email: str) -> str:
        """Finds a user by email and regenerates their connection link."""
        config = self.repo.load()
        inbound = self._find_vless_inbound(config)
        clients = inbound['settings']['clients']

        user = next((c for c in clients if c.get('email') == email), None)

        if not user:
            raise ValueError(f"User '{email}' not found.")
        
        return self._generate_link(user['id'], email, inbound)

    def _find_vless_inbound(self, config: Dict) -> Dict:
        """Finds the VLESS Reality inbound in the configuration.

        Args:
            config: The full configuration dictionary.

        Returns:
            The inbound dictionary object (by reference).

        Raises:
            XrayError: If no VLESS Reality inbound is found.
        """
        inbounds = config.get('inbounds', [])
        for inbound in inbounds:
            protocol = inbound.get('protocol')
            security = inbound.get('streamSettings', {}).get('security')
            
            if protocol == 'vless' and security == 'reality':
                return inbound
        
        raise XrayError("No VLESS+Reality inbound found in config.json")

    def _generate_link(self, user_uuid: str, email: str, inbound: Dict) -> str:
        """Constructs the VLESS connection string.

        Args:
            user_uuid: The user's UUID.
            email: The user's email (alias).
            inbound: The inbound configuration dictionary.

        Returns:
            A formatted vless:// URL.
        """
        port = inbound['port']
        stream = inbound['streamSettings']
        reality = stream['realitySettings']
        
        sni = reality['serverNames'][0]
        sid = reality['shortIds'][0]
        fp = reality.get('fingerprint', 'chrome')
        spx = reality.get('spiderX', '')

        server_ip = str(settings.SERVER_IP)
        pub_key = settings.XRAY_PUB_KEY

        link = (
            f"vless://{user_uuid}@{server_ip}:{port}"
            f"?security=reality"
            f"&encryption=none"
            f"&pbk={pub_key}"
            f"&headerType=none"
            f"&fp={fp}"
            f"&type=tcp"
            f"&flow=xtls-rprx-vision"
            f"&sni={sni}"
            f"&sid={sid}"
        )

        if spx:
            link += f"&spx={spx}"

        link += f"#{email}"
        return link
