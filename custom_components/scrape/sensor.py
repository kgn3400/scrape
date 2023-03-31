"""Support for getting data from websites with scraping."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging
import re
from typing import Any, cast

import voluptuous as vol

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.sensor.helpers import async_parse_date_datetime
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ATTRIBUTE,
    CONF_NAME,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.template import Template
from homeassistant.helpers.template_entity import (
    TEMPLATE_SENSOR_BASE_SCHEMA,
    TemplateSensor,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_BS_SEARCH_FIND,
    CONF_BS_SEARCH_FIND_STRING,
    CONF_BS_SEARCH_SELECT,
    CONF_BS_SEARCH_TYPE,
    CONF_CLEAR_UPDATED_BIN_SENSOR_AFTER,
    CONF_INDEX,
    CONF_SELECT,
    DOMAIN,
)
from .coordinator import ScrapeCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Web scrape sensor."""
    discovery_info = cast(DiscoveryInfoType, discovery_info)
    coordinator: ScrapeCoordinator = discovery_info["coordinator"]
    sensors_config: list[ConfigType] = discovery_info["configs"]

    await coordinator.async_refresh()
    if coordinator.data is None:
        raise PlatformNotReady

    entities: list[ScrapeSensor] = []
    for sensor_config in sensors_config:
        value_template: Template | None = sensor_config.get(CONF_VALUE_TEMPLATE)
        if value_template is not None:
            value_template.hass = hass

        entities.append(
            ScrapeSensor(
                hass,
                coordinator,
                sensor_config,
                sensor_config[CONF_NAME],
                sensor_config.get(CONF_UNIQUE_ID),
                sensor_config.get(CONF_BS_SEARCH_TYPE, CONF_BS_SEARCH_SELECT),
                sensor_config[CONF_SELECT],
                sensor_config.get(CONF_ATTRIBUTE),
                sensor_config[CONF_INDEX],
                value_template,
                sensor_config.get(CONF_CLEAR_UPDATED_BIN_SENSOR_AFTER, 24),
            )
        )

    async_add_entities(entities)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Scrape sensor entry."""
    entities: list = []

    coordinator: ScrapeCoordinator = hass.data[DOMAIN][entry.entry_id]
    config = dict(entry.options)

    for sensor in config["sensor"]:
        sensor_config: ConfigType = vol.Schema(
            TEMPLATE_SENSOR_BASE_SCHEMA.schema, extra=vol.ALLOW_EXTRA
        )(sensor)

        name: str = sensor_config[CONF_NAME]
        select: str = sensor_config[CONF_SELECT]
        attr: str | None = sensor_config.get(CONF_ATTRIBUTE)
        index: int = int(sensor_config[CONF_INDEX])
        value_string: str | None = sensor_config.get(CONF_VALUE_TEMPLATE)
        unique_id: str = sensor_config[CONF_UNIQUE_ID]
        search_type: str = sensor_config[CONF_BS_SEARCH_TYPE]
        clear_udated_bin_sensor_after: float = float(
            sensor_config.get(CONF_CLEAR_UPDATED_BIN_SENSOR_AFTER, 24)
        )

        value_template: Template | None = (
            Template(value_string, hass) if value_string is not None else None
        )
        entities.append(
            ScrapeSensor(
                hass,
                coordinator,
                sensor_config,
                name,
                unique_id,
                search_type,
                select,
                attr,
                index,
                value_template,
                clear_udated_bin_sensor_after,
            )
        )

    async_add_entities(entities)


class ScrapeSensor(CoordinatorEntity[ScrapeCoordinator], TemplateSensor):
    """Representation of a web scrape sensor."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: ScrapeCoordinator,
        config: ConfigType,
        name: str,
        unique_id: str | None,
        # KGN start
        search_type: str,
        # KGN end
        select: str,
        attr: str | None,
        index: int,
        value_template: Template | None,
        # KGN start
        clear_updated_bin_sensor_after: float,
        # KGN end
    ) -> None:
        """Initialize a web scrape sensor."""
        CoordinatorEntity.__init__(self, coordinator)
        TemplateSensor.__init__(
            self,
            hass,
            config=config,
            fallback_name=name,
            unique_id=unique_id,
        )
        self._name: Template = name  # type: ignore
        self._select = select
        self._attr = attr
        self._index = index
        self._value_template = value_template
        #      self.hass = hass
        # KGN start
        self._search_type = search_type
        self._clear_updated_bin_sensor_after: float = clear_updated_bin_sensor_after
        self.sensor_name: str = self._name.template  # type: ignore
        self.forced_refresh: bool = False
        # KGN end

    def _extract_value(self) -> Any:
        """Parse the html extraction in the executor."""
        raw_data = self.coordinator.data
        value = ""

        # KGN start
        if self._search_type == CONF_BS_SEARCH_SELECT:
            # KGN end
            try:
                if self._attr is not None:
                    value = raw_data.select(self._select)[self._index][self._attr]
                else:
                    tag = raw_data.select(self._select)[self._index]
                    if tag.name in ("style", "script", "template"):
                        value = tag.string
                    else:
                        value = tag.text
            except IndexError:
                _LOGGER.warning(
                    "Index '%s' not found in %s", self._index, self.entity_id
                )
                value = None
            except KeyError:
                _LOGGER.warning(
                    "Attribute '%s' not found in %s", self._attr, self.entity_id
                )
                value = None

        # KGN start
        elif self._search_type == CONF_BS_SEARCH_FIND:
            try:
                value = raw_data.find_all(self._select)[self._index].string

            except AttributeError:
                value = None

            except Exception:
                _LOGGER.exception("BS find exception")
                value = None

        elif self._search_type == CONF_BS_SEARCH_FIND_STRING:
            try:
                value = raw_data.find_all(string=re.compile(self._select))[
                    self._index
                ].string

            except AttributeError:
                value = None

            except Exception:
                _LOGGER.exception("BS find exception")
                value = None
        # KGN end

        _LOGGER.debug("Parsed value: %s", value)
        return value

    async def async_added_to_hass(self) -> None:
        """Ensure the data from the initial update is reflected in the state."""
        await super().async_added_to_hass()
        self._async_update_from_rest_data()

    def _async_update_from_rest_data(self) -> None:
        """Update state from the rest data."""
        value = self._extract_value()

        if (template := self._value_template) is not None:
            value = template.async_render_with_possible_json_value(value, None)

        # KGN start
        if value is not None:
            self.update_binary_sensor_values(value)
        # KGN end

        if self.device_class not in {
            SensorDeviceClass.DATE,
            SensorDeviceClass.TIMESTAMP,
        }:
            self._attr_native_value = value
            return

        self._attr_native_value = async_parse_date_datetime(
            value, self.entity_id, self.device_class
        )

    # KGN start
    def update_binary_sensor_values(self, value: str) -> None:
        """Set status for updated."""

        if (
            self.coordinator.updated.get(self.sensor_name, False) is True
            and self.forced_refresh is False
            and self.coordinator.new_value.get(self.sensor_name, "") != value
        ):
            # Updated state is true, but we already got a updated new value.
            # Force updated state to false and que a refresh.
            self.forced_refresh = True
            self.coordinator.old_value[self.sensor_name] = ""
            self.coordinator.updated[self.sensor_name] = False

            # I'm not sure this is the correct/safe way to call a async refresh from a non async function!?
            # https://developers.home-assistant.io/docs/asyncio_working_with_async/#calling-async-functions-from-threads
            asyncio.run_coroutine_threadsafe(
                self.coordinator.async_refresh(), self.hass.loop
            )
            return

        self.forced_refresh = False

        # First time
        if self.coordinator.new_value.get(self.sensor_name, "") == "":
            self.coordinator.new_value[self.sensor_name] = value
            self.coordinator.old_value[self.sensor_name] = ""
            self.coordinator.updated[self.sensor_name] = False
            self.coordinator.updated_at[self.sensor_name] = datetime.now()

        # New value
        elif self.coordinator.new_value.get(self.sensor_name, "") != value:
            self.coordinator.old_value[self.sensor_name] = self.coordinator.new_value[
                self.sensor_name
            ]
            self.coordinator.new_value[self.sensor_name] = str(value)
            self.coordinator.updated_at[self.sensor_name] = datetime.now()
            self.coordinator.updated[self.sensor_name] = True

        # Clear updated state
        elif (
            self.coordinator.updated.get(self.sensor_name, False) is True
            and (
                self.coordinator.updated_at.get(self.sensor_name, datetime.now())
                + timedelta(hours=self._clear_updated_bin_sensor_after)
            )
            < datetime.now()
        ):
            self.coordinator.old_value[self.sensor_name] = ""
            self.coordinator.updated[self.sensor_name] = False

        # Hmm
        # elif self.coordinator.old_value.get(self.sensor_name, "") != "":
        #     self.coordinator.updated[self.sensor_name] = True
        # KGN end

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._async_update_from_rest_data()
        super()._handle_coordinator_update()
