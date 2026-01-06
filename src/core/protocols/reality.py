import secrets
from urllib.parse import quote
from typing import Dict, Any, Optional

from .base import ProtocolHandler
from ..docker_controller import DockerController
from ..exceptions import XrayError


class RealityHandler(ProtocolHandler):
    """Implementation of the VLESS-Reality protocol logic."""

    @property
    def name(self) -> str:
        return "vless-reality"

    def find_inbound(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Finds the inbound with protocol='vless' and security='reality'."""
        inbounds = config.get('inbounds', [])
        for inbound in inbounds:
            protocol = inbound.get('protocol')
            stream_settings = inbound.get('streamSettings', {})
            security = stream_settings.get('security')
            
            if protocol == 'vless' and security == 'reality':
                return inbound
        
        raise XrayError("No VLESS+Reality inbound found in configuration.")
    
    @property
    def requires_domain(self) -> bool:
        return True

    def create_client(self, email: str, user_id: str) -> Dict[str, Any]:
        """Creates a client with the required 'xtls-rprx-vision' flow."""
        return {
            "id": user_id,
            "flow": "xtls-rprx-vision",
            "email": email
        }

    def generate_link(
        self, 
        inbound: Dict[str, Any], 
        user_id: str, 
        email: str, 
        host: str, 
        **kwargs
    ) -> str:
        """Generates a VLESS-Reality link."""
        pub_key = kwargs.get('pub_key')
        if not pub_key:
            raise ValueError("Public Key is required for Reality links.")

        port = inbound['port']
        stream = inbound['streamSettings']
        reality = stream['realitySettings']

        sni = reality['serverNames'][0]
        sid = reality['shortIds'][0]
        fp = reality.get('fingerprint', 'chrome')
        spx = reality.get('spiderX', '')

        link = (
            f"vless://{user_id}@{host}:{port}"
            f"?security=reality"
            f"&sni={sni}"
            f"&fp={fp}"
            f"&pbk={quote(pub_key)}"
            f"&sid={sid}"
            f"&type=tcp"
            f"&flow=xtls-rprx-vision"
            f"&encryption=none"
        )
        
        if spx:
            link += f"&spx={spx}"
        
        link += f"#{email}"
        return link

    def on_initialize(
        self, 
        config: Dict[str, Any], 
        docker: DockerController,
        domain: Optional[str] = None
    ) -> Dict[str, str]:
        """Generates x25519 keys, creates ShortId, and updates config."""
        if not domain:
            raise ValueError("Domain is required for Reality initialization.")
        
        priv_key, pub_key = docker.generate_x25519_keys()
        
        short_id = secrets.token_hex(8)

        inbound = self.find_inbound(config)
        reality = inbound['streamSettings']['realitySettings']
        
        reality['privateKey'] = priv_key
        reality['shortIds'] = [short_id]
        reality['dest'] = f"{domain}:443"
        reality['serverNames'] = [domain]

        return {
            "XRAY_PUB_KEY": pub_key,
            "XRAY_PROTOCOL": self.name
        }
