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
