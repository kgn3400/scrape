"""Support for getting data from websites with scraping."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
import re
from typing import Any

import voluptuous as vol

from homeassistant.components.rest import RESOURCE_SCHEMA, create_rest_data_from_config
from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    DEVICE_CLASSES_SCHEMA,
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    STATE_CLASSES_SCHEMA,
    SensorDeviceClass,
)
from homeassistant.components.sensor.helpers import async_parse_date_datetime
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (  # KGN start; CONF_SCAN_INTERVAL,; KGN end
    CONF_ATTRIBUTE,
    CONF_AUTHENTICATION,
    CONF_DEVICE_CLASS,
    CONF_HEADERS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_RESOURCE,
    CONF_UNIQUE_ID,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_USERNAME,
    CONF_VALUE_TEMPLATE,
    CONF_VERIFY_SSL,
    HTTP_BASIC_AUTHENTICATION,
    HTTP_DIGEST_AUTHENTICATION,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.template import Template
from homeassistant.helpers.template_entity import (
    TEMPLATE_SENSOR_BASE_SCHEMA,
    TemplateSensor,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (  # KGN Start; DEFAULT_SCAN_INTERVAL,
    CONF_BS_SEARCH_FIND,
    CONF_BS_SEARCH_FIND_STRING,
    CONF_BS_SEARCH_SELECT,
    CONF_BS_SEARCH_TYPE,
    CONF_CLEAR_UPDATED_BIN_SENSOR_AFTER,
    CONF_INDEX,
    CONF_SCAN_INTERVAL_USER,
    CONF_SELECT,
    DEFAULT_NAME,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)
from .coordinator import ScrapeCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PARENT_PLATFORM_SCHEMA.extend(
    {
        # Linked to the loading of the page (can be linked to RestData)
        vol.Optional(CONF_AUTHENTICATION): vol.In(
            [HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION]
        ),
        vol.Optional(CONF_HEADERS): vol.Schema({cv.string: cv.string}),
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Required(CONF_RESOURCE): cv.string,
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
        # KGN Start
        vol.Optional(CONF_SCAN_INTERVAL_USER, default=10): cv.positive_int,
        vol.Optional(CONF_CLEAR_UPDATED_BIN_SENSOR_AFTER, default=24): cv.positive_int,
        # KGN end
        vol.Optional(CONF_INDEX, default=0): cv.positive_int,
        # Linked to the parsing of the page (specific to scrape)
        vol.Optional(CONF_ATTRIBUTE): cv.string,
        vol.Optional(CONF_INDEX, default=0): cv.positive_int,
        # KGN Start
        vol.Required(CONF_BS_SEARCH_TYPE, default=CONF_BS_SEARCH_SELECT): cv.string,
        # KGN End
        vol.Required(CONF_SELECT): cv.string,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        # Linked to the sensor definition (can be linked to TemplateSensor)
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_STATE_CLASS): STATE_CLASSES_SCHEMA,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Web scrape sensor."""
    coordinator: ScrapeCoordinator
    sensors_config: list[ConfigType]
    if discovery_info is None:
        async_create_issue(
            hass,
            DOMAIN,
            "moved_yaml",
            breaks_in_ha_version="2022.12.0",
            is_fixable=False,
            severity=IssueSeverity.WARNING,
            translation_key="moved_yaml",
        )
        resource_config = vol.Schema(RESOURCE_SCHEMA, extra=vol.REMOVE_EXTRA)(config)
        rest = create_rest_data_from_config(hass, resource_config)

        # scan_interval: timedelta = config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        coordinator = ScrapeCoordinator(
            hass, rest, timedelta(minutes=config.get(CONF_SCAN_INTERVAL_USER, 10))
        )

        sensors_config = [
            vol.Schema(TEMPLATE_SENSOR_BASE_SCHEMA.schema, extra=vol.ALLOW_EXTRA)(
                config
            )
        ]

    else:
        coordinator = discovery_info["coordinator"]
        sensors_config = discovery_info["configs"]

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
        # KGN start
        self._search_type = search_type
        self._clear_updated_bin_sensor_after: float = clear_updated_bin_sensor_after
        self.sensor_name: str = self._name.template  # type: ignore
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
        self.set_updated_status(value)
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
    def set_updated_status(self, value: str) -> None:
        """Set status for updated"""

        if value is None:
            return

        if self.coordinator.new_value.get(self.sensor_name, "") == "":
            self.coordinator.new_value[self.sensor_name] = value
            self.coordinator.old_value[self.sensor_name] = ""
            self.coordinator.updated[self.sensor_name] = False
            self.coordinator.updated_at[self.sensor_name] = datetime.now()

        elif self.coordinator.new_value.get(self.sensor_name, "") != value:
            self.coordinator.old_value[self.sensor_name] = self.coordinator.new_value[
                self.sensor_name
            ]
            self.coordinator.new_value[self.sensor_name] = str(value)
            self.coordinator.updated_at[self.sensor_name] = datetime.now()
            self.coordinator.updated[self.sensor_name] = True

        elif (
            self.coordinator.old_value.get(self.sensor_name, "") != ""
            and (
                self.coordinator.updated_at.get(self.sensor_name, datetime.now())
                + timedelta(hours=self._clear_updated_bin_sensor_after)
            )
            < datetime.now()
        ):
            self.coordinator.old_value[self.sensor_name] = ""
            self.coordinator.updated[self.sensor_name] = False

        elif self.coordinator.old_value.get(self.sensor_name, "") != "":
            self.coordinator.updated[self.sensor_name] = True
        # KGN end

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._async_update_from_rest_data()
        super()._handle_coordinator_update()
