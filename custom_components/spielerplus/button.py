"""Manual calendar refresh."""

from homeassistant.components.button import ButtonEntity
from .const import DOMAIN
from .entity import SpielerPlusEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([SpielerPlusRefresh(hass.data[DOMAIN][entry.entry_id], entry)])


class SpielerPlusRefresh(SpielerPlusEntity, ButtonEntity):
    _attr_icon = "mdi:refresh"
    _attr_translation_key = "refresh"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_refresh"

    @property
    def available(self):
        return True

    async def async_press(self):
        await self.coordinator.async_request_refresh()
