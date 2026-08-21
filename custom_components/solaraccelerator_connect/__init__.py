"""Integracja SolarAccelerator Connect — lokalny odczyt bramki SA Connect."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import GatewayApi
from .coordinator import SaConnectCoordinator

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.SENSOR]

type SaConnectConfigEntry = ConfigEntry[SaConnectCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: SaConnectConfigEntry) -> bool:
    api = GatewayApi(
        async_get_clientsession(hass),
        entry.data[CONF_HOST],
        entry.data.get(CONF_PASSWORD),
    )
    coordinator = SaConnectCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SaConnectConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_entry(hass: HomeAssistant, entry: SaConnectConfigEntry) -> None:
    """Zmiana adresu albo hasła (reauth) — najprościej postawić wpis od nowa."""
    await hass.config_entries.async_reload(entry.entry_id)
