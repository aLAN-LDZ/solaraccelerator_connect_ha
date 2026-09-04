"""Katalog nastaw STEROWALNYCH: klucz odczytu → rejestr Modbus + sposób zapisu.

`catalog.py` opisuje, jak POKAZAĆ to, co bramka przeczytała. Ten plik opisuje,
jak ZAPISAĆ to, co użytkownik ustawił — i jest świadomie osobny, bo odczyt ma
inne ryzyko niż zapis.

## Podział odpowiedzialności

Bramka pozostaje głupia: dostaje gotową parę `(rejestr, wartość)` i wykonuje
surowy zapis Modbus, dokładnie tak jak przy komendach z serwera. Cała wiedza
o tym, co znaczy który rejestr, jaki ma zakres i których bitów NIE WOLNO ruszyć,
siedzi tutaj.

## Pola bitowe

Dwie nastawy nie mają własnego rejestru, tylko kilka bitów we wspólnym:

* `program_charging_N` (172-177) — bit0 Grid, bit1 Generator, **bit5 Sell**,
* `grid_peak_shaving` — bit4 rejestru 178, obok bit0 (odcięcie eksportu
  mikrofalowników), bit2 (peak shaving generatora) i bit6 (generator zawsze
  on-grid).

Zapis całej wartości zgasiłby sąsiednie bity. Odczyt z realnego falownika dał
`178 = 11052`, czyli siedem zapalonych bitów — wpisanie samego `16` skasowałoby
je wszystkie. Dlatego każdy cel z `bit_mask` idzie przez read-modify-write:
`(bieżąca AND NOT maska) OR (nowa AND maska)`, a gdy bieżącej wartości nie ma
(bramka nie zdążyła przeczytać), zapis jest ODMAWIANY zamiast zgadywany.

## Zakresy

Granice mocy i prądów odpowiadają Deye SUN-12K-SG04LP3 — jedynemu modelowi
z potwierdzoną na sprzęcie mapą rejestrów. Na mocniejszej jednostce będą zbyt
ciasne; wtedy trzeba je rozszerzyć razem z mapą, a nie osobno.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from homeassistant.components.number import NumberDeviceClass, NumberMode
from homeassistant.const import PERCENTAGE, UnitOfElectricCurrent, UnitOfPower

# Liczba slotów harmonogramu (Time of Use) w falownikach Deye.
NUM_PROGRAMS = 6

# Bazowe adresy serii TOU. Sloty leżą w ciągłych blokach, więc adres slotu N to
# `base + (N - 1)`. Potwierdzone odczytem z urządzenia (slave 1, 2026-08-16).
REG_PROGRAM_TIME = 148      # 148-153, u16 = HHMM (600 = 06:00)
REG_PROGRAM_POWER = 154     # 154-159, u16 = W
REG_PROGRAM_SOC = 166       # 166-171, u16 = %
REG_PROGRAM_CHARGING = 172  # 172-177, pole bitowe

REG_WORK_MODE = 142
REG_EXPORT_SURPLUS_POWER = 143
REG_MAX_CHARGE_CURRENT = 108
REG_MAX_DISCHARGE_CURRENT = 109
REG_GEN_CONFIG = 178        # pole bitowe (bit4 = peak shaving sieci)
REG_GRID_PEAK_SHAVING_POWER = 191
REG_PV_POWER = 340

# Maski w polach bitowych.
MASK_CHARGING = 0b0000_0011   # bit0 Grid + bit1 Generator; bit5 (Sell) zostaje
MASK_GRID_PEAK_SHAVING = 0b0001_0000

MAX_POWER_W = 12000
MAX_CURRENT_A = 240

WORK_MODE_OPTIONS = {
    0: "Selling First",
    1: "Zero Export To Load",
    2: "Zero Export To CT",
}

CHARGING_OPTIONS = {
    0: "Disabled",
    1: "Grid",
    2: "Generator",
    3: "Both",
}


@dataclass(frozen=True, kw_only=True)
class ControlDef:
    """Jedna nastawa, którą użytkownik może zmienić ręcznie."""

    # Klucz odczytu z bramki — jest też `translation_key`, dzięki czemu encja
    # sterująca i jej odczytowy bliźniak z `catalog.py` mają tę samą nazwę.
    key: str
    register: int
    platform: str  # "number" | "select" | "switch" | "time"
    icon: str | None = None

    # Skąd wziąć bieżącą wartość, gdy leży w innym kluczu niż `key`
    # (przełącznik peak shavingu czyta wspólny rejestr `set_gen_config`).
    source_key: str | None = None
    # Maska bitowa → zapis przez read-modify-write.
    bit_mask: int | None = None

    # number
    min_value: float = 0
    max_value: float = 100
    step: float = 1
    unit: str | None = None
    device_class: NumberDeviceClass | None = None
    mode: NumberMode = NumberMode.BOX

    # select
    options: dict[int, str] = field(default_factory=dict)

    @property
    def read_key(self) -> str:
        """Klucz w `/api/inverter/readings`, z którego czytamy stan."""
        return self.source_key or self.key


def _power(key: str, register: int, icon: str) -> ControlDef:
    return ControlDef(
        key=key,
        register=register,
        platform="number",
        icon=icon,
        min_value=0,
        max_value=MAX_POWER_W,
        step=10,
        unit=UnitOfPower.WATT,
        device_class=NumberDeviceClass.POWER,
    )


def _current(key: str, register: int) -> ControlDef:
    return ControlDef(
        key=key,
        register=register,
        platform="number",
        icon="mdi:current-dc",
        min_value=0,
        max_value=MAX_CURRENT_A,
        step=1,
        unit=UnitOfElectricCurrent.AMPERE,
        device_class=NumberDeviceClass.CURRENT,
    )


def _build_controls() -> list[ControlDef]:
    controls: list[ControlDef] = [
        ControlDef(
            key="set_work_mode",
            register=REG_WORK_MODE,
            platform="select",
            icon="mdi:home-lightning-bolt",
            options=WORK_MODE_OPTIONS,
        ),
        _current("set_max_charge_current", REG_MAX_CHARGE_CURRENT),
        _current("set_max_discharge_current", REG_MAX_DISCHARGE_CURRENT),
        # Limit mocy PV. Zero znaczy „bez limitu" — a że firmware falownika
        # czyta wartości poniżej ~400 W właśnie jako zero, ustawienie 100 W nie
        # zdławi produkcji, tylko ją odblokuje. Zakres zostaje pełny, bo to
        # zachowanie samego falownika, nie nasza reguła.
        _power("set_pv_power", REG_PV_POWER, "mdi:solar-power-variant"),
        _power(
            "set_export_surplus_power",
            REG_EXPORT_SURPLUS_POWER,
            "mdi:transmission-tower-import",
        ),
        _power(
            "set_grid_peak_shaving_power",
            REG_GRID_PEAK_SHAVING_POWER,
            "mdi:transmission-tower",
        ),
        ControlDef(
            key="grid_peak_shaving",
            register=REG_GEN_CONFIG,
            platform="switch",
            icon="mdi:transmission-tower",
            source_key="set_gen_config",
            bit_mask=MASK_GRID_PEAK_SHAVING,
        ),
    ]

    for n in range(1, NUM_PROGRAMS + 1):
        i = n - 1
        controls += [
            ControlDef(
                key=f"set_program_time_{n}",
                register=REG_PROGRAM_TIME + i,
                platform="time",
                icon="mdi:clock-outline",
            ),
            ControlDef(
                key=f"set_program_power_{n}",
                register=REG_PROGRAM_POWER + i,
                platform="number",
                icon="mdi:battery-charging",
                min_value=0,
                max_value=MAX_POWER_W,
                step=10,
                unit=UnitOfPower.WATT,
                device_class=NumberDeviceClass.POWER,
            ),
            ControlDef(
                key=f"set_program_soc_{n}",
                register=REG_PROGRAM_SOC + i,
                platform="number",
                icon="mdi:battery-70",
                min_value=0,
                max_value=100,
                step=1,
                unit=PERCENTAGE,
                mode=NumberMode.SLIDER,
            ),
            ControlDef(
                key=f"set_program_charging_{n}",
                register=REG_PROGRAM_CHARGING + i,
                platform="select",
                icon="mdi:transmission-tower-export",
                bit_mask=MASK_CHARGING,
                options=CHARGING_OPTIONS,
            ),
        ]

    return controls


CONTROLS: list[ControlDef] = _build_controls()


def controls_for(platform: str) -> list[ControlDef]:
    return [c for c in CONTROLS if c.platform == platform]


def apply_bit_mask(current: int, value: int, mask: int) -> int:
    """Read-modify-write pojedynczego pola bitowego."""
    return ((current & ~mask) | (value & mask)) & 0xFFFF


# Nazwy encji STERUJĄCYCH. Klucze pokrywające się z `catalog.NAMES_PL` biorą
# nazwę stamtąd (encja sterująca i odczytowa opisują tę samą nastawę), więc
# tutaj zostaje wyłącznie to, czego katalog odczytu nie zna: przełącznik peak
# shavingu, który w odczycie jest tylko bitem w `set_gen_config`.
CONTROL_NAMES: dict[str, tuple[str, str]] = {
    "grid_peak_shaving": ("Peak shaving z sieci", "Grid Peak Shaving"),
}
