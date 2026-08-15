"use client";

import { memo, useCallback, useMemo, useState } from "react";
import { motion } from "framer-motion";

import type { Concept, Relationship } from "@/lib/api";

const CONTAINMENT = new Set(["PART_OF", "INSTANCE_OF"]);
const DIRECTED = new Set(["PREREQUISITE", "DEPENDS_ON", "PART_OF", "INSTANCE_OF"]);

const EDGE_COLORS: Record<string, string> = {
  PREREQUISITE: "#2563eb",
  DEPENDS_ON: "#7c3aed",
  PART_OF: "#0891b2",
  INSTANCE_OF: "#0d9488",
  RELATED_TO: "#64748b",
  CONTRASTS_WITH: "#db2777",
};

const ROOT_ID = "__root__";

const NODE_W = 208;
const NODE_H = 42;
const HORIZ = 300;
const VGAP = 58;
const PAD = 40;

type ParentLink = { parentId: string; type: string; reason: string; confidence: number };
type GraphIndex = { byId: Map<string, Concept>; children: Map<string, string[]>; parentLinks: Map<string, ParentLink[]> };

function buildIndex(concepts: Concept[], relationships: Relationship[]): GraphIndex {
  const byId = new Map<string, Concept>(concepts.map((c) => [c.id, c]));
  const children = new Map<string, string[]>();
  const parentLinks = new Map<string, ParentLink[]>();
  for (const r of relationships) {
    if (!CONTAINMENT.has(r.relationshipType)) continue;
    const childId = r.fromConceptId;
    const parentId = r.toConceptId;
    if (!byId.has(childId) || !byId.has(parentId)) continue;
    const list = parentLinks.get(childId) ?? [];
    if (list.some((l) => l.parentId === parentId)) continue;
    list.push({ parentId, type: r.relationshipType, reason: r.reason ?? "", confidence: r.confidence });
    parentLinks.set(childId, list);
    const arr = children.get(parentId) ?? [];
    if (!arr.includes(childId)) arr.push(childId);
    children.set(parentId, arr);
  }
  const rootChildren = concepts.filter((c) => !parentLinks.has(c.id)).map((c) => c.id);
  children.set(ROOT_ID, rootChildren);
  return { byId, children, parentLinks };
}

type TreeLayout = { pos: Map<string, { x: number; y: number }>; edges: { from: string; to: string }[]; canvasW: number; canvasH: number };

function computeTreeLayout(expanded: Set<string>, idx: GraphIndex): TreeLayout {
  const visibleParent = new Map<string, string>();
  const depth = new Map<string, number>();
  const stack: [string, number, string | null][] = [[ROOT_ID, 0, null]];
  const ids: string[] = [];
  while (stack.length) {
    const [id, d, parent] = stack.pop()!;
    if (depth.has(id)) continue;
    depth.set(id, d);
    if (parent !== null) visibleParent.set(id, parent);
    ids.push(id);
    if (expanded.has(id)) {
      const kids = idx.children.get(id) ?? [];
      for (let i = kids.length - 1; i >= 0; i--) stack.push([kids[i], d + 1, id]);
    }
  }
  const yOf = new Map<string, number>();
  let cursor = 0;
  const place = (id: string) => {
    const kids = (idx.children.get(id) ?? []).filter((k) => expanded.has(id) && depth.has(k));
    if (kids.length === 0) {
      yOf.set(id, cursor);
      cursor += 1;
      return;
    }
    for (const k of kids) place(k);
    const ys = kids.map((k) => yOf.get(k)!);
    yOf.set(id, (ys[0] + ys[ys.length - 1]) / 2);
  };
  place(ROOT_ID);
  const pos = new Map<string, { x: number; y: number }>();
  for (const id of ids) pos.set(id, { x: PAD + depth.get(id)! * HORIZ, y: PAD + yOf.get(id)! * VGAP });
  const maxDepth = ids.reduce((m, id) => Math.max(m, depth.get(id)!), 0);
  return {
    pos,
    edges: [...visibleParent.entries()].map(([child, parent]) => ({ from: parent, to: child })),
    canvasW: PAD * 2 + maxDepth * HORIZ + NODE_W,
    canvasH: PAD * 2 + Math.max(cursor, 1) * VGAP,
  };
}

type NodePos = { x: number; y: number };

function computeGraphLayout(concepts: Concept[], relationships: Relationship[]) {
  const nodes = concepts.map((c) => ({ id: c.id, name: c.name }));
  const adj = new Map<string, string[]>();
  const indeg = new Map(nodes.map((n) => [n.id, 0]));
  for (const r of relationships) {
    if (!DIRECTED.has(r.relationshipType)) continue;
    const froms = adj.get(r.fromConceptId) ?? [];
    froms.push(r.toConceptId);
    adj.set(r.fromConceptId, froms);
    indeg.set(r.toConceptId, (indeg.get(r.toConceptId) ?? 0) + 1);
  }
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
    for (const t of adj.get(id) ?? []) layer.set(t, Math.max(layer.get(t) ?? 0, l + 1));
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
      pos.set(id, { x: PAD + layerIdx * HORIZ, y: PAD + (canvasH - block) / 2 + i * (NODE_H + VGAP) });
    });
  }
  return {
    pos,
    canvasW: PAD * 2 + Math.max(layers.length - 1, 0) * HORIZ + NODE_W,
    canvasH: canvasH + PAD * 2,
  };
}

type TreeNodeProps = {
  id: string;
  name: string;
  isRoot: boolean;
  hasChildren: boolean;
  isExpanded: boolean;
  childCount: number;
  isSelected: boolean;
  onToggle: (id: string) => void;
  onSelect: (id: string) => void;
};

const TreeNode = memo(function TreeNode({
  id,
  name,
  isRoot,
  hasChildren,
  isExpanded,
  childCount,
  isSelected,
  onToggle,
  onSelect,
}: TreeNodeProps) {
  const isParent = hasChildren;
  return (
    <g>
      <rect
        x={0}
        y={0}
        width={NODE_W}
        height={NODE_H}
        rx={10}
        className={
          isRoot
            ? "fill-zinc-900 stroke-zinc-900 dark:fill-zinc-100 dark:stroke-zinc-100"
            : isParent
              ? "fill-zinc-100 stroke-zinc-300 dark:fill-zinc-800 dark:stroke-zinc-600"
              : "fill-zinc-50 stroke-zinc-200 dark:fill-zinc-900 dark:stroke-zinc-700"
        }
        strokeWidth={isSelected ? 2 : 1}
        style={{ cursor: "pointer" }}
        onClick={() => onSelect(id)}
      />
      <text
        x={16}
        y={NODE_H / 2}
        dominantBaseline="middle"
        className={
          isRoot
            ? "fill-zinc-50 text-[12px] font-bold dark:fill-black"
            : isParent
              ? "fill-zinc-900 text-[11px] font-semibold dark:fill-zinc-100"
              : "fill-zinc-700 text-[11px] dark:fill-zinc-300"
        }
        pointerEvents="none"
      >
        {name}
      </text>
      {hasChildren && (
        <g
          transform={`translate(${NODE_W - 22}, ${NODE_H / 2})`}
          onClick={(e) => {
            e.stopPropagation();
            onToggle(id);
          }}
          style={{ cursor: "pointer" }}
        >
          <circle r={9} className={isRoot ? "fill-zinc-100" : "fill-zinc-200 dark:fill-zinc-600"} />
          <text
            textAnchor="middle"
            dominantBaseline="central"
            className="fill-zinc-700 text-[9px] font-bold dark:fill-zinc-100"
            pointerEvents="none"
          >
            {isExpanded ? "−" : `+${childCount}`}
          </text>
        </g>
      )}
      {!hasChildren && <circle cx={NODE_W - 16} cy={NODE_H / 2} r={3} className="fill-zinc-300 dark:fill-zinc-600" />}
    </g>
  );
});

type DrawerProps = {
  concept: Concept;
  label: string;
  isRoot: boolean;
  childrenIds: string[];
  parents: ParentLink[];
  relationships: Relationship[];
  byId: Map<string, Concept>;
  onSelect: (id: string) => void;
  onClose: () => void;
  onStudy: (concept: Concept, mode: "understand" | "test") => void;
};

function Drawer({ concept, label, isRoot, childrenIds, parents, relationships, byId, onSelect, onClose, onStudy }: DrawerProps) {
  const diff = concept.difficulty ?? 0;
  const diffLabel = diff >= 4 ? "Advanced" : diff === 3 ? "Intermediate" : diff === 2 ? "Foundation" : "Basic";
  return (
    <div className="pointer-events-auto fixed bottom-4 right-4 top-4 z-30 flex w-full max-w-md flex-col overflow-y-auto rounded-2xl border border-zinc-200 bg-white p-5 shadow-2xl dark:border-zinc-700 dark:bg-zinc-950">
      <div className="flex items-start justify-between gap-3 border-b border-zinc-100 pb-3 dark:border-zinc-800">
        <div className="min-w-0">
          <h3 className="text-xl font-bold text-black dark:text-zinc-50">{label}</h3>
          {!isRoot && <p className="mt-0.5 truncate text-xs text-zinc-400">{concept.canonicalName}</p>}
        </div>
        <button
          onClick={onClose}
          aria-label="Close"
          className="rounded-lg p-1.5 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700 dark:hover:bg-zinc-800 dark:hover:text-zinc-200"
        >
          ✕
        </button>
      </div>

      {!isRoot && (
        <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-3 dark:border-zinc-800 dark:bg-zinc-900">
          <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
            Adaptive learning
          </p>
          <div className="mt-2 grid grid-cols-2 gap-2">
            <button
              onClick={() => onStudy(concept, "understand")}
              className="rounded-lg bg-zinc-900 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 dark:bg-zinc-100 dark:text-black dark:hover:bg-zinc-300"
            >
              Understand this topic
            </button>
            <button
              onClick={() => onStudy(concept, "test")}
              className="rounded-lg border border-zinc-300 px-3 py-2 text-sm font-medium text-zinc-800 transition-colors hover:border-teal-600 hover:text-teal-700 dark:border-zinc-600 dark:text-zinc-200 dark:hover:border-teal-400 dark:hover:text-teal-300"
            >
              Test myself
            </button>
          </div>
        </div>
      )}

      <div className="space-y-4 py-4">
        {!isRoot && (
          <span className="rounded-full bg-zinc-100 px-2.5 py-1 text-[11px] font-medium text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
            Difficulty: {diffLabel}
          </span>
        )}

        {concept.description && (
          <div>
            <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-zinc-400">Description</h4>
            <p className="text-sm leading-relaxed text-zinc-700 dark:text-zinc-300">{concept.description}</p>
          </div>
        )}

        {concept.expectedUnderstanding && (
          <div>
            <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-zinc-400">Expected understanding</h4>
            <p className="text-sm leading-relaxed text-zinc-700 dark:text-zinc-300">{concept.expectedUnderstanding}</p>
          </div>
        )}

        {concept.commonMisconceptions && concept.commonMisconceptions.length > 0 && (
          <div>
            <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-zinc-400">Common misconceptions</h4>
            <ul className="list-inside list-disc space-y-1 text-sm text-zinc-700 dark:text-zinc-300">
              {concept.commonMisconceptions.map((m, i) => (
                <li key={i}>{m}</li>
              ))}
            </ul>
          </div>
        )}

        {!isRoot && parents.length > 0 && (
          <div>
            <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-zinc-400">Part of</h4>
            <ul className="space-y-1.5">
              {parents.map((p, i) => (
                <li key={i}>
                  <button
                    onClick={() => onSelect(p.parentId)}
                    className="text-sm font-medium text-teal-700 hover:underline dark:text-teal-300"
                  >
                    {byId.get(p.parentId)?.name ?? p.parentId}
                  </button>
                  {p.reason && <p className="mt-0.5 text-xs text-zinc-400">— {p.reason}</p>}
                </li>
              ))}
            </ul>
          </div>
        )}

        {childrenIds.length > 0 && (
          <div>
            <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-zinc-400">
              Child topics ({childrenIds.length})
            </h4>
            <ul className="space-y-1">
              {childrenIds.map((childId) => (
                <li key={childId}>
                  <button
                    onClick={() => onSelect(childId)}
                    className="text-sm text-zinc-700 hover:text-teal-700 hover:underline dark:text-zinc-300 dark:hover:text-teal-300"
                  >
                    {byId.get(childId)?.name ?? childId}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        {relationships.length > 0 && (
          <div>
            <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-zinc-400">
              Connections ({relationships.length})
            </h4>
            <ul className="space-y-2">
              {relationships.map((r) => {
                const otherId = r.fromConceptId === concept.id ? r.toConceptId : r.fromConceptId;
                const other = byId.get(otherId);
                const color = EDGE_COLORS[r.relationshipType] ?? "#64748b";
                return (
                  <li key={r.id} className="rounded-lg border border-zinc-100 p-2 dark:border-zinc-800">
                    <div className="flex items-center gap-1.5 text-sm">
                      <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: color }} />
                      <span className="font-medium capitalize text-zinc-800 dark:text-zinc-200">
                        {r.relationshipType.toLowerCase().replace(/_/g, " ")}
                      </span>
                      <span className="text-zinc-400">→</span>
                      <button
                        onClick={() => onSelect(otherId)}
                        className="text-zinc-700 hover:text-teal-700 hover:underline dark:text-zinc-300 dark:hover:text-teal-300"
                      >
                        {other?.name ?? otherId}
                      </button>
                    </div>
                    {r.reason && <p className="mt-1 pl-3.5 text-xs text-zinc-500 dark:text-zinc-400">{r.reason}</p>}
                    {r.sourceReferences && r.sourceReferences.length > 0 && (
                      <p className="mt-0.5 pl-3.5 text-[11px] text-zinc-400">
                        Source chunk{r.sourceReferences.length === 1 ? "" : "s"}: {r.sourceReferences.join(", ")}
                      </p>
                    )}
                  </li>
                );
              })}
            </ul>
          </div>
        )}

        {!isRoot && concept.sourceReferences && concept.sourceReferences.length > 0 && (
          <div>
            <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-zinc-400">Source evidence</h4>
            <p className="text-sm text-zinc-600 dark:text-zinc-300">
              Grounded in {concept.sourceReferences.length} source chunk
              {concept.sourceReferences.length === 1 ? "" : "s"}: {concept.sourceReferences.join(", ")}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

export default function KnowledgeGraph({
  concepts,
  relationships,
  subjectName,
  onStudy,
}: {
  concepts: Concept[];
  relationships: Relationship[];
  subjectName?: string;
  onStudy?: (concept: Concept, mode: "understand" | "test") => void;
}) {
  const [mode, setMode] = useState<"map" | "graph">("map");
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set([ROOT_ID]));
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);

  const idx = useMemo(() => buildIndex(concepts, relationships), [concepts, relationships]);
  const mapLayout = useMemo(() => computeTreeLayout(expanded, idx), [expanded, idx]);
  const graphLayout = useMemo(() => computeGraphLayout(concepts, relationships), [concepts, relationships]);

  const toggle = useCallback((id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const select = useCallback((id: string) => setSelectedId(id), []);

  const selected = selectedId ? idx.byId.get(selectedId) : null;
  const selectedRelationships = useMemo(() => {
    if (!selected) return [];
    return relationships.filter((r) => r.fromConceptId === selected.id || r.toConceptId === selected.id);
  }, [selected, relationships]);

  const zoomIn = useCallback(() => setZoom((z) => Math.min(z + 0.2, 2.5)), []);
  const zoomOut = useCallback(() => setZoom((z) => Math.max(z - 0.2, 0.4)), []);
  const zoomReset = useCallback(() => setZoom(1), []);

  if (concepts.length === 0) {
    return (
      <div className="flex items-center justify-center rounded-xl border border-dashed border-zinc-300 py-16 text-sm text-zinc-500 dark:border-zinc-700">
        No concepts yet — upload a PDF to build the knowledge graph.
      </div>
    );
  }

  const rootLabel = subjectName?.trim() || "Course Map";
  const selectedChildren = selected ? (idx.children.get(selected.id) ?? []) : [];
  const selectedParents = selected ? (idx.parentLinks.get(selected.id) ?? []) : [];

  const renderZoomControls = (
    <div className="flex items-center gap-1 rounded-lg bg-zinc-100 p-0.5 dark:bg-zinc-800">
      <button
        onClick={zoomOut}
        aria-label="Zoom out"
        className="rounded-md px-2 py-1 text-sm text-zinc-500 hover:bg-white hover:text-zinc-900 dark:hover:bg-zinc-900 dark:hover:text-zinc-100"
      >
        −
      </button>
      <span className="w-9 text-center text-xs tabular-nums text-zinc-500">{Math.round(zoom * 100)}%</span>
      <button
        onClick={zoomIn}
        aria-label="Zoom in"
        className="rounded-md px-2 py-1 text-sm text-zinc-500 hover:bg-white hover:text-zinc-900 dark:hover:bg-zinc-900 dark:hover:text-zinc-100"
      >
        +
      </button>
      <button
        onClick={zoomReset}
        className="rounded-md px-2 py-1 text-xs font-medium text-zinc-500 hover:bg-white hover:text-zinc-900 dark:hover:bg-zinc-900 dark:hover:text-zinc-100"
      >
        Fit
      </button>
    </div>
  );

  const renderZoomableSvg = (canvasW: number, canvasH: number, content: React.ReactNode) => (
    <div className="max-h-[70vh] overflow-auto" style={{ touchAction: "pan-x pan-y" }}>
      <div style={{ transform: `scale(${zoom})`, transformOrigin: "top left", width: canvasW * zoom, height: canvasH * zoom }}>
        <svg viewBox={`0 0 ${canvasW} ${canvasH}`} width={canvasW} height={canvasH} role="img" aria-label="Knowledge map">
          {content}
        </svg>
      </div>
    </div>
  );

  return (
    <div className="rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-100 p-3 dark:border-zinc-800">
        <div className="flex items-center gap-1 rounded-lg bg-zinc-100 p-0.5 dark:bg-zinc-800">
          <button
            onClick={() => setMode("map")}
            className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
              mode === "map"
                ? "bg-white text-zinc-900 shadow-sm dark:bg-zinc-900 dark:text-zinc-100"
                : "text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
            }`}
          >
            Learning Map
          </button>
          <button
            onClick={() => setMode("graph")}
            className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
              mode === "graph"
                ? "bg-white text-zinc-900 shadow-sm dark:bg-zinc-900 dark:text-zinc-100"
                : "text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
            }`}
          >
            Graph
          </button>
        </div>
        <div className="flex items-center gap-2">
          <span className="hidden text-xs text-zinc-400 sm:inline">
            {mode === "map" ? "Click + to reveal topics" : "Explore all connections"}
          </span>
          {renderZoomControls}
        </div>
      </div>

      {mode === "map" ? (
        renderZoomableSvg(
          mapLayout.canvasW,
          mapLayout.canvasH,
          <>
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
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#0891b2" />
              </marker>
            </defs>
            {mapLayout.edges.map((e) => {
              const from = mapLayout.pos.get(e.from);
              const to = mapLayout.pos.get(e.to);
              if (!from || !to) return null;
              const x1 = from.x + NODE_W;
              const y1 = from.y + NODE_H / 2;
              const x2 = to.x;
              const y2 = to.y + NODE_H / 2;
              const midX = (x1 + x2) / 2;
              const child = idx.byId.get(e.to);
              const parent = idx.byId.get(e.from);
              return (
                <motion.path
                  key={`${e.from}-${e.to}`}
                  d={`M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`}
                  fill="none"
                  stroke="#0891b2"
                  strokeWidth={1.5}
                  markerEnd="url(#arrow)"
                  initial={{ pathLength: 0, opacity: 0 }}
                  animate={{ pathLength: 1, opacity: 1 }}
                  transition={{ duration: 0.25, ease: "easeOut" }}
                >
                  <title>{`${parent?.name ?? ""} → ${child?.name ?? ""}`}</title>
                </motion.path>
              );
            })}
            {[...mapLayout.pos.keys()].map((id) => {
              const p = mapLayout.pos.get(id)!;
              const isRoot = id === ROOT_ID;
              const concept = idx.byId.get(id);
              const label = isRoot ? rootLabel : concept?.name ?? "";
              const kids = idx.children.get(id) ?? [];
              return (
                <g key={id} transform={`translate(${p.x}, ${p.y})`}>
                  <TreeNode
                    id={id}
                    name={label}
                    isRoot={isRoot}
                    hasChildren={kids.length > 0}
                    isExpanded={expanded.has(id)}
                    childCount={kids.length}
                    isSelected={selectedId === id}
                    onToggle={toggle}
                    onSelect={select}
                  />
                </g>
              );
            })}
          </>
        )
      ) : (
        renderZoomableSvg(
          graphLayout.canvasW,
          graphLayout.canvasH,
          <>
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
              const from = graphLayout.pos.get(r.fromConceptId);
              const to = graphLayout.pos.get(r.toConceptId);
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
                  transition={{ duration: 0.5, ease: "easeOut" }}
                >
                  <title>{`${r.fromName} ${r.relationshipType} ${r.toName}${r.reason ? ` — ${r.reason}` : ""}`}</title>
                </motion.path>
              );
            })}
            {concepts.map((c) => {
              const p = graphLayout.pos.get(c.id);
              if (!p) return null;
              return (
                <motion.g
                  key={c.id}
                  transform={`translate(${p.x}, ${p.y})`}
                  initial={{ opacity: 0, scale: 0.6 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ duration: 0.4, ease: "easeOut" }}
                >
                  <rect
                    width={NODE_W}
                    height={NODE_H}
                    rx={10}
                    className={
                      selectedId === c.id
                        ? "fill-zinc-100 stroke-teal-600 dark:fill-zinc-800 dark:stroke-teal-400"
                        : "fill-zinc-50 stroke-zinc-300 dark:fill-zinc-900 dark:stroke-zinc-700"
                    }
                    strokeWidth={selectedId === c.id ? 2 : 1}
                    style={{ cursor: "pointer" }}
                    onClick={() => select(c.id)}
                  />
                  <text
                    x={NODE_W / 2}
                    y={NODE_H / 2}
                    textAnchor="middle"
                    dominantBaseline="middle"
                    className="fill-zinc-800 text-[11px] font-medium dark:fill-zinc-100"
                    pointerEvents="none"
                  >
                    {c.name}
                  </text>
                  <title>{`${c.name} — ${c.description || c.canonicalName}`}</title>
                </motion.g>
              );
            })}
          </>
        )
      )}

      {selected && (
        <Drawer
          concept={selected}
          label={selectedId === ROOT_ID ? rootLabel : selected.name}
          isRoot={selectedId === ROOT_ID}
          childrenIds={selectedChildren}
          parents={selectedParents}
relationships={selectedRelationships}
          byId={idx.byId}
          onSelect={select}
          onClose={() => setSelectedId(null)}
          onStudy={onStudy ?? (() => {})}
        />
      )}
    </div>
  );
}
