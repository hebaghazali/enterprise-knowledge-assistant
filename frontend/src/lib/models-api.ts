import { apiFetch } from "./api-client";

export interface ModelInfo {
  status: "ok" | "degraded";
  version: string | null;
  configured_model: string;
  configured_model_present: boolean;
  models: string[];
}

export interface ConfiguredModelInfo {
  status: "ok" | "degraded" | "error";
  version?: string | null;
  configured_model: string;
  configured_model_present: boolean;
  detail?: string;
}

export const listModels = () => apiFetch<ModelInfo>("/models");
export const getConfiguredModel = () => apiFetch<ConfiguredModelInfo>("/models/configured");
