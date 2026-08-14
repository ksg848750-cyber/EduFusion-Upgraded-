from typing import Literal

from pydantic import BaseModel, Field

RelationshipType = Literal[
    "PREREQUISITE_OF",
    "DEPENDS_ON",
    "PART_OF",
    "RELATED_TO",
    "CONTRASTS_WITH",
    "INSTANCE_OF",
]


class ConceptOut(BaseModel):
    name: str = Field(min_length=1, description="Readable concept name")
    canonical_name: str = Field(min_length=1, description="Normalized, deduplicated label")
    description: str = ""
    difficulty: int = Field(ge=1, le=5, default=3)
    expected_understanding: str = ""
    common_misconceptions: list[str] = []
    parent_concept: str | None = Field(
        default=None,
        description="canonical_name of the broader topic/section this concept belongs to",
    )
    source_chunks: list[int] = Field(
        default_factory=list,
        description="chunk indices that evidence this concept",
    )


class RelationshipOut(BaseModel):
    from_concept: str = Field(min_length=1)
    to_concept: str = Field(min_length=1)
    relationship_type: RelationshipType
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)
    reason: str = Field(
        default="",
        description="short explanation of why this relationship is supported by the text",
    )
    source_chunks: list[int] = Field(
        default_factory=list,
        description="chunk indices that evidence this relationship",
    )


class KnowledgeExtraction(BaseModel):
    concepts: list[ConceptOut] = []
    relationships: list[RelationshipOut] = []