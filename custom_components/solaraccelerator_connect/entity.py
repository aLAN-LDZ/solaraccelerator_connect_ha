"""Wspólna baza encji integracji."""

from __future__ import annotations

import logging

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import GatewayError
from .const import DOMAIN
from .control import ControlDef, apply_bit_mask
from .coordinator import SaConnectCoordinator

_LOGGER = logging.getLogger(__name__)


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


class SaConnectControlEntity(SaConnectEntity):
    """Baza encji ZAPISUJĄCEJ nastawę falownika.

    Stan czytamy z tego samego snapshotu, co sensory — nie ma osobnego odczytu
    per encja. Zapis idzie przez bramkę i czeka na weryfikację; dopiero potem
    prosimy koordynator o odświeżenie, żeby UI pokazało stan faktyczny, a nie
    ten, który użytkownik zamówił.

    Ręczna zmiana jest zmianą DO NAJBLIŻSZEGO dispatchu: jeśli instalacja jest
    sterowana przez optymalizator, ten nadpisze nastawy o pełnej godzinie.
    Mówi o tym opis encji — nie próbujemy tego blokować ani ukrywać.
    """

    def __init__(
        self,
        coordinator: SaConnectCoordinator,
        control: ControlDef,
        entity_id_format: str,
    ) -> None:
        super().__init__(coordinator, control.key)
        self._control = control
        self.entity_id = build_entity_id(coordinator, entity_id_format, control.key)
        self._attr_translation_key = control.key
        self._attr_icon = control.icon

    @property
    def available(self) -> bool:
        # Bez bieżącej wartości rejestru nie wolno pisać w pole bitowe, a i stan
        # byłby zmyślony — encja ma być wtedy niedostępna, nie „domyślna".
        return super().available and self.coordinator.is_metric_available(
            self._control.read_key
        )

    @property
    def raw_register(self) -> int | None:
        """Pełna wartość rejestru, jak ją przeczytała bramka."""
        value = self.coordinator.data.values.get(self._control.read_key)
        try:
            return int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None

    @property
    def field_value(self) -> int | None:
        """Wartość SAMEJ nastawy — po odcięciu sąsiednich bitów."""
        raw = self.raw_register
        if raw is None or self._control.bit_mask is None:
            return raw
        return raw & self._control.bit_mask

    async def async_write_field(self, value: int) -> None:
        """Zapisuje nastawę, składając ją z bieżącym stanem rejestru."""
        control = self._control
        to_write = value

        if control.bit_mask is not None:
            current = self.raw_register
            if current is None:
                # Zapis „w ciemno" zgasiłby cudze bity — np. peak shaving
                # generatora, który w rejestrze 178 siedzi obok naszego.
                # Brak nastawy jest odwracalny, zgaszona funkcja falownika
                # niekoniecznie.
                raise HomeAssistantError(
                    f"{self.entity_id}: brak bieżącej wartości rejestru "
                    f"{control.register} — nie zapisuję, żeby nie zgasić "
                    "sąsiednich ustawień falownika"
                )
            to_write = apply_bit_mask(current, value, control.bit_mask)

        try:
            await self.coordinator.api.async_write_register(control.register, to_write)
        except GatewayError as err:
            raise HomeAssistantError(f"{self.entity_id}: {err}") from err

        _LOGGER.debug(
            "Zapisano %s: rejestr %d = %d", self.entity_id, control.register, to_write
        )
        await self.coordinator.async_request_refresh()


def build_entity_id(coordinator: SaConnectCoordinator, fmt: str, key: str) -> str:
    """Buduje `entity_id` w postaci `sensor.<prefiks>_<klucz>`.

    Prefiks pochodzi z kreatora. Przy tym samym prefiksie encje wracają pod
    swoimi identyfikatorami, więc gotowe dashboardy i automatyzacje działają
    dalej bez przepisywania.
    """
    prefix = coordinator.entry.data.get("prefix") or ""
    object_id = f"{prefix}_{key}" if prefix else key
    return async_generate_entity_id(fmt, object_id, hass=coordinator.hass)
