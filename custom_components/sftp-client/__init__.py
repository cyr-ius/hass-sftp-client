"""The SFTPClient integration."""

from __future__ import annotations

import logging

from asyncssh import PermissionDenied

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady

from .const import (
    CONF_BACKUP_PATH,
    DATA_BACKUP_AGENT_LISTENERS,
    DEFAULT_BACKUP_PATH,
    DOMAIN,
)
from .helpers import SFTPConnection

type SFTPClientConfigEntry = ConfigEntry[SFTPConnection]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: SFTPClientConfigEntry) -> bool:
    """Set up SFTPClient from a config entry."""
    sftp = SFTPConnection(
        host=entry.data[CONF_HOST],
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
    )

    try:
        await sftp.async_connect()
        result = await sftp.client.listdir()
    except PermissionDenied as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="invalid_username_password",
        ) from err
    except ConnectionRefusedError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="server_not_found",
        ) from err
    except OSError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from err

    # Check if we can connect to the SFTP server
    # and access the root directory
    if not result:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        )

    path = entry.data.get(CONF_BACKUP_PATH, DEFAULT_BACKUP_PATH)

    # Ensure the backup directory exists
    if not await sftp.async_ensure_path_exists(path):
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_access_or_create_backup_path",
        )

    entry.runtime_data = sftp
    await sftp.async_close()

    def async_notify_backup_listeners() -> None:
        for listener in hass.data.get(DATA_BACKUP_AGENT_LISTENERS, []):
            listener()

    entry.async_on_unload(entry.async_on_state_change(async_notify_backup_listeners))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SFTPClientConfigEntry) -> bool:
    """Unload a SFTPClient config entry."""
    sftp = entry.runtime_data
    await sftp.async_close()
    return True
