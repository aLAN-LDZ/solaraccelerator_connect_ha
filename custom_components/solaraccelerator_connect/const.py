"""Stałe integracji Solar Accelerator Connect.

Integracja czyta bramkę SA Connect wprost z sieci lokalnej — bez chmury, bez
klucza API. Bramka odpytuje falownik po Modbus RTU i trzyma świeży snapshot
w RAM; my odpytujemy ją w TYM SAMYM tempie, które ustawiono w jej portalu.
"""

DOMAIN = "solaraccelerator_connect"

# === Klucze w entry.data ===
CONF_PREFIX = "prefix"          # prefiks entity_id, np. "deye"

# Użytkownik portalu jest stały — hasło ustawia kreator bramki.
GATEWAY_USERNAME = "admin"

# === Endpointy bramki ===
API_STATUS = "/api/status"
API_READINGS = "/api/inverter/readings"
API_OTA_CHECK = "/api/ota/check"
# Zapis pojedynczego rejestru — dwuetapowy jak odczyt diagnostyczny: POST zleca,
# GET odbiera wynik. Transakcja Modbus z weryfikacją trwa dłużej, niż wolno
# blokować callback serwera bramki. Firmware ≥ 0.1.14.
API_MODBUS_WRITE = "/api/modbus/write"

# === Czasy ===
# Interwał odczytów podaje bramka (`poll_interval_ms`). Ten jest używany tylko
# zanim przyjdzie pierwsza odpowiedź oraz gdy pole nie dotrze (stare firmware).
DEFAULT_POLL_INTERVAL = 5.0
# Dolna granica ochronna — gdyby bramka podała bzdurę, nie zajeżdżamy jej.
MIN_POLL_INTERVAL = 0.5
# Stan bramki (wersja firmware, RSSI, uptime, mapa rejestrów) zmienia się wolno.
STATUS_INTERVAL = 60.0
REQUEST_TIMEOUT = 5.0

# === Odporność na chwilowe zerwania ===
# Bramka to ESP32 na Wi-Fi, a nie serwer w szafie: pojedyncze zapytanie potrafi
# przepaść kilka razy na godzinę (zerwane połączenie keep-alive, retransmisja,
# chwila bez pamięci na odpowiedź). Nie znaczy to, że danych nie ma — one wciąż
# leżą w RAM-ie bramki i przyjdą przy następnym odpytaniu za kilka sekund.
#
# Ile razy ponawiamy JEDNO zapytanie w obrębie cyklu, zanim uznamy je za
# nieudane. Dotyczy wyłącznie odczytów (GET) — zapisu nie wolno powtarzać
# w ciemno, bo nie wiemy, czy pierwszy nie wszedł.
REQUEST_RETRIES = 1
RETRY_BACKOFF = 0.3

# Ile kolejnych nieudanych cykli tolerujemy, zanim WSZYSTKIE encje pójdą
# w `unavailable`. Bez tego jedno zgubione zapytanie gasiło całe urządzenie
# na jeden cykl — w historii encji zostawał ząb „Niedostępny", a automatyzacje
# na `state` dostawały fałszywy alarm.
UPDATE_FAILURE_TOLERANCE = 3

# Ile kolejnych odpowiedzi bez danego klucza czekamy, zanim encja pójdzie
# w `unavailable`. Bramka POMIJA metryki z nieudanych bloków Modbus, więc
# pojedyncza dziura jest normalna i nie powinna rwać wykresu.
MISSING_TOLERANCE = 3

# Prefiks nastaw falownika (nie pomiarów) w odpowiedzi `/api/inverter/readings`.
SETTING_PREFIX = "set_"

# Domyślny prefiks encji, gdy bramka nie zna producenta falownika.
FALLBACK_PREFIX = "inverter"

# === Zapis nastaw ===
# Firmware, od którego bramka ma `/api/modbus/write`. Na starszej encje
# sterujące powstaną, ale zapis zwróci błąd — i tak jest uczciwiej niż ukryć
# połowę integracji przed użytkownikiem, który po prostu nie wgrał aktualizacji.
MIN_WRITE_FIRMWARE = "0.1.14"
# Zapis to do 2 prób po 2 s, przerwa 400 ms i weryfikacja odczytem po 500 ms.
# W najgorszym razie ~6,5 s — z zapasem na zajętą magistralę.
WRITE_TIMEOUT = 12.0
WRITE_POLL_INTERVAL = 0.4
