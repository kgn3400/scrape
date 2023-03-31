"""The scrape component."""
from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from datetime import timedelta
from typing import Any

import voluptuous as vol

from homeassistant.components.rest import RESOURCE_SCHEMA, create_rest_data_from_config
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ATTRIBUTE,
    CONF_SCAN_INTERVAL,
    CONF_VALUE_TEMPLATE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.template_entity import TEMPLATE_SENSOR_BASE_SCHEMA
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_BS_SEARCH_SELECT,
    CONF_BS_SEARCH_TYPE,
    CONF_BS_SEARCH_TYPES,
    CONF_CLEAR_UPDATED_BIN_SENSOR_AFTER,
    CONF_INDEX,
    CONF_NICKNAME,
    CONF_SELECT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import ScrapeCoordinator

SENSOR_SCHEMA = vol.Schema(
    {
        **TEMPLATE_SENSOR_BASE_SCHEMA.schema,
        vol.Optional(CONF_ATTRIBUTE): cv.string,
        vol.Optional(CONF_INDEX, default=0): cv.positive_int,
        vol.Required(CONF_SELECT): cv.string,
        vol.Required(CONF_BS_SEARCH_TYPE, default=CONF_BS_SEARCH_SELECT): vol.In(
            CONF_BS_SEARCH_TYPES
        ),
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        # KGN start
        vol.Required(CONF_CLEAR_UPDATED_BIN_SENSOR_AFTER): cv.positive_int,
        # KGN end
    }
)

COMBINED_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_SCAN_INTERVAL): cv.positive_int,
        # KGN Start
        vol.Optional(CONF_NICKNAME): cv.string,
        # KGN end
        **RESOURCE_SCHEMA,
        vol.Optional(SENSOR_DOMAIN): vol.All(
            cv.ensure_list, [vol.Schema(SENSOR_SCHEMA)]
        ),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {vol.Optional(DOMAIN): vol.All(cv.ensure_list, [COMBINED_SCHEMA])},
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Scrape from yaml config."""
    scrape_config: list[ConfigType] | None
    if not (scrape_config := config.get(DOMAIN)):
        return True

    load_coroutines: list[Coroutine[Any, Any, None]] = []
    for resource_config in scrape_config:
        rest = create_rest_data_from_config(hass, resource_config)
        scan_interval: timedelta = timedelta(
            minutes=resource_config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        coordinator = ScrapeCoordinator(hass, rest, scan_interval)

        sensors: list[ConfigType] = resource_config.get(SENSOR_DOMAIN, [])
        if sensors:
            load_coroutines.append(
                discovery.async_load_platform(
                    hass,
                    Platform.SENSOR,
                    DOMAIN,
                    {"coordinator": coordinator, "configs": sensors},
                    config,
                )
            )

    if load_coroutines:
        await asyncio.gather(*load_coroutines)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Scrape from a config entry."""

    rest_config: dict[str, Any] = COMBINED_SCHEMA(dict(entry.options))
    rest = create_rest_data_from_config(hass, rest_config)

    coordinator = ScrapeCoordinator(
        hass,
        rest,
        timedelta(minutes=rest_config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)),
    )

    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Scrape config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        del hass.data[DOMAIN][entry.entry_id]
        if not hass.data[DOMAIN]:
            del hass.data[DOMAIN]
    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
