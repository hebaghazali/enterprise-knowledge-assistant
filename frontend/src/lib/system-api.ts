import { apiFetch } from "./api-client";

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

export const getServiceInfo = () => apiFetch<ServiceInfo>("/");
export const getHealth = () => apiFetch<HealthResponse>("/health");
export const getDatabaseHealth = () => apiFetch<DatabaseHealthResponse>("/health/db");
