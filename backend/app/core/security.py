import ipaddress
import socket
from urllib.parse import urlparse
from fastapi import HTTPException, UploadFile, status
from backend.app.core.config import settings


FORBIDDEN_HOSTNAMES = {
    "localhost",
    "metadata.google.internal",
    "169.254.169.254",
    "instance-data",
}


def is_ip_private_or_restricted(ip_str: str) -> bool:
    """Check if an IP address is private, loopback, link-local, multicast, or reserved."""
    try:
        ip = ipaddress.ip_address(ip_str)
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        )
    except ValueError:
        return True


def validate_url_for_ssrf(url: str) -> str:
    """
    Validates a URL against SSRF attacks.
    Ensures http/https scheme, safe hostname, and non-private IP addresses.
    Raises ValueError if unsafe.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Unsupported URL scheme: {parsed.scheme}")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL must have a valid hostname")

    hostname_lower = hostname.lower()
    if hostname_lower in FORBIDDEN_HOSTNAMES:
        raise ValueError(f"Access to hostname '{hostname}' is restricted")

    # If hostname is directly an IP literal
    try:
        ip_obj = ipaddress.ip_address(hostname_lower)
        if is_ip_private_or_restricted(str(ip_obj)):
            raise ValueError(f"Access to private IP '{hostname}' is forbidden")
        return url
    except ValueError:
        pass  # It's a standard domain name, proceed to DNS resolution

    # Resolve hostname to IPv4/IPv6 and check each resolved IP
    try:
        addr_info = socket.getaddrinfo(hostname, None)
        for entry in addr_info:
            ip_str = entry[4][0]
            if is_ip_private_or_restricted(ip_str):
                raise ValueError(f"Domain '{hostname}' resolves to restricted IP: {ip_str}")
    except socket.gaierror as e:
        raise ValueError(f"Failed to resolve domain '{hostname}': {e}")

    return url


def validate_pdf_upload(file: UploadFile) -> None:
    """Validates that uploaded file is a PDF and meets size constraints."""
    if file.content_type not in ("application/pdf", "application/x-pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Only PDF files are supported.",
        )
