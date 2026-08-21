"""Sensory: pomiary z falownika + diagnostyka bramki."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    ENTITY_ID_FORMAT,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SaConnectConfigEntry
from .catalog import describe
from .const import SETTING_PREFIX
from .coordinator import GatewayData, SaConnectCoordinator
from .entity import SaConnectEntity, build_entity_id


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SaConnectConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data

    entities: list[SensorEntity] = [
        SaConnectDiagnosticSensor(coordinator, spec) for spec in DIAGNOSTIC_SENSORS
    ]
    entities += [
        SaConnectMetricSensor(coordinator, key)
        for key in sorted(coordinator.data.values)
    ]
    async_add_entities(entities)

    @callback
    def _add_new_metrics(keys: set[str]) -> None:
        """Mapa rejestrów urosła w trakcie pracy — dokładamy encje bez restartu."""
        async_add_entities(
            SaConnectMetricSensor(coordinator, key) for key in sorted(keys)
        )

    coordinator.add_new_key_listener(_add_new_metrics)


class SaConnectMetricSensor(SaConnectEntity, SensorEntity):
    """Jedna metryka z `/api/inverter/readings`."""

    def __init__(self, coordinator: SaConnectCoordinator, key: str) -> None:
        super().__init__(coordinator, key)
        spec = describe(key)
        self.entity_id = build_entity_id(coordinator, ENTITY_ID_FORMAT, key)
        self._options = spec.options
        self._attr_native_unit_of_measurement = spec.unit
        self._attr_device_class = spec.device_class
        self._attr_state_class = spec.state_class
        self._attr_entity_registry_enabled_default = not key.startswith(SETTING_PREFIX)
        if spec.diagnostic:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        if spec.options:
            self._attr_options = sorted(set(spec.options.values()))
        if spec.translation_key:
            self._attr_translation_key = spec.translation_key
        else:
            # Klucz spoza katalogu — nazwa z humanizacji, żeby encja była
            # użyteczna zanim ktoś dopisze jej tłumaczenie.
            self._attr_name = spec.name_en

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.is_metric_available(self._key)

    @property
    def native_value(self) -> Any:
        value = self.coordinator.data.values.get(self._key)
        if value is None:
            return None
        if self._options is not None:
            # Enumy idą z bramki SUROWE. Nieznany kod pokazujemy jako liczbę —
            # cisza byłaby gorsza: użytkownik ma zobaczyć, że falownik zgłasza
            # stan, którego jeszcze nie opisaliśmy.
            try:
                return self._options.get(int(value), str(value))
            except (TypeError, ValueError):
                return str(value)
        return value


@dataclass(frozen=True, kw_only=True)
class DiagnosticSpec:
    """Sensor liczony ze stanu bramki, a nie z mapy rejestrów."""

    key: str
    translation_key: str
    value: Callable[[GatewayData], Any]
    unit: str | None = None
    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = None


def _status(data: GatewayData, *path: str) -> Any:
    node: Any = data.status
    for part in path:
        if not isinstance(node, dict):
            return None
        node = node.get(part)
    return node


DIAGNOSTIC_SENSORS: tuple[DiagnosticSpec, ...] = (
    DiagnosticSpec(
        key="last_ok",
        translation_key="last_ok",
        value=lambda d: d.last_ok,
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    DiagnosticSpec(
        key="blocks_ok",
        translation_key="blocks_ok",
        value=lambda d: d.readings.get("blocks_ok"),
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DiagnosticSpec(
        key="blocks_total",
        translation_key="blocks_total",
        value=lambda d: d.readings.get("blocks_total"),
    ),
    DiagnosticSpec(
        key="cycle_ms",
        translation_key="cycle_ms",
        value=lambda d: d.readings.get("cycle_ms"),
        unit=UnitOfTime.MILLISECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DiagnosticSpec(
        key="failed_cycles",
        translation_key="failed_cycles",
        value=lambda d: d.readings.get("failed_cycles"),
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DiagnosticSpec(
        key="last_error",
        translation_key="last_error",
        # Komunikat bramki bywa dłuższy niż limit stanu w HA (255 znaków).
        value=lambda d: (str(d.readings.get("last_error") or "") or None),
    ),
    DiagnosticSpec(
        key="map_version",
        translation_key="map_version",
        value=lambda d: d.readings.get("map_version"),
    ),
    DiagnosticSpec(
        key="metrics",
        translation_key="metrics",
        value=lambda d: d.readings.get("metrics"),
    ),
    DiagnosticSpec(
        key="poll_interval",
        translation_key="poll_interval",
        value=lambda d: _seconds(d.readings.get("poll_interval_ms")),
        unit=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
    ),
    DiagnosticSpec(
        key="rssi",
        translation_key="rssi",
        value=lambda d: _status(d, "rssi"),
        unit=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DiagnosticSpec(
        key="uptime",
        translation_key="uptime",
        value=lambda d: _status(d, "uptime_s"),
        unit=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DiagnosticSpec(
        key="firmware_version",
        translation_key="firmware_version",
        value=lambda d: _status(d, "firmware_version"),
    ),
)


def _seconds(ms: Any) -> float | None:
    try:
        return round(float(ms) / 1000.0, 1)
    except (TypeError, ValueError):
        return None


class SaConnectDiagnosticSensor(SaConnectEntity, SensorEntity):
    """Stan bramki i magistrali — to, co dotąd widać było tylko w jej portalu."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, coordinator: SaConnectCoordinator, spec: DiagnosticSpec
    ) -> None:
        super().__init__(coordinator, spec.key)
        self._spec = spec
        self.entity_id = build_entity_id(coordinator, ENTITY_ID_FORMAT, spec.key)
        self._attr_translation_key = spec.translation_key
        self._attr_native_unit_of_measurement = spec.unit
        self._attr_device_class = spec.device_class
        self._attr_state_class = spec.state_class

    @property
    def native_value(self) -> Any:
        value = self._spec.value(self.coordinator.data)
        if isinstance(value, str) and len(value) > 255:
            return value[:252] + "..."
        if isinstance(value, datetime):
            return value
        return value
