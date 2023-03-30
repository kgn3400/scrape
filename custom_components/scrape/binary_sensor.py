"""Support for Scrape binary sensor."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ATTRIBUTE,
    CONF_NAME,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.template import Template
from homeassistant.helpers.template_entity import TEMPLATE_SENSOR_BASE_SCHEMA
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_INDEX, CONF_SELECT, DOMAIN
from .coordinator import ScrapeCoordinator

_LOGGER = logging.getLogger(__name__)


# ------------------------------------------------------
async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Scrape sensor entry."""
    entities: list = []

    coordinator: ScrapeCoordinator = hass.data[DOMAIN][entry.entry_id]
    config = dict(entry.options)
    for sensor in config["sensor"]:
        sensor_config: ConfigType = vol.Schema(
            TEMPLATE_SENSOR_BASE_SCHEMA.schema, extra=vol.ALLOW_EXTRA
        )(sensor)

        name: Template = sensor_config[CONF_NAME]
        select: str = sensor_config[CONF_SELECT]
        attr: str | None = sensor_config.get(CONF_ATTRIBUTE)
        index: int = int(sensor_config[CONF_INDEX])
        value_string: str | None = sensor_config.get(CONF_VALUE_TEMPLATE)
        unique_id: str = sensor_config[CONF_UNIQUE_ID]

        value_template: Template | None = (
            Template(value_string, hass) if value_string is not None else None
        )
        entities.append(
            ScrapeBinarySensor(
                hass,
                coordinator,
                sensor_config,
                config["resource"],
                name,
                unique_id,
                select,
                attr,
                index,
                value_template,
            )
        )

    async_add_entities(entities)


# ------------------------------------------------------
# ------------------------------------------------------
class ScrapeBinarySensor(CoordinatorEntity[ScrapeCoordinator], BinarySensorEntity):
    """Binary Sensor class for Scrape updates."""

    # ------------------------------------------------------
    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: ScrapeCoordinator,
        config: ConfigType,
        resource: str,
        name: Template,
        unique_id: str,
        select: str,
        attr: str | None,
        index: int,
        value_template: Template | None,
    ) -> None:
        """Initialize a web scrape sensor."""
        CoordinatorEntity.__init__(self, coordinator)
        self.resource: str = resource
        self._select = select
        self._attr = attr
        self._index = index
        self._value_template = value_template
        self.sensor_name = name.template

        self._name: str = name.template + " Updated"
        self._unique_id: str = unique_id + "_updated"

    # ------------------------------------------------------
    @property
    def name(self) -> str:
        """Name."""
        return self._name

    # ------------------------------------------------------
    @property
    def icon(self) -> str:
        """Icon."""
        if self.coordinator.old_value[self.sensor_name] != "":
            return "mdi:eye-plus-outline"

        return "mdi:eye-outline"

    # ------------------------------------------------------
    @property
    def is_on(self) -> bool:
        """Get the state."""

        return self.coordinator.updated[self.sensor_name]

    # ------------------------------------------------------
    @property
    def extra_state_attributes(self) -> dict:
        """Extra state attributes."""
        attr: dict = {}

        attr["resource"] = self.resource
        attr["new_value"] = self.coordinator.new_value[self.sensor_name]
        attr["old_value"] = self.coordinator.old_value[self.sensor_name]

        if self.coordinator.old_value[self.sensor_name] != "":
            attr["markdown"] = (
                '<font color= dodgerblue><ha-icon icon="mdi:eye-plus-outline"></ha-icon></font>'
                f" [{self.sensor_name.capitalize()}]({self.resource})"
                f" value updated to **'{self.coordinator.new_value[self.sensor_name]}'**"
                f" from '{self.coordinator.old_value[self.sensor_name]}'"
            )
        else:
            attr["markdown"] = (
                '<font color= dodgerblue><ha-icon icon="mdi:eye-outline"></ha-icon></font>'
                f" [{self.sensor_name.capitalize()}]({self.resource})"
                f" value **'{self.coordinator.new_value[self.sensor_name]}'**"
            )

        return attr

    # ------------------------------------------------------
    @property
    def unique_id(self) -> str:
        """Unique id."""
        return self._unique_id

    # ------------------------------------------------------
    @property
    def should_poll(self) -> bool:
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    # ------------------------------------------------------
    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    # ------------------------------------------------------
    async def async_update(self) -> None:
        """Update the entity. Only used by the generic entity update service."""
        await self.coordinator.async_request_refresh()

    # ------------------------------------------------------
    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )
