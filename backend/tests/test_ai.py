import asyncio

import pytest

from app.ai.context_builder import build_extraction_context
from app.ai.service import AIService, _clean_json


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class FakeProvider:
    def __init__(self, responses):
        self.responses = list(responses)

    async def complete(self, system, user, temperature=0.0):
        return self.responses.pop(0)


def test_clean_json_strips_fences():
    assert _clean_json("```json\n{\"a\":1}\n```") == '{"a":1}'
    assert _clean_json('{"a":1}') == '{"a":1}'


def test_context_builder_includes_section_and_page():
    chunks = [
        {"text": "Pipelines overlap stages.", "sectionTitle": "Hazards",
         "headingPath": ["Operating Systems", "Disk Scheduling"], "pageNumber": 2},
    ]
    ctx = build_extraction_context(chunks)
    assert "Disk Scheduling" in ctx
    assert "PAGE: 2" in ctx
    assert "Pipelines overlap" in ctx


def test_context_builder_uses_full_heading_path():
    chunks = [
        {"text": "Directory entries.", "sectionTitle": "Directory Structure",
         "headingPath": ["Operating Systems", "File Systems", "Directory Structure"],
         "pageNumber": 1},
    ]
    ctx = build_extraction_context(chunks)
    assert "Operating Systems / File Systems / Directory Structure" in ctx


def test_context_builder_truncates_budget():
    chunks = [{"text": "x" * 5000, "sectionTitle": None, "pageNumber": 1}] * 10
    ctx = build_extraction_context(chunks)
    assert len(ctx) <= 12000


def test_extract_knowledge_parses_valid_output():
    payload = {
        "concepts": [
            {
                "name": "Instruction Pipeline",
                "canonical_name": "instruction pipeline",
                "description": "overlapping stages",
                "difficulty": 3,
                "expected_understanding": "know the five stages",
                "common_misconceptions": ["latency equals throughput"],
            }
        ],
        "relationships": [
            {
                "from_concept": "instruction pipeline",
                "to_concept": "data hazard",
                "relationship_type": "RELATED_TO",
                "confidence": 0.9,
            }
        ],
    }
    import json

    provider = FakeProvider([json.dumps(payload)])
    service = AIService(provider=provider)
    result = _run(service.extract_knowledge([{"text": "body"}]))
    assert result.concepts[0].canonical_name == "instruction pipeline"
    assert result.relationships[0].relationship_type == "RELATED_TO"


def test_extract_knowledge_retries_on_invalid_json_then_succeeds():
    import json

    payload = json.dumps(
        {
            "concepts": [{"name": "A", "canonical_name": "a"}],
            "relationships": [],
        }
    )
    provider = FakeProvider(["not json at all", payload])
    service = AIService(provider=provider)
    result = _run(service.extract_knowledge([{"text": "body"}]))
    assert result.concepts[0].canonical_name == "a"


def test_extract_knowledge_rejects_empty_concepts():
    import json

    provider = FakeProvider([json.dumps({"concepts": [], "relationships": []})] * 2)
    service = AIService(provider=provider)
    with pytest.raises(RuntimeError):
        _run(service.extract_knowledge([{"text": "body"}]))