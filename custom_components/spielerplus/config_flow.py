"""Configure a private SpielerPlus calendar from Home Assistant UI."""

from urllib.parse import urlparse

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME

from .const import CONF_URL, DOMAIN


class SpielerPlusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

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
