import {
  AnalysisStatus,
  LeaderboardResponse,
  ResultResponse,
} from "@/types";

const rawApiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const API_BASE = rawApiUrl.endsWith("/api/v1") ? rawApiUrl : `${rawApiUrl.replace(/\/+$/, "")}/api/v1`;

export async function createAnalysis(alias?: string): Promise<AnalysisStatus> {
  const res = await fetch(`${API_BASE}/analyses`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(alias ? { alias } : {}),
  });
  if (!res.ok) {
    throw new Error(`Failed to create analysis: ${res.statusText}`);
  }
  return res.json();
}

export async function uploadResume(analysisId: string, file: File): Promise<void> {
  const formData = new FormData();
  formData.append("file", file);

  const headers: Record<string, string> = {};
  if (typeof window !== "undefined") {
    const userKeysRaw = localStorage.getItem("doyoularp_user_keys");
    if (userKeysRaw) {
      try {
        const parsed = JSON.parse(userKeysRaw);
        if (Array.isArray(parsed) && parsed.length > 0) {
          const payload = parsed
            .filter((item: any) => item.key && item.key.trim())
            .map((item: any) => ({
              provider: item.provider || "groq",
              api_key: item.key.trim(),
            }));
          if (payload.length > 0) {
            headers["X-User-Api-Keys"] = JSON.stringify(payload);
            headers["X-User-Api-Key"] = payload[0].api_key;
            headers["X-User-Provider"] = payload[0].provider;
          }
        }
      } catch {
        // Fall back to individual keys
      }
    }

    if (!headers["X-User-Api-Key"]) {
      const userApiKey = localStorage.getItem("doyoularp_user_api_key");
      const userProvider = localStorage.getItem("doyoularp_user_provider");
      if (userApiKey && userApiKey.trim()) {
        headers["X-User-Api-Key"] = userApiKey.trim();
      }
      if (userProvider && userProvider.trim()) {
        headers["X-User-Provider"] = userProvider.trim();
      }
    }
  }

  const res = await fetch(`${API_BASE}/analyses/${analysisId}/resume`, {
    method: "POST",
    headers,
    body: formData,
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => null);
    throw new Error(errorData?.detail || `Failed to upload resume: ${res.statusText}`);
  }
}

export async function getAnalysisStatus(analysisId: string): Promise<AnalysisStatus> {
  const res = await fetch(`${API_BASE}/analyses/${analysisId}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch status: ${res.statusText}`);
  }
  return res.json();
}

export async function getAnalysisResult(analysisId: string): Promise<ResultResponse> {
  const res = await fetch(`${API_BASE}/analyses/${analysisId}/result`);
  if (!res.ok) {
    const errorData = await res.json().catch(() => null);
    throw new Error(errorData?.detail || `Failed to fetch result: ${res.statusText}`);
  }
  return res.json();
}

export async function getLeaderboard(analysisId?: string | null): Promise<LeaderboardResponse> {
  const url =
    analysisId && analysisId !== "global"
      ? `${API_BASE}/analyses/${analysisId}/leaderboard`
      : `${API_BASE}/leaderboard`;

  let res = await fetch(url);
  if (!res.ok) {
    // Fallback to /analyses/global/leaderboard if /leaderboard root fails
    res = await fetch(`${API_BASE}/analyses/global/leaderboard`);
    if (!res.ok) {
      throw new Error(`Failed to fetch leaderboard: ${res.statusText}`);
    }
  }
  return res.json();
}

export function subscribeToAnalysisEvents(
  analysisId: string,
  onProgress: (status: AnalysisStatus) => void,
  onCompleted: (data: { analysis_id: string }) => void,
  onError: (errorMsg: string) => void
): () => void {
  const eventSource = new EventSource(`${API_BASE}/analyses/${analysisId}/stream`);

  eventSource.addEventListener("progress", (event) => {
    try {
      const data: AnalysisStatus = JSON.parse(event.data);
      onProgress(data);
    } catch (err) {
      console.error("Failed to parse progress event data", err);
    }
  });

  eventSource.addEventListener("completed", (event) => {
    try {
      const data = JSON.parse(event.data);
      onCompleted(data);
    } catch {
      onCompleted({ analysis_id: analysisId });
    }
    eventSource.close();
  });

  eventSource.addEventListener("failed", (event) => {
    try {
      const data = JSON.parse(event.data);
      onError(data.error || "Analysis pipeline halted.");
    } catch {
      onError("Analysis pipeline halted.");
    }
    eventSource.close();
  });

  eventSource.onerror = (err) => {
    console.error("SSE stream error:", err);
    if (eventSource.readyState === EventSource.CLOSED) {
      onError("Stream connection closed unexpectedly.");
    }
  };

  return () => {
    eventSource.close();
  };
}

