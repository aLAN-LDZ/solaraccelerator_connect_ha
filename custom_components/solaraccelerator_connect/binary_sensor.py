"""Binary sensory: czy falownik odpowiada i czy odczyt jest kompletny."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    ENTITY_ID_FORMAT,
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SaConnectConfigEntry
from .coordinator import SaConnectCoordinator
from .entity import SaConnectEntity, build_entity_id


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SaConnectConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [
            InverterOnlineSensor(coordinator),
            PartialReadSensor(coordinator),
        ]
    )


class InverterOnlineSensor(SaConnectEntity, BinarySensorEntity):
    """Bramka odpowiada, ale czy falownik z nią gada.

    To dwie różne awarie i UI musi je rozróżniać: gdy bramka jest nieosiągalna,
    wszystkie encje idą w `unavailable`; gdy milczy falownik, bramka dalej
    odpowiada, a problem jest na magistrali RS485.
    """

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_translation_key = "inverter_online"

    def __init__(self, coordinator: SaConnectCoordinator) -> None:
        super().__init__(coordinator, "inverter_online")
        self.entity_id = build_entity_id(coordinator, ENTITY_ID_FORMAT, "inverter_online")

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.inverter_online

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        # `last_error` to gotowy komunikat diagnostyczny z bramki — ten sam,
        # który pokazuje jej portal. Podajemy go bez przetwarzania.
        error = str(self.coordinator.data.readings.get("last_error") or "")
        return {"last_error": error} if error else {}


class PartialReadSensor(SaConnectEntity, BinarySensorEntity):
    """Część bloków Modbus nie przeszła — dane są, ale niekompletne."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "partial_read"

    def __init__(self, coordinator: SaConnectCoordinator) -> None:
        super().__init__(coordinator, "partial_read")
        self.entity_id = build_entity_id(coordinator, ENTITY_ID_FORMAT, "partial_read")

    @property
    def is_on(self) -> bool:
        readings = self.coordinator.data.readings
        ok = readings.get("blocks_ok")
        total = readings.get("blocks_total")
        if not isinstance(ok, int) or not isinstance(total, int) or total == 0:
            return False
        return ok < total
