export const API_BASE =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly detail?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function detailMessage(detail: unknown): string | null {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const messages = detail.map(detailMessage).filter((value): value is string => Boolean(value));
    return messages.length > 0 ? messages.join("; ") : null;
  }
  if (detail && typeof detail === "object") {
    const record = detail as Record<string, unknown>;
    if (typeof record.msg === "string") return record.msg;
    if (typeof record.detail === "string") return record.detail;
    try {
      return JSON.stringify(record);
    } catch {
      return null;
    }
  }
  return null;
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, init);
  } catch {
    throw new ApiError(
      0,
      `Could not connect to the EKA API at ${API_BASE}. Check that the backend is running and allows this frontend origin.`,
    );
  }
  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as { detail?: unknown } | null;
    throw new ApiError(
      res.status,
      detailMessage(body?.detail) ?? `HTTP ${res.status}`,
      body?.detail,
    );
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}
