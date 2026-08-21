"use client";

import type { ComponentType } from "react";
import { motion } from "framer-motion";

import { normalizeToRenderable } from "./types";
import type { VisualizationSpec } from "./types";
import { selectRenderer } from "./registry";

/**
 * VisualizationHost: the single entry point that renders a visualizationSpec.
 * Uses the registry + fail-safe normalization so a visualization always
 * renders (doc5). The interest lens alters the caption/narrative text only;
 * the diagram itself stays concept-accurate.
 */
export default function VisualizationHost({ spec }: { spec: VisualizationSpec | null | undefined }) {
  const renderable = normalizeToRenderable(spec);
  const { entry, payload } = selectRenderer(renderable);
  const Renderer = entry.Component as ComponentType<{ spec: unknown }>;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950"
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <h4 className="text-sm font-semibold text-black dark:text-zinc-100">{renderable.title}</h4>
        <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400">
          {entry.label}
        </span>
      </div>
      <Renderer spec={payload} />
      {renderable.caption && (
        <p className="mt-3 text-[11px] leading-relaxed text-zinc-500 dark:text-zinc-400">
          {renderable.caption}
        </p>
      )}
    </motion.div>
  );
}