"""Katalog prezentacji: klucz z bramki → encja Home Assistanta.

Podział odpowiedzialności, na którym stoi ta integracja:

* **bramka** odpowiada za odczyt i przeskalowanie wartości — na zewnątrz
  oddaje wyłącznie `{key, value}`.
* **ta integracja** odpowiada za prezentację — nazwę, jednostkę, ikonę,
  `device_class`, `state_class` i słowniki enumów.

Nazwy, jednostki i ikony trzymają się konwencji przyjętej w Home Assistancie
dla falowników Deye odczytywanych po Modbusie. Dzięki temu dashboard zbudowany
pod inne źródło danych wygląda tak samo po przejściu na bramkę. Nazwy są
angielskie i celowo nie są tłumaczone — takie widzi użytkownik w tej konwencji.

Klucz, który pojawi się w odczytach bramki później, zadziała OD RAZU dzięki
`_heuristic()` — dostanie poprawną jednostkę i klasę, a zabraknie mu tylko
ładnej nazwy. `scripts/check_catalog.py` wypisuje takie klucze, żeby rozjazd
był widoczny, a nie cichy.
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

    name: str
    unit: str | None = None
    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = None
    icon: str | None = None
    # Enumy przychodzą z bramki jako LICZBY — na tekst zamienia je ta mapa.
    options: dict[int, str] | None = None
    # Nastawy (`set_*`) i pola serwisowe lądują w sekcji diagnostycznej.
    diagnostic: bool = False
    # Klucz tłumaczenia; domyślnie równy kluczowi metryki (uzupełnia CATALOG).
    translation_key: str = field(default="")


def _power(name: str, icon: str | None = None) -> MetricDef:
    return MetricDef(name, UnitOfPower.WATT, SensorDeviceClass.POWER, MEASUREMENT, icon)


def _voltage(name: str, icon: str | None = None) -> MetricDef:
    return MetricDef(
        name, UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, MEASUREMENT, icon
    )


def _current(name: str, icon: str | None = None) -> MetricDef:
    return MetricDef(
        name, UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, MEASUREMENT, icon
    )


def _temp(name: str, icon: str | None = None) -> MetricDef:
    return MetricDef(
        name, UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, MEASUREMENT, icon
    )


def _energy(name: str, icon: str | None = None) -> MetricDef:
    """Licznik energii. `total_increasing` obsługuje dobowy reset, dzięki czemu
    Energy Dashboard przyjmuje te encje bez żadnej konfiguracji."""
    return MetricDef(
        name, UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, TOTAL_INCREASING, icon
    )


def _freq(name: str, icon: str | None = None) -> MetricDef:
    return MetricDef(
        name, UnitOfFrequency.HERTZ, SensorDeviceClass.FREQUENCY, MEASUREMENT, icon
    )


def _soc(name: str, icon: str | None = None) -> MetricDef:
    return MetricDef(name, PERCENTAGE, SensorDeviceClass.BATTERY, MEASUREMENT, icon)


# ── Enumy ───────────────────────────────────────────────────────────────────
# `inverter_status` nie jest zwykłą numeracją, tylko maską bitową źródeł
# zasilania — stąd dziury w kluczach i powtarzające się wartości. Teksty są
# stanami encji wprost (bez tłumaczeń), żeby zgadzały się z tym, co pokazują
# inne integracje czytające ten falownik.
DEVICE_RELAY = {
    0x0: "Off",
    0x1: "Inverter",
    0x3: "Inverter",
    0x4: "Grid",
    0x6: "Grid",
    0x5: "Inverter-Grid",
    0x7: "Inverter-Grid",
    0x8: "Generator",
    0x9: "Inverter-Gen",
    0xB: "Inverter-Gen",
    0xC: "Grid-Generator",
    0xE: "Grid-Generator",
    0xD: "Inv-Grid-Gen",
    0xF: "Inv-Grid-Gen",
}

DEVICE_STATE = {
    0: "Standby",
    1: "Self-test",
    2: "Normal",
    3: "Alarm",
    4: "Fault",
}


CATALOG: dict[str, MetricDef] = {
    # ── PV ────────────────────────────────────────────────────────────────────
    "pv1_power": _power("PV1 Power", "mdi:solar-power-variant"),
    "pv2_power": _power("PV2 Power", "mdi:solar-power-variant"),
    "pv3_power": _power("PV3 Power", "mdi:solar-power-variant"),
    "pv4_power": _power("PV4 Power", "mdi:solar-power-variant"),
    "pv1_voltage": _voltage("PV1 Voltage", "mdi:solar-power-variant"),
    "pv1_current": _current("PV1 Current", "mdi:solar-power-variant"),
    "pv2_voltage": _voltage("PV2 Voltage", "mdi:solar-power-variant"),
    "pv2_current": _current("PV2 Current", "mdi:solar-power-variant"),
    "pv3_voltage": _voltage("PV3 Voltage", "mdi:solar-power-variant"),
    "pv3_current": _current("PV3 Current", "mdi:solar-power-variant"),
    "pv4_voltage": _voltage("PV4 Voltage", "mdi:solar-power-variant"),
    "pv4_current": _current("PV4 Current", "mdi:solar-power-variant"),
    # ── Bateria ───────────────────────────────────────────────────────────────
    "battery_temp": _temp("Battery Temperature"),
    "battery_voltage": _voltage("Battery Voltage"),
    "battery_soc": _soc("Battery"),
    "battery2_soc": _soc("Battery 2", "mdi:battery"),
    "battery_power": _power("Battery Power"),
    "battery_current": _current("Battery Current", "mdi:current-dc"),
    "battery_corrected_capacity": MetricDef(
        "Battery Corrected Capacity",
        "Ah",
        None,
        MEASUREMENT,
        "mdi:battery",
    ),
    "battery2_voltage": _voltage("Battery 2 Voltage"),
    "battery2_current": _current("Battery 2 Current", "mdi:current-dc"),
    "battery2_power": _power("Battery 2 Power"),
    "battery2_temperature": _temp("Battery 2 Temperature"),
    "battery_soh": MetricDef(
        "Battery SOH",
        PERCENTAGE,
        None,
        MEASUREMENT,
        "mdi:battery-heart",
    ),
    # ── Sieć i przekładniki ───────────────────────────────────────────────────
    "grid_l1_voltage": _voltage("Grid L1 Voltage", "mdi:transmission-tower"),
    "grid_l2_voltage": _voltage("Grid L2 Voltage", "mdi:transmission-tower"),
    "grid_l3_voltage": _voltage("Grid L3 Voltage", "mdi:transmission-tower"),
    "grid_frequency": _freq("Grid Frequency"),
    "grid_power_factor": MetricDef(
        "Grid Power Factor",
        PERCENTAGE,
        SensorDeviceClass.POWER_FACTOR,
        MEASUREMENT,
        "mdi:transmission-tower",
    ),
    "grid_l1_power": _power("Grid L1 Power", "mdi:transmission-tower"),
    "grid_l2_power": _power("Grid L2 Power", "mdi:transmission-tower"),
    "grid_l3_power": _power("Grid L3 Power", "mdi:transmission-tower"),
    "grid_power": _power("Grid Power", "mdi:transmission-tower"),
    "grid_ct_power_l1": _power("Internal CT1 Power", "mdi:transmission-tower"),
    "grid_ct_power_l2": _power("Internal CT2 Power", "mdi:transmission-tower"),
    "grid_ct_power_l3": _power("Internal CT3 Power", "mdi:transmission-tower"),
    "internal_ct_power": _power("Internal Power", "mdi:transmission-tower"),
    "internal_ct_l1_current": _current(
        "Internal CT1 Current",
        "mdi:transmission-tower",
    ),
    "internal_ct_l2_current": _current(
        "Internal CT2 Current",
        "mdi:transmission-tower",
    ),
    "internal_ct_l3_current": _current(
        "Internal CT3 Current",
        "mdi:transmission-tower",
    ),
    "external_ct_l1_current": _current(
        "External CT1 Current",
        "mdi:transmission-tower",
    ),
    "external_ct_l2_current": _current(
        "External CT2 Current",
        "mdi:transmission-tower",
    ),
    "external_ct_l3_current": _current(
        "External CT3 Current",
        "mdi:transmission-tower",
    ),
    "external_ct_l1_power": _power("External CT1 Power", "mdi:transmission-tower"),
    "external_ct_l2_power": _power("External CT2 Power", "mdi:transmission-tower"),
    "external_ct_l3_power": _power("External CT3 Power", "mdi:transmission-tower"),
    "external_ct_power": _power("External Power", "mdi:transmission-tower"),
    # ── Wyjście falownika ─────────────────────────────────────────────────────
    "inverter_voltage_l1": _voltage("Output L1 Voltage"),
    "inverter_voltage_l2": _voltage("Output L2 Voltage"),
    "inverter_voltage_l3": _voltage("Output L3 Voltage"),
    "inverter_current_l1": _current("Output L1 Current"),
    "inverter_current_l2": _current("Output L2 Current"),
    "inverter_current_l3": _current("Output L3 Current"),
    "output_l1_power": _power("Output L1 Power"),
    "output_l2_power": _power("Output L2 Power"),
    "output_l3_power": _power("Output L3 Power"),
    "inverter_power": _power("Power"),
    "output_frequency": _freq("Output Frequency"),
    "inverter_status": MetricDef(
        "Device Relay",
        None,
        SensorDeviceClass.ENUM,
        None,
        "mdi:directions-fork",
        options=DEVICE_RELAY,
    ),
    # ── Obciążenie ────────────────────────────────────────────────────────────
    "load_ups_l1_power": _power("Load UPS L1 Power", "mdi:home-lightning-bolt"),
    "load_ups_l2_power": _power("Load UPS L2 Power", "mdi:home-lightning-bolt"),
    "load_ups_l3_power": _power("Load UPS L3 Power", "mdi:home-lightning-bolt"),
    "load_ups_power": _power("Load UPS Power", "mdi:home-lightning-bolt"),
    "load_l1_voltage": _voltage("Load L1 Voltage"),
    "load_l2_voltage": _voltage("Load L2 Voltage"),
    "load_l3_voltage": _voltage("Load L3 Voltage"),
    "load_power_l1": _power("Load L1 Power"),
    "load_power_l2": _power("Load L2 Power"),
    "load_power_l3": _power("Load L3 Power"),
    "load_power": _power("Load Power"),
    "load_frequency": _freq("Load Frequency"),
    # ── Temperatury ───────────────────────────────────────────────────────────
    "dc_transformer_temp": _temp("DC Temperature", "mdi:thermometer"),
    "radiator_temp": _temp("Temperature", "mdi:thermometer"),
    # ── Liczniki energii ──────────────────────────────────────────────────────
    "day_battery_charge": _energy("Today Battery Charge", "mdi:battery-plus"),
    "day_battery_discharge": _energy("Today Battery Discharge", "mdi:battery-minus"),
    "total_battery_charge": _energy("Total Battery Charge", "mdi:battery-plus"),
    "total_battery_discharge": _energy("Total Battery Discharge", "mdi:battery-minus"),
    "day_grid_import": _energy("Today Energy Import", "mdi:transmission-tower-export"),
    "day_grid_export": _energy("Today Energy Export", "mdi:transmission-tower-import"),
    "total_energy_bought": _energy(
        "Total Energy Import",
        "mdi:transmission-tower-export",
    ),
    "total_energy_sold": _energy(
        "Total Energy Export",
        "mdi:transmission-tower-import",
    ),
    "day_load_energy": _energy("Today Load Consumption"),
    "total_consumption": _energy("Total Load Consumption"),
    "day_pv_energy": _energy("Today Production", "mdi:solar-power"),
    "total_pv_generation": _energy("Total Production", "mdi:solar-power"),
    "daily_generator_production": _energy("Generator Energy - today"),
    "total_generator_production": _energy("Generator Energy"),
    # ── Stan pracy ────────────────────────────────────────────────────────────
    "running_status": MetricDef(
        "Device State",
        None,
        SensorDeviceClass.ENUM,
        None,
        "mdi:state-machine",
        options=DEVICE_STATE,
    ),
    # ── Nastawy falownika — w M1 tylko do odczytu ─────────────────────────────
    "set_work_mode": MetricDef(
        "Work Mode",
        None,
        None,
        None,
        "mdi:home-lightning-bolt",
        diagnostic=True,
    ),
    "set_export_surplus_power": MetricDef(
        "Export Surplus Power",
        UnitOfPower.WATT,
        SensorDeviceClass.POWER,
        None,
        "mdi:transmission-tower-import",
        diagnostic=True,
    ),
    "set_max_charge_current": MetricDef(
        "Battery Max Charging Current",
        UnitOfElectricCurrent.AMPERE,
        SensorDeviceClass.CURRENT,
        None,
        "mdi:current-dc",
        diagnostic=True,
    ),
    "set_max_discharge_current": MetricDef(
        "Battery Max Discharging Current",
        UnitOfElectricCurrent.AMPERE,
        SensorDeviceClass.CURRENT,
        None,
        "mdi:current-dc",
        diagnostic=True,
    ),
    "set_pv_power": MetricDef(
        "PV Power",
        UnitOfPower.WATT,
        SensorDeviceClass.POWER,
        None,
        "mdi:solar-power-variant",
        diagnostic=True,
    ),
    "set_gen_config": MetricDef(
        "Generator Config Register",
        None,
        None,
        None,
        "mdi:cog",
        diagnostic=True,
    ),
    "set_grid_peak_shaving_power": MetricDef(
        "Grid Peak shaving",
        UnitOfPower.WATT,
        SensorDeviceClass.POWER,
        None,
        "mdi:transmission-tower",
        diagnostic=True,
    ),
    "set_tou_config": MetricDef(
        "Time of Use Register",
        None,
        None,
        None,
        "mdi:cog",
        diagnostic=True,
    ),
    "set_program_time_1": MetricDef(
        "Program 1 Time",
        None,
        None,
        None,
        "mdi:sun-clock",
        diagnostic=True,
    ),
    "set_program_time_2": MetricDef(
        "Program 2 Time",
        None,
        None,
        None,
        "mdi:sun-clock",
        diagnostic=True,
    ),
    "set_program_time_3": MetricDef(
        "Program 3 Time",
        None,
        None,
        None,
        "mdi:sun-clock",
        diagnostic=True,
    ),
    "set_program_time_4": MetricDef(
        "Program 4 Time",
        None,
        None,
        None,
        "mdi:sun-clock",
        diagnostic=True,
    ),
    "set_program_time_5": MetricDef(
        "Program 5 Time",
        None,
        None,
        None,
        "mdi:sun-clock",
        diagnostic=True,
    ),
    "set_program_time_6": MetricDef(
        "Program 6 Time",
        None,
        None,
        None,
        "mdi:sun-clock",
        diagnostic=True,
    ),
    "set_program_power_1": MetricDef(
        "Program 1 Power",
        UnitOfPower.WATT,
        SensorDeviceClass.POWER,
        None,
        "mdi:sun-clock",
        diagnostic=True,
    ),
    "set_program_power_2": MetricDef(
        "Program 2 Power",
        UnitOfPower.WATT,
        SensorDeviceClass.POWER,
        None,
        "mdi:sun-clock",
        diagnostic=True,
    ),
    "set_program_power_3": MetricDef(
        "Program 3 Power",
        UnitOfPower.WATT,
        SensorDeviceClass.POWER,
        None,
        "mdi:sun-clock",
        diagnostic=True,
    ),
    "set_program_power_4": MetricDef(
        "Program 4 Power",
        UnitOfPower.WATT,
        SensorDeviceClass.POWER,
        None,
        "mdi:sun-clock",
        diagnostic=True,
    ),
    "set_program_power_5": MetricDef(
        "Program 5 Power",
        UnitOfPower.WATT,
        SensorDeviceClass.POWER,
        None,
        "mdi:sun-clock",
        diagnostic=True,
    ),
    "set_program_power_6": MetricDef(
        "Program 6 Power",
        UnitOfPower.WATT,
        SensorDeviceClass.POWER,
        None,
        "mdi:sun-clock",
        diagnostic=True,
    ),
    "set_program_soc_1": MetricDef(
        "Program 1 SOC",
        PERCENTAGE,
        None,
        None,
        "mdi:sun-clock",
        diagnostic=True,
    ),
    "set_program_soc_2": MetricDef(
        "Program 2 SOC",
        PERCENTAGE,
        None,
        None,
        "mdi:sun-clock",
        diagnostic=True,
    ),
    "set_program_soc_3": MetricDef(
        "Program 3 SOC",
        PERCENTAGE,
        None,
        None,
        "mdi:sun-clock",
        diagnostic=True,
    ),
    "set_program_soc_4": MetricDef(
        "Program 4 SOC",
        PERCENTAGE,
        None,
        None,
        "mdi:sun-clock",
        diagnostic=True,
    ),
    "set_program_soc_5": MetricDef(
        "Program 5 SOC",
        PERCENTAGE,
        None,
        None,
        "mdi:sun-clock",
        diagnostic=True,
    ),
    "set_program_soc_6": MetricDef(
        "Program 6 SOC",
        PERCENTAGE,
        None,
        None,
        "mdi:sun-clock",
        diagnostic=True,
    ),
    "set_program_charging_1": MetricDef(
        "Program 1 Charging",
        None,
        None,
        None,
        "mdi:sun-clock",
        diagnostic=True,
    ),
    "set_program_charging_2": MetricDef(
        "Program 2 Charging",
        None,
        None,
        None,
        "mdi:sun-clock",
        diagnostic=True,
    ),
    "set_program_charging_3": MetricDef(
        "Program 3 Charging",
        None,
        None,
        None,
        "mdi:sun-clock",
        diagnostic=True,
    ),
    "set_program_charging_4": MetricDef(
        "Program 4 Charging",
        None,
        None,
        None,
        "mdi:sun-clock",
        diagnostic=True,
    ),
    "set_program_charging_5": MetricDef(
        "Program 5 Charging",
        None,
        None,
        None,
        "mdi:sun-clock",
        diagnostic=True,
    ),
    "set_program_charging_6": MetricDef(
        "Program 6 Charging",
        None,
        None,
        None,
        "mdi:sun-clock",
        diagnostic=True,
    ),
}

CATALOG = {key: replace(spec, translation_key=key) for key, spec in CATALOG.items()}


# ── Heurystyka dla kluczy spoza katalogu ────────────────────────────────────
# Kolejność ma znaczenie: prefiksy energii przed sufiksami mocy, bo
# `total_pv_generation` to kWh, a nie W.
_ENERGY_PREFIXES = ("day_", "daily_", "total_")
_SUFFIX_RULES: tuple[
    tuple[str, str | None, SensorDeviceClass | None, SensorStateClass | None], ...
] = (
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
    (
        "_apparent_power",
        UnitOfApparentPower.VOLT_AMPERE,
        SensorDeviceClass.APPARENT_POWER,
        MEASUREMENT,
    ),
)


def humanize(key: str) -> str:
    """`battery2_voltage` → `Battery2 voltage`. Awaryjna nazwa dla nowych kluczy."""
    return key.replace("_", " ").strip().capitalize()


def _heuristic(key: str) -> MetricDef:
    """Opis wyprowadzony z samej nazwy klucza."""
    name = humanize(key)
    base = key.removeprefix("set_")
    diagnostic = key.startswith("set_")

    if base.startswith(_ENERGY_PREFIXES):
        return MetricDef(
            name,
            UnitOfEnergy.KILO_WATT_HOUR,
            SensorDeviceClass.ENERGY,
            TOTAL_INCREASING,
            diagnostic=diagnostic,
        )

    for suffix, unit, device_class, state_class in _SUFFIX_RULES:
        if base.endswith(suffix):
            # Nastawa to wartość zadana, nie przebieg — `state_class` psułby
            # statystyki długoterminowe (średnia z limitu nie znaczy nic).
            return MetricDef(
                name,
                unit,
                device_class,
                None if diagnostic else state_class,
                diagnostic=diagnostic,
            )

    return MetricDef(name, diagnostic=diagnostic)


def describe(key: str) -> MetricDef:
    """Opis metryki: jawny wpis z katalogu, a gdy go nie ma — heurystyka."""
    return CATALOG.get(key) or _heuristic(key)


def is_known(key: str) -> bool:
    return key in CATALOG


# ── Polskie nazwy encji ─────────────────────────────────────────────────────
# Angielskie nazwy w `CATALOG` trzymają się konwencji przyjętej dla tych
# falowników i są wspólne dla wszystkich instalacji; tu leży ich tłumaczenie.
# Klucz bez wpisu dostanie nazwę angielską — to poprawny stan, nie błąd.
NAMES_PL: dict[str, str] = {
    "pv1_power": "Moc PV string 1",
    "pv2_power": "Moc PV string 2",
    "pv3_power": "Moc PV string 3",
    "pv4_power": "Moc PV string 4",
    "pv1_voltage": "Napięcie PV string 1",
    "pv1_current": "Prąd PV string 1",
    "pv2_voltage": "Napięcie PV string 2",
    "pv2_current": "Prąd PV string 2",
    "pv3_voltage": "Napięcie PV string 3",
    "pv3_current": "Prąd PV string 3",
    "pv4_voltage": "Napięcie PV string 4",
    "pv4_current": "Prąd PV string 4",
    "battery_temp": "Temperatura baterii",
    "battery_voltage": "Napięcie baterii",
    "battery_soc": "Naładowanie baterii",
    "battery2_soc": "Naładowanie baterii 2",
    "battery_power": "Moc baterii",
    "battery_current": "Prąd baterii",
    "battery_corrected_capacity": "Pojemność baterii (skorygowana)",
    "battery2_voltage": "Napięcie baterii 2",
    "battery2_current": "Prąd baterii 2",
    "battery2_power": "Moc baterii 2",
    "battery2_temperature": "Temperatura baterii 2",
    "battery_soh": "Kondycja baterii",
    "grid_l1_voltage": "Napięcie sieci L1",
    "grid_l2_voltage": "Napięcie sieci L2",
    "grid_l3_voltage": "Napięcie sieci L3",
    "grid_frequency": "Częstotliwość sieci",
    "grid_power_factor": "Współczynnik mocy",
    "grid_l1_power": "Moc sieci L1",
    "grid_l2_power": "Moc sieci L2",
    "grid_l3_power": "Moc sieci L3",
    "grid_power": "Moc sieci",
    "grid_ct_power_l1": "Moc CT L1",
    "grid_ct_power_l2": "Moc CT L2",
    "grid_ct_power_l3": "Moc CT L3",
    "internal_ct_power": "Moc CT wewnętrznego",
    "internal_ct_l1_current": "Prąd CT wewnętrznego L1",
    "internal_ct_l2_current": "Prąd CT wewnętrznego L2",
    "internal_ct_l3_current": "Prąd CT wewnętrznego L3",
    "external_ct_l1_current": "Prąd CT zewnętrznego L1",
    "external_ct_l2_current": "Prąd CT zewnętrznego L2",
    "external_ct_l3_current": "Prąd CT zewnętrznego L3",
    "external_ct_l1_power": "Moc CT zewnętrznego L1",
    "external_ct_l2_power": "Moc CT zewnętrznego L2",
    "external_ct_l3_power": "Moc CT zewnętrznego L3",
    "external_ct_power": "Moc CT zewnętrznego",
    "inverter_voltage_l1": "Napięcie falownika L1",
    "inverter_voltage_l2": "Napięcie falownika L2",
    "inverter_voltage_l3": "Napięcie falownika L3",
    "inverter_current_l1": "Prąd falownika L1",
    "inverter_current_l2": "Prąd falownika L2",
    "inverter_current_l3": "Prąd falownika L3",
    "output_l1_power": "Moc wyjściowa L1",
    "output_l2_power": "Moc wyjściowa L2",
    "output_l3_power": "Moc wyjściowa L3",
    "inverter_power": "Moc falownika",
    "output_frequency": "Częstotliwość wyjściowa",
    "inverter_status": "Stan falownika",
    "load_ups_l1_power": "Moc UPS L1",
    "load_ups_l2_power": "Moc UPS L2",
    "load_ups_l3_power": "Moc UPS L3",
    "load_ups_power": "Moc UPS",
    "load_l1_voltage": "Napięcie obciążenia L1",
    "load_l2_voltage": "Napięcie obciążenia L2",
    "load_l3_voltage": "Napięcie obciążenia L3",
    "load_power_l1": "Moc obciążenia L1",
    "load_power_l2": "Moc obciążenia L2",
    "load_power_l3": "Moc obciążenia L3",
    "load_power": "Moc obciążenia",
    "load_frequency": "Częstotliwość obciążenia",
    "dc_transformer_temp": "Temperatura transformatora DC",
    "radiator_temp": "Temperatura radiatora",
    "day_battery_charge": "Dzienne ładowanie baterii",
    "day_battery_discharge": "Dzienne rozładowanie baterii",
    "total_battery_charge": "Całkowite ładowanie baterii",
    "total_battery_discharge": "Całkowite rozładowanie baterii",
    "day_grid_import": "Dzienny pobór z sieci",
    "day_grid_export": "Dzienne oddanie do sieci",
    "total_energy_bought": "Całkowity pobór z sieci",
    "total_energy_sold": "Całkowite oddanie do sieci",
    "day_load_energy": "Dzienne zużycie",
    "total_consumption": "Całkowite zużycie",
    "day_pv_energy": "Dzienna produkcja PV",
    "total_pv_generation": "Całkowita produkcja PV",
    "daily_generator_production": "Dzienna produkcja generatora",
    "total_generator_production": "Całkowita produkcja generatora",
    "running_status": "Stan pracy",
    "set_work_mode": "Tryb pracy",
    "set_export_surplus_power": "Limit oddawania nadwyżki",
    "set_max_charge_current": "Maks. prąd ładowania",
    "set_max_discharge_current": "Maks. prąd rozładowania",
    "set_pv_power": "Zadeklarowana moc PV",
    "set_gen_config": "Rejestr gen_config",
    "set_grid_peak_shaving_power": "Limit mocy z sieci (peak shaving)",
    "set_tou_config": "Rejestr tou_config",
    "set_program_time_1": "Harmonogram 1: godzina",
    "set_program_time_2": "Harmonogram 2: godzina",
    "set_program_time_3": "Harmonogram 3: godzina",
    "set_program_time_4": "Harmonogram 4: godzina",
    "set_program_time_5": "Harmonogram 5: godzina",
    "set_program_time_6": "Harmonogram 6: godzina",
    "set_program_power_1": "Harmonogram 1: moc",
    "set_program_power_2": "Harmonogram 2: moc",
    "set_program_power_3": "Harmonogram 3: moc",
    "set_program_power_4": "Harmonogram 4: moc",
    "set_program_power_5": "Harmonogram 5: moc",
    "set_program_power_6": "Harmonogram 6: moc",
    "set_program_soc_1": "Harmonogram 1: SOC",
    "set_program_soc_2": "Harmonogram 2: SOC",
    "set_program_soc_3": "Harmonogram 3: SOC",
    "set_program_soc_4": "Harmonogram 4: SOC",
    "set_program_soc_5": "Harmonogram 5: SOC",
    "set_program_soc_6": "Harmonogram 6: SOC",
    "set_program_charging_1": "Harmonogram 1: ładowanie z sieci",
    "set_program_charging_2": "Harmonogram 2: ładowanie z sieci",
    "set_program_charging_3": "Harmonogram 3: ładowanie z sieci",
    "set_program_charging_4": "Harmonogram 4: ładowanie z sieci",
    "set_program_charging_5": "Harmonogram 5: ładowanie z sieci",
    "set_program_charging_6": "Harmonogram 6: ładowanie z sieci",
}


# Stany enumów po polsku. Kluczem jest WARTOŚĆ stanu encji, bo tym posługuje
# się mechanizm tłumaczeń Home Assistanta.
STATE_LABELS_PL: dict[str, dict[str, str]] = {
    "inverter_status": {
        "Off": "Wyłączony",
        "Inverter": "Falownik",
        "Grid": "Sieć",
        "Inverter-Grid": "Falownik + sieć",
        "Generator": "Generator",
        "Inverter-Gen": "Falownik + generator",
        "Grid-Generator": "Sieć + generator",
        "Inv-Grid-Gen": "Falownik + sieć + generator",
    },
    "running_status": {
        "Standby": "Czuwanie",
        "Self-test": "Autotest",
        "Normal": "Praca normalna",
        "Alarm": "Alarm",
        "Fault": "Awaria",
    },
}
