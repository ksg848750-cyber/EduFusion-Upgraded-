"""Pydantic contracts for the M6 Visualization Engine (doc5).

The LLM produces a *declarative* ``visualizationSpec`` describing generic
structure — stages, items, arrows, animation steps, and semantic hints — never
executable frontend code. This module validates that spec before it is stored
in ``lessons.visualization_spec`` (jsonb).

Renderers are *structure interpreters*: the same schema describes a CPU
pipeline, an HTTP lifecycle, or any process flow. Semantic hints (HAZARD,
FORWARDING) are generic structural signals, not topic-specific code.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

VisualizationType = Literal[
    "PROCESS_FLOW",
    "CONCEPT_MAP",
    "GENERIC_PROCESS",
]

ConnectionKind = Literal["DEPENDENCY", "HAZARD", "FORWARDING", "STALL", "FLOW"]


class VizStage(BaseModel):
    """One column / lane in a process flow."""

    id: str = Field(min_length=1)
    label: str = Field(min_length=1)


class VizItem(BaseModel):
    """One moving token that occupies a stage at a given animation step."""

    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    color: Optional[str] = None


class VizConnection(BaseModel):
    """An arrow/edge active at a specific animation step."""

    source: str = Field(min_length=1, alias="from")
    target: str = Field(min_length=1, alias="to")
    label: Optional[str] = None
    kind: ConnectionKind = "DEPENDENCY"

    model_config = {"populate_by_name": True}


class VizAnimationStep(BaseModel):
    """One frame of the animation: where each item sits and which edges light up."""

    stepIndex: int = Field(ge=1)
    description: str = Field(min_length=1)
    stageState: dict[str, str] = Field(default_factory=dict)
    connections: list[VizConnection] = Field(default_factory=list)
    hazardHighlight: bool = False
    forwardingHighlight: bool = False
    pause: bool = False


class VizAnimation(BaseModel):
    """The ordered playable frames plus playback defaults."""

    steps: list[VizAnimationStep] = Field(default_factory=list, min_length=1)
    loop: bool = False


class ProcessFlowSpec(BaseModel):
    """A lane-based process animation (the pipeline workhorse)."""

    stages: list[VizStage] = Field(min_length=1)
    items: list[VizItem] = Field(default_factory=list)
    animation: VizAnimation

    @field_validator("stages")
    @classmethod
    def _unique_stages(cls, v: list[VizStage]) -> list[VizStage]:
        ids = [s.id for s in v]
        if len(ids) != len(set(ids)):
            raise ValueError("stages must have unique ids")
        return v

    @field_validator("items")
    @classmethod
    def _unique_items(cls, v: list[VizItem]) -> list[VizItem]:
        ids = [i.id for i in v]
        if len(ids) != len(set(ids)):
            raise ValueError("items must have unique ids")
        return v


class ConceptMapNode(BaseModel):
    """One node in a concept-map visualization."""

    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    color: Optional[str] = None


class ConceptMapEdge(BaseModel):
    """One directed relationship between two concept-map nodes."""

    source: str = Field(min_length=1, alias="from")
    target: str = Field(min_length=1, alias="to")
    label: Optional[str] = None

    model_config = {"populate_by_name": True}


class ConceptMapSpec(BaseModel):
    """A node-and-edge concept map (generic fallback for any topic)."""

    nodes: list[ConceptMapNode] = Field(min_length=1)
    edges: list[ConceptMapEdge] = Field(default_factory=list)


class VisualizationSpec(BaseModel):
    """The master, discriminated spec stored in ``lessons.visualization_spec``.

    ``type`` selects the renderer via the Visualization Registry; the
    corresponding ``*Spec`` payload holds the generic structure. Unknown or
    malformed specs are caught at validation time and routed to a generic
    fallback renderer by the service (fail-safe, doc5).
    """

    type: VisualizationType
    title: str = Field(min_length=1)
    # Rendered below the diagram so the interest lens can add narrative color
    # without altering the (concept-accurate) visual.
    caption: str = ""
    # Contextual emphasis hint aligned with the diagnosis (doc5 table).
    emphasis: Optional[str] = None

    process: Optional[ProcessFlowSpec] = None
    conceptMap: Optional[ConceptMapSpec] = None

    @field_validator("type")
    @classmethod
    def _payload_matches_type(cls, v: str, info) -> str:
        # Payload presence is enforced in the service (normalize_to_renderable),
        # not here, so the same schema can represent every variant without
        # heavy discriminated-union boilerplate.
        return v