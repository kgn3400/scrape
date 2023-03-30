"""Coordinator for the scrape component."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging

from bs4 import BeautifulSoup

from homeassistant.components.rest import RestData
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


class ScrapeCoordinator(DataUpdateCoordinator[BeautifulSoup]):
    """Scrape Coordinator."""

    def __init__(
        self, hass: HomeAssistant, rest: RestData, update_interval: timedelta
    ) -> None:
        """Initialize Scrape coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Scrape Coordinator",
            update_interval=update_interval,
        )
        self._rest = rest
        # KGN Start
        self.updated: dict[str, bool] = {}
        self.new_value: dict[str, str] = {}
        self.old_value: dict[str, str] = {}
        self.updated_at: dict[str, datetime] = {}
        # KGN End

    async def _async_update_data(self) -> BeautifulSoup:
        """Fetch data from Rest."""
        await self._rest.async_update()
        if (data := self._rest.data) is None:
            raise UpdateFailed("REST data is not available")
        soup = await self.hass.async_add_executor_job(BeautifulSoup, data, "lxml")
        _LOGGER.debug("Raw beautiful soup: %s", soup)
        return soup
