from __future__ import annotations
import uuid
from abc import ABC, abstractmethod
import asyncpg


class TrainingChannel(ABC):
    def __init__(
        self,
        conn: asyncpg.Connection,
        intellion_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> None:
        self._conn = conn
        self._intellion_id = intellion_id
        self._session_id = session_id

    @abstractmethod
    async def run(self, **kwargs) -> dict:
        """Run the channel. Returns a summary dict."""
        ...
