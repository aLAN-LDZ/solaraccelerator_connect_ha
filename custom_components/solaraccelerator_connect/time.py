"""Godziny startu slotów harmonogramu (Time of Use).

Deye trzyma je jako `u16 = HHMM` — 600 to 06:00, nie 600 minut. Falownik
przyjmuje wyłącznie pełne dziesiątki minut w tym zapisie, więc sekundy są
obcinane, a użytkownik zobaczy w encji dokładnie to, co siedzi w rejestrze.
"""

from __future__ import annotations

from datetime import time as dt_time

from homeassistant.components.time import ENTITY_ID_FORMAT, TimeEntity
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
        SaConnectTime(coordinator, control) for control in controls_for("time")
    )


def hhmm_to_time(raw: int) -> dt_time | None:
    hour, minute = divmod(raw, 100)
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return dt_time(hour=hour, minute=minute)


class SaConnectTime(SaConnectControlEntity, TimeEntity):
    """Godzina startu jednego slotu TOU."""

    def __init__(
        self, coordinator: SaConnectCoordinator, control: ControlDef
    ) -> None:
        super().__init__(coordinator, control, ENTITY_ID_FORMAT)

    @property
    def native_value(self) -> dt_time | None:
        raw = self.field_value
        if raw is None:
            return None
        # Wartość spoza HHMM (uszkodzony odczyt) pokazujemy jako brak, zamiast
        # zaokrąglać do czegoś, czego w falowniku nie ma.
        return hhmm_to_time(raw)

    async def async_set_value(self, value: dt_time) -> None:
        await self.async_write_field(value.hour * 100 + value.minute)
