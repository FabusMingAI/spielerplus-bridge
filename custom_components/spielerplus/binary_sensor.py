"""Connection diagnostic visible during fetch failures."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from .const import DOMAIN
from .entity import SpielerPlusEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(
        [SpielerPlusConnection(hass.data[DOMAIN][entry.entry_id], entry)]
    )


class SpielerPlusConnection(SpielerPlusEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "connection"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_connection"

    @property
    def available(self):
        return True

    @property
    def is_on(self):
        return self.coordinator.last_update_success

    @property
    def extra_state_attributes(self):
        return {"last_error": self.coordinator.last_error}
