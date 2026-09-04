"""Integracja Solar Accelerator Connect — lokalny odczyt i sterowanie bramką."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import GatewayApi
from .const import MIN_WRITE_FIRMWARE
from .coordinator import SaConnectCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TIME,
]

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
    _warn_if_write_unsupported(coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


def _version_tuple(raw: str) -> tuple[int, ...]:
    try:
        return tuple(int(part) for part in raw.split("."))
    except ValueError:
        return ()


def _warn_if_write_unsupported(coordinator: SaConnectCoordinator) -> None:
    """Encje sterujące powstają zawsze — na starym firmware zapis zwróci błąd.

    Ukrycie połowy integracji przed użytkownikiem, który po prostu nie wgrał
    aktualizacji, byłoby gorsze: nie miałby jak się domyślić, czego brakuje
    ani dlaczego. Zamiast tego zostawiamy encje i mówimy wprost w logu.
    """
    status = coordinator.data.status if coordinator.data else {}
    current = str(status.get("firmware_version") or "")
    if not current:
        return
    have, need = _version_tuple(current), _version_tuple(MIN_WRITE_FIRMWARE)
    if have and need and have < need:
        _LOGGER.warning(
            "Bramka ma firmware %s — ręczne sterowanie falownikiem wymaga %s. "
            "Encje sterujące będą widoczne, ale zapis zwróci błąd.",
            current,
            MIN_WRITE_FIRMWARE,
        )


async def async_unload_entry(hass: HomeAssistant, entry: SaConnectConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_entry(hass: HomeAssistant, entry: SaConnectConfigEntry) -> None:
    """Zmiana adresu albo hasła (reauth) — najprościej postawić wpis od nowa."""
    await hass.config_entries.async_reload(entry.entry_id)
