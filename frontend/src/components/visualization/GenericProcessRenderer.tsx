"use client";

import type { ProcessFlowSpec } from "./types";

const STAGE_W = 96;
const STAGE_H = 44;

/**
 * Static process-flow renderer: lays out the stages as a row and shows items
 * in their step-1 positions. Used as the GENERIC_PROCESS fallback (no player),
 * and as the static base for the animated ProcessFlow renderer.
 */
export default function GenericProcessRenderer({ spec }: { spec: ProcessFlowSpec }) {
  const stages = spec.stages;
  const first = spec.animation?.steps?.[0];
  const width = Math.max(1, stages.length) * STAGE_W;
  const height = 130;

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="w-full h-auto"
      role="img"
      aria-label="Process flow"
    >
      {stages.map((stage, i) => {
        const x = i * STAGE_W + 8;
        const cx = x + STAGE_W / 2 - 8;
        const inStage = first?.stageState
          ? Object.entries(first.stageState).find(([, s]) => s === stage.id)
          : undefined;
        return (
          <g key={stage.id}>
            <rect
              x={x}
              y={12}
              width={STAGE_W - 16}
              height={STAGE_H}
              rx={6}
              fill="#f4f4f5"
              stroke="#a1a1aa"
              strokeWidth={1.5}
            />
            <text
              x={cx}
              y={34}
              textAnchor="middle"
              fontSize={12}
              fontWeight={600}
              fill="#18181b"
            >
              {stage.label}
            </text>
            {i < stages.length - 1 && (
              <text
                x={x + STAGE_W - 10}
                y={34}
                textAnchor="middle"
                fontSize={14}
                fill="#a1a1aa"
              >
                →
              </text>
            )}
            {inStage && (
              <text
                x={cx}
                y={90}
                textAnchor="middle"
                fontSize={11}
                fontWeight={600}
                fill={inStage[0] === "__color__" ? "#f43f5e" : "#3f3f46"}
              >
                {inStage[0]}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}