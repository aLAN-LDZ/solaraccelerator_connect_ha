"""Koordynator odczytów z bramki SA Connect."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    GatewayApi,
    GatewayAuthError,
    GatewayError,
    GatewayNotReady,
    readings_to_values,
)
from .const import (
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    MIN_POLL_INTERVAL,
    MISSING_TOLERANCE,
    STATUS_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

# 32-bitowy licznik millis() bramki przekręca się po ~49 dniach pracy.
_MILLIS_WRAP = 1 << 32


@dataclass
class GatewayData:
    """Migawka stanu bramki, wspólna dla wszystkich encji."""

    values: dict[str, object] = field(default_factory=dict)
    readings: dict[str, object] = field(default_factory=dict)
    status: dict[str, object] = field(default_factory=dict)
    last_ok: datetime | None = None

    @property
    def inverter_online(self) -> bool:
        return bool(self.readings.get("online"))


class SaConnectCoordinator(DataUpdateCoordinator[GatewayData]):
    """Odpytuje bramkę w TYM SAMYM tempie, w którym ona odpytuje falownik.

    Interwał nie jest opcją integracji: bramka ma go w swoim portalu, a pytanie
    jej częściej zwraca ten sam snapshot z RAM-u. Wartość przyjeżdża w każdej
    odpowiedzi (`poll_interval_ms`), więc zmiana w portalu przenosi się tutaj
    w ciągu jednego cyklu.
    """

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, api: GatewayApi
    ) -> None:
        self.api = api
        self.entry = entry
        # Ile kolejnych odpowiedzi nie zawierało danego klucza. Bramka POMIJA
        # metryki z nieudanych bloków Modbus, więc pojedyncza dziura jest
        # normalna — dopiero seria oznacza, że wartości naprawdę nie ma.
        self._missing: dict[str, int] = {}
        self._known_keys: set[str] = set()
        self._new_key_listeners: list[Callable[[set[str]], None]] = []
        self._status_due = 0.0

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_POLL_INTERVAL),
            config_entry=entry,
        )

    # ── Encje pojawiające się w locie ───────────────────────────────────────

    def add_new_key_listener(self, listener: Callable[[set[str]], None]) -> None:
        """Platforma rejestruje się po encje dla kluczy, które dojdą później.

        Zestaw metryk bramki potrafi się zmienić w trakcie pracy — w `items`
        pojawiają się wtedy klucze, których nie było przy starcie HA. Bez tego
        użytkownik musiałby przeładować integrację, żeby je zobaczyć.
        """
        self._new_key_listeners.append(listener)

    @property
    def known_keys(self) -> set[str]:
        return set(self._known_keys)

    def is_metric_available(self, key: str) -> bool:
        return self._missing.get(key, 0) < MISSING_TOLERANCE

    # ── Pobranie ────────────────────────────────────────────────────────────

    async def _async_update_data(self) -> GatewayData:
        previous = self.data or GatewayData()
        try:
            readings = await self.api.async_get_readings()
            status = await self._maybe_refresh_status(previous)
        except GatewayAuthError as err:
            # Użytkownik ustawił albo zmienił hasło portalu po instalacji.
            raise ConfigEntryAuthFailed(str(err)) from err
        except (GatewayNotReady, GatewayError) as err:
            raise UpdateFailed(str(err)) from err

        values = readings_to_values(readings)
        self._track_missing(values)
        self._apply_gateway_interval(readings, status)

        data = GatewayData(
            values=values,
            readings=readings,
            status=status,
            last_ok=_last_ok_timestamp(readings),
        )
        self._notify_new_keys(values)
        return data

    async def _maybe_refresh_status(self, previous: GatewayData) -> dict[str, object]:
        """Stan bramki zmienia się wolno — nie ma po co ciągnąć go co cykl."""
        now = self.hass.loop.time()
        if previous.status and now < self._status_due:
            return previous.status
        self._status_due = now + STATUS_INTERVAL
        return await self.api.async_get_status()

    def _track_missing(self, values: dict[str, object]) -> None:
        for key in self._known_keys | set(values):
            if key in values:
                self._missing[key] = 0
            else:
                self._missing[key] = self._missing.get(key, 0) + 1

    def _apply_gateway_interval(
        self, readings: dict[str, object], status: dict[str, object]
    ) -> None:
        raw = readings.get("poll_interval_ms")
        if raw is None:
            modbus = status.get("modbus")
            if isinstance(modbus, dict):
                raw = modbus.get("poll_interval_ms")
        try:
            seconds = float(raw) / 1000.0  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return
        seconds = max(MIN_POLL_INTERVAL, seconds)
        wanted = timedelta(seconds=seconds)
        if self.update_interval != wanted:
            _LOGGER.debug("Interwał z bramki: %.1f s", seconds)
            self.update_interval = wanted

    def _notify_new_keys(self, values: dict[str, object]) -> None:
        fresh = set(values) - self._known_keys
        if not fresh:
            return
        self._known_keys |= fresh
        _LOGGER.debug("Nowe metryki z bramki: %s", ", ".join(sorted(fresh)))
        for listener in self._new_key_listeners:
            listener(fresh)


def _last_ok_timestamp(readings: dict[str, object]) -> datetime | None:
    """Moment ostatniego udanego odczytu falownika, w czasie bezwzględnym.

    Firmware ≥0.1.11 podaje gotowe `last_ok_at` (ISO 8601 UTC). Starsze wersje
    i bramka bez synchronizacji SNTP dają wyłącznie `millis()` — wtedy liczymy
    różnicę WEWNĄTRZ jednej odpowiedzi i odejmujemy ją od czasu HA. Różnica
    musi zawijać się na 32 bitach, bo licznik bramki przekręca się po ~49 dniach.
    """
    iso = readings.get("last_ok_at")
    if isinstance(iso, str) and iso:
        parsed = dt_util.parse_datetime(iso)
        if parsed is not None:
            return parsed

    now_ms = readings.get("now_ms")
    last_ok_ms = readings.get("last_ok_ms")
    if not isinstance(now_ms, int) or not isinstance(last_ok_ms, int) or not last_ok_ms:
        return None
    age_ms = (now_ms - last_ok_ms) % _MILLIS_WRAP
    return dt_util.utcnow() - timedelta(milliseconds=age_ms)
