"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

import {
  createSubject,
  fetchMe,
  fetchSubjectLearner,
  listSubjects,
  Subject,
  UserProfile,
} from "@/lib/api";
import { supabase } from "@/lib/supabase";

function MasteryBar({ mastery }: { mastery: number }) {
  const pct = Math.round(mastery * 100);
  const color =
    pct >= 85
      ? "bg-emerald-500"
      : pct >= 50
      ? "bg-amber-500"
      : pct > 0
      ? "bg-rose-500"
      : "bg-zinc-200 dark:bg-zinc-700";
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 w-24 overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-800">
        <div className={`h-full rounded-full transition-all ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-mono text-zinc-500 dark:text-zinc-400">{pct}%</span>
    </div>
  );
}

export default function DashboardPage() {
  const router = useRouter();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [masteryMap, setMasteryMap] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const { data } = await supabase.auth.getSession();
      if (!data.session) {
        router.replace("/login");
        return;
      }
      try {
        const [me, list] = await Promise.all([fetchMe(), listSubjects()]);
        if (cancelled) return;
        setProfile(me);
        setSubjects(list);

        // Fetch mastery for each subject in parallel
        const entries = await Promise.all(
          list.map(async (s) => {
            try {
              const learner = await fetchSubjectLearner(s.id);
              return [s.id, learner.overallMastery] as const;
            } catch {
              return [s.id, 0] as const;
            }
          })
        );
        if (cancelled) return;
        const map: Record<string, number> = {};
        for (const [id, m] of entries) map[id] = m;
        setMasteryMap(map);
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
  }, [router]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setCreating(true);
    setCreateError(null);
    try {
      const subject = await createSubject(name.trim(), description.trim());
      router.push(`/subjects/${subject.id}`);
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : "Failed to create subject");
    } finally {
      setCreating(false);
    }
  }

  async function handleLogout() {
    await supabase.auth.signOut();
    router.replace("/login");
  }

  if (loading) {
    return (
      <main className="flex flex-1 items-center justify-center bg-zinc-50 dark:bg-black">
        <div className="flex items-center gap-3 text-zinc-500">
          <svg className="h-5 w-5 animate-spin" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          Loading…
        </div>
      </main>
    );
  }

  return (
    <main className="flex flex-1 justify-center bg-zinc-50 px-4 py-10 dark:bg-black">
      <div className="w-full max-w-3xl space-y-8">
        <header className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-semibold text-black dark:text-zinc-50">
              Dashboard
            </h1>
            <p className="mt-1 text-sm text-zinc-500">
              {profile ? `Signed in as ${profile.name}` : "Your learning workspace"}
            </p>
          </div>
          <button
            onClick={handleLogout}
            className="h-10 rounded-lg border border-zinc-300 px-4 text-sm font-medium text-zinc-700 transition-colors hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-900"
          >
            Log out
          </button>
        </header>

        <form
          onSubmit={handleCreate}
          className="rounded-2xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950"
        >
          <h2 className="text-lg font-semibold text-black dark:text-zinc-50">
            New subject
          </h2>
          <p className="mt-1 text-sm text-zinc-500">
            Create a subject to upload learning material and build its knowledge
            graph.
          </p>
          <div className="mt-4 flex flex-col gap-3">
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Subject name (e.g. Data Structures)"
              className="h-11 rounded-lg border border-zinc-300 px-4 text-sm text-black outline-none focus:border-zinc-500 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
            />
            <input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Description (optional)"
              className="h-11 rounded-lg border border-zinc-300 px-4 text-sm text-black outline-none focus:border-zinc-500 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
            />
            <button
              type="submit"
              disabled={!name.trim() || creating}
              className="h-11 rounded-lg bg-zinc-900 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-zinc-50 dark:text-black"
            >
              {creating ? "Creating…" : "Create subject"}
            </button>
            {createError && (
              <p className="text-sm text-red-600 dark:text-red-400">{createError}</p>
            )}
          </div>
        </form>

        <section>
          <h2 className="mb-3 text-lg font-semibold text-black dark:text-zinc-50">
            Subjects
          </h2>
          {subjects.length === 0 ? (
            <div className="rounded-xl border border-dashed border-zinc-300 p-8 text-center dark:border-zinc-700">
              <p className="text-sm text-zinc-500">
                No subjects yet. Create one to get started.
              </p>
            </div>
          ) : (
            <ul className="divide-y divide-zinc-200 rounded-xl border border-zinc-200 dark:divide-zinc-800 dark:border-zinc-800">
              {subjects.map((s) => (
                <li key={s.id}>
                  <Link
                    href={`/subjects/${s.id}`}
                    className="flex items-center justify-between px-4 py-4 transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-900"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="font-medium text-black dark:text-zinc-100">
                        {s.name}
                      </p>
                      {s.description && (
                        <p className="mt-0.5 truncate text-sm text-zinc-500">
                          {s.description}
                        </p>
                      )}
                      <div className="mt-2">
                        <MasteryBar mastery={masteryMap[s.id] ?? 0} />
                      </div>
                    </div>
                    <span className="ml-4 shrink-0 rounded-full bg-zinc-100 px-2.5 py-1 text-xs font-medium text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
                      {s.conceptCount} concept{s.conceptCount === 1 ? "" : "s"}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>

        {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
      </div>
    </main>
  );
}
