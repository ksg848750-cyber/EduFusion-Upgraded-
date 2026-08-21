"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useRef, useState } from "react";

import type {
  ConnectionKind,
  ProcessFlowSpec,
  VizAnimationStep,
} from "./types";

const STAGE_W = 110;
const STAGE_H = 46;
const ITEM_W = 84;
const ITEM_H = 30;
const TOP = 18;
const ITEM_Y = TOP + STAGE_H + 26;

const SPEEDS = [0.5, 1, 2] as const;

type Props = {
  spec: ProcessFlowSpec;
};

function clampStep(spec: ProcessFlowSpec, index: number): number {
  const max = spec.animation.steps.length - 1;
  return Math.min(Math.max(index, 0), max);
}

/** Which color to use for a given connection kind. */
function colorFor(kind: ConnectionKind) {
  if (kind === "HAZARD" || kind === "STALL") return "#f43f5e";
  if (kind === "FORWARDING") return "#22c55e";
  return "#a1a1aa";
}

/**
 * ProcessFlow renderer: a lane-based animated diagram with a play/pause/step
 * player (doc5). Items move through stages as the spec's animation steps
 * advance; Framer Motion interpolates the transitions.
 *
 * Hazard + Forwarding behaviors (doc5):
 *   HAZARD    → red dashed arrow, auto-pauses at conflict, stage pulses red.
 *   FORWARDING → neon-green glowing path, step counter shown.
 *   STALL     → item rendered as a grey bubble (stalled instruction).
 */
export default function ProcessFlowRenderer({ spec }: Props) {
  const steps = spec.animation.steps;
  const [stepIndex, setStepIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState<(typeof SPEEDS)[number]>(1);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const step: VizAnimationStep = steps[clampStep(spec, stepIndex)];
  const stageWidth = Math.max(1, spec.stages.length) * STAGE_W;
  const totalHeight = ITEM_Y + ITEM_H + 24;

  const play = () => setPlaying(true);
  const pause = () => setPlaying(false);
  const toStep = (i: number) => {
    setStepIndex(clampStep(spec, i));
    pause();
  };

  useEffect(() => {
    if (!playing) return;
    timer.current = setInterval(() => {
      setStepIndex((prev) => {
        const next = clampStep(spec, prev + 1);
        if (next === prev) {
          if (spec.animation.loop) return 0;
          setPlaying(false);
          return prev;
        }
        return next;
      });
    }, 1600 / speed);
    return () => {
      if (timer.current) clearInterval(timer.current);
    };
  }, [playing, speed, spec]);

  // Auto-pause when a step has `pause: true` (e.g. at a hazard conflict point)
  useEffect(() => {
    if (step.pause && playing) {
      pause();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stepIndex]);

  const stageIndex = (id: string) => spec.stages.findIndex((s) => s.id === id);
  const itemX = (stageId: string) =>
    stageIndex(stageId) * STAGE_W + (STAGE_W - ITEM_W) / 2;

  return (
    <div className="select-none">
      <svg
        viewBox={`0 0 ${stageWidth} ${totalHeight}`}
        className="w-full h-auto"
        role="img"
        aria-label={step.description}
      >
        {/* SVG filters for neon glow effects */}
        <defs>
          <filter id="glow-green" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <filter id="glow-red" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Stages */}
        {spec.stages.map((stage, i) => {
          const x = i * STAGE_W;
          const cx = x + STAGE_W / 2;
          const isHazardStage =
            step.hazardHighlight &&
            Object.values(step.stageState).includes(stage.id) &&
            step.connections.some(
              (c) => c.kind === "HAZARD" || c.kind === "STALL"
            );
          const isForwardingStage =
            step.forwardingHighlight &&
            Object.values(step.stageState).includes(stage.id) &&
            step.connections.some((c) => c.kind === "FORWARDING");

          return (
            <motion.g
              key={stage.id}
              animate={
                isHazardStage
                  ? { opacity: [1, 0.4, 1] }
                  : isForwardingStage
                    ? { opacity: [1, 0.7, 1] }
                    : { opacity: 1 }
              }
              transition={
                isHazardStage
                  ? { duration: 0.7, repeat: Infinity }
                  : isForwardingStage
                    ? { duration: 1.2, repeat: Infinity }
                    : {}
              }
            >
              <rect
                x={x + 4}
                y={TOP}
                width={STAGE_W - 8}
                height={STAGE_H}
                rx={7}
                fill={
                  isHazardStage
                    ? "#fff1f2"
                    : isForwardingStage
                      ? "#f0fdf4"
                      : "#f4f4f5"
                }
                stroke={
                  isHazardStage
                    ? "#f43f5e"
                    : isForwardingStage
                      ? "#22c55e"
                      : "#a1a1aa"
                }
                strokeWidth={isHazardStage || isForwardingStage ? 2 : 1.5}
              />
              <text
                x={cx}
                y={TOP + STAGE_H / 2 + 4}
                textAnchor="middle"
                fontSize={12}
                fontWeight={600}
                fill="#18181b"
              >
                {stage.label}
              </text>
              {i < spec.stages.length - 1 && (
                <text
                  x={x + STAGE_W - 2}
                  y={TOP + STAGE_H / 2 + 4}
                  textAnchor="middle"
                  fontSize={13}
                  fill="#a1a1aa"
                >
                  →
                </text>
              )}
            </motion.g>
          );
        })}

        {/* Connections active in the current step */}
        {step.connections.map((conn, i) => {
          const sx = stageIndex(conn.from);
          const tx = stageIndex(conn.to);
          if (sx < 0 || tx < 0) return null;
          const x1 = sx * STAGE_W + STAGE_W / 2;
          const x2 = tx * STAGE_W + STAGE_W / 2;
          const y = TOP + STAGE_H / 2;
          const color = colorFor(conn.kind);
          const isHazard = conn.kind === "HAZARD" || conn.kind === "STALL";
          const isForwarding = conn.kind === "FORWARDING";

          return (
            <g key={i}>
              {/* Neon glow layer for forwarding */}
              {isForwarding && (
                <motion.path
                  d={`M ${x1} ${y} C ${x1} ${y - 48}, ${x2} ${y - 48}, ${x2} ${y}`}
                  fill="none"
                  stroke={color}
                  strokeWidth={6}
                  strokeLinecap="round"
                  filter="url(#glow-green)"
                  initial={{ pathLength: 0, opacity: 0 }}
                  animate={{ pathLength: 1, opacity: [0.4, 0.7, 0.4] }}
                  transition={{
                    pathLength: { duration: 0.6 },
                    opacity: { duration: 1.5, repeat: Infinity },
                  }}
                />
              )}

              {/* Main path */}
              <motion.path
                d={
                  isForwarding
                    ? `M ${x1} ${y} C ${x1} ${y - 48}, ${x2} ${y - 48}, ${x2} ${y}`
                    : isHazard
                      ? `M ${x1} ${y} C ${x1} ${y - 36}, ${x2} ${y - 36}, ${x2} ${y}`
                      : `M ${x1} ${y} C ${x1} ${y - 30}, ${x2} ${y - 30}, ${x2} ${y}`
                }
                fill="none"
                stroke={color}
                strokeWidth={isForwarding ? 3 : 2.5}
                strokeDasharray={isHazard ? "6 5" : isForwarding ? "0" : "6 5"}
                filter={isForwarding ? "url(#glow-green)" : isHazard ? "url(#glow-red)" : undefined}
                initial={{ pathLength: 0 }}
                animate={{ pathLength: 1 }}
                transition={{ duration: 0.6 }}
              />

              {/* Hazard pulse overlay */}
              {isHazard && (
                <motion.path
                  d={`M ${x1} ${y} C ${x1} ${y - 36}, ${x2} ${y - 36}, ${x2} ${y}`}
                  fill="none"
                  stroke={color}
                  strokeWidth={4}
                  strokeLinecap="round"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: [0, 0.8, 0] }}
                  transition={{ duration: 1.2, repeat: Infinity }}
                />
              )}

              {/* Arrowhead */}
              <motion.polygon
                points={`${x2 - 6},${y - 4} ${x2},${y + 2} ${x2 - 6},${y + 8}`}
                fill={color}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.4 }}
              />

              {/* Label */}
              {conn.label && (
                <motion.text
                  x={(x1 + x2) / 2}
                  y={y - (isForwarding ? 52 : isHazard ? 40 : 36)}
                  textAnchor="middle"
                  fontSize={isForwarding ? 11 : 10}
                  fontWeight={700}
                  fill={color}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 0.3 }}
                >
                  {conn.label}
                </motion.text>
              )}
            </g>
          );
        })}

        {/* Items — animate position; STALL state renders as grey bubble */}
        {spec.items.map((item) => {
          const targetStage = step.stageState[item.id];
          const isStalled = targetStage === "STALL";
          const tx = isStalled
            ? stageIndex(
                Object.entries(step.stageState).find(
                  ([k, v]) => v !== "STALL" && k !== item.id
                )?.[1] ?? spec.stages[0].id
              ) *
              STAGE_W +
              (STAGE_W - ITEM_W) / 2
            : itemX(targetStage ?? spec.stages[0].id);

          return (
            <motion.g
              key={item.id}
              initial={false}
              animate={{ x: tx, y: ITEM_Y }}
              transition={{ type: "spring", stiffness: 180, damping: 20 }}
            >
              {isStalled ? (
                /* STALL bubble — grey, dashed outline, X pattern */
                <g>
                  <rect
                    width={ITEM_W}
                    height={ITEM_H}
                    rx={6}
                    fill="#e4e4e7"
                    stroke="#71717a"
                    strokeWidth={1.5}
                    strokeDasharray="4 3"
                  />
                  <line
                    x1={4}
                    y1={4}
                    x2={ITEM_W - 4}
                    y2={ITEM_H - 4}
                    stroke="#a1a1aa"
                    strokeWidth={1}
                  />
                  <line
                    x1={ITEM_W - 4}
                    y1={4}
                    x2={4}
                    y2={ITEM_H - 4}
                    stroke="#a1a1aa"
                    strokeWidth={1}
                  />
                  <text
                    x={ITEM_W / 2}
                    y={ITEM_H / 2 + 4}
                    textAnchor="middle"
                    fontSize={9}
                    fontWeight={600}
                    fill="#52525b"
                  >
                    STALL
                  </text>
                </g>
              ) : (
                /* Normal item */
                <g>
                  <rect
                    width={ITEM_W}
                    height={ITEM_H}
                    rx={6}
                    fill={item.color ?? "#c084fc"}
                    stroke="#9333ea"
                    strokeWidth={1.5}
                  />
                  <text
                    x={ITEM_W / 2}
                    y={ITEM_H / 2 + 4}
                    textAnchor="middle"
                    fontSize={10}
                    fontWeight={600}
                    fill="#fff"
                  >
                    {item.label.length > 12
                      ? item.label.slice(0, 11) + "…"
                      : item.label}
                  </text>
                </g>
              )}
            </motion.g>
          );
        })}
      </svg>

      {/* Step description — synced explanation highlight */}
      <div className="mt-2 rounded-lg bg-zinc-50 px-3 py-2 text-center dark:bg-zinc-900">
        <p className="text-[10px] uppercase tracking-wide text-zinc-400 dark:text-zinc-500">
          Step {step.stepIndex} / {steps.length}
        </p>
        <p className="mt-0.5 text-xs leading-relaxed text-zinc-700 dark:text-zinc-200">
          {step.description}
        </p>
      </div>

      {/* Player controls */}
      <div className="mt-2 flex flex-wrap items-center justify-center gap-2">
        <button
          onClick={() => toStep(stepIndex - 1)}
          disabled={stepIndex === 0}
          aria-label="Previous step"
          className="rounded-md bg-zinc-200 px-2.5 py-1 text-xs font-medium text-zinc-700 transition-colors hover:bg-zinc-300 disabled:opacity-40 dark:bg-zinc-800 dark:text-zinc-200 dark:hover:bg-zinc-700"
        >
          ⏮
        </button>
        <button
          onClick={playing ? pause : play}
          disabled={steps.length < 2}
          aria-label={playing ? "Pause" : "Play"}
          className="rounded-md bg-purple-600 px-3.5 py-1 text-xs font-semibold text-white transition-colors hover:bg-purple-500 disabled:opacity-40"
        >
          {playing ? "⏸" : "▶"}
        </button>
        <button
          onClick={() => toStep(stepIndex + 1)}
          disabled={stepIndex >= steps.length - 1}
          aria-label="Next step"
          className="rounded-md bg-zinc-200 px-2.5 py-1 text-xs font-medium text-zinc-700 transition-colors hover:bg-zinc-300 disabled:opacity-40 dark:bg-zinc-800 dark:text-zinc-200 dark:hover:bg-zinc-700"
        >
          ⏭
        </button>
        <div className="ml-1 flex items-center gap-1 rounded-md bg-zinc-100 p-0.5 dark:bg-zinc-800">
          {SPEEDS.map((s) => (
            <button
              key={s}
              onClick={() => setSpeed(s)}
              className={`rounded px-1.5 py-0.5 text-[10px] font-semibold transition-colors ${
                speed === s
                  ? "bg-white text-zinc-900 shadow-sm dark:bg-zinc-900 dark:text-zinc-100"
                  : "text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-200"
              }`}
            >
              {s}x
            </button>
          ))}
        </div>
      </div>
      <AnimatePresence />
    </div>
  );
}
