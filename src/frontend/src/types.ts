export type JobStatus =
  | "pending"
  | "queued"
  | "running"
  | "parser_queued"
  | "retrying"
  | "parsing"
  | "parsed"
  | "dispatch_queued"
  | "dispatching"
  | "stored_local"
  | "indexed_elastic"
  | "retryable_failure"
  | "completed"
  | "failed";

export type Pipeline = "standard" | "vlm" | "auto";
export type ChunkingStrategy = "token" | "page" | "line";
export type DispatchSinkMode = "local" | "elastic" | "local_and_elastic";

export interface CapabilityOption {
  value: string;
  label: string;
  default?: boolean;
  supported_input_formats?: string[];
  chunking?: ParserChunkingCapabilities;
}

export interface ParserChunkingCapabilities {
  enabled: boolean;
  default_strategy?: ChunkingStrategy | null;
  strategies: CapabilityOption[];
}

export interface IngestionCapabilities {
  service: string;
  max_upload_size_mb: number;
  allowed_upload_extensions: string[];
  parsers: CapabilityOption[];
  pipelines: CapabilityOption[];
  default_parser: string;
  default_pipeline: Pipeline;
  default_dispatch_sink_mode: DispatchSinkMode;
  dispatchers: CapabilityOption[];
  ocr: {
    enabled: boolean;
    engine: string;
    default_languages: string[];
    languages: CapabilityOption[];
  };
  chunking: {
    enabled: boolean;
    default_strategy?: ChunkingStrategy | null;
    strategies: CapabilityOption[];
    by_parser?: Record<string, ParserChunkingCapabilities>;
  };
  runtime: Record<string, unknown>;
  output_types: string[];
  job_statuses: JobStatus[];
}

export type IngestorSettingKind =
  | "boolean"
  | "integer"
  | "number"
  | "text"
  | "list"
  | "secret"
  | "select";

export interface IngestorSettingOption {
  value: string;
  label: string;
}

export interface IngestorSettingField {
  key: string;
  env_var: string;
  label: string;
  group: string;
  kind: IngestorSettingKind;
  value: unknown;
  source: "env" | "sqlite";
  configured: boolean;
  secret: boolean;
  options: IngestorSettingOption[];
}

export interface IngestorSettingsResponse {
  fields: IngestorSettingField[];
  boot_time_keys: string[];
}

export interface IngestorSettingsUpdate {
  values?: Record<string, unknown>;
  reset_keys?: string[];
}

export interface IngestionOptions {
  parser: string;
  pipeline: Pipeline;
  chunkingEnabled: boolean;
  chunkingStrategy: ChunkingStrategy;
  dispatchSinkMode: DispatchSinkMode;
  ocrLanguages: string[];
  asyncMode: boolean;
  includeDocument: boolean;
  includeHtml: boolean;
}

export interface OutputFiles {
  output_dir: string;
  markdown: string;
  document_metadata_json?: string | null;
  rag_chunks_jsonl?: string | null;
  html?: string | null;
  raw_docling_json?: string | null;
  normalized_json?: string | null;
  text?: string | null;
  chunks_json?: string | null;
  embedding_input_jsonl?: string | null;
  confidence_json?: string | null;
  manifest_json?: string | null;
}

export interface IngestResponse {
  job_id: string;
  status: JobStatus;
  parser: string;
  document_id?: string | null;
  source_file_name?: string | null;
  created_at: string;
  status_url?: string | null;
  outputs_url?: string | null;
  input_path?: string | null;
  outputs?: OutputFiles | null;
  metadata: Record<string, unknown>;
  document?: unknown | null;
  chunks?: unknown[] | null;
  error?: string | null;
}

export interface IngestBatchResponse {
  created_at: string;
  jobs: IngestResponse[];
  failed: IngestResponse[];
}

export interface IngestionJob {
  job_id: string;
  status: JobStatus;
  parser: string;
  source_file_name?: string | null;
  input_path?: string | null;
  document_id?: string | null;
  outputs?: OutputFiles | null;
  metadata: Record<string, unknown>;
  error?: string | null;
  created_at: string;
  updated_at: string;
  started_at?: string | null;
  completed_at?: string | null;
}

export type IngestionRunSummary = IngestionJob & {
  run_id: string;
  attempt_number: number;
  pipeline?: string | null;
  status_url: string;
  outputs_url: string;
};

export interface IngestionDocumentSummary {
  document_id: string;
  content_hash: string;
  source_file_name?: string | null;
  size_bytes?: number | null;
  mime_type?: string | null;
  created_at: string;
  updated_at: string;
}

export interface IngestionDocumentEnvelope {
  document: IngestionDocumentSummary;
  latest_run?: IngestionRunSummary | null;
  runs: IngestionRunSummary[];
}

export interface IngestDocumentsResponse {
  documents: IngestionDocumentEnvelope[];
  failed: IngestionRunSummary[];
}

export interface IngestionRunListResponse {
  runs: IngestionRunSummary[];
}

export interface JobRemovalResult {
  job_id: string;
  previous_status: JobStatus;
  removed: boolean;
  parser_process_terminated: boolean;
  parser_process_signal?: number | null;
  parser_process_error?: string | null;
  removed_dispatch_queue_item: boolean;
  removed_artifact_count: number;
}

export interface ProgressUpdate {
  component?: string;
  stage?: string;
  message?: string;
  input_format?: string;
  pipeline?: string;
  page_count?: number;
  pages_completed?: number;
  pages_remaining?: number;
  percent_complete?: number;
  current_page?: number;
  updated_at?: string;
  details?: Record<string, unknown>;
}

export interface TrackedJob {
  local_id: string;
  document_id?: string;
  file_name: string;
  file_size: number;
  submitted_at: string;
  job_id?: string;
  response?: IngestResponse;
  job?: IngestionJob;
  runs?: IngestionRunSummary[];
  upload_error?: string;
  retained_file?: File;
}

export interface QueueJobSummary {
  job_id: string;
  status: JobStatus;
  parser: string;
  source_file_name?: string | null;
  document_id?: string | null;
  metadata: Record<string, unknown>;
  error?: string | null;
  created_at: string;
  updated_at: string;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface QueueStageMetrics {
  name: string;
  statuses: JobStatus[];
  count: number;
  jobs: QueueJobSummary[];
}

export interface DispatchQueueCounts {
  max_bulk_size: number;
  max_size: number;
  max_payload_bytes?: number | null;
  queued_count: number;
  in_flight_count: number;
  completed_count: number;
  failed_count: number;
}

export interface QueueMetrics {
  queue_backend: string;
  parser_queue_name: string;
  dispatch_queue_name: string;
  parser_process_count: number;
  parser_threads_per_process: number;
  active_parser_job_count: number;
  queued_parser_job_count: number;
  stale_parser_job_count: number;
  parser_worker_count: number;
  dispatch_worker_count: number;
  status_counts: Record<string, number>;
  stages: QueueStageMetrics[];
  dispatch_queue?: DispatchQueueCounts | null;
}
