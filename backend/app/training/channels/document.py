"""
Document ingestion channel: PDF / Markdown / plain text → knowledge nodes.
Pipeline: parse → semantic chunks (500 tokens, 50 overlap) → Claude fact extraction
→ NodeWritePipeline.ingest_fact for each triple.
Also pushes high-priority frontier tasks for any rule discovered.
"""
from __future__ import annotations

import io
import json
import textwrap
import uuid
from pathlib import Path

import anthropic

from ..channels.base import TrainingChannel
from ...config import settings
from ...models.enums import Layer, SourceType
from ...services.write_pipeline import NodeWritePipeline
from ...training.explorer.frontier import FrontierItem, FrontierScheduler

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

_SYSTEM = (
    "You extract structured knowledge from product documentation for a web application. "
    "Return concise facts as typed nodes. Be conservative — only assert what the document explicitly states."
)


def _chunk_text(text: str, token_limit: int = 500, overlap: int = 50) -> list[str]:
    words = text.split()
    chunks = []
    step = max(1, token_limit - overlap)
    for i in range(0, len(words), step):
        chunk = " ".join(words[i : i + token_limit])
        if chunk:
            chunks.append(chunk)
    return chunks


def _parse_pdf(content: bytes) -> str:
    try:
        import PyPDF2  # noqa: F401
        reader = PyPDF2.PdfReader(io.BytesIO(content))
        return "\n".join(p.extract_text() or "" for p in reader.pages)
    except Exception:
        return content.decode("utf-8", errors="ignore")


def _parse_document(content: bytes, doc_type: str) -> str:
    if doc_type == "pdf":
        return _parse_pdf(content)
    return content.decode("utf-8", errors="ignore")


class DocumentIngestionChannel(TrainingChannel):
    async def run(
        self,
        content: bytes,
        filename: str,
        doc_type: str = "text",
        document_id: uuid.UUID | None = None,
        frontier: FrontierScheduler | None = None,
    ) -> dict:
        text = _parse_document(content, doc_type)
        chunks = _chunk_text(text)
        pipeline = NodeWritePipeline(
            self._conn,
            self._intellion_id,
            self._session_id,
            source_type=SourceType.DOCUMENT,
        )

        total_nodes = 0
        for chunk in chunks:
            facts = await self._extract_facts(chunk)
            for fact in facts:
                node = await pipeline.ingest_fact(
                    semantic_id=fact["semantic_id"],
                    semantic_definition=fact["definition"],
                    layer=Layer(fact["layer"]),
                    document_id=document_id,
                )
                total_nodes += 1

                # Rule nodes trigger frontier exploration tasks
                if fact["layer"] == 4 and frontier:
                    item = FrontierItem(
                        target_description=f"Verify rule: {fact['definition'][:100]}",
                        target_node_id=node.id,
                        created_by_source="document",
                        gap_weight=80.0,
                        doc_intent=True,
                    )
                    frontier.push(item)
                    await frontier.persist(item)

        return {"chunks_processed": len(chunks), "nodes_written": total_nodes}

    async def _extract_facts(self, chunk: str) -> list[dict]:
        tools = [
            {
                "name": "record_facts",
                "description": "Record facts extracted from document chunk",
                "input_schema": {
                    "type": "object",
                    "required": ["facts"],
                    "properties": {
                        "facts": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["semantic_id", "definition", "layer"],
                                "properties": {
                                    "semantic_id": {"type": "string"},
                                    "definition": {"type": "string"},
                                    "layer": {
                                        "type": "integer",
                                        "enum": [1, 2, 3, 4],
                                        "description": "1=structural 2=interaction 3=behavioral 4=rule",
                                    },
                                },
                            },
                        }
                    },
                },
            }
        ]

        response = _client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Extract knowledge nodes from this document excerpt.\n\n"
                        + textwrap.shorten(chunk, width=3000)
                    ),
                }
            ],
            tools=tools,
            tool_choice={"type": "any"},
        )

        for block in response.content:
            if block.type == "tool_use" and block.name == "record_facts":
                return block.input.get("facts", [])
        return []
