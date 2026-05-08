"""
Human teaching channel: highest-confidence direct instruction.
Confidence forced to 95 — the human is always the highest trust source.
"""
from __future__ import annotations
import uuid
from ..channels.base import TrainingChannel
from ...models.enums import Layer, SourceType
from ...services.write_pipeline import NodeWritePipeline


class HumanTeachingChannel(TrainingChannel):
    async def run(
        self,
        semantic_id: str,
        fact: str,
        layer: Layer,
        page_path: str | None = None,
    ) -> dict:
        pipeline = NodeWritePipeline(
            self._conn,
            self._intellion_id,
            self._session_id,
            source_type=SourceType.HUMAN,
        )
        node = await pipeline.ingest_fact(
            semantic_id=semantic_id,
            semantic_definition=fact,
            layer=layer,
            page_path=page_path,
            confidence_override=95.0,
        )
        return {"node_id": str(node.id), "semantic_id": node.semantic_id, "confidence": node.confidence}
