"use client";

import type { ConceptMapSpec } from "./types";

const NODE_W = 150;
const NODE_H = 44;
const GAP_X = 44;
const GAP_Y = 66;

function layout(nodes: ConceptMapSpec["nodes"]) {
  const n = nodes.length;
  const cols = Math.max(1, Math.ceil(Math.sqrt(n * 1.6)));
  const positions = nodes.map((node, i) => {
    const col = i % cols;
    const row = Math.floor(i / cols);
    return {
      node,
      x: col * (NODE_W + GAP_X),
      y: row * (NODE_H + GAP_Y),
      cx: col * (NODE_W + GAP_X) + NODE_W / 2,
      cy: row * (NODE_H + GAP_Y) + NODE_H / 2,
    };
  });
  const maxRow = Math.floor((n - 1) / cols);
  return {
    positions,
    width: cols * (NODE_W + GAP_X) - GAP_X + 20,
    height: maxRow * (NODE_H + GAP_Y) + NODE_H + 20,
  };
}

export default function ConceptMapRenderer({ spec }: { spec: ConceptMapSpec }) {
  const { positions, width, height } = layout(spec.nodes);
  const byId = new Map(spec.nodes.map((n) => [n.id, n]));
  const anchors = new Map(positions.map((p) => [p.node.id, p]));

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="w-full h-auto"
      role="img"
      aria-label="Concept map"
    >
      {spec.edges.map((edge, i) => {
        const a = anchors.get(edge.from);
        const b = anchors.get(edge.to);
        if (!a || !b) return null;
        const mx = (a.cx + b.cx) / 2;
        const my = (a.cy + b.cy) / 2;
        const dx = b.cx - a.cx;
        const dy = b.cy - a.cy;
        const len = Math.hypot(dx, dy) || 1;
        const ux = dx / len;
        const uy = dy / len;
        const sx = a.cx + ux * (NODE_W / 2);
        const sy = a.cy + uy * (NODE_H / 2);
        const ex = b.cx - ux * (NODE_W / 2);
        const ey = b.cy - uy * (NODE_H / 2);
        const ax = b.cx - ux * (NODE_W / 2 + 8);
        const ay = b.cy - uy * (NODE_H / 2 + 8);
        return (
          <g key={i}>
            <line
              x1={sx}
              y1={sy}
              x2={ex}
              y2={ey}
              stroke="#a1a1aa"
              strokeWidth={1.5}
            />
            <path
              d={`M ${ax} ${ay} l ${-ux * 10 - uy * 5} ${-uy * 10 + ux * 5} l ${ux * 10 - uy * 5} ${uy * 10 + ux * 5} z`}
              fill="#a1a1aa"
            />
            {edge.label && (
              <text
                x={mx}
                y={my - 4}
                textAnchor="middle"
                fontSize={10}
                fill="#71717a"
              >
                {edge.label}
              </text>
            )}
          </g>
        );
      })}
      {positions.map(({ node, x, y }) => (
        <g key={node.id}>
          <rect
            x={x}
            y={y}
            width={NODE_W}
            height={NODE_H}
            rx={8}
            fill={node.color ?? "#f4f4f5"}
            stroke="#a1a1aa"
            strokeWidth={1.5}
          />
          <text
            x={x + NODE_W / 2}
            y={y + NODE_H / 2 + 4}
            textAnchor="middle"
            fontSize={12}
            fontWeight={600}
            fill="#18181b"
          >
            {node.label.length > 18 ? node.label.slice(0, 17) + "…" : node.label}
          </text>
        </g>
      ))}
      {byId.size === 0 && (
        <text x={20} y={24} fontSize={12} fill="#71717a">
          No concepts to map.
        </text>
      )}
    </svg>
  );
}