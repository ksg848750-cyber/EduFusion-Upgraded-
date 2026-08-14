"""Modular embedding provider.

Default provider is fastembed (ONNX) with BAAI/bge-small-en-v1.5 (384-dim,
cosine). Swap by changing embedding_provider/model in settings — nothing else
in the codebase depends on a specific model.
"""
import asyncio
from typing import Any

from app.core.config import get_settings

_models: dict[str, Any] = {}


def _provider_key() -> str:
    s = get_settings()
    return f"{s.embedding_provider}:{s.embedding_model}"


def _load_model():
    s = get_settings()
    if s.embedding_provider == "fastembed":
        from fastembed import TextEmbedding

        return TextEmbedding(model_name=s.embedding_model)
    raise ValueError(f"Unsupported embedding_provider: {s.embedding_provider}")


async def _get_model():
    key = _provider_key()
    if key not in _models:
        _models[key] = await asyncio.to_thread(_load_model)
    return _models[key]


def _embed_sync(model, texts: list[str]) -> list[list[float]]:
    vectors = list(model.embed(texts))
    return [list(map(float, v)) for v in vectors]


async def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    model = await _get_model()
    return await asyncio.to_thread(_embed_sync, model, texts)


async def embed_single(text: str) -> list[float]:
    vectors = await embed_texts([text])
    return vectors[0]


def to_vector_string(vector: list[float]) -> str:
    """Render a vector as a Postgres vector literal, e.g. '[0.1,0.2]'."""
    inner = ",".join(f"{v:.6f}" for v in vector)
    return f"[{inner}]"