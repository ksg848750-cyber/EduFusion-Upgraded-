"use client";

import type { ComponentType } from "react";

import ConceptMapRenderer from "./ConceptMapRenderer";
import GenericProcessRenderer from "./GenericProcessRenderer";
import ProcessFlowRenderer from "./ProcessFlowRenderer";
import type { VisualizationSpec } from "./types";

type Renderer = { label: string; Component: ComponentType<{ spec: never }> };

/**
 * Visualization Registry: maps a spec `type` to its deterministic React
 * renderer (doc5). New renderers are added here as one registry entry — no
 * changes anywhere else. The fallback below guarantees a visual always renders.
 */
export const REGISTRY: Record<string, Renderer> = {
  PROCESS_FLOW: {
    label: "Process flow",
    Component: ProcessFlowRenderer as ComponentType<{ spec: never }>,
  },
  GENERIC_PROCESS: {
    label: "Process flow",
    Component: GenericProcessRenderer as ComponentType<{ spec: never }>,
  },
  CONCEPT_MAP: {
    label: "Concept map",
    Component: ConceptMapRenderer as ComponentType<{ spec: never }>,
  },
};

const FALLBACK: Renderer = {
  label: "Concept map",
  Component: ConceptMapRenderer as ComponentType<{ spec: never }>,
};

export function selectRenderer(spec: VisualizationSpec): {
  entry: Renderer;
  payload: unknown;
} {
  if (spec.type === "PROCESS_FLOW" && spec.process) {
    return { entry: REGISTRY.PROCESS_FLOW, payload: spec.process };
  }
  if (spec.type === "GENERIC_PROCESS" && spec.process) {
    return { entry: REGISTRY.GENERIC_PROCESS, payload: spec.process };
  }
  if (spec.type === "CONCEPT_MAP" && spec.conceptMap) {
    return { entry: REGISTRY.CONCEPT_MAP, payload: spec.conceptMap };
  }
  return {
    entry: FALLBACK,
    payload: { nodes: [{ id: "n1", label: spec.title || "Concept" }], edges: [] },
  };
}