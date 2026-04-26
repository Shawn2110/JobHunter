const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export interface HealthResponse {
  status: string;
}

export interface ProvidersResponse {
  version: string;
  ai_configured: boolean;
  aggregators: string[];
  search_provider: string | null;
  crawler: string;
  github_token_configured: boolean;
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`${path} returned ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export function fetchHealth(): Promise<HealthResponse> {
  return getJson<HealthResponse>("/health");
}

export function fetchProviders(): Promise<ProvidersResponse> {
  return getJson<ProvidersResponse>("/providers");
}

// ─── Profile ──────────────────────────────────────────────────────────────

export type HandleKind =
  | "github"
  | "leetcode"
  | "kaggle"
  | "linkedin"
  | "portfolio";

export interface ProfileHandle {
  id?: number;
  kind: HandleKind | string;
  username?: string | null;
  url: string;
  last_fetched_at?: string | null;
}

export interface Profile {
  id?: number;
  name: string;
  headline: string | null;
  about_me_text: string | null;
  target_seniority: string | null;
  work_authorization: Record<string, unknown> | null;
  salary_floor: number | null;
  salary_currency: string | null;
  notice_period_days: number | null;
  anti_preferences: Record<string, unknown> | null;
  handles: ProfileHandle[];
  created_at?: string;
  updated_at?: string;
}

export interface ResumeOut {
  id: number;
  version: number;
  is_master: boolean;
  label: string | null;
  parsed_json: Record<string, unknown> | null;
  source_file_path: string | null;
  created_at: string;
}

export async function fetchProfile(): Promise<Profile | null> {
  return getJson<Profile | null>("/profile");
}

export async function upsertProfile(
  payload: Omit<Profile, "id" | "created_at" | "updated_at">,
): Promise<Profile> {
  const res = await fetch(`${API_BASE}/profile`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error(`PUT /profile returned ${res.status}: ${await res.text()}`);
  }
  return res.json() as Promise<Profile>;
}

export async function uploadResume(file: File): Promise<ResumeOut> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/profile/resume`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    throw new Error(
      `POST /profile/resume returned ${res.status}: ${await res.text()}`,
    );
  }
  return res.json() as Promise<ResumeOut>;
}
