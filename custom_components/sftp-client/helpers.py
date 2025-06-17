"""Helper functions for the SFTPClient component."""

from __future__ import annotations

from collections.abc import AsyncIterator
import logging

from asyncssh import SFTPClient, SSHClientConnection, connect

_LOGGER = logging.getLogger(__name__)


class SSHClient:
    """SSH Client."""

    def __init__(self, *, host: str, username: str, password: str, ssl: bool = False):
        """Initialize."""
        self.host = host
        self._username = username
        self._password = password
        self._ssl = ssl
        self._conn: SSHClientConnection | None = None

    async def _async_ssh_connect(self) -> None:
        """Create a ssh connection."""
        self._conn = await connect(
            self.host,
            username=self._username,
            password=self._password,
            known_hosts=None,
        )

    async def _async_ssh_close(self) -> None:
        """Close SSH session."""
        if self._conn is not None:
            try:
                self._conn.close()
                await self._conn.wait_closed()
            except Exception as e:  # noqa: BLE001
                _LOGGER.warning("Error while closing SSH connection: %s", e)
            finally:
                self._conn = None


class SFTPConnection(SSHClient):
    """Client."""

    client: SFTPClient | None = None

    async def async_connect(self) -> None:
        """Open SFTP Connection."""
        await self._async_ssh_connect()
        self.client = await self._conn.start_sftp_client()

    async def async_close(self) -> None:
        """Close SFTP Connection."""
        if self.client:
            try:
                self.client.exit()
            except Exception as e:  # noqa: BLE001
                _LOGGER.warning("Error while closing SFTP client: %s", e)
            self.client = None
        await self._async_ssh_close()

    async def async_ensure_path_exists(self, path: str) -> bool:
        """Ensure that a path exists recursively on the SFTP server."""
        if self.client is None:
            raise RuntimeError("SFTP client not connected")
        if not await self.client.isdir(path):
            await self.client.mkdir(path)
            return False
        return True

    async def __aenter__(self):
        """Async init."""
        await self.async_connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async exit."""
        await self.async_close()


def json_to_stream(json_str: str, chunk_size: int = 8192) -> AsyncIterator[bytes]:
    """Convert a JSON string into an async iterator of bytes."""

    async def generator() -> AsyncIterator[bytes]:
        encoded = json_str.encode("utf-8")
        for i in range(0, len(encoded), chunk_size):
            yield encoded[i : i + chunk_size]

    return generator()
