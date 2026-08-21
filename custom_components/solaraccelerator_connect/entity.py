"""Wspólna baza encji integracji."""

from __future__ import annotations

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SaConnectCoordinator


class SaConnectEntity(CoordinatorEntity[SaConnectCoordinator]):
    """Encja związana z jedną bramką.

    Urządzenie w HA opisujemy falownikiem, nie bramką: to jego dane widzi
    użytkownik, a bramka jest drogą do nich. Wersję firmware i link do portalu
    zostawiamy w tym samym urządzeniu, żeby diagnostyka była pod ręką.
    """

    _attr_has_entity_name = True

    def __init__(self, coordinator: SaConnectCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_unique_id = f"{coordinator.entry.unique_id}_{key}"

    @property
    def device_info(self) -> DeviceInfo:
        status = self.coordinator.data.status if self.coordinator.data else {}
        mac = str(status.get("mac") or "")
        name = str(status.get("inverter_name") or "Solar Accelerator Connect")
        info = DeviceInfo(
            identifiers={(DOMAIN, str(self.coordinator.entry.unique_id))},
            name=name,
            manufacturer=str(status.get("inverter_manufacturer") or "Solar Accelerator"),
            model=str(status.get("inverter_model") or "SA Connect"),
            sw_version=str(status.get("firmware_version") or ""),
            configuration_url=self.coordinator.api.base_url,
        )
        if mac:
            info["connections"] = {(CONNECTION_NETWORK_MAC, mac.lower())}
        return info


def build_entity_id(coordinator: SaConnectCoordinator, fmt: str, key: str) -> str:
    """Buduje `entity_id` w postaci `sensor.<prefiks>_<klucz>`.

    Prefiks pochodzi z kreatora. Przy tym samym prefiksie encje wracają pod
    swoimi identyfikatorami, więc gotowe dashboardy i automatyzacje działają
    dalej bez przepisywania.
    """
    prefix = coordinator.entry.data.get("prefix") or ""
    object_id = f"{prefix}_{key}" if prefix else key
    return async_generate_entity_id(fmt, object_id, hass=coordinator.hass)
