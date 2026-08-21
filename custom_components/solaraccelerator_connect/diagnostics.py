"""Zrzut diagnostyczny do zgłoszeń błędów."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from . import SaConnectConfigEntry

# `ssid` i `ip` same w sobie nie są sekretem, ale w zgłoszeniu na GitHubie
# opisują czyjąś sieć dokładniej, niż potrzeba do diagnozy.
TO_REDACT = {CONF_PASSWORD, "ssid", "ip", "mac"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SaConnectConfigEntry
) -> dict[str, Any]:
    coordinator = entry.runtime_data
    data = coordinator.data
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "status": async_redact_data(dict(data.status), TO_REDACT),
        # Same odczyty bez `items` — interesuje nas stan magistrali, a nie
        # 120 liczb, które i tak widać w encjach.
        "readings": {
            key: value for key, value in data.readings.items() if key != "items"
        },
        "metric_keys": sorted(data.values),
        "update_interval_s": (
            coordinator.update_interval.total_seconds()
            if coordinator.update_interval
            else None
        ),
    }
