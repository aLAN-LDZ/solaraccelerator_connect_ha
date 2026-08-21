# SolarAccelerator Connect — integracja Home Assistant

Czyta dane z falownika **wprost z bramki SA Connect w Twojej sieci lokalnej**.
Bez chmury, bez klucza API, bez pośredników.

To jest odpowiednik tego, co pokazuje aplikacja iOS w trybie lokalnym: bramka
odpytuje falownik po Modbus RTU i trzyma świeży snapshot w RAM, a Home Assistant
czyta go w tym samym tempie.

## Jak to działa

Bramka SA Connect siedzi w Twojej sieci i sama rozmawia z falownikiem przez
Modbus RTU. Ta integracja odpytuje ją po HTTP i zamienia odczyty na encje
Home Assistanta. Cały ruch zostaje w LAN-ie — integracja nie łączy się z niczym
poza bramką.

Jeśli używasz też integracji `solaraccelerator` (ceny energii, plan, rozliczenie
zysku), obie mogą działać obok siebie — nie wchodzą sobie w drogę.

## Wymagania

* Bramka SA Connect z firmware **0.1.11 lub nowszym**, po zakończonym kreatorze
  (tryb STA, nie punkt dostępowy).
* Home Assistant w tej samej sieci lokalnej co bramka.
* Hasło portalu bramki, jeśli zostało ustawione w kreatorze (użytkownik: `admin`).

## Instalacja

**HACS:** dodaj to repozytorium jako custom repository → zainstaluj → zrestartuj HA.

**Ręcznie:** skopiuj `custom_components/solaraccelerator_connect` do katalogu
`custom_components` w konfiguracji HA i zrestartuj.

## Konfiguracja

Bramka zwykle zgłasza się sama (mDNS) — powiadomienie o wykryciu pojawi się
w **Ustawienia → Urządzenia i usługi**. Jeśli nie, dodaj integrację ręcznie
i podaj adres IP.

Kreator ma trzy kroki:

1. **Adres** — z autowykrycia albo wpisany ręcznie.
2. **Hasło portalu** — pomijane, gdy bramka go nie wymaga.
3. **Przedrostek encji** — domyślnie producent falownika, np. `deye`.

Przedrostek daje encje w postaci `sensor.deye_pv1_power` — **to ta sama
konwencja, której używa integracja Solarman**. Przy przesiadce wystarczy usunąć
Solarmana i podać ten sam przedrostek, żeby dashboardy i automatyzacje działały
dalej bez przepisywania.

> Przedrostek ustala się przy pierwszym uruchomieniu i potem trzyma go rejestr
> encji — późniejsza zmiana wymagałaby przenazwania encji ręcznie.

## Interwał odpytywania

**Nie ma go w opcjach integracji i to jest celowe.** Ustawia się go raz,
w portalu bramki (*Ustawienia Modbus → Odpytywanie falownika*), a Home Assistant
sam się do niego dostraja. Pytanie bramki częściej niż ona pyta falownik zwraca
w kółko ten sam snapshot; rzadziej — gubi odczyty.

Wartość poniżej długości cyklu odczytu (widocznej w portalu jako czas cyklu)
oznacza magistralę pracującą bez przerwy. Portal o tym ostrzega, ale nie blokuje.

## Encje

* **Pomiary** — wszystko, co bramka czyta z mapy rejestrów: PV, bateria, sieć,
  wyjście, obciążenie, przekładniki, temperatury, liczniki. Nazwy, jednostki
  i klasy urządzeń pochodzą z katalogu w tej integracji; metryka, która dojdzie
  w bramce później, pojawi się w HA od razu — z jednostką rozpoznaną po nazwie
  i angielską nazwą do czasu dopisania tłumaczenia.
* **Liczniki energii** (`day_*`, `total_*`) mają `state_class: total_increasing`,
  więc **Energy Dashboard widzi je bez żadnej konfiguracji**.
* **Stany** — `Falownik odpowiada` i `Odczyt niekompletny` (część bloków Modbus
  nie przeszła; dane są, ale niepełne).
* **Diagnostyka** — czas cyklu, bloki OK/wszystkie, nieudane cykle, ostatni błąd
  magistrali, wersja mapy rejestrów, RSSI, czas pracy i wersja firmware bramki.
  Dotąd te liczby widać było wyłącznie w portalu bramki.
* **Nastawy** (`set_*`) — domyślnie wyłączone, jako sensory diagnostyczne.
  Sterowanie nimi przyjdzie w kolejnym etapie.

Metryka, której bramka nie odczytała, **nie jest zerowana** — encja idzie
w `unavailable` dopiero po trzech kolejnych odpytaniach bez niej. Brak wartości
znaczy „nie wiem", nigdy „zero".

## Czego jeszcze nie ma

* **Sterowanie falownikiem.** Na razie integracja tylko czyta. Zapis nastaw
  z Home Assistanta jest następnym krokiem.
* **Historia.** Bramka trzyma tylko bieżący snapshot — wykresy buduje recorder
  Home Assistanta od momentu instalacji.
