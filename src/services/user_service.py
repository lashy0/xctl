import uuid
from typing import List, Dict

from ..config.settings import Settings
from ..core.config_repository import ConfigRepository
from ..core.docker_controller import DockerController
from ..core.exceptions import XrayError
from ..core.protocol_factory import get_handler


class UserService:
    """Manages Xray users, configuration updates, and service restarts."""

    def __init__(self, docker_controller: DockerController, settings: Settings):
        """Initializes the service with repository and docker controller."""
        self.settings = settings
        self.repo = ConfigRepository(self.settings.CONFIG_PATH)
        self.docker = docker_controller
        self.handler = get_handler(self.settings.XRAY_PROTOCOL)

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
        with self.repo.atomic_write() as config:
            inbound = self.handler.find_inbound(config)
            clients = inbound['settings']['clients']

            if any(c.get('email') == email for c in clients):
                raise ValueError(f"User '{email}' already exists.")
            
            new_uuid = str(uuid.uuid4())

            new_client = self.handler.create_client(email, new_uuid)
            clients.append(new_client)
        
        self.docker.reload_config()

        return self.handler.generate_link(
            inbound=inbound,
            user_id=new_uuid,
            email=email,
            host=str(self.settings.SERVER_IP),
            pub_key=self.settings.XRAY_PUB_KEY
        )

    def remove_user(self, email: str) -> bool:
        """Removes a user by email and restarts Xray.

        Args:
            email: The identifier of the user to remove.

        Returns:
            True if the user was removed, False if not found.
        """
        user_removed = False

        with self.repo.atomic_write() as config:
            inbound = self.handler.find_inbound(config)
            clients = inbound['settings']['clients']

            initial_count = len(clients)
            inbound['settings']['clients'] = [c for c in clients if c.get('email') != email]

            if len(inbound['settings']['clients']) < initial_count:
                user_removed = True
        
        if user_removed:
            self.docker.reload_config()
            return True
        
        return False

    def get_users(self) -> List[Dict[str, str]]:
        """Retrieves a list of all active users.

        Returns:
            A list of dictionaries with user details (email, id, flow).
        """
        config = self.repo.load()
        inbound = self.handler.find_inbound(config)
        return inbound['settings']['clients']
    
    def get_user_link(self, email: str) -> str:
        """Finds a user by email and regenerates their connection link."""
        config = self.repo.load()
        inbound = self.handler.find_inbound(config)
        clients = inbound['settings']['clients']

        user = next((c for c in clients if c.get('email') == email), None)

        if not user:
            raise ValueError(f"User '{email}' not found.")
        
        return self.handler.generate_link(
            inbound=inbound,
            user_id=user['id'],
            email=email,
            host=str(self.settings.SERVER_IP),
            pub_key=self.settings.XRAY_PUB_KEY
        )
    
    def get_users_with_stats(self) -> Dict:
        """Retrieves users and merges their traffic stats."""
        config = self.repo.load()
        inbound = self.handler.find_inbound(config)
        users = inbound['settings']['clients']
        
        try:
            stats = self.docker.get_traffic_stats()
        except Exception:
            stats = {}
        
        result = []
        for user in users:
            email = user.get('email')
            user_stats = stats.get(email, {'up': 0, 'down': 0})
            result.append({
                **user,
                'traffic_up': user_stats['up'],
                'traffic_down': user_stats['down'],
                'total': user_stats['up'] + user_stats['down']
            })
            
        return result
    
    def get_user_traffic(self, email: str) -> Dict:
        """Retrieves traffic statistics for a specific user."""
        all_users = self.get_users_with_stats()
        
        target_user = next((u for u in all_users if u['email'] == email), None)
        
        if not target_user:
            raise ValueError(f"User '{email}' not found.")
            
        return target_user
