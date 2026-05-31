import type { IngestionJob, JobStatus, ProgressUpdate } from "./types";

export const lifecycle: JobStatus[] = [
  "parser_queued",
  "parsing",
  "parsed",
  "dispatch_queued",
  "dispatching",
  "stored_local",
  "indexed_elastic",
  "completed",
];

export const terminalStatuses = new Set<JobStatus>(["completed", "failed"]);

export function isTerminalStatus(status?: JobStatus): boolean {
  return status !== undefined && terminalStatuses.has(status);
}

export function currentStatus(job?: IngestionJob, fallback?: JobStatus): JobStatus | undefined {
  return job?.status ?? fallback;
}

export function progressUpdate(job?: IngestionJob): ProgressUpdate | undefined {
  const update = job?.metadata?.progress;
  return isRecord(update) ? (update as ProgressUpdate) : undefined;
}

export function progressHistory(job?: IngestionJob): ProgressUpdate[] {
  const history = job?.metadata?.progress_history;
  return Array.isArray(history) ? (history.filter(isRecord) as ProgressUpdate[]) : [];
}

export function progressPercent(job?: IngestionJob, fallback?: JobStatus): number {
  const status = currentStatus(job, fallback);
  if (status === "completed") {
    return 100;
  }
  if (status === "failed") {
    return 100;
  }

  const progress = progressUpdate(job);
  if (typeof progress?.percent_complete === "number" && status === "parsing") {
    return bounded(15 + progress.percent_complete * 0.55);
  }

  const index = status ? lifecycle.indexOf(status) : -1;
  if (index >= 0) {
    return bounded((index / (lifecycle.length - 1)) * 100);
  }
  return 0;
}

export function phaseState(phase: JobStatus, status?: JobStatus): "done" | "active" | "pending" {
  if (status === "failed") {
    return "pending";
  }
  const phaseIndex = lifecycle.indexOf(phase);
  const statusIndex = status ? lifecycle.indexOf(status) : -1;
  if (phaseIndex < statusIndex) {
    return "done";
  }
  if (phaseIndex === statusIndex) {
    return "active";
  }
  return "pending";
}

export function statusLabel(status?: JobStatus): string {
  if (!status) {
    return "waiting";
  }
  return status.replaceAll("_", " ");
}

export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) {
    return "0 B";
  }
  const units = ["B", "KB", "MB", "GB"];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / 1024 ** index).toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

export function metadataValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "none";
  }
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value, null, 2);
}

function bounded(value: number): number {
  return Math.max(0, Math.min(100, Math.round(value)));
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
