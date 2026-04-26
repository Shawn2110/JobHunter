from __future__ import annotations

from abc import ABC, abstractmethod

import structlog

from app.discovery.types import DiscoveredJob, SearchInput

log = structlog.get_logger("app.discovery.adapter")


class DiscoveryAdapter(ABC):
    """Base class for all discovery adapters.

    Every adapter:
    - Has a unique `name` (stored as `job_source.source_provider`).
    - Implements `is_configured` to indicate whether the user has set
      the required env keys.
    - Implements `discover()` returning a list of normalized
      DiscoveredJob records — never raises into the orchestrator,
      always returns [] on failure (logs the error structured).
    """

    name: str
    source_kind: str = "aggregator"

    @abstractmethod
    def is_configured(self) -> bool: ...

    @abstractmethod
    async def _fetch(self, query: SearchInput) -> list[DiscoveredJob]: ...

    async def discover(self, query: SearchInput) -> list[DiscoveredJob]:
        if not self.is_configured():
            log.info("adapter.skipped", adapter=self.name, reason="not_configured")
            return []
        try:
            results = await self._fetch(query)
            log.info("adapter.results", adapter=self.name, count=len(results))
            return results
        except Exception as e:  # noqa: BLE001
            log.warning(
                "adapter.error",
                adapter=self.name,
                error=type(e).__name__,
                detail=str(e)[:300],
            )
            return []
