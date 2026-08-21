"""Stałe integracji SolarAccelerator Connect.

Integracja czyta bramkę SA Connect wprost z sieci lokalnej — bez chmury, bez
klucza API. Bramka odpytuje falownik po Modbus RTU i trzyma świeży snapshot
w RAM; my odpytujemy ją w TYM SAMYM tempie, które ustawiono w jej portalu.
"""

DOMAIN = "solaraccelerator_connect"

# === Klucze w entry.data ===
CONF_PREFIX = "prefix"          # przedrostek entity_id, np. "deye"

# Użytkownik portalu jest stały — hasło ustawia kreator bramki.
GATEWAY_USERNAME = "admin"

# === Endpointy bramki ===
API_STATUS = "/api/status"
API_READINGS = "/api/inverter/readings"
API_OTA_CHECK = "/api/ota/check"

# === Czasy ===
# Interwał odczytów podaje bramka (`poll_interval_ms`). Ten jest używany tylko
# zanim przyjdzie pierwsza odpowiedź oraz gdy pole nie dotrze (stare firmware).
DEFAULT_POLL_INTERVAL = 5.0
# Dolna granica ochronna — gdyby bramka podała bzdurę, nie zajeżdżamy jej.
MIN_POLL_INTERVAL = 0.5
# Stan bramki (wersja firmware, RSSI, uptime, mapa rejestrów) zmienia się wolno.
STATUS_INTERVAL = 60.0
REQUEST_TIMEOUT = 5.0

# Ile kolejnych odpowiedzi bez danego klucza czekamy, zanim encja pójdzie
# w `unavailable`. Bramka POMIJA metryki z nieudanych bloków Modbus, więc
# pojedyncza dziura jest normalna i nie powinna rwać wykresu.
MISSING_TOLERANCE = 3

# Prefiks nastaw falownika (nie pomiarów) w odpowiedzi `/api/inverter/readings`.
SETTING_PREFIX = "set_"

# Domyślny przedrostek encji, gdy bramka nie zna producenta falownika.
FALLBACK_PREFIX = "inverter"
