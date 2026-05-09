"""Rapidly load test authentication utilities.

Provides helper functions for constructing authenticated HTTP headers
used by Locust load test scenarios against the Rapidly API.
"""

from load_tests.config import config


def get_auth_headers(include_content_type: bool = True) -> dict[str, str]:
    """
    Get authentication headers for API requests.

    Args:
        include_content_type: Whether to include Content-Type header

    Returns:
        Dictionary of headers including authorization
    """
    headers = {}

    if include_content_type:
        headers["Content-Type"] = "application/json"
        headers["Accept"] = "application/json"

    if config.api_token:
        headers["Authorization"] = f"Bearer {config.api_token}"

    return headers
