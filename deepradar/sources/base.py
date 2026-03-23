from __future__ import annotations

import abc
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

    from deepradar.processing.models import RawNewsItem

logger = logging.getLogger(__name__)


class BaseSource(abc.ABC):
    """Abstract base class for all news sources."""

    name: str = "base"

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.name}")

    @abc.abstractmethod
    async def fetch(self) -> list[RawNewsItem]:
        """Fetch raw items. Must handle its own errors and return [] on failure."""
        ...

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r}>"
