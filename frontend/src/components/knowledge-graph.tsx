"use client";

import { motion } from "framer-motion";
import { useMemo } from "react";

import type { Concept, Relationship } from "@/lib/api";

type NodePos = { x: number; y: number };

const NODE_W = 150;
const NODE_H = 54;
const HSPACE = 280;
const VGAP = 80;
const PAD = 40;

const DIRECTED = new Set(["PREREQUISITE", "DEPENDS_ON", "PART_OF"]);

const EDGE_COLORS: Record<string, string> = {
  PREREQUISITE: "#2563eb",
  DEPENDS_ON: "#7c3aed",
  PART_OF: "#0891b2",
  RELATED_TO: "#64748b",
  CONTRASTS_WITH: "#db2777",
};

/** Longest-path layered layout over the directed (ordering) edges. */
function computeLayout(concepts: Concept[], relationships: Relationship[]) {
  const nodes = concepts.map((c) => ({ id: c.id, name: c.name }));
  const adj = new Map<string, string[]>();
  const inEdges = new Map<string, string[]>();
  for (const r of relationships) {
    if (!DIRECTED.has(r.relationshipType)) continue;
    const froms = adj.get(r.fromConceptId) ?? [];
    froms.push(r.toConceptId);
    adj.set(r.fromConceptId, froms);
    const tos = inEdges.get(r.toConceptId) ?? [];
    tos.push(r.fromConceptId);
    inEdges.set(r.toConceptId, tos);
  }

  const indeg = new Map(nodes.map((n) => [n.id, 0]));
  for (const tos of adj.values()) for (const t of tos) indeg.set(t, (indeg.get(t) ?? 0) + 1);

  const queue = nodes.filter((n) => (indeg.get(n.id) ?? 0) === 0).map((n) => n.id);
  const topo: string[] = [];
  while (queue.length) {
    const id = queue.shift()!;
    topo.push(id);
    for (const t of adj.get(id) ?? []) {
      indeg.set(t, (indeg.get(t) ?? 0) - 1);
      if (indeg.get(t) === 0) queue.push(t);
    }
  }

  const layer = new Map<string, number>();
  for (const id of topo) {
    const l = layer.get(id) ?? 0;
    for (const t of adj.get(id) ?? []) {
      layer.set(t, Math.max(layer.get(t) ?? 0, l + 1));
    }
  }
  for (const n of nodes) if (!layer.has(n.id)) layer.set(n.id, 0);

  const byLayer = new Map<number, string[]>();
  for (const n of nodes) {
    const l = layer.get(n.id) ?? 0;
    const arr = byLayer.get(l) ?? [];
    arr.push(n.id);
    byLayer.set(l, arr);
  }
  const layers = [...byLayer.keys()].sort((a, b) => a - b);
  const maxPerLayer = Math.max(...layers.map((l) => (byLayer.get(l) ?? []).length), 1);

  const pos = new Map<string, NodePos>();
  const canvasH = maxPerLayer * NODE_H + (maxPerLayer - 1) * VGAP;
  for (const [layerIdx, l] of layers.entries()) {
    const ids = byLayer.get(l) ?? [];
    const block = ids.length * NODE_H + (ids.length - 1) * VGAP;
    ids.forEach((id, i) => {
      pos.set(id, {
        x: PAD + layerIdx * HSPACE,
        y: PAD + (canvasH - block) / 2 + i * (NODE_H + VGAP),
      });
    });
  }
  const canvasW = PAD * 2 + Math.max(layers.length - 1, 0) * HSPACE + NODE_W;
  return { pos, canvasW, canvasH: canvasH + PAD * 2 };
}

export default function KnowledgeGraph({
  concepts,
  relationships,
}: {
  concepts: Concept[];
  relationships: Relationship[];
}) {
  const { pos, canvasW, canvasH } = useMemo(
    () => computeLayout(concepts, relationships),
    [concepts, relationships]
  );

  if (concepts.length === 0) {
    return (
      <div className="flex items-center justify-center rounded-xl border border-dashed border-zinc-300 py-16 text-sm text-zinc-500 dark:border-zinc-700">
        No concepts yet — upload a PDF to build the knowledge graph.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
      <svg
        viewBox={`0 0 ${canvasW} ${canvasH}`}
        className="mx-auto h-auto w-full max-w-4xl"
        role="img"
        aria-label="Knowledge graph"
      >
        <defs>
          <marker
            id="arrow"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            orient="auto-start-reverse"
          >
            <path d="M 0 0 L 10 5 L 0 10 z" fill="currentColor" />
          </marker>
        </defs>

        {relationships.map((r) => {
          const from = pos.get(r.fromConceptId);
          const to = pos.get(r.toConceptId);
          if (!from || !to) return null;
          const color = EDGE_COLORS[r.relationshipType] ?? "#64748b";
          const directed = DIRECTED.has(r.relationshipType);
          const x1 = from.x + NODE_W / 2;
          const y1 = from.y + NODE_H / 2;
          const x2 = to.x + NODE_W / 2;
          const y2 = to.y + NODE_H / 2;
          const midX = (x1 + x2) / 2;
          const d = directed
            ? `M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`
            : `M ${x1} ${y1} C ${x1 + 40} ${y1}, ${x2 - 40} ${y2}, ${x2} ${y2}`;
          return (
            <motion.path
              key={r.id}
              d={d}
              fill="none"
              stroke={color}
              strokeWidth={1.5}
              markerEnd={directed ? "url(#arrow)" : undefined}
              strokeDasharray={directed ? undefined : "4 4"}
              initial={{ pathLength: 0, opacity: 0 }}
              animate={{ pathLength: 1, opacity: 1 }}
              transition={{ duration: 0.6, ease: "easeOut" }}
            >
              <title>{`${r.fromName} ${r.relationshipType} ${r.toName}`}</title>
            </motion.path>
          );
        })}

        {concepts.map((c) => {
          const p = pos.get(c.id);
          if (!p) return null;
          return (
            <motion.g
              key={c.id}
              initial={{ opacity: 0, scale: 0.6 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.4, ease: "easeOut" }}
            >
              <rect
                x={p.x}
                y={p.y}
                width={NODE_W}
                height={NODE_H}
                rx={10}
                className="fill-zinc-50 stroke-zinc-300 dark:fill-zinc-900 dark:stroke-zinc-700"
                strokeWidth={1}
              />
              <text
                x={p.x + NODE_W / 2}
                y={p.y + NODE_H / 2}
                textAnchor="middle"
                dominantBaseline="middle"
                className="fill-zinc-800 text-[11px] font-medium dark:fill-zinc-100"
              >
                {c.name}
              </text>
              <title>{`${c.name} — ${c.description || c.canonicalName}`}</title>
            </motion.g>
          );
        })}
      </svg>
    </div>
  );
}