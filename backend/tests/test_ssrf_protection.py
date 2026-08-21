import pytest
from backend.app.core.security import is_ip_private_or_restricted, validate_url_for_ssrf


def test_private_ip_detection():
    # Loopback
    assert is_ip_private_or_restricted("127.0.0.1") is True
    assert is_ip_private_or_restricted("::1") is True

    # RFC 1918 Private
    assert is_ip_private_or_restricted("10.0.0.1") is True
    assert is_ip_private_or_restricted("172.16.0.1") is True
    assert is_ip_private_or_restricted("192.168.1.1") is True

    # Cloud metadata
    assert is_ip_private_or_restricted("169.254.169.254") is True

    # Public IPs
    assert is_ip_private_or_restricted("8.8.8.8") is False
    assert is_ip_private_or_restricted("1.1.1.1") is False


def test_ssrf_url_validation_blocks_restricted():
    with pytest.raises(ValueError, match="restricted"):
        validate_url_for_ssrf("http://localhost/admin")

    with pytest.raises(ValueError, match="restricted"):
        validate_url_for_ssrf("http://169.254.169.254/latest/meta-data/")

    with pytest.raises(ValueError, match=r"forbidden|restricted"):
        validate_url_for_ssrf("http://127.0.0.1:8000/secret")

    with pytest.raises(ValueError, match=r"forbidden|restricted"):
        validate_url_for_ssrf("http://192.168.1.50/dashboard")

    with pytest.raises(ValueError, match="Unsupported URL scheme"):
        validate_url_for_ssrf("file:///etc/passwd")


def test_ssrf_url_validation_allows_safe_domains():
    safe_url = validate_url_for_ssrf("https://github.com/torvalds")
    assert safe_url == "https://github.com/torvalds"
