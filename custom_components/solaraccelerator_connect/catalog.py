"""Katalog prezentacji: klucz z bramki → encja Home Assistanta.

Podział odpowiedzialności, na którym stoi ta integracja:

* **bramka** odpowiada za odczyt i przeskalowanie wartości — na zewnątrz
  oddaje wyłącznie `{key, value}`.
* **ta integracja** odpowiada za prezentację — nazwę, jednostkę,
  `device_class`, `state_class` i słowniki enumów.

Dzięki temu nie ma dwóch źródeł tej samej prawdy. Klucz, który pojawi się
w odczytach bramki później, zadziała tutaj OD RAZU dzięki `_heuristic()` —
dostanie poprawną jednostkę i klasę, a jedyne czego mu zabraknie, to ładna
nazwa. `scripts/check_catalog.py` wypisuje takie klucze, żeby rozjazd był
widoczny, a nie cichy.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    PERCENTAGE,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
)

MEASUREMENT = SensorStateClass.MEASUREMENT
TOTAL_INCREASING = SensorStateClass.TOTAL_INCREASING


@dataclass(frozen=True)
class MetricDef:
    """Opis jednej metryki w kategoriach Home Assistanta."""

    name_pl: str
    name_en: str
    unit: str | None = None
    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = None
    # Enumy przychodzą z bramki jako LICZBY — na tekst zamienia je ta mapa.
    options: dict[int, str] | None = None
    # Nastawy (`set_*`) i pola serwisowe lądują w sekcji diagnostycznej.
    diagnostic: bool = False
    # Klucz tłumaczenia; domyślnie równy kluczowi metryki (uzupełnia CATALOG).
    translation_key: str = field(default="")


def _power(pl: str, en: str) -> MetricDef:
    return MetricDef(pl, en, UnitOfPower.WATT, SensorDeviceClass.POWER, MEASUREMENT)


def _voltage(pl: str, en: str) -> MetricDef:
    return MetricDef(
        pl, en, UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, MEASUREMENT
    )


def _current(pl: str, en: str) -> MetricDef:
    return MetricDef(
        pl, en, UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, MEASUREMENT
    )


def _temp(pl: str, en: str) -> MetricDef:
    return MetricDef(
        pl, en, UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, MEASUREMENT
    )


def _energy(pl: str, en: str) -> MetricDef:
    return MetricDef(
        pl, en, UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, TOTAL_INCREASING
    )


def _percent(pl: str, en: str, device_class: SensorDeviceClass | None) -> MetricDef:
    return MetricDef(pl, en, PERCENTAGE, device_class, MEASUREMENT)


def _freq(pl: str, en: str) -> MetricDef:
    return MetricDef(
        pl, en, UnitOfFrequency.HERTZ, SensorDeviceClass.FREQUENCY, MEASUREMENT
    )


# ── Enumy (Deye SG0*LP3) ────────────────────────────────────────────────────
# `inverter_status` nie jest zwykłą numeracją, tylko maską bitową źródeł
# zasilania — stąd dziury w kluczach i powtarzające się wartości.
INVERTER_STATUS = {
    0x0: "off",
    0x1: "inverter",
    0x3: "inverter",
    0x4: "grid",
    0x6: "grid",
    0x5: "inverter_grid",
    0x7: "inverter_grid",
    0x8: "generator",
    0x9: "inverter_generator",
    0xB: "inverter_generator",
    0xC: "grid_generator",
    0xE: "grid_generator",
    0xD: "inverter_grid_generator",
    0xF: "inverter_grid_generator",
}

RUNNING_STATUS = {
    0: "standby",
    1: "selfcheck",
    2: "normal",
    3: "alarm",
    4: "fault",
}

WORK_MODE = {
    0: "selling_first",
    1: "zero_export_to_load",
    2: "zero_export_to_ct",
}


CATALOG: dict[str, MetricDef] = {
    # ── PV ──────────────────────────────────────────────────────────────────
    "pv1_power": _power("Moc PV string 1", "PV1 power"),
    "pv2_power": _power("Moc PV string 2", "PV2 power"),
    "pv3_power": _power("Moc PV string 3", "PV3 power"),
    "pv4_power": _power("Moc PV string 4", "PV4 power"),
    "pv1_voltage": _voltage("Napięcie PV string 1", "PV1 voltage"),
    "pv2_voltage": _voltage("Napięcie PV string 2", "PV2 voltage"),
    "pv3_voltage": _voltage("Napięcie PV string 3", "PV3 voltage"),
    "pv4_voltage": _voltage("Napięcie PV string 4", "PV4 voltage"),
    "pv1_current": _current("Prąd PV string 1", "PV1 current"),
    "pv2_current": _current("Prąd PV string 2", "PV2 current"),
    "pv3_current": _current("Prąd PV string 3", "PV3 current"),
    "pv4_current": _current("Prąd PV string 4", "PV4 current"),
    "day_pv_energy": _energy("Dzienna produkcja PV", "Daily PV energy"),
    "total_pv_generation": _energy("Całkowita produkcja PV", "Total PV generation"),
    # ── Bateria ─────────────────────────────────────────────────────────────
    # Znak dodatni = ładowanie, ujemny = rozładowanie. `device_class: battery`
    # rezerwujemy dla SOC, bo w HA oznacza procent naładowania.
    "battery_power": _power("Moc baterii", "Battery power"),
    "battery_voltage": _voltage("Napięcie baterii", "Battery voltage"),
    "battery_current": _current("Prąd baterii", "Battery current"),
    "battery_temp": _temp("Temperatura baterii", "Battery temperature"),
    "battery_soc": _percent("Naładowanie baterii", "Battery SOC", SensorDeviceClass.BATTERY),
    "battery_soh": _percent("Kondycja baterii", "Battery SOH", None),
    "battery_corrected_capacity": MetricDef(
        "Pojemność baterii (skorygowana)", "Battery corrected capacity", "Ah", None, MEASUREMENT
    ),
    "battery2_soc": _percent("Naładowanie baterii 2", "Battery 2 SOC", SensorDeviceClass.BATTERY),
    "battery2_voltage": _voltage("Napięcie baterii 2", "Battery 2 voltage"),
    "battery2_current": _current("Prąd baterii 2", "Battery 2 current"),
    "battery2_power": _power("Moc baterii 2", "Battery 2 power"),
    "battery2_temperature": _temp("Temperatura baterii 2", "Battery 2 temperature"),
    "day_battery_charge": _energy("Dzienne ładowanie baterii", "Daily battery charge"),
    "day_battery_discharge": _energy("Dzienne rozładowanie baterii", "Daily battery discharge"),
    "total_battery_charge": _energy("Całkowite ładowanie baterii", "Total battery charge"),
    "total_battery_discharge": _energy("Całkowite rozładowanie baterii", "Total battery discharge"),
    # ── Sieć ────────────────────────────────────────────────────────────────
    # Znak dodatni = pobór z sieci, ujemny = oddawanie.
    "grid_power": _power("Moc sieci", "Grid power"),
    "grid_l1_power": _power("Moc sieci L1", "Grid L1 power"),
    "grid_l2_power": _power("Moc sieci L2", "Grid L2 power"),
    "grid_l3_power": _power("Moc sieci L3", "Grid L3 power"),
    "grid_l1_voltage": _voltage("Napięcie sieci L1", "Grid L1 voltage"),
    "grid_l2_voltage": _voltage("Napięcie sieci L2", "Grid L2 voltage"),
    "grid_l3_voltage": _voltage("Napięcie sieci L3", "Grid L3 voltage"),
    "grid_frequency": _freq("Częstotliwość sieci", "Grid frequency"),
    "grid_power_factor": MetricDef(
        "Współczynnik mocy", "Power factor", None, SensorDeviceClass.POWER_FACTOR, MEASUREMENT
    ),
    "grid_ct_power_l1": _power("Moc CT L1", "CT L1 power"),
    "grid_ct_power_l2": _power("Moc CT L2", "CT L2 power"),
    "grid_ct_power_l3": _power("Moc CT L3", "CT L3 power"),
    "day_grid_import": _energy("Dzienny pobór z sieci", "Daily grid import"),
    "day_grid_export": _energy("Dzienne oddanie do sieci", "Daily grid export"),
    "total_energy_bought": _energy("Całkowity pobór z sieci", "Total energy bought"),
    "total_energy_sold": _energy("Całkowite oddanie do sieci", "Total energy sold"),
    # ── Przekładniki ────────────────────────────────────────────────────────
    "internal_ct_power": _power("Moc CT wewnętrznego", "Internal CT power"),
    "internal_ct_l1_current": _current("Prąd CT wewnętrznego L1", "Internal CT L1 current"),
    "internal_ct_l2_current": _current("Prąd CT wewnętrznego L2", "Internal CT L2 current"),
    "internal_ct_l3_current": _current("Prąd CT wewnętrznego L3", "Internal CT L3 current"),
    "external_ct_power": _power("Moc CT zewnętrznego", "External CT power"),
    "external_ct_l1_power": _power("Moc CT zewnętrznego L1", "External CT L1 power"),
    "external_ct_l2_power": _power("Moc CT zewnętrznego L2", "External CT L2 power"),
    "external_ct_l3_power": _power("Moc CT zewnętrznego L3", "External CT L3 power"),
    "external_ct_l1_current": _current("Prąd CT zewnętrznego L1", "External CT L1 current"),
    "external_ct_l2_current": _current("Prąd CT zewnętrznego L2", "External CT L2 current"),
    "external_ct_l3_current": _current("Prąd CT zewnętrznego L3", "External CT L3 current"),
    # ── Falownik / wyjście ──────────────────────────────────────────────────
    "inverter_power": _power("Moc falownika", "Inverter power"),
    "inverter_voltage_l1": _voltage("Napięcie falownika L1", "Inverter L1 voltage"),
    "inverter_voltage_l2": _voltage("Napięcie falownika L2", "Inverter L2 voltage"),
    "inverter_voltage_l3": _voltage("Napięcie falownika L3", "Inverter L3 voltage"),
    "inverter_current_l1": _current("Prąd falownika L1", "Inverter L1 current"),
    "inverter_current_l2": _current("Prąd falownika L2", "Inverter L2 current"),
    "inverter_current_l3": _current("Prąd falownika L3", "Inverter L3 current"),
    "output_l1_power": _power("Moc wyjściowa L1", "Output L1 power"),
    "output_l2_power": _power("Moc wyjściowa L2", "Output L2 power"),
    "output_l3_power": _power("Moc wyjściowa L3", "Output L3 power"),
    "output_frequency": _freq("Częstotliwość wyjściowa", "Output frequency"),
    "inverter_status": MetricDef(
        "Stan falownika", "Inverter status",
        None, SensorDeviceClass.ENUM, None, options=INVERTER_STATUS,
    ),
    "running_status": MetricDef(
        "Stan pracy", "Running status",
        None, SensorDeviceClass.ENUM, None, options=RUNNING_STATUS,
    ),
    # ── Obciążenie ──────────────────────────────────────────────────────────
    "load_power": _power("Moc obciążenia", "Load power"),
    "load_power_l1": _power("Moc obciążenia L1", "Load L1 power"),
    "load_power_l2": _power("Moc obciążenia L2", "Load L2 power"),
    "load_power_l3": _power("Moc obciążenia L3", "Load L3 power"),
    "load_l1_voltage": _voltage("Napięcie obciążenia L1", "Load L1 voltage"),
    "load_l2_voltage": _voltage("Napięcie obciążenia L2", "Load L2 voltage"),
    "load_l3_voltage": _voltage("Napięcie obciążenia L3", "Load L3 voltage"),
    "load_frequency": _freq("Częstotliwość obciążenia", "Load frequency"),
    "load_ups_power": _power("Moc UPS", "UPS power"),
    "load_ups_l1_power": _power("Moc UPS L1", "UPS L1 power"),
    "load_ups_l2_power": _power("Moc UPS L2", "UPS L2 power"),
    "load_ups_l3_power": _power("Moc UPS L3", "UPS L3 power"),
    "day_load_energy": _energy("Dzienne zużycie", "Daily load energy"),
    "total_consumption": _energy("Całkowite zużycie", "Total consumption"),
    # ── Generator ───────────────────────────────────────────────────────────
    "daily_generator_production": _energy("Dzienna produkcja generatora", "Daily generator production"),
    "total_generator_production": _energy("Całkowita produkcja generatora", "Total generator production"),
    # ── Temperatury ─────────────────────────────────────────────────────────
    "radiator_temp": _temp("Temperatura radiatora", "Radiator temperature"),
    "dc_transformer_temp": _temp("Temperatura transformatora DC", "DC transformer temperature"),
    # ── Nastawy (`set_*`) — w M1 tylko do odczytu, diagnostycznie ───────────
    "set_work_mode": MetricDef(
        "Tryb pracy", "Work mode",
        None, SensorDeviceClass.ENUM, None, options=WORK_MODE, diagnostic=True,
    ),
    "set_max_charge_current": MetricDef(
        "Maks. prąd ładowania", "Max charge current",
        UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, None, diagnostic=True,
    ),
    "set_max_discharge_current": MetricDef(
        "Maks. prąd rozładowania", "Max discharge current",
        UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, None, diagnostic=True,
    ),
    "set_export_surplus_power": MetricDef(
        "Limit oddawania nadwyżki", "Export surplus power limit",
        UnitOfPower.WATT, SensorDeviceClass.POWER, None, diagnostic=True,
    ),
    "set_grid_peak_shaving_power": MetricDef(
        "Limit mocy z sieci (peak shaving)", "Grid peak shaving power",
        UnitOfPower.WATT, SensorDeviceClass.POWER, None, diagnostic=True,
    ),
    "set_pv_power": MetricDef(
        "Zadeklarowana moc PV", "Declared PV power",
        UnitOfPower.WATT, SensorDeviceClass.POWER, None, diagnostic=True,
    ),
}

# Sloty harmonogramu 1–6 — sześć razy to samo, więc generujemy zamiast
# przepisywać. `set_program_time_N` to surowe HHMM (1500 = 15:00), nie minuty.
for _slot in range(1, 7):
    CATALOG[f"set_program_time_{_slot}"] = MetricDef(
        f"Harmonogram {_slot}: godzina", f"Program {_slot} time", diagnostic=True
    )
    CATALOG[f"set_program_power_{_slot}"] = MetricDef(
        f"Harmonogram {_slot}: moc", f"Program {_slot} power",
        UnitOfPower.WATT, SensorDeviceClass.POWER, None, diagnostic=True,
    )
    CATALOG[f"set_program_soc_{_slot}"] = MetricDef(
        f"Harmonogram {_slot}: SOC", f"Program {_slot} SOC",
        PERCENTAGE, None, None, diagnostic=True,
    )
    CATALOG[f"set_program_charging_{_slot}"] = MetricDef(
        f"Harmonogram {_slot}: ładowanie z sieci", f"Program {_slot} grid charging",
        diagnostic=True,
    )

# Nastawy bez rozpoznanej semantyki — surowe rejestry konfiguracyjne. Pokazujemy
# je jako liczby, bo ukrycie ich znaczyłoby, że bramka czyta coś, czego nie widać.
for _raw in ("set_gen_config", "set_tou_config"):
    CATALOG[_raw] = MetricDef(
        f"Rejestr {_raw.removeprefix('set_')}", f"Register {_raw.removeprefix('set_')}",
        diagnostic=True,
    )

CATALOG = {key: replace(spec, translation_key=key) for key, spec in CATALOG.items()}


# ── Heurystyka dla kluczy spoza katalogu ────────────────────────────────────
# Kolejność ma znaczenie: prefiksy energii przed sufiksami mocy, bo
# `total_pv_generation` to kWh, a nie W.
_ENERGY_PREFIXES = ("day_", "daily_", "total_")
_SUFFIX_RULES: tuple[tuple[str, str | None, SensorDeviceClass | None, SensorStateClass | None], ...] = (
    ("_power_factor", None, SensorDeviceClass.POWER_FACTOR, MEASUREMENT),
    ("_frequency", UnitOfFrequency.HERTZ, SensorDeviceClass.FREQUENCY, MEASUREMENT),
    ("_voltage", UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, MEASUREMENT),
    ("_current", UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, MEASUREMENT),
    ("_temperature", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, MEASUREMENT),
    ("_temp", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, MEASUREMENT),
    ("_soc", PERCENTAGE, SensorDeviceClass.BATTERY, MEASUREMENT),
    ("_soh", PERCENTAGE, None, MEASUREMENT),
    ("_energy", UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, TOTAL_INCREASING),
    ("_power", UnitOfPower.WATT, SensorDeviceClass.POWER, MEASUREMENT),
    ("_apparent_power", UnitOfApparentPower.VOLT_AMPERE, SensorDeviceClass.APPARENT_POWER, MEASUREMENT),
)


def humanize(key: str) -> str:
    """`battery2_voltage` → `Battery2 voltage`. Awaryjna nazwa dla nowych kluczy."""
    return key.replace("_", " ").strip().capitalize()


def _heuristic(key: str) -> MetricDef:
    """Opis wyprowadzony z samej nazwy klucza.

    Dzięki temu metryka, która pojawi się w odczytach bramki, daje w HA
    działającą encję z poprawną jednostką jeszcze zanim ktokolwiek wyda nową
    wersję integracji.
    """
    name = humanize(key)
    base = key.removeprefix("set_")
    diagnostic = key.startswith("set_")

    if base.startswith(_ENERGY_PREFIXES):
        return MetricDef(
            name, name, UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY,
            TOTAL_INCREASING, diagnostic=diagnostic,
        )

    for suffix, unit, device_class, state_class in _SUFFIX_RULES:
        if base.endswith(suffix):
            # Nastawa to wartość zadana, nie przebieg — `state_class` psułby
            # statystyki długoterminowe (średnia z limitu nie znaczy nic).
            return MetricDef(
                name, name, unit, device_class,
                None if diagnostic else state_class, diagnostic=diagnostic,
            )

    return MetricDef(name, name, diagnostic=diagnostic)


def describe(key: str) -> MetricDef:
    """Opis metryki: jawny wpis z katalogu, a gdy go nie ma — heurystyka."""
    return CATALOG.get(key) or _heuristic(key)


def is_known(key: str) -> bool:
    return key in CATALOG


# ── Etykiety stanów enumów (pl, en) ─────────────────────────────────────────
# Osobno od samego mapowania kodów, bo tłumaczenia idą do plików `translations/`
# generowanych przez `scripts/gen_translations.py`. Katalog zostaje jedynym
# źródłem prawdy — pliki JSON są artefaktem.
OPTION_LABELS: dict[str, dict[str, tuple[str, str]]] = {
    "inverter_status": {
        "off": ("Wyłączony", "Off"),
        "inverter": ("Falownik", "Inverter"),
        "grid": ("Sieć", "Grid"),
        "inverter_grid": ("Falownik + sieć", "Inverter-Grid"),
        "generator": ("Generator", "Generator"),
        "inverter_generator": ("Falownik + generator", "Inverter-Generator"),
        "grid_generator": ("Sieć + generator", "Grid-Generator"),
        "inverter_grid_generator": ("Falownik + sieć + generator", "Inverter-Grid-Generator"),
    },
    "running_status": {
        "standby": ("Czuwanie", "Standby"),
        "selfcheck": ("Autotest", "Self-check"),
        "normal": ("Praca normalna", "Normal"),
        "alarm": ("Alarm", "Alarm"),
        "fault": ("Awaria", "Fault"),
    },
    "set_work_mode": {
        "selling_first": ("Sprzedaż nadwyżek", "Selling first"),
        "zero_export_to_load": ("Zero eksportu (odbiory)", "Zero export to load"),
        "zero_export_to_ct": ("Zero eksportu (CT)", "Zero export to CT"),
    },
}
