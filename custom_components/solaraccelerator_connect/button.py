"""Przycisk: wymuszenie sprawdzenia aktualizacji firmware bramki."""

from __future__ import annotations

from homeassistant.components.button import (
    ENTITY_ID_FORMAT,
    ButtonDeviceClass,
    ButtonEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SaConnectConfigEntry
from .api import GatewayError
from .coordinator import SaConnectCoordinator
from .entity import SaConnectEntity, build_entity_id


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SaConnectConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([OtaCheckButton(entry.runtime_data)])


class OtaCheckButton(SaConnectEntity, ButtonEntity):
    """Bramka sama sprawdza aktualizacje co 6 h — to jest droga na skróty."""

    _attr_device_class = ButtonDeviceClass.UPDATE
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "ota_check"

    def __init__(self, coordinator: SaConnectCoordinator) -> None:
        super().__init__(coordinator, "ota_check")
        self.entity_id = build_entity_id(coordinator, ENTITY_ID_FORMAT, "ota_check")

    async def async_press(self) -> None:
        try:
            await self.coordinator.api.async_ota_check()
        except GatewayError as err:
            raise HomeAssistantError(f"Bramka odrzuciła żądanie: {err}") from err
