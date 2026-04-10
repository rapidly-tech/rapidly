"""ClamAV-related exceptions."""


class ClamAVError(Exception):
    """Base exception for ClamAV operations."""

    pass


class ClamAVConnectionError(ClamAVError):
    """Failed to connect to ClamAV daemon."""

    pass


class ClamAVScanError(ClamAVError):
    """Error during file scanning."""

    pass
