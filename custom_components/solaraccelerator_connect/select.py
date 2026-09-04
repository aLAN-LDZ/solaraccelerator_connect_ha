"""Nastawy wyborem z listy: tryb pracy i źródło ładowania w harmonogramie."""

from __future__ import annotations

from homeassistant.components.select import ENTITY_ID_FORMAT, SelectEntity
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
        SaConnectSelect(coordinator, control) for control in controls_for("select")
    )


class SaConnectSelect(SaConnectControlEntity, SelectEntity):
    """Rejestr (albo pole bitowe w rejestrze) pokazany jako lista opcji."""

    def __init__(
        self, coordinator: SaConnectCoordinator, control: ControlDef
    ) -> None:
        super().__init__(coordinator, control, ENTITY_ID_FORMAT)
        self._by_code = control.options
        self._by_label = {label: code for code, label in control.options.items()}
        self._attr_options = list(control.options.values())

    @property
    def current_option(self) -> str | None:
        value = self.field_value
        if value is None:
            return None
        # Kod spoza listy oznacza kombinację bitów, której nie opisaliśmy —
        # wtedy stan jest nieznany. Podstawienie pierwszej lepszej opcji
        # kłamałoby o tym, co falownik faktycznie robi.
        return self._by_code.get(value)

    async def async_select_option(self, option: str) -> None:
        await self.async_write_field(self._by_label[option])
