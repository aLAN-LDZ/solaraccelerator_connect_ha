"""Nastawy liczbowe falownika: moce, prądy, SOC harmonogramu."""

from __future__ import annotations

from homeassistant.components.number import (
    ENTITY_ID_FORMAT,
    NumberEntity,
)
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
        SaConnectNumber(coordinator, control) for control in controls_for("number")
    )


class SaConnectNumber(SaConnectControlEntity, NumberEntity):
    """Rejestr u16 pokazany jako liczba."""

    def __init__(
        self, coordinator: SaConnectCoordinator, control: ControlDef
    ) -> None:
        super().__init__(coordinator, control, ENTITY_ID_FORMAT)
        self._attr_native_min_value = control.min_value
        self._attr_native_max_value = control.max_value
        self._attr_native_step = control.step
        self._attr_native_unit_of_measurement = control.unit
        self._attr_device_class = control.device_class
        self._attr_mode = control.mode

    @property
    def native_value(self) -> float | None:
        return self.field_value

    async def async_set_native_value(self, value: float) -> None:
        # Rejestry Deye są całkowite — HA potrafi przysłać ułamek z suwaka
        # albo z szablonu w automatyzacji.
        await self.async_write_field(int(round(value)))
