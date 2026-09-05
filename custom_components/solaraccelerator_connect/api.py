"""Klient HTTP bramki SA Connect.

Transport jest celowo prosty: HTTP bez TLS w obrębie LAN (bramka nie ma i nie
może mieć ważnego certyfikatu dla adresu IP ani `.local`), HTTP Basic z
użytkownikiem `admin`, timeouty liczone w sekundach.

Bramka wymaga autoryzacji tylko wtedy, gdy użytkownik ustawił hasło portalu
w jej kreatorze. Dlatego `password=None` jest poprawnym stanem konfiguracji,
a nie brakiem ustawienia.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from .const import (
    API_MODBUS_WRITE,
    API_OTA_CHECK,
    API_READINGS,
    API_STATUS,
    GATEWAY_USERNAME,
    REQUEST_RETRIES,
    REQUEST_TIMEOUT,
    RETRY_BACKOFF,
    WRITE_POLL_INTERVAL,
    WRITE_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)


class GatewayError(Exception):
    """Bramka nieosiągalna albo odpowiedziała czymś, czego nie umiemy użyć."""


class GatewayAuthError(GatewayError):
    """Bramka zażądała hasła portalu albo odrzuciła podane."""


class GatewayTransportError(GatewayError):
    """Zapytanie nie doszło albo nie wróciło — bez winy po stronie treści.

    Zerwane połączenie, timeout, 503 „brak pamięci na odpowiedź". Wspólne dla
    nich jest to, że POWTÓRZENIE ma sens: stan bramki się nie zmienił, po
    prostu ta jedna wymiana pakietów się nie udała.
    """


class GatewayNotReady(GatewayError):
    """Bramka żyje, ale siedzi w kreatorze (tryb AP) — nie ma z czego czytać."""


class GatewayWriteError(GatewayError):
    """Zapis nie wszedł: magistrala milczy albo falownik cofnął wartość."""


class GatewayApi:
    """Cienka warstwa nad `/api/*` bramki."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        password: str | None = None,
    ) -> None:
        self._session = session
        self._host = host
        self._password = password
        # Bramka obsługuje JEDEN zapis naraz (odpowiada 409 na kolejny) —
        # a Home Assistant potrafi wysłać kilka nastaw w jednej sekundzie,
        # choćby ze skryptu. Kolejkujemy je tutaj, zamiast oddawać
        # użytkownikowi błąd za coś, co jest zwykłym wyścigiem.
        self._write_lock = asyncio.Lock()

    @property
    def host(self) -> str:
        return self._host

    @property
    def base_url(self) -> str:
        return f"http://{self._host}"

    def set_password(self, password: str | None) -> None:
        """Po reauth — hasło zmienia się bez przebudowy klienta."""
        self._password = password

    @property
    def _auth(self) -> aiohttp.BasicAuth | None:
        if self._password is None:
            return None
        return aiohttp.BasicAuth(GATEWAY_USERNAME, self._password)

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        retries: int = 0,
    ) -> dict[str, Any]:
        """Wykonuje zapytanie, ponawiając je po zerwaniu połączenia.

        `retries` podajemy tylko dla odczytów. Zapis rejestru jest operacją
        jednorazową: gdy odpowiedź przepadnie po drodze, nie wiemy, czy nastawa
        weszła — powtórzenie w ciemno byłoby drugim zapisem, nie ponowieniem.
        """
        attempt = 0
        while True:
            try:
                return await self._attempt(method, path, params)
            except GatewayTransportError as err:
                if attempt >= retries:
                    raise
                attempt += 1
                _LOGGER.debug("%s: %s — ponawiam (%d/%d)", path, err, attempt, retries)
                await asyncio.sleep(RETRY_BACKOFF)

    async def _attempt(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            async with self._session.request(
                method,
                url,
                params=params,
                auth=self._auth,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            ) as resp:
                if resp.status == 401:
                    raise GatewayAuthError(f"{path}: bramka wymaga hasła portalu")
                if resp.status == 503:
                    # Bramka odmawia, gdy nie ma ciągłego bloku pamięci na
                    # odpowiedź (~5 KB JSON-a z odczytami). To stan chwilowy
                    # — sama prosi w treści, żeby spróbować ponownie.
                    raise GatewayTransportError(
                        f"{path}: bramka chwilowo bez pamięci na odpowiedź"
                    )
                if resp.status >= 400:
                    # Bramka odrzuca żądania tekstem, nie JSON-em — powód
                    # („kreator niedokonczony", „poprzedni zapis jeszcze trwa")
                    # jest dla użytkownika ważniejszy niż sam numer statusu.
                    detail = (await resp.text()).strip()
                    raise GatewayError(
                        f"{path}: HTTP {resp.status}{f' — {detail}' if detail else ''}"
                    )
                # Bramka deklaruje application/json, ale przy pustych
                # odpowiedziach (np. /api/ota/check) nie ma czego parsować.
                if resp.content_length == 0:
                    return {}
                return await resp.json(content_type=None)
        except aiohttp.ClientError as err:
            raise GatewayTransportError(f"{path}: {err}") from err
        except TimeoutError as err:
            raise GatewayTransportError(
                f"{path}: przekroczono {REQUEST_TIMEOUT} s"
            ) from err
        except ValueError as err:
            # Ucięte ciało odpowiedzi — bramka buduje JSON w arenie i przy
            # skrajnym braku pamięci potrafi wysłać go niepełnego. Powtórzenie
            # zwykle trafia już na zdrową chwilę.
            raise GatewayTransportError(f"{path}: odpowiedź nie jest JSON-em") from err

    async def async_get_status(self) -> dict[str, Any]:
        """Tożsamość bramki i stan magistrali.

        Rzuca `GatewayNotReady`, gdy bramka nie jest w trybie STA — w kreatorze
        nie ma jeszcze mapy rejestrów ani połączenia z falownikiem.
        """
        data = await self._request("GET", API_STATUS, retries=REQUEST_RETRIES)
        if data.get("mode") != "STA":
            raise GatewayNotReady(
                f"bramka w trybie {data.get('mode', '?')} — dokończ kreator"
            )
        return data

    async def async_get_readings(self) -> dict[str, Any]:
        return await self._request("GET", API_READINGS, retries=REQUEST_RETRIES)

    async def async_write_register(self, register: int, value: int, fc: int = 16) -> int:
        """Zapisuje jeden rejestr i CZEKA na potwierdzenie odczytem.

        Bramka wykonuje zapis w swoim tasku Modbus: dwie próby, a po nich
        weryfikacja odczytem — bo Deye potrafi potwierdzić zapis i po chwili
        cofnąć nastawę. Czekamy na ten werdykt, zamiast raportować sukces
        w chwili przyjęcia zlecenia: encja, która mówi „ustawione", gdy nastawa
        nie weszła, jest gorsza niż encja, która chwilę myśli.

        Zwraca wartość faktycznie odczytaną z rejestru.
        """
        async with self._write_lock:
            await self._request(
                "POST",
                API_MODBUS_WRITE,
                {"reg": str(register), "value": str(value), "fc": str(fc)},
            )

            deadline = asyncio.get_running_loop().time() + WRITE_TIMEOUT
            while True:
                await asyncio.sleep(WRITE_POLL_INTERVAL)
                # Sam odczyt werdyktu jest niegroźny do powtórzenia — a jego
                # zgubienie zamieniłoby udany zapis w błąd na ekranie.
                status = await self._request(
                    "GET", API_MODBUS_WRITE, retries=REQUEST_RETRIES
                )
                state = status.get("state")
                if state == "done":
                    read_back = status.get("read_back")
                    return int(read_back) if read_back is not None else value
                if state == "error":
                    raise GatewayWriteError(
                        str(status.get("error") or f"zapis rejestru {register} nieudany")
                    )
                if asyncio.get_running_loop().time() > deadline:
                    raise GatewayWriteError(
                        f"zapis rejestru {register}: brak odpowiedzi bramki "
                        f"w {WRITE_TIMEOUT:.0f} s"
                    )

    async def async_ota_check(self) -> None:
        await self._request("POST", API_OTA_CHECK)

    async def async_probe(self) -> dict[str, Any]:
        """Czy pod tym adresem faktycznie siedzi bramka SA Connect.

        Używane przez config flow: samo HTTP 200 nie wystarcza, bo w `_http._tcp`
        ogłasza się pół sieci. Rozstrzyga obecność `firmware_version`.
        """
        data = await self._request("GET", API_STATUS)
        if "firmware_version" not in data:
            raise GatewayError("odpowiedź bez firmware_version — to nie bramka")
        return data


def readings_to_values(payload: dict[str, Any]) -> dict[str, Any]:
    """`items: [{key, value}]` → `{key: value}`.

    Bramka podaje wyłącznie klucz i wartość — bez nazwy, jednostki i grupy.
    Całą prezentację trzyma ta integracja (`catalog.py`).
    """
    values: dict[str, Any] = {}
    for item in payload.get("items") or ():
        key = item.get("key")
        if key:
            values[key] = item.get("value")
    return values
