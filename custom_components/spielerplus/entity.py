"""Shared device metadata for subscription entities."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.const import CONF_NAME
from .const import DOMAIN


class SpielerPlusEntity(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"SpielerPlus {entry.data[CONF_NAME]}",
            model="ICS calendar",
            sw_version="0.3.0",
        )

    @property
    def available(self):
        return super().available and not getattr(
            self.coordinator, "calendar_notice", None
        )
