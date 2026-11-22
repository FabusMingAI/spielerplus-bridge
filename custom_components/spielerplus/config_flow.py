"""Configure a private SpielerPlus calendar from Home Assistant UI."""

from urllib.parse import urlparse

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_NAME

from .const import CONF_URL, DOMAIN


class SpielerPlusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return SpielerPlusOptionsFlow()

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            url = user_input[CONF_URL].strip()
            if url.startswith("webcal://"):
                url = "https://" + url[len("webcal://") :]
            parsed = urlparse(url)
            if (
                parsed.scheme != "https"
                or parsed.netloc != "www.spielerplus.de"
                or parsed.path != "/events/ics"
                or not parsed.query
                or parsed.username
                or parsed.password
                or parsed.fragment
            ):
                errors["base"] = "invalid_url"
            else:
                await self.async_set_unique_id(url)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data={CONF_NAME: user_input[CONF_NAME], CONF_URL: url},
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME): str,
                    vol.Required(CONF_URL): str,
                }
            ),
            errors=errors,
        )


class SpielerPlusOptionsFlow(config_entries.OptionsFlow):
    """Optional account credentials are entered only into the local HA UI."""

    async def async_step_init(self, user_input=None):
        return self.async_show_menu(step_id="init", menu_options=["account", "disable"])

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
                {
                    vol.Required("membership_id"): vol.In(self._memberships),
                }
            ),
        )

    async def async_step_disable(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data={})
        return self.async_show_form(step_id="disable", data_schema=vol.Schema({}))
