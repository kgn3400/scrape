"""Constants for Scrape integration."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "scrape"
DEFAULT_ENCODING = "UTF-8"
DEFAULT_NAME = "Web scrape"
DEFAULT_VERIFY_SSL = True
DEFAULT_SCAN_INTERVAL = timedelta(minutes=10)

# KGN start
PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]
CONF_SCAN_INTERVAL_USER = "scan_interval_user"
CONF_CLEAR_UPDATED_BIN_SENSOR_AFTER = "clear_updated_bin_sensor_after"
CONF_BS_SEARCH_TYPE = "search_type"
CONF_NICKNAME = "nickname"

CONF_BS_SEARCH_SELECT = "select"
CONF_BS_SEARCH_FIND = "find"
CONF_BS_SEARCH_FIND_STRING = "find_string"
CONF_BS_SEARCH_TYPES = [
    CONF_BS_SEARCH_SELECT,
    CONF_BS_SEARCH_FIND,
    CONF_BS_SEARCH_FIND_STRING,
]

# KGN end

CONF_ENCODING = "encoding"
CONF_SELECT = "select"
CONF_INDEX = "index"
