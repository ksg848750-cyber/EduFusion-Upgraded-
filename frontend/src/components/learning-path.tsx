"use client";

import { motion } from "framer-motion";

type Resolution = {
  status?: string;
  conceptId?: string | null;
  conceptName?: string | null;
  path?: string[];
  rootGap?: boolean;
  reason?: string;
};

export default function LearningPath({ resolution }: { resolution: Resolution }) {
  const path = resolution?.path ?? [];
  if (path.length === 0) return null;

  const rootGap = resolution.rootGap ?? false;
  const target = resolution.conceptName ?? path[path.length - 1];
  const surface = path[0];

  return (
    <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-900">
      <h4 className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
        Your learning path
      </h4>
      {rootGap ? (
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-300">
          <span className="font-semibold text-zinc-900 dark:text-zinc-50">{surface}</span> builds on{" "}
          <span className="font-semibold text-purple-700 dark:text-purple-300">{target}</span>. We
          repair the foundation first — the rest unlocks after.
        </p>
      ) : (
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-300">
          This is your target right now. The nodes below are what unlock it.
        </p>
      )}

      <div className="mt-4 flex flex-col gap-2">
        {path.map((name, i) => {
          const isTarget = name === target;
          const isSurface = i === 0;
          const isLocked = !isTarget;
          return (
            <div key={`${name}-${i}`} className="flex flex-col gap-2">
              {i > 0 && (
                <div className="ml-5 h-3 w-px bg-zinc-300 dark:bg-zinc-700" aria-hidden />
              )}
              <motion.div
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.08 }}
                className={`flex items-center gap-3 rounded-lg border px-3 py-2.5 ${
                  isTarget
                    ? "border-purple-300 bg-purple-50 dark:border-purple-700 dark:bg-purple-950"
                    : "border-zinc-200 bg-white dark:border-zinc-700 dark:bg-zinc-950"
                }`}
              >
                <span
                  className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                    isTarget
                      ? "bg-purple-600 text-white"
                      : isLocked
                        ? "bg-zinc-200 text-zinc-500 dark:bg-zinc-700 dark:text-zinc-300"
                        : "bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300"
                  }`}
                >
                  {isTarget ? "★" : isSurface ? "▶" : i + 1}
                </span>
                <div className="min-w-0">
                  <p
                    className={`truncate text-sm font-medium ${
                      isTarget
                        ? "text-purple-900 dark:text-purple-100"
                        : "text-zinc-800 dark:text-zinc-100"
                    }`}
                  >
                    {name}
                  </p>
                  <p className="text-[11px] text-zinc-500 dark:text-zinc-400">
                    {isTarget
                      ? rootGap
                        ? "Repair this foundation first"
                        : "Ready to learn now"
                      : isSurface
                        ? "You asked about this — locked until its prerequisite is solid"
                        : "Locked until its prerequisite is complete"}
                  </p>
                </div>
              </motion.div>
            </div>
          );
        })}
      </div>

      {resolution.reason && (
        <p className="mt-3 text-[11px] italic text-zinc-400">{resolution.reason}</p>
      )}
    </div>
  );
}