"""Connection diagnostic visible during fetch failures."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from .const import DOMAIN
from .entity import SpielerPlusEntity


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [SpielerPlusConnection(coordinator, entry)]
    if coordinator.account_client is not None:
        entities.append(SpielerPlusAccountConnection(coordinator, entry))
    async_add_entities(entities)


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


class SpielerPlusAccountConnection(SpielerPlusConnection):
    _attr_translation_key = "account_connection"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_account_connection"

    @property
    def is_on(self):
        return (
            self.coordinator.account_last_success is not None
            and self.coordinator.account_error is None
        )

    @property
    def extra_state_attributes(self):
        return {"last_error": self.coordinator.account_error}
