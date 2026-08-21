"""Kreator: autowykrycie → hasło → prefiks encji."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import slugify

from .api import GatewayApi, GatewayAuthError, GatewayError, GatewayNotReady
from .const import CONF_PREFIX, DOMAIN, FALLBACK_PREFIX

if TYPE_CHECKING:
    # Import wyłącznie dla typów: ścieżka tej klasy zmieniała się między
    # wydaniami HA (`components.zeroconf` → `helpers.service_info.zeroconf`),
    # a w czasie działania obiekt i tak podaje rdzeń.
    from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

_LOGGER = logging.getLogger(__name__)


class SaConnectConfigFlow(ConfigFlow, domain=DOMAIN):
    """Trzy kroki, z których dwa zwykle przelatują bez pytania."""

    VERSION = 1

    def __init__(self) -> None:
        self._host: str = ""
        self._password: str | None = None
        self._status: dict[str, Any] = {}

    # ── Krok 1: adres ───────────────────────────────────────────────────────

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            self._host = user_input[CONF_HOST].strip()
            self._password = user_input.get(CONF_PASSWORD) or None
            result = await self._async_probe(errors)
            if result is not None:
                return result

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=self._host): str,
                    vol.Optional(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Kandydat z `_http._tcp`.

        W tej usłudze ogłasza się pół sieci, więc dopiero `/api/status`
        z polem `firmware_version` rozstrzyga, że to bramka. Filtr nazwy
        `solaraccelerator*` z manifestu odsiewa większość ruchu wcześniej.
        """
        self._host = discovery_info.host
        self._async_abort_entries_match({CONF_HOST: self._host})
        # Kafelek „Wykryto" rysuje się ZANIM poznamy falownik: `/api/status`
        # jest za hasłem portalu, więc przed autoryzacją bramka nie zdradza
        # nawet modelu. Do czasu udanego odpytania pokazujemy to, co daje samo
        # rozgłoszenie mDNS — nazwę hosta i adres. Bez tego HA nie ma czego
        # wstawić w `flow_title` i wypisuje surową domenę integracji.
        self._set_title(discovery_info.hostname)

        errors: dict[str, str] = {}
        result = await self._async_probe(errors)
        if result is not None:
            return result
        if "auth" in errors.values() or errors.get("base") == "invalid_auth":
            return await self.async_step_password()
        return self.async_abort(reason="cannot_connect")

    # ── Krok 2: hasło portalu ───────────────────────────────────────────────

    async def async_step_password(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            self._password = user_input[CONF_PASSWORD]
            result = await self._async_probe(errors)
            if result is not None:
                return result

        return self.async_show_form(
            step_id="password",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
            description_placeholders={"host": self._host},
        )

    # ── Krok 3: prefiks encji ───────────────────────────────────────────

    async def async_step_prefix(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            prefix = slugify(user_input.get(CONF_PREFIX, ""))
            return self.async_create_entry(
                title=self._title(),
                data={
                    CONF_HOST: self._host,
                    CONF_PASSWORD: self._password,
                    CONF_PREFIX: prefix,
                },
            )

        return self.async_show_form(
            step_id="prefix",
            data_schema=vol.Schema(
                {vol.Optional(CONF_PREFIX, default=self._default_prefix()): str}
            ),
            description_placeholders={
                "example": f"sensor.{self._default_prefix()}_pv1_power"
            },
        )

    # ── Reauth ──────────────────────────────────────────────────────────────

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        self._host = entry_data[CONF_HOST]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            self._password = user_input[CONF_PASSWORD]
            try:
                await self._api().async_probe()
            except GatewayAuthError:
                errors["base"] = "invalid_auth"
            except GatewayError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates={CONF_PASSWORD: self._password},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
            description_placeholders={"host": self._host},
        )

    # ── Wspólne ─────────────────────────────────────────────────────────────

    def _api(self) -> GatewayApi:
        return GatewayApi(
            async_get_clientsession(self.hass), self._host, self._password
        )

    async def _async_probe(self, errors: dict[str, str]) -> ConfigFlowResult | None:
        """Sprawdza kandydata i — gdy się uda — prowadzi do kroku prefiksu.

        Zwraca `None`, gdy trzeba jeszcze raz pokazać formularz; `errors` jest
        wtedy wypełnione.
        """
        try:
            self._status = await self._api().async_probe()
        except GatewayAuthError:
            errors["base"] = "invalid_auth"
            return None
        except GatewayNotReady:
            errors["base"] = "setup_incomplete"
            return None
        except GatewayError as err:
            _LOGGER.debug("Bramka %s nie odpowiedziała: %s", self._host, err)
            errors["base"] = "cannot_connect"
            return None

        # MAC jest jedynym stabilnym identyfikatorem bramki: IP przyznaje DHCP,
        # hostname zmienia użytkownik. Starsze firmware go nie zwraca — wtedy
        # zostaje hostname i taka instalacja rozjedzie się po zmianie nazwy.
        unique = str(self._status.get("mac") or self._status.get("hostname") or self._host)
        await self.async_set_unique_id(unique.lower())
        self._abort_if_unique_id_configured(updates={CONF_HOST: self._host})

        # Po autoryzacji znamy już falownik — kafelek wykrycia dostaje jego
        # nazwę w miejsce hosta z mDNS. Odświeżamy po KAŻDYM udanym odpytaniu,
        # bo przy bramce z hasłem sukces przychodzi dopiero z kroku hasła.
        self._set_title()
        return await self.async_step_prefix()

    def _title(self) -> str:
        name = str(self._status.get("inverter_name") or "").strip()
        return name or "Solar Accelerator Connect"

    def _set_title(self, fallback_hostname: str = "") -> None:
        """Wypełnia `flow_title` — wzorzec „nazwa (adres)", jak w innych
        integracjach wykrywanych po sieci."""
        name = str(self._status.get("inverter_name") or "").strip()
        if not name and fallback_hostname:
            # "solaraccelerator-connect.local." → "solaraccelerator-connect"
            name = fallback_hostname.rstrip(".").removesuffix(".local")
        self.context["title_placeholders"] = {
            "name": name or "Solar Accelerator Connect",
            "host": self._host,
        }

    def _default_prefix(self) -> str:
        """Producent falownika, np. `deye`."""
        manufacturer = str(self._status.get("inverter_manufacturer") or "").strip()
        return slugify(manufacturer) if manufacturer else FALLBACK_PREFIX
