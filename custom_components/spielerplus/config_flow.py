"""Configure separate children/memberships, reusing an existing local login."""

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_NAME

from .const import CONF_URL, DOMAIN
from .config_helpers import (
    normalize_subscription,
    subscription_conflict,
    subscription_identity,
)


def account_sources(hass):
    return {
        entry.entry_id: entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.disabled_by is None
        and all(entry.options.get(key) for key in ("account_email", "account_password"))
    }


async def reuse_account(entry):
    from .account import SpielerPlusAccount

    credentials = {
        key: entry.options[key] for key in ("account_email", "account_password")
    }
    client = SpielerPlusAccount(
        credentials["account_email"], credentials["account_password"]
    )
    try:
        return credentials, await client.async_login()
    finally:
        await client.async_close()


class SpielerPlusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return SpielerPlusOptionsFlow()

    async def async_step_user(self, user_input=None):
        # Continue to accept the original direct form API for existing clients.
        if user_input is not None:
            return await self.async_step_calendar(user_input)
        if not account_sources(self.hass):
            return await self.async_step_calendar()
        return self.async_show_menu(step_id="user", menu_options=["calendar", "family"])

    async def async_step_family(self, user_input=None):
        from .attendance import AccountError

        sources = account_sources(self.hass)
        if not sources:
            return self.async_abort(reason="no_account")
        errors = {}
        source_id = (
            user_input.get("source")
            if user_input
            else next(iter(sources))
            if len(sources) == 1
            else None
        )
        if source_id is not None:
            if source_id not in sources:
                return self.async_abort(reason="no_account")
            try:
                self._family_credentials, self._memberships = await reuse_account(
                    sources[source_id]
                )
                return await self.async_step_family_team()
            except AccountError as exc:
                errors["base"] = exc.code
        return self.async_show_form(
            step_id="family",
            data_schema=vol.Schema(
                {
                    vol.Required("source"): vol.In(
                        {key: entry.title for key, entry in sources.items()}
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_family_team(self, user_input=None):
        from .account import SpielerPlusAccount
        from .attendance import AccountError

        errors = {}
        if user_input is not None:
            member = user_input["membership_id"]
            if member not in self._memberships:
                return self.async_abort(reason="no_memberships")
            self._family_options = {**self._family_credentials, "membership_id": member}
            self._family_name = self._memberships[member].rsplit(" · ", 1)[-1]
            client = SpielerPlusAccount(
                self._family_credentials["account_email"],
                self._family_credentials["account_password"],
                member,
            )
            try:
                self._detected_url = await client.async_calendar_subscription()
            except AccountError as exc:
                errors["base"] = exc.code
            finally:
                await client.async_close()
            if not errors:
                return await self.async_step_calendar()
        return self.async_show_form(
            step_id="family_team",
            data_schema=vol.Schema(
                {
                    vol.Required("membership_id"): vol.In(self._memberships),
                }
            ),
            errors=errors,
        )

    async def async_step_calendar(self, user_input=None):
        options = getattr(self, "_family_options", {})
        detected = getattr(self, "_detected_url", None)
        errors = {}
        if user_input is not None and not user_input.get(CONF_NAME, "").strip():
            errors["base"] = "invalid_name"
            user_input = None
        if user_input is not None:
            try:
                url = normalize_subscription(detected or user_input.get(CONF_URL, ""))
            except ValueError:
                errors["base"] = "invalid_url"
            else:
                member = options.get("membership_id")
                entries = [
                    (entry.data, entry.options)
                    for entry in self._async_current_entries()
                ]
                if subscription_conflict(entries, url, member):
                    return self.async_abort(reason="already_configured")
                await self.async_set_unique_id(subscription_identity(url, member))
                self._abort_if_unique_id_configured()
                data = {CONF_NAME: user_input[CONF_NAME].strip(), CONF_URL: url}
                if options:
                    data["child_name"] = data[CONF_NAME]
                return self.async_create_entry(
                    title=data[CONF_NAME], data=data, options=options
                )
        schema = {
            vol.Required(CONF_NAME, default=getattr(self, "_family_name", "")): vol.All(
                str, vol.Length(min=1, max=100)
            )
        }
        if not detected:
            schema[vol.Required(CONF_URL)] = str
        return self.async_show_form(
            step_id="calendar", data_schema=vol.Schema(schema), errors=errors
        )


class SpielerPlusOptionsFlow(config_entries.OptionsFlow):
    """Credentials never need to be retyped when reusing the same local account."""

    async def async_step_init(self, user_input=None):
        menu = ["account", "disable"]
        if account_sources(self.hass):
            menu.insert(1, "reuse")
        return self.async_show_menu(step_id="init", menu_options=menu)

    async def async_step_reuse(self, user_input=None):
        from .attendance import AccountError

        sources = account_sources(self.hass)
        if not sources:
            return self.async_abort(reason="no_account")
        errors = {}
        source_id = (
            user_input.get("source")
            if user_input
            else next(iter(sources))
            if len(sources) == 1
            else None
        )
        if source_id is not None:
            if source_id not in sources:
                return self.async_abort(reason="no_account")
            try:
                self._credentials, self._memberships = await reuse_account(
                    sources[source_id]
                )
                return await self.async_step_team()
            except AccountError as exc:
                errors["base"] = exc.code
        return self.async_show_form(
            step_id="reuse",
            data_schema=vol.Schema(
                {
                    vol.Required("source"): vol.In(
                        {key: entry.title for key, entry in sources.items()}
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_account(self, user_input=None):
        from homeassistant.helpers import selector
        from .account import SpielerPlusAccount
        from .attendance import AccountError

        errors = {}
        if user_input is not None:
            client = SpielerPlusAccount(
                user_input["email"].strip(), user_input["password"]
            )
            try:
                self._memberships = await client.async_login()
                self._credentials = {
                    "account_email": user_input["email"].strip(),
                    "account_password": user_input["password"],
                }
                return await self.async_step_team()
            except AccountError as exc:
                errors["base"] = exc.code
            finally:
                await client.async_close()
        return self.async_show_form(
            step_id="account",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "email",
                        default=self.config_entry.options.get("account_email", ""),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.EMAIL
                        )
                    ),
                    vol.Required("password"): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_team(self, user_input=None):
        if user_input is not None:
            if user_input["membership_id"] not in self._memberships:
                return self.async_abort(reason="no_memberships")
            return self.async_create_entry(
                title="",
                data={
                    **self._credentials,
                    "membership_id": user_input["membership_id"],
                },
            )
        return self.async_show_form(
            step_id="team",
            data_schema=vol.Schema(
                {vol.Required("membership_id"): vol.In(self._memberships)}
            ),
        )

    async def async_step_disable(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data={})
        return self.async_show_form(step_id="disable", data_schema=vol.Schema({}))
