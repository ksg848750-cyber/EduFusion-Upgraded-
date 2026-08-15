import { supabase } from "./supabase";

export type UserProfile = {
  id: string;
  authUserId: string;
  email: string;
  name: string;
  isOnboarded: boolean;
  createdAt: string;
  updatedAt: string;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";

/** Get the current access token from the Supabase session. */
export async function getAccessToken(): Promise<string> {
  const { data, error } = await supabase.auth.getSession();
  if (error || !data.session) {
    throw new Error("No active session");
  }
  return data.session.access_token;
}

async function authedFetch(path: string, init?: RequestInit): Promise<Response> {
  const token = await getAccessToken();
  const headers: Record<string, string> = {
    Authorization: `Bearer ${token}`,
    ...(init?.headers as Record<string, string> | undefined),
  };
  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Request failed (${res.status}): ${detail}`);
  }
  return res;
}

/** Call the protected backend /auth/me endpoint with the Supabase JWT. */
export async function fetchMe(): Promise<UserProfile> {
  const res = await authedFetch("/auth/me");
  return res.json();
}

// ---- Milestone 2: subjects, materials, knowledge graph ----

export type Subject = {
  id: string;
  ownerId: string;
  name: string;
  description: string;
  status: string;
  conceptCount: number;
  createdAt: string;
  updatedAt: string;
};

export type Material = {
  id: string;
  subjectId: string;
  ownerId: string;
  filename: string;
  fileType: string;
  storageReference: string;
  processingStatus: string;
  pageCount: number | null;
  processingError: string | null;
  createdAt: string;
  updatedAt: string;
};

export type Concept = {
  id: string;
  name: string;
  canonicalName: string;
  description: string;
  difficulty: number;
  expectedUnderstanding: string;
  commonMisconceptions: string[];
  sourceReferences?: number[];
};

export type Relationship = {
  id: string;
  fromConceptId: string;
  toConceptId: string;
  relationshipType: string;
  confidence: number;
  fromName: string;
  toName: string;
  reason?: string;
  sourceReferences?: number[];
};

export type KnowledgeGraph = {
  subject: Subject;
  concepts: Concept[];
  relationships: Relationship[];
  status: string;
  conceptCount: number;
};

export async function listSubjects(): Promise<Subject[]> {
  const res = await authedFetch("/subjects");
  return res.json();
}

export async function createSubject(name: string, description: string): Promise<Subject> {
  const res = await authedFetch("/subjects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, description }),
  });
  return res.json();
}

export async function listMaterials(subjectId: string): Promise<Material[]> {
  const res = await authedFetch(`/subjects/${subjectId}/materials`);
  return res.json();
}

export async function uploadMaterial(subjectId: string, file: File): Promise<Material> {
  const token = await getAccessToken();
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/subjects/${subjectId}/materials`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  });
  if (res.ok) {
    return res.json();
  }
  if (res.status === 422) {
    const body = await res.json().catch(() => null);
    const material = body?.detail?.material;
    if (material) return material as Material;
  }
  throw new Error(`Upload failed (${res.status})`);
}

export async function fetchKnowledgeGraph(subjectId: string): Promise<KnowledgeGraph> {
  const res = await authedFetch(`/subjects/${subjectId}/knowledge-graph`);
  return res.json();
}
