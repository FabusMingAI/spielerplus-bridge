"""SpielerPlus custom integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from datetime import timedelta
import logging
import voluptuous as vol

from .const import DOMAIN
from .coordinator import SpielerPlusCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    from .dashboard import async_rebuild_dashboard
    from homeassistant.exceptions import HomeAssistantError

    async def rebuild(call):
        try:
            await async_rebuild_dashboard(hass)
        except (OSError, ValueError):
            raise HomeAssistantError(
                "Family dashboard could not be rebuilt; an existing unowned file is preserved."
            ) from None

    if not hass.services.has_service(DOMAIN, "rebuild_dashboard"):
        hass.services.async_register(
            DOMAIN, "rebuild_dashboard", rebuild, schema=vol.Schema({})
        )
    return True


PLATFORMS = ["calendar", "sensor", "binary_sensor", "button"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = SpielerPlusCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Refresh derived states every minute, without another HTTP request.
    @callback
    def async_tick(now):
        coordinator.async_update_listeners()

    entry.async_on_unload(
        async_track_time_interval(hass, async_tick, timedelta(minutes=1))
    )
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    from .dashboard import async_rebuild_dashboard

    try:
        await async_rebuild_dashboard(hass, only_if_managed=True)
    except (OSError, ValueError):
        _LOGGER.warning("Managed family dashboard could not be updated")
    return True


async def async_reload_entry(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator = hass.data[DOMAIN].pop(entry.entry_id, None)
        if coordinator is not None and coordinator.account_client is not None:
            await coordinator.account_client.async_close()
        return True
    return False
