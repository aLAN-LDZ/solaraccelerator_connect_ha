"""Przełączniki nastaw falownika siedzących w polach bitowych."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import ENTITY_ID_FORMAT, SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SaConnectConfigEntry
from .control import ControlDef, controls_for
from .coordinator import SaConnectCoordinator
from .entity import SaConnectControlEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SaConnectConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        SaConnectSwitch(coordinator, control) for control in controls_for("switch")
    )


class SaConnectSwitch(SaConnectControlEntity, SwitchEntity):
    """Pojedynczy bit we wspólnym rejestrze konfiguracyjnym.

    Zapis idzie przez read-modify-write (`SaConnectControlEntity`), więc
    sąsiednie funkcje falownika zostają nietknięte — w rejestrze 178 obok
    peak shavingu sieci siedzą jeszcze trzy inne przełączniki.
    """

    def __init__(
        self, coordinator: SaConnectCoordinator, control: ControlDef
    ) -> None:
        super().__init__(coordinator, control, ENTITY_ID_FORMAT)
        self._mask = control.bit_mask or 0

    @property
    def is_on(self) -> bool | None:
        value = self.field_value
        return None if value is None else bool(value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.async_write_field(self._mask)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.async_write_field(0)
