import {
  AlertTriangle,
  CheckCircle2,
  Copy,
  Download,
  FileText,
  Loader2,
  RefreshCw,
  RotateCcw,
  Server,
  Settings2,
  UploadCloud,
  X,
} from "lucide-react";
import { ChangeEvent, DragEvent, FormEvent, useEffect, useMemo, useRef, useState } from "react";

import {
  defaultApiBaseUrl,
  getCapabilities,
  getJobs,
  outputUrl,
  uploadFiles,
} from "./api";
import { createLocalId } from "./id";
import {
  formatBytes,
  isTerminalStatus,
  lifecycle,
  metadataValue,
  phaseState,
  progressHistory,
  progressPercent,
  progressUpdate,
  statusLabel,
} from "./status";
import type {
  CapabilityOption,
  IngestionCapabilities,
  IngestionJob,
  IngestionOptions,
  JobStatus,
  TrackedJob,
} from "./types";

const persistedJobsKey = "ingest-orquestator.frontend.jobs";
const jobPollingIntervalMs = 5000;

const defaultOptions: IngestionOptions = {
  parser: "docling",
  pipeline: "standard",
  chunkingEnabled: true,
  chunkingStrategy: "hybrid",
  asyncMode: false,
  includeDocument: true,
};

function App() {
  const [apiBaseUrl] = useState(defaultApiBaseUrl);
  const [capabilities, setCapabilities] = useState<IngestionCapabilities | null>(null);
  const [capabilityError, setCapabilityError] = useState<string | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [jobs, setJobs] = useState<TrackedJob[]>(() => restoreJobs());
  const [options, setOptions] = useState<IngestionOptions>(() => restoreOptions());
  const [submitting, setSubmitting] = useState(false);
  const [activeFilter, setActiveFilter] = useState<"all" | "active" | "completed" | "failed">(
    "all",
  );
  const jobsRef = useRef(jobs);

  useEffect(() => {
    let ignore = false;
    getCapabilities(apiBaseUrl)
      .then((data) => {
        if (ignore) {
          return;
        }
        setCapabilities(data);
        setCapabilityError(null);
        setOptions((current) => ({
          ...current,
          parser: current.parser || data.default_parser,
          pipeline: current.pipeline || data.default_pipeline,
          chunkingEnabled: current.chunkingEnabled ?? data.chunking.enabled,
          chunkingStrategy: current.chunkingStrategy || data.chunking.default_strategy,
        }));
      })
      .catch((error: Error) => {
        if (!ignore) {
          setCapabilityError(error.message);
        }
      });
    return () => {
      ignore = true;
    };
  }, [apiBaseUrl]);

  useEffect(() => {
    localStorage.setItem(persistedJobsKey, JSON.stringify(jobs.map(stripFile)));
    jobsRef.current = jobs;
  }, [jobs]);

  useEffect(() => {
    localStorage.setItem("ingest-orquestator.frontend.options", JSON.stringify(options));
  }, [options]);

  useEffect(() => {
    let cancelled = false;
    let inFlight = false;
    const poll = async () => {
      if (inFlight) {
        return;
      }
      const active = jobsRef.current.filter(
        (job) => job.job_id && !isTerminalStatus(job.job?.status),
      );
      if (active.length === 0) {
        return;
      }
      inFlight = true;
      const jobIds = active.map((tracked) => tracked.job_id!);
      const updates = await getJobs(jobIds, apiBaseUrl).catch(() => []);
      inFlight = false;
      if (cancelled) {
        return;
      }
      const updatesById = new Map(updates.map((job) => [job.job_id, job]));
      setJobs((current) =>
        current.map((tracked) => {
          const update = tracked.job_id ? updatesById.get(tracked.job_id) : undefined;
          if (!update) {
            return tracked;
          }
          return { ...tracked, job: update };
        }),
      );
    };

    void poll();
    const interval = window.setInterval(poll, jobPollingIntervalMs);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [apiBaseUrl]);

  const filteredJobs = useMemo(
    () =>
      jobs.filter((job) => {
        const status = job.job?.status ?? job.response?.status;
        if (activeFilter === "all") {
          return true;
        }
        if (activeFilter === "active") {
          return !job.upload_error && !isTerminalStatus(status);
        }
        if (activeFilter === "completed") {
          return status === "completed";
        }
        return job.upload_error !== undefined || status === "failed";
      }),
    [activeFilter, jobs],
  );

  const summary = useMemo(() => {
    const total = jobs.length;
    const completed = jobs.filter((job) => job.job?.status === "completed").length;
    const failed = jobs.filter((job) => job.upload_error || job.job?.status === "failed").length;
    return {
      total,
      active: Math.max(total - completed - failed, 0),
      completed,
      failed,
    };
  }, [jobs]);

  function addFiles(nextFiles: File[]) {
    setFiles((current) => {
      const merged = [...current];
      for (const file of nextFiles) {
        const duplicate = merged.some(
          (candidate) =>
            candidate.name === file.name &&
            candidate.size === file.size &&
            candidate.lastModified === file.lastModified,
        );
        if (!duplicate) {
          merged.push(file);
        }
      }
      return merged;
    });
  }

  function removeFile(index: number) {
    setFiles((current) => current.filter((_, candidateIndex) => candidateIndex !== index));
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (files.length === 0 || submitting) {
      return;
    }

    const submittedFiles = [...files];
    const pendingJobs = submittedFiles.map((file) => ({
      local_id: createLocalId(),
      file_name: file.name,
      file_size: file.size,
      retained_file: file,
      submitted_at: new Date().toISOString(),
    }));
    setJobs((current) => [...pendingJobs, ...current]);
    setSubmitting(true);

    try {
      const responses = await uploadFiles(submittedFiles, options, apiBaseUrl);
      setJobs((current) =>
        current.map((tracked) => {
          const response = responses.find(
            (candidate) => candidate.source_file_name === tracked.file_name,
          );
          if (!response) {
            return tracked;
          }
          return {
            ...tracked,
            job_id: response.job_id,
            response,
            upload_error: response.error ?? undefined,
          };
        }),
      );
      setFiles([]);
    } catch (error) {
      setJobs((current) =>
        current.map((tracked) =>
          pendingJobs.some((pending) => pending.local_id === tracked.local_id)
            ? { ...tracked, upload_error: (error as Error).message }
            : tracked,
        ),
      );
    } finally {
      setSubmitting(false);
    }
  }

  async function retry(tracked: TrackedJob) {
    if (!tracked.retained_file) {
      return;
    }
    setFiles([tracked.retained_file]);
  }

  function clearFinished() {
    setJobs((current) =>
      current.filter((job) => {
        const status = job.job?.status ?? job.response?.status;
        return !job.upload_error && !isTerminalStatus(status);
      }),
    );
  }

  return (
    <main>
      <header className="app-header">
        <div>
          <p className="eyebrow">Open-RAG ingestion</p>
          <h1>Ingest Orquestator</h1>
        </div>
        <div className="server-strip">
          <Server size={18} aria-hidden="true" />
          <span>{apiBaseUrl}</span>
          <StatusDot ok={!capabilityError} />
        </div>
      </header>

      <section className="workspace">
        <UploadPanel
          capabilities={capabilities}
          capabilityError={capabilityError}
          files={files}
          options={options}
          submitting={submitting}
          onAddFiles={addFiles}
          onRemoveFile={removeFile}
          onOptionsChange={setOptions}
          onSubmit={submit}
        />

        <section className="dashboard" aria-label="Ingestion jobs">
          <div className="dashboard-toolbar">
            <div className="summary-grid">
              <SummaryCell label="Total" value={summary.total} />
              <SummaryCell label="Active" value={summary.active} />
              <SummaryCell label="Done" value={summary.completed} />
              <SummaryCell label="Failed" value={summary.failed} tone="danger" />
            </div>
            <div className="toolbar-actions">
              <FilterButton active={activeFilter === "all"} onClick={() => setActiveFilter("all")}>
                All
              </FilterButton>
              <FilterButton
                active={activeFilter === "active"}
                onClick={() => setActiveFilter("active")}
              >
                Active
              </FilterButton>
              <FilterButton
                active={activeFilter === "completed"}
                onClick={() => setActiveFilter("completed")}
              >
                Done
              </FilterButton>
              <FilterButton
                active={activeFilter === "failed"}
                onClick={() => setActiveFilter("failed")}
              >
                Failed
              </FilterButton>
              <button className="icon-button" type="button" onClick={clearFinished}>
                <X size={16} aria-hidden="true" />
                Clear done
              </button>
            </div>
          </div>

          {filteredJobs.length === 0 ? (
            <div className="empty-state">
              <FileText size={22} aria-hidden="true" />
              <span>No jobs in this view.</span>
            </div>
          ) : (
            <div className="job-list">
              {filteredJobs.map((tracked) => (
                <JobPanel
                  key={tracked.local_id}
                  apiBaseUrl={apiBaseUrl}
                  capabilities={capabilities}
                  tracked={tracked}
                  onRetry={retry}
                />
              ))}
            </div>
          )}
        </section>
      </section>
    </main>
  );
}

interface UploadPanelProps {
  capabilities: IngestionCapabilities | null;
  capabilityError: string | null;
  files: File[];
  options: IngestionOptions;
  submitting: boolean;
  onAddFiles: (files: File[]) => void;
  onRemoveFile: (index: number) => void;
  onOptionsChange: (options: IngestionOptions) => void;
  onSubmit: (event: FormEvent) => void;
}

function UploadPanel(props: UploadPanelProps) {
  const {
    capabilities,
    capabilityError,
    files,
    options,
    submitting,
    onAddFiles,
    onRemoveFile,
    onOptionsChange,
    onSubmit,
  } = props;

  function onFileInput(event: ChangeEvent<HTMLInputElement>) {
    onAddFiles(Array.from(event.target.files ?? []));
    event.target.value = "";
  }

  function onDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    onAddFiles(Array.from(event.dataTransfer.files));
  }

  const disabled = files.length === 0 || submitting;
  const fileErrors = files.map((file) => validateFile(file, capabilities));
  const hasInvalidFiles = fileErrors.some(Boolean);

  return (
    <form className="upload-panel" onSubmit={onSubmit}>
      <label
        className="drop-zone"
        onDragOver={(event) => event.preventDefault()}
        onDrop={onDrop}
      >
        <UploadCloud size={28} aria-hidden="true" />
        <span>Drop files or browse</span>
        <small>
          {capabilities
            ? `${capabilities.allowed_upload_extensions.join(", ")} up to ${
                capabilities.max_upload_size_mb
              } MB`
            : "Loading accepted formats"}
        </small>
        <input type="file" multiple onChange={onFileInput} />
      </label>

      {capabilityError ? (
        <div className="notice danger">
          <AlertTriangle size={16} aria-hidden="true" />
          <span>{capabilityError}</span>
        </div>
      ) : null}

      <div className="file-stack">
        {files.map((file, index) => {
          const error = fileErrors[index];
          return (
            <div
              className={`file-row ${error ? "invalid" : ""}`}
              key={`${file.name}-${file.size}-${file.lastModified}`}
            >
              <FileText size={16} aria-hidden="true" />
              <span title={file.name}>{file.name}</span>
              <small>{error ?? formatBytes(file.size)}</small>
              <button
                aria-label={`Remove ${file.name}`}
                className="tiny-button"
                type="button"
                onClick={() => onRemoveFile(index)}
              >
                <X size={14} aria-hidden="true" />
              </button>
            </div>
          );
        })}
      </div>

      <div className="options-panel">
        <div className="section-title">
          <Settings2 size={17} aria-hidden="true" />
          <span>Options</span>
        </div>
        <div className="field-grid">
          <SelectField
            label="Parser"
            value={options.parser}
            options={capabilities?.parsers ?? [{ value: "docling", label: "Docling" }]}
            onChange={(value) => onOptionsChange({ ...options, parser: value })}
          />
          <SelectField
            label="Pipeline"
            value={options.pipeline}
            options={
              capabilities?.pipelines ?? [
                { value: "standard", label: "Standard" },
                { value: "vlm", label: "VLM" },
                { value: "auto", label: "Auto" },
              ]
            }
            onChange={(value) =>
              onOptionsChange({ ...options, pipeline: value as IngestionOptions["pipeline"] })
            }
          />
          <SelectField
            label="Chunking"
            value={options.chunkingStrategy}
            options={
              capabilities?.chunking.strategies ?? [
                { value: "hybrid", label: "Hybrid" },
                { value: "line_based", label: "Line Based" },
                { value: "legacy_char", label: "Legacy Char" },
              ]
            }
            onChange={(value) =>
              onOptionsChange({
                ...options,
                chunkingStrategy: value as IngestionOptions["chunkingStrategy"],
              })
            }
            disabled={!options.chunkingEnabled}
          />
        </div>
        <div className="toggle-row">
          <Toggle
            checked={options.chunkingEnabled}
            label="Chunking"
            onChange={(checked) => onOptionsChange({ ...options, chunkingEnabled: checked })}
          />
          <Toggle
            checked={options.includeDocument}
            label="Include document"
            onChange={(checked) => onOptionsChange({ ...options, includeDocument: checked })}
          />
          <Toggle
            checked={options.asyncMode}
            label="Async mode"
            onChange={(checked) => onOptionsChange({ ...options, asyncMode: checked })}
          />
        </div>
      </div>

      <button className="submit-button" disabled={disabled || hasInvalidFiles} type="submit">
        {submitting ? <Loader2 className="spin" size={18} aria-hidden="true" /> : null}
        <UploadCloud size={18} aria-hidden="true" />
        Ingest {files.length || ""} {files.length === 1 ? "file" : "files"}
      </button>
    </form>
  );
}

interface JobPanelProps {
  apiBaseUrl: string;
  capabilities: IngestionCapabilities | null;
  tracked: TrackedJob;
  onRetry: (tracked: TrackedJob) => void;
}

function JobPanel({ apiBaseUrl, capabilities, tracked, onRetry }: JobPanelProps) {
  const job = tracked.job;
  const status = job?.status ?? tracked.response?.status;
  const percent = progressPercent(job, status);
  const progress = progressUpdate(job);
  const failed = Boolean(tracked.upload_error || status === "failed");
  const completed = status === "completed";
  const metadata = job?.metadata ?? tracked.response?.metadata ?? {};

  return (
    <article className={`job-panel ${failed ? "failed" : ""}`}>
      <div className="job-head">
        <div className="job-title">
          {completed ? (
            <CheckCircle2 size={18} aria-hidden="true" />
          ) : failed ? (
            <AlertTriangle size={18} aria-hidden="true" />
          ) : (
            <Loader2 className="spin" size={18} aria-hidden="true" />
          )}
          <div>
            <h2 title={tracked.file_name}>{tracked.file_name}</h2>
            <span>{formatBytes(tracked.file_size)}</span>
          </div>
        </div>
        <div className={`status-pill ${failed ? "danger" : completed ? "success" : ""}`}>
          {statusLabel(status)}
        </div>
      </div>

      <div className="progress-line" aria-label={`${percent}% complete`}>
        <span style={{ width: `${percent}%` }} />
      </div>
      <div className="progress-meta">
        <span>{percent}%</span>
        {progress?.stage ? <span>{progress.stage}</span> : null}
        {progress?.page_count ? (
          <span>
            {progress.pages_completed ?? 0}/{progress.page_count} pages
          </span>
        ) : null}
      </div>

      <PhaseTimeline status={status} />

      {tracked.job_id ? (
        <div className="job-id-row">
          <code>{tracked.job_id}</code>
          <button className="tiny-button" type="button" onClick={() => copy(tracked.job_id!)}>
            <Copy size={14} aria-hidden="true" />
          </button>
        </div>
      ) : null}

      {tracked.upload_error || job?.error ? (
        <div className="notice danger">
          <AlertTriangle size={16} aria-hidden="true" />
          <span>{tracked.upload_error || job?.error}</span>
          {tracked.retained_file ? (
            <button className="tiny-button" type="button" onClick={() => onRetry(tracked)}>
              <RotateCcw size={14} aria-hidden="true" />
            </button>
          ) : null}
        </div>
      ) : null}

      <ProgressHistory job={job} />

      {completed && job ? (
        <MetadataPanel
          apiBaseUrl={apiBaseUrl}
          capabilities={capabilities}
          job={job}
          metadata={metadata}
        />
      ) : null}
    </article>
  );
}

function PhaseTimeline({ status }: { status?: JobStatus }) {
  return (
    <ol className="timeline">
      {lifecycle.map((phase) => (
        <li className={phaseState(phase, status)} key={phase}>
          <span />
          {statusLabel(phase)}
        </li>
      ))}
    </ol>
  );
}

function ProgressHistory({ job }: { job?: IngestionJob }) {
  const history = progressHistory(job).slice(-5).reverse();
  if (history.length === 0) {
    return null;
  }
  return (
    <details className="history">
      <summary>Progress history</summary>
      <ul>
        {history.map((item, index) => (
          <li key={`${item.updated_at}-${index}`}>
            <span>{item.stage ?? item.component ?? "progress"}</span>
            <small>{item.message ?? metadataValue(item.details)}</small>
          </li>
        ))}
      </ul>
    </details>
  );
}

interface MetadataPanelProps {
  apiBaseUrl: string;
  capabilities: IngestionCapabilities | null;
  job: IngestionJob;
  metadata: Record<string, unknown>;
}

function MetadataPanel({ apiBaseUrl, capabilities, job, metadata }: MetadataPanelProps) {
  const keys = [
    "source_file_name",
    "input_format",
    "pipeline",
    "profile",
    "ocr_engine",
    "vlm_model",
    "vlm_runtime",
    "chunking_enabled",
    "chunking_strategy",
    "embedding_record_count",
    "page_count",
    "element_count",
    "chunk_count",
    "conversion_status",
    "warning_count",
  ];
  const confidence = metadata.confidence_summary;
  const outputTypes = capabilities?.output_types ?? [
    "manifest",
    "normalized",
    "markdown",
    "text",
    "chunks",
    "embedding",
    "confidence",
  ];

  return (
    <div className="metadata-grid">
      <section className="metadata-section">
        <h3>Metadata</h3>
        <dl>
          <dt>document_id</dt>
          <dd>{job.document_id ?? "pending"}</dd>
          {keys.map((key) => (
            <FragmentEntry keyName={key} value={metadata[key]} key={key} />
          ))}
        </dl>
      </section>

      <section className="metadata-section">
        <h3>Confidence</h3>
        <pre>{metadataValue(confidence)}</pre>
      </section>

      <section className="metadata-section outputs">
        <h3>Outputs</h3>
        <div className="output-grid">
          {outputTypes.map((type) => (
            <a
              href={outputUrl(job.job_id, type, apiBaseUrl)}
              key={type}
              rel="noreferrer"
              target="_blank"
            >
              <Download size={14} aria-hidden="true" />
              {type}
            </a>
          ))}
        </div>
      </section>
    </div>
  );
}

function FragmentEntry({ keyName, value }: { keyName: string; value: unknown }) {
  return (
    <>
      <dt>{keyName}</dt>
      <dd>{metadataValue(value)}</dd>
    </>
  );
}

function SelectField({
  disabled,
  label,
  onChange,
  options,
  value,
}: {
  disabled?: boolean;
  label: string;
  onChange: (value: string) => void;
  options: CapabilityOption[];
  value: string;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <select disabled={disabled} value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function Toggle({
  checked,
  label,
  onChange,
}: {
  checked: boolean;
  label: string;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className="toggle">
      <input
        checked={checked}
        type="checkbox"
        onChange={(event) => onChange(event.target.checked)}
      />
      <span>{label}</span>
    </label>
  );
}

function SummaryCell({
  label,
  tone,
  value,
}: {
  label: string;
  tone?: "danger";
  value: number;
}) {
  return (
    <div className={`summary-cell ${tone ?? ""}`}>
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}

function FilterButton({
  active,
  children,
  onClick,
}: {
  active: boolean;
  children: string;
  onClick: () => void;
}) {
  return (
    <button className={`filter-button ${active ? "active" : ""}`} type="button" onClick={onClick}>
      {children}
    </button>
  );
}

function StatusDot({ ok }: { ok: boolean }) {
  return <span className={`status-dot ${ok ? "ok" : "bad"}`} />;
}

function restoreOptions(): IngestionOptions {
  const raw = localStorage.getItem("ingest-orquestator.frontend.options");
  if (!raw) {
    return defaultOptions;
  }
  try {
    return { ...defaultOptions, ...(JSON.parse(raw) as Partial<IngestionOptions>) };
  } catch {
    return defaultOptions;
  }
}

function restoreJobs(): TrackedJob[] {
  const raw = localStorage.getItem(persistedJobsKey);
  if (!raw) {
    return [];
  }
  try {
    return (JSON.parse(raw) as TrackedJob[]).map(stripFile);
  } catch {
    return [];
  }
}

function stripFile(job: TrackedJob): TrackedJob {
  const { retained_file: _retainedFile, ...rest } = job;
  return rest;
}

function copy(text: string) {
  void navigator.clipboard?.writeText(text);
}

function validateFile(file: File, capabilities: IngestionCapabilities | null): string | null {
  if (!capabilities) {
    return null;
  }
  const extension = `.${file.name.split(".").pop()?.toLowerCase() ?? ""}`;
  if (!capabilities.allowed_upload_extensions.includes(extension)) {
    return `Unsupported ${extension}`;
  }
  const maxBytes = capabilities.max_upload_size_mb * 1024 * 1024;
  if (file.size > maxBytes) {
    return `Over ${capabilities.max_upload_size_mb} MB`;
  }
  return null;
}

export default App;
