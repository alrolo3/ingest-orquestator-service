import type {
  IngestBatchResponse,
  IngestResponse,
  IngestionCapabilities,
  IngestionJob,
  IngestionOptions,
  IngestorSettingsResponse,
  IngestorSettingsUpdate,
  OutputFiles,
  QueueMetrics,
} from "./types";

export const defaultApiBaseUrl =
  import.meta.env.VITE_INGEST_API_BASE_URL?.replace(/\/$/, "") || "http://127.0.0.1:8000";

export function buildIngestQuery(options: IngestionOptions): string {
  const params = new URLSearchParams();
  params.set("parser", options.parser);
  params.set("pipeline", options.pipeline);
  params.set("chunking_enabled", String(options.chunkingEnabled));
  if (options.chunkingEnabled) {
    params.set("chunking_strategy", options.chunkingStrategy);
  }
  params.set("dispatch_sink_mode", options.dispatchSinkMode);
  if (options.ocrLanguages.length > 0) {
    params.set("ocr_languages", options.ocrLanguages.join(","));
  }
  params.set("async_mode", String(options.asyncMode));
  params.set("include_document", String(options.includeDocument));
  params.set("include_html", String(options.includeHtml));
  return params.toString();
}

export async function getCapabilities(
  apiBaseUrl = defaultApiBaseUrl,
): Promise<IngestionCapabilities> {
  return requestJson<IngestionCapabilities>(`${apiBaseUrl}/v1/ingest/capabilities`);
}

export async function getIngestorSettings(
  apiBaseUrl = defaultApiBaseUrl,
): Promise<IngestorSettingsResponse> {
  return requestJson<IngestorSettingsResponse>(`${apiBaseUrl}/v1/ingest/settings`);
}

export async function updateIngestorSettings(
  update: IngestorSettingsUpdate,
  apiBaseUrl = defaultApiBaseUrl,
): Promise<IngestorSettingsResponse> {
  return requestJson<IngestorSettingsResponse>(`${apiBaseUrl}/v1/ingest/settings`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(update),
  });
}

export async function uploadFiles(
  files: File[],
  options: IngestionOptions,
  apiBaseUrl = defaultApiBaseUrl,
): Promise<IngestResponse[]> {
  const query = buildIngestQuery(options);
  if (files.length === 1) {
    const formData = new FormData();
    formData.set("file", files[0]);
    const response = await requestJson<IngestResponse>(
      `${apiBaseUrl}/v1/ingest/file?${query}`,
      {
        method: "POST",
        body: formData,
      },
    );
    return [response];
  }

  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }
  const response = await requestJson<IngestBatchResponse>(
    `${apiBaseUrl}/v1/ingest/files?${query}`,
    {
      method: "POST",
      body: formData,
    },
  );
  return [...response.jobs, ...response.failed];
}

export async function getJob(
  jobId: string,
  apiBaseUrl = defaultApiBaseUrl,
): Promise<IngestionJob> {
  return requestJson<IngestionJob>(`${apiBaseUrl}/v1/ingest/jobs/${jobId}`);
}

export async function getJobs(
  jobIds: string[],
  apiBaseUrl = defaultApiBaseUrl,
): Promise<IngestionJob[]> {
  if (jobIds.length === 0) {
    return [];
  }
  const params = new URLSearchParams();
  params.set("ids", jobIds.join(","));
  return requestJson<IngestionJob[]>(`${apiBaseUrl}/v1/ingest/jobs?${params.toString()}`);
}

export async function getQueueMetrics(
  apiBaseUrl = defaultApiBaseUrl,
  limit = 20,
): Promise<QueueMetrics> {
  const params = new URLSearchParams();
  params.set("limit", String(limit));
  return requestJson<QueueMetrics>(`${apiBaseUrl}/v1/ingest/queue/metrics?${params.toString()}`);
}

export async function listOutputs(
  jobId: string,
  apiBaseUrl = defaultApiBaseUrl,
): Promise<OutputFiles> {
  return requestJson<OutputFiles>(`${apiBaseUrl}/v1/ingest/jobs/${jobId}/outputs`);
}

export function outputUrl(jobId: string, outputType: string, apiBaseUrl = defaultApiBaseUrl) {
  return `${apiBaseUrl}/v1/ingest/jobs/${jobId}/outputs/${outputType}`;
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    const detail = await readError(response);
    throw new Error(detail || `${response.status} ${response.statusText}`);
  }
  return (await response.json()) as T;
}

async function readError(response: Response): Promise<string> {
  const text = await response.text();
  if (!text) {
    return "";
  }
  try {
    const payload = JSON.parse(text) as { detail?: unknown; error?: unknown };
    const detail = payload.detail ?? payload.error;
    return typeof detail === "string" ? detail : JSON.stringify(detail);
  } catch {
    return text;
  }
}
