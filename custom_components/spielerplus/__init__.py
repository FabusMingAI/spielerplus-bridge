"""SpielerPlus custom integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from datetime import timedelta

from .const import DOMAIN
from .coordinator import SpielerPlusCoordinator

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
