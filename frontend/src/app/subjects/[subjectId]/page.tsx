"use client";

import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

import KnowledgeGraph from "@/components/knowledge-graph";
import ConceptStudy from "@/components/concept-study";
import {
  fetchKnowledgeGraph,
  KnowledgeGraph as KnowledgeGraphData,
  listMaterials,
  Material,
  Concept,
  uploadMaterial,
} from "@/lib/api";
import { supabase } from "@/lib/supabase";

const STATUS_LABEL: Record<string, string> = {
  UPLOADED: "Uploaded",
  PROCESSING: "Processing…",
  COMPLETED: "Ready",
  FAILED: "Failed",
};

export default function SubjectPage({ params }: { params: Promise<{ subjectId: string }> }) {
  const { subjectId } = use(params);
  const router = useRouter();

  const [graph, setGraph] = useState<KnowledgeGraphData | null>(null);
  const [materials, setMaterials] = useState<Material[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const [study, setStudy] = useState<{ concept: Concept; mode: "understand" | "test" } | null>(null);

  async function refresh() {
    const [g, m] = await Promise.all([
      fetchKnowledgeGraph(subjectId),
      listMaterials(subjectId),
    ]);
    setGraph(g);
    setMaterials(m);
  }

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const { data } = await supabase.auth.getSession();
      if (!data.session) {
        router.replace("/login");
        return;
      }
      try {
        const [g, m] = await Promise.all([
          fetchKnowledgeGraph(subjectId),
          listMaterials(subjectId),
        ]);
        if (cancelled) return;
        setGraph(g);
        setMaterials(m);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [subjectId, router]);

  async function handleUpload() {
    if (!selectedFile) return;
    setUploading(true);
    setUploadError(null);
    try {
      const material = await uploadMaterial(subjectId, selectedFile);
      if (material.processingStatus === "FAILED") {
        setUploadError(
          material.processingError ?? "Ingestion failed for this PDF"
        );
      }
      await refresh();
      setSelectedFile(null);
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  if (loading) {
    return (
      <main className="flex flex-1 items-center justify-center bg-zinc-50 dark:bg-black">
        <p className="text-zinc-500">Loading…</p>
      </main>
    );
  }

  if (error) {
    return (
      <main className="flex flex-1 items-center justify-center bg-zinc-50 dark:bg-black">
        <p className="text-red-600 dark:text-red-400">{error}</p>
      </main>
    );
  }

  return (
    <main className="flex flex-1 justify-center bg-zinc-50 px-4 py-10 dark:bg-black">
      <div className="w-full max-w-4xl space-y-8">
        <div className="flex items-center justify-between">
          <div>
            <Link
              href="/dashboard"
              className="text-sm text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100"
            >
              ← Dashboard
            </Link>
            <h1 className="mt-1 text-3xl font-semibold text-black dark:text-zinc-50">
              {graph?.subject.name ?? "Subject"}
            </h1>
            <p className="mt-1 text-sm text-zinc-500">
              {graph?.conceptCount ?? 0} concepts · {materials.length} material
              {materials.length === 1 ? "" : "s"}
            </p>
          </div>
        </div>

        <section className="rounded-2xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950">
          <h2 className="text-lg font-semibold text-black dark:text-zinc-50">
            Upload learning material
          </h2>
          <p className="mt-1 text-sm text-zinc-500">
            Upload a text-based PDF. EduFusion will extract the concepts and
            relationships and build this subject&apos;s knowledge graph.
          </p>
          <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center">
            <input
              type="file"
              accept="application/pdf"
              onChange={(e) => setSelectedFile(e.target.files?.[0] ?? null)}
              className="block w-full text-sm text-zinc-700 file:mr-3 file:rounded-lg file:border-0 file:bg-zinc-900 file:px-4 file:py-2 file:text-sm file:font-medium file:text-white hover:file:bg-zinc-700 dark:text-zinc-300 dark:file:bg-zinc-50 dark:file:text-black"
            />
            <button
              onClick={handleUpload}
              disabled={!selectedFile || uploading}
              className="h-10 shrink-0 rounded-lg bg-zinc-900 px-5 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-zinc-50 dark:text-black"
            >
              {uploading ? "Processing…" : "Upload & build graph"}
            </button>
          </div>
          {uploadError && (
            <p className="mt-3 text-sm text-red-600 dark:text-red-400">
              {uploadError}
            </p>
          )}
        </section>

        <section>
          <h2 className="mb-3 text-lg font-semibold text-black dark:text-zinc-50">
            Knowledge graph
          </h2>
          <KnowledgeGraph
            concepts={graph?.concepts ?? []}
            relationships={graph?.relationships ?? []}
            subjectName={graph?.subject.name}
            onStudy={(concept, mode) => setStudy({ concept, mode })}
          />
        </section>

        {study && (
          <ConceptStudy
            subjectId={subjectId}
            concept={study.concept}
            mode={study.mode}
            onClose={() => setStudy(null)}
            onModeChange={(mode) => setStudy((prev) => (prev ? { ...prev, mode } : prev))}
          />
        )}

        <section>
          <h2 className="mb-3 text-lg font-semibold text-black dark:text-zinc-50">
            Materials
          </h2>
          {materials.length === 0 ? (
            <p className="text-sm text-zinc-500">No materials uploaded yet.</p>
          ) : (
            <ul className="divide-y divide-zinc-200 rounded-xl border border-zinc-200 dark:divide-zinc-800 dark:border-zinc-800">
              {materials.map((m) => (
                <li
                  key={m.id}
                  className="flex items-center justify-between px-4 py-3"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-black dark:text-zinc-100">
                      {m.filename}
                    </p>
                    {m.pageCount != null && (
                      <p className="text-xs text-zinc-500">{m.pageCount} pages</p>
                    )}
                  </div>
                  <span
                    className={
                      m.processingStatus === "FAILED"
                        ? "rounded-full bg-red-100 px-2 py-1 text-xs font-medium text-red-700 dark:bg-red-900 dark:text-red-200"
                        : m.processingStatus === "COMPLETED"
                          ? "rounded-full bg-emerald-100 px-2 py-1 text-xs font-medium text-emerald-700 dark:bg-emerald-900 dark:text-emerald-200"
                          : "rounded-full bg-zinc-100 px-2 py-1 text-xs font-medium text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300"
                    }
                  >
                    {STATUS_LABEL[m.processingStatus] ?? m.processingStatus}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </main>
  );
}