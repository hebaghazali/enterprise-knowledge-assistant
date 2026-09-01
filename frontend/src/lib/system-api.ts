import { ApiError, apiFetch } from "./api-client";

export interface ServiceInfo {
  name: string;
  version: string;
  status: string;
}

export interface HealthResponse {
  status: string;
  service: string;
}

export interface DatabaseHealthResponse {
  status: string;
  database: string;
}

export interface DependencyHealth {
  status: "ok" | "degraded" | "error";
  detail?: string;
  configured_model?: string;
  configured_model_present?: boolean;
  version?: string | null;
}

export interface ReadinessResponse {
  status: "ok" | "degraded";
  services: Record<"api" | "postgresql" | "chroma" | "ollama", DependencyHealth>;
}

export const getServiceInfo = () => apiFetch<ServiceInfo>("/");
export const getHealth = () => apiFetch<HealthResponse>("/health");
export const getDatabaseHealth = () => apiFetch<DatabaseHealthResponse>("/health/db");
export async function getReadiness(): Promise<ReadinessResponse> {
  try {
    return await apiFetch<ReadinessResponse>("/health/ready");
  } catch (error) {
    if (error instanceof ApiError && error.status === 503 && error.detail) {
      return error.detail as ReadinessResponse;
    }
    throw error;
  }
}
