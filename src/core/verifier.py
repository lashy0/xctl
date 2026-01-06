import ssl
import socket
from typing import Tuple, Optional
from urllib.parse import urlparse


class DomainVerifier:
    """Verifies if a remote domain is suitable for Xray masking (SNI).

    Checks for DNS resolution, TLS 1.3/1.2 support, and HTTP/2 (h2) ALPN.
    Useful for Reality, VLESS-TLS, Trojan, etc.
    """
    @staticmethod
    def extract_hostname(url_or_domain: str) -> str:
        """Extracts the hostname from a URL or raw domain string.

        Args:
            url_or_domain: Input string (e.g., 'https://google.com/foo' or 'google.com').

        Returns:
            str: The clean hostname.
        """
        if "://" not in url_or_domain:
            url_or_domain = f"https://{url_or_domain}"
        parsed = urlparse(url_or_domain)
        return parsed.hostname or url_or_domain

    @staticmethod
    def verify(
        domain: str, 
        timeout: float = 3.0,
        forbidden_ip: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Checks domain suitability for Reality configuration.

        Performs a full connection handshake to inspect ALPN and TLS versions.

        Args:
            domain: The domain name (SNI) to check.
            timeout: Socket connection timeout in seconds. Defaults to 3.0.
            forbidden_ip: An IP address (usually the server's public IP) 
                that the domain must NOT resolve to.

        Returns:
            Tuple[bool, str]: A tuple containing:
                - bool: True if the domain is valid for Reality.
                - str: A description message (success details or failure reason).
        """
        hostname = DomainVerifier.extract_hostname(domain)
        
        try:
            target_ip = socket.gethostbyname(hostname)
        except socket.gaierror:
            return False, f"DNS resolution failed for '{hostname}'"
        
        if forbidden_ip and target_ip == forbidden_ip:
            return False, (
                f"Domain resolves to this server's IP ({target_ip}). "
                "This would cause a routing loop."
            )

        if target_ip in ("127.0.0.1", "::1", "0.0.0.0"):
             return False, "Domain resolves to a local/loopback address."
        
        context = ssl.create_default_context()
        context.set_alpn_protocols(['h2', 'http/1.1'])
        
        try:
            with socket.create_connection((hostname, 443), timeout=timeout) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    tls_version = ssock.version()
                    alpn_proto = ssock.selected_alpn_protocol()
                    
                    if tls_version not in ('TLSv1.3', 'TLSv1.2'):
                        return False, (
                            f"Unsupported TLS version: {tls_version}. "
                            "Reality requires TLS 1.3 or 1.2."
                        )
                    
                    if alpn_proto != 'h2':
                        return False, (
                            f"HTTP/2 not supported (ALPN: {alpn_proto}). "
                            "Browsers expect h2 for modern sites."
                        )
                    
                    return True, (
                        f"Compatible! IP: {target_ip} | "
                        f"Proto: {tls_version} | ALPN: {alpn_proto}"
                    )

        except ssl.SSLError as e:
            return False, f"SSL Handshake failed: {e.reason}"
        except socket.timeout:
            return False, "Connection timed out (Port 443 unreachable)."
        except OSError as e:
            return False, f"Network error: {str(e)}"
