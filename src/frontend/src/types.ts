export type JobStatus =
  | "pending"
  | "queued"
  | "running"
  | "parser_queued"
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
export type ChunkingStrategy = "hybrid" | "line_based" | "legacy_char";

export interface CapabilityOption {
  value: string;
  label: string;
  default?: boolean;
  supported_input_formats?: string[];
}

export interface IngestionCapabilities {
  service: string;
  max_upload_size_mb: number;
  allowed_upload_extensions: string[];
  parsers: CapabilityOption[];
  pipelines: CapabilityOption[];
  default_parser: string;
  default_pipeline: Pipeline;
  chunking: {
    enabled: boolean;
    default_strategy: ChunkingStrategy;
    strategies: CapabilityOption[];
  };
  runtime: Record<string, unknown>;
  output_types: string[];
  job_statuses: JobStatus[];
}

export interface IngestionOptions {
  parser: string;
  pipeline: Pipeline;
  chunkingEnabled: boolean;
  chunkingStrategy: ChunkingStrategy;
  asyncMode: boolean;
  includeDocument: boolean;
}

export interface OutputFiles {
  output_dir: string;
  raw_docling_json: string;
  normalized_json: string;
  markdown: string;
  text: string;
  html?: string | null;
  chunks_json?: string | null;
  embedding_input_jsonl?: string | null;
  confidence_json?: string | null;
  manifest_json: string;
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
  file_name: string;
  file_size: number;
  submitted_at: string;
  job_id?: string;
  response?: IngestResponse;
  job?: IngestionJob;
  upload_error?: string;
  retained_file?: File;
}
