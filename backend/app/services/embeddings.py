"""Thin wrapper around OpenAI text-embedding-3-small."""
from __future__ import annotations
import openai
from ..config import settings

_client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
_MODEL = "text-embedding-3-small"


async def get_embedding(text: str) -> list[float]:
    text = text.replace("\n", " ").strip()
    response = await _client.embeddings.create(input=[text], model=_MODEL)
    return response.data[0].embedding
