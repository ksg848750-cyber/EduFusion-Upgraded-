import asyncio

import pytest

from app.rag.embeddings import to_vector_string
from app.rag import retriever
from app.services import chunks as chunks_module


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_to_vector_string():
    s = to_vector_string([0.123456789, -1.0, 2.5])
    assert s == "[0.123457,-1.000000,2.500000]"


def test_embed_single_returns_correct_dimension():
    vec = _run(chunks_embed_single())
    assert len(vec) == 384


async def chunks_embed_single():
    from app.rag.embeddings import embed_single

    return await embed_single("pipeline data hazard forwarding")


def test_insert_chunk_uses_vector_cast(monkeypatch):
    captured = {}

    class FakeRecord:
        def __getitem__(self, i):
            return ["chunk-1", 0, 1, "Intro"][i]

    class FakeRow:
        async def fetchone(self):
            return FakeRecord()

    class FakeConn:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def execute(self, sql, params):
            captured["sql"] = sql
            captured["params"] = params
            return FakeRow()

    fake_conn = FakeConn()
    monkeypatch.setattr(chunks_module, "connection", lambda: fake_conn)

    result = _run(chunks_module.insert_chunk("mat-1", "subj-1", 0, "text", 1, "Intro", {}, [0.5, 0.5]))
    assert result["id"] == "chunk-1"
    assert "CAST(%s AS vector)" in captured["sql"]
    assert captured["params"][7] == "[0.500000,0.500000]"


def test_retrieve_embeds_and_queries(monkeypatch):
    async def fake_embed_single(text):
        return [0.1] * 384

    async def fake_query_chunks(owner_id, subject_id, qv, top_k=6):
        assert len(qv) == 384
        assert top_k == 3
        return [{"text": "a chunk", "score": 0.9}]

    monkeypatch.setattr(retriever, "embed_single", fake_embed_single)
    monkeypatch.setattr(retriever, "query_chunks", fake_query_chunks)

    out = _run(retriever.retrieve("owner-1", "subj-1", "query", top_k=3))
    assert out[0]["score"] == 0.9