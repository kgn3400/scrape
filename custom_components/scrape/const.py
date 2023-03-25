"""Constants for Scrape integration."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "scrape"
DEFAULT_NAME = "Web scrape"
DEFAULT_VERIFY_SSL = True
DEFAULT_SCAN_INTERVAL = timedelta(minutes=1)

# KGN start
PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]
CONF_SCAN_INTERVAL_USER = "scan_interval_user"
CONF_CLEAR_UPDATE_SWITCH_AFTER = "clear_update_switch_after"
CONF_BS_SELECT_TYPE = "select_type"

CONF_BS_SELECT_SELECT = "Select"
CONF_BS_SELECT_FIND = "Find"
CONF_BS_SELECT_FIND_STRING = "Find string"
CONF_BS_SELECT_TYPES = [
    CONF_BS_SELECT_SELECT,
    CONF_BS_SELECT_FIND,
    CONF_BS_SELECT_FIND_STRING,
]

# KGN end

CONF_SELECT = "select"
CONF_INDEX = "index"
