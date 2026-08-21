/**
 * Frontend types mirroring the backend visualizationSpec Pydantic contract
 * (backend/app/ai/schemas/visualization.py). The LLM produces a declarative
 * spec; the renderers interpret generic structure — never executable code.
 */

export type VisualizationType =
  | "PROCESS_FLOW"
  | "CONCEPT_MAP"
  | "GENERIC_PROCESS";

export type ConnectionKind =
  | "DEPENDENCY"
  | "HAZARD"
  | "FORWARDING"
  | "STALL"
  | "FLOW";

export type VizStage = { id: string; label: string };
export type VizItem = { id: string; label: string; color?: string | null };

export type VizConnection = {
  from: string;
  to: string;
  label?: string | null;
  kind: ConnectionKind;
};

export type VizAnimationStep = {
  stepIndex: number;
  description: string;
  stageState: Record<string, string>;
  connections: VizConnection[];
  hazardHighlight?: boolean;
  forwardingHighlight?: boolean;
  pause?: boolean;
};

export type VizAnimation = {
  steps: VizAnimationStep[];
  loop?: boolean;
};

export type ProcessFlowSpec = {
  stages: VizStage[];
  items: VizItem[];
  animation: VizAnimation;
};

export type ConceptMapNode = { id: string; label: string; color?: string | null };
export type ConceptMapEdge = { from: string; to: string; label?: string | null };

export type ConceptMapSpec = {
  nodes: ConceptMapNode[];
  edges: ConceptMapEdge[];
};

export type VisualizationSpec = {
  type: VisualizationType;
  title: string;
  caption?: string;
  emphasis?: string | null;
  process?: ProcessFlowSpec | null;
  conceptMap?: ConceptMapSpec | null;
};

/** Type guard: does the spec describe a renderable process-flow diagram? */
export function isProcessFlow(spec: VisualizationSpec | null | undefined): spec is VisualizationSpec & { process: ProcessFlowSpec } {
  return !!spec && spec.type === "PROCESS_FLOW" && !!spec.process;
}

/** Type guard: does the spec describe a renderable concept map? */
export function isConceptMap(spec: VisualizationSpec | null | undefined): spec is VisualizationSpec & { conceptMap: ConceptMapSpec } {
  return !!spec && spec.type === "CONCEPT_MAP" && !!spec.conceptMap;
}

/**
 * Fail-safe: given any parsed spec, return a guaranteed-renderable one.
 * Falls back to CONCEPT_MAP so a visualization always renders (doc5).
 */
export function normalizeToRenderable(spec: VisualizationSpec | null | undefined): VisualizationSpec {
  if (isProcessFlow(spec)) return spec;
  if (isConceptMap(spec)) return spec;
  return {
    type: "CONCEPT_MAP",
    title: spec?.title ?? "Concept map",
    caption: spec?.caption ?? "",
    conceptMap: {
      nodes: [{ id: "n1", label: spec?.title ?? "Concept" }],
      edges: [],
    },
  };
}