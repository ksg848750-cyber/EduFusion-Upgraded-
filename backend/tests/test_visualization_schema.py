"""Tests for M6 slice 1 — the declarative visualizationSpec Pydantic contract.

Confirms the spec is validated, JSON round-trips (matching jsonb storage), and
malformed specs are rejected so they can be routed to a fallback renderer.
"""

import pytest

from app.ai.schemas.visualization import (
    ConceptMapSpec,
    ProcessFlowSpec,
    VisualizationSpec,
    VizAnimation,
    VizAnimationStep,
    VizItem,
    VizStage,
)


def _pipeline_spec(**over):
    return {
        "type": "PROCESS_FLOW",
        "title": "Pipeline",
        "process": {
            "stages": [
                {"id": "IF", "label": "IF"},
                {"id": "ID", "label": "ID"},
                {"id": "EX", "label": "EX"},
            ],
            "items": [{"id": "I1", "label": "ADD R1, R2, R3"}],
            "animation": {
                "steps": [
                    {"stepIndex": 1, "description": "I1 in IF", "stageState": {"I1": "IF"}},
                    {
                        "stepIndex": 2,
                        "description": "I1 in EX",
                        "stageState": {"I1": "EX"},
                        "connections": [
                            {"from": "I1", "to": "EX", "kind": "FLOW"}
                        ],
                    },
                ]
            },
        },
        **over,
    }


def test_process_flow_validates():
    spec = VisualizationSpec.model_validate(_pipeline_spec())
    assert spec.type == "PROCESS_FLOW"
    assert len(spec.process.animation.steps) == 2
    assert spec.process.animation.steps[1].connections[0].kind == "FLOW"


def test_json_round_trip_by_alias():
    """Pydantic's by_alias output is what gets serialized to jsonb and back."""
    spec = VisualizationSpec.model_validate(_pipeline_spec())
    data = spec.model_dump(by_alias=True)
    conn = data["process"]["animation"]["steps"][1]["connections"][0]
    assert conn["from"] == "I1"
    assert conn["to"] == "EX"
    reparsed = VisualizationSpec.model_validate(data)
    assert reparsed == spec


def test_concept_map_validates():
    spec = VisualizationSpec(
        type="CONCEPT_MAP",
        title="Map",
        conceptMap=ConceptMapSpec(nodes=[{"id": "a", "label": "A"}]),
    )
    assert spec.conceptMap.nodes[0].label == "A"


def test_empty_steps_rejected():
    with pytest.raises(Exception):
        VisualizationSpec.model_validate(_pipeline_spec(process={
            "stages": [{"id": "A", "label": "A"}],
            "items": [],
            "animation": {"steps": []},
        }))


def test_duplicate_stage_rejected():
    with pytest.raises(Exception):
        VisualizationSpec.model_validate(_pipeline_spec(process={
            "stages": [
                {"id": "A", "label": "A"},
                {"id": "A", "label": "A"},
            ],
            "items": [],
            "animation": {"steps": [{"stepIndex": 1, "description": "x"}]},
        }))


def test_invalid_type_rejected():
    with pytest.raises(Exception):
        VisualizationSpec.model_validate(_pipeline_spec(type="NOT_A_TYPE"))


def test_missing_payload_is_lax():
    """A spec with no matching payload still parses; the service enforces a
    renderable fallback (ConceptMap) before persistence."""
    spec = VisualizationSpec.model_validate({"type": "PROCESS_FLOW", "title": "x"})
    assert spec.process is None


# --- _normalize_visualization_spec tests (slice 5) ---

def test_normalize_valid_spec():
    from app.ai.service import _normalize_visualization_spec
    raw = _pipeline_spec()
    result = _normalize_visualization_spec(raw, "Test")
    assert result["type"] == "PROCESS_FLOW"
    assert len(result["process"]["animation"]["steps"]) == 2


def test_normalize_none_fallback():
    from app.ai.service import _normalize_visualization_spec
    result = _normalize_visualization_spec(None, "MyConcept")
    assert result["type"] == "CONCEPT_MAP"
    assert result["conceptMap"]["nodes"][0]["label"] == "MyConcept"


def test_normalize_invalid_spec_fallback():
    from app.ai.service import _normalize_visualization_spec
    result = _normalize_visualization_spec({"type": "NOPE", "title": "x"}, "Fallback")
    assert result["type"] == "CONCEPT_MAP"
    assert result["title"] == "Fallback"


def test_normalize_empty_dict_fallback():
    from app.ai.service import _normalize_visualization_spec
    result = _normalize_visualization_spec({}, "")
    assert result["type"] == "CONCEPT_MAP"