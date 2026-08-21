"""Klient HTTP bramki SA Connect.

Transport jest celowo prosty: HTTP bez TLS w obrębie LAN (bramka nie ma i nie
może mieć ważnego certyfikatu dla adresu IP ani `.local`), HTTP Basic z
użytkownikiem `admin`, timeouty liczone w sekundach.

Bramka wymaga autoryzacji tylko wtedy, gdy użytkownik ustawił hasło portalu
w jej kreatorze. Dlatego `password=None` jest poprawnym stanem konfiguracji,
a nie brakiem ustawienia.
"""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

from .const import (
    API_OTA_CHECK,
    API_READINGS,
    API_STATUS,
    GATEWAY_USERNAME,
    REQUEST_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)


class GatewayError(Exception):
    """Bramka nieosiągalna albo odpowiedziała czymś, czego nie umiemy użyć."""


class GatewayAuthError(GatewayError):
    """Bramka zażądała hasła portalu albo odrzuciła podane."""


class GatewayNotReady(GatewayError):
    """Bramka żyje, ale siedzi w kreatorze (tryb AP) — nie ma z czego czytać."""


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

    async def _request(self, method: str, path: str) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            async with self._session.request(
                method,
                url,
                auth=self._auth,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            ) as resp:
                if resp.status == 401:
                    raise GatewayAuthError(f"{path}: bramka wymaga hasła portalu")
                if resp.status >= 400:
                    raise GatewayError(f"{path}: HTTP {resp.status}")
                # Bramka deklaruje application/json, ale przy pustych
                # odpowiedziach (np. /api/ota/check) nie ma czego parsować.
                if resp.content_length == 0:
                    return {}
                return await resp.json(content_type=None)
        except aiohttp.ClientError as err:
            raise GatewayError(f"{path}: {err}") from err
        except TimeoutError as err:
            raise GatewayError(f"{path}: przekroczono {REQUEST_TIMEOUT} s") from err

    async def async_get_status(self) -> dict[str, Any]:
        """Tożsamość bramki i stan magistrali.

        Rzuca `GatewayNotReady`, gdy bramka nie jest w trybie STA — w kreatorze
        nie ma jeszcze mapy rejestrów ani połączenia z falownikiem.
        """
        data = await self._request("GET", API_STATUS)
        if data.get("mode") != "STA":
            raise GatewayNotReady(
                f"bramka w trybie {data.get('mode', '?')} — dokończ kreator"
            )
        return data

    async def async_get_readings(self) -> dict[str, Any]:
        return await self._request("GET", API_READINGS)

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
