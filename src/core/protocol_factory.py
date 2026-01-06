from typing import Dict, Type

from .protocols.base import ProtocolHandler
from .protocols.reality import RealityHandler


STRATEGIES: Dict[str, Type[ProtocolHandler]] = {
    "vless-reality": RealityHandler,
}

def get_handler(protocol_name: str) -> ProtocolHandler:
    """Factory function to get the appropriate protocol handler.

    Args:
        protocol_name: The name of the protocol (e.g., 'vless-reality').

    Returns:
        An instance of the concrete ProtocolHandler.

    Raises:
        ValueError: If the protocol name is not supported.
    """
    handler_class = STRATEGIES.get(protocol_name)
    if not handler_class:
        return RealityHandler()
    
    return handler_class()
