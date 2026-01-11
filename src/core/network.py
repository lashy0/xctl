import urllib.request
from typing import Optional


class NetworkUtils:
    """Utilities for network discovery and IP detection."""

    PROVIDERS = [
        ("https://1.1.1.1/cdn-cgi/trace", "cloudflare"),
        ("https://api.ipify.org", "plain"),
        ("https://ifconfig.me/ip", "plain"),
        ("https://checkip.amazonaws.com", "plain"),
        ("https://icanhazip.com", "plain"),
    ]

    @staticmethod
    def get_public_ip(timeout: float = 3.0) -> Optional[str]:
        """
        Attempts to detect the public IP address using a list of reliable providers.
        Returns None if all attempts fail.
        """
        for url, parser_type in NetworkUtils.PROVIDERS:
            try:
                with urllib.request.urlopen(url, timeout=timeout) as response:
                    content = response.read().decode('utf-8').strip()
                    
                    if parser_type == "cloudflare":
                        for line in content.split('\n'):
                            if line.startswith('ip='):
                                return line.split('=')[1]
                    else:
                        if 7 <= len(content) <= 15:
                            return content
                            
            except Exception:
                continue
        
        return None