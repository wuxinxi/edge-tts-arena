export interface ModelItem {
  key: string;
  name: string;
  param_size: string;
  category: string;
  architecture: string;
  desc: string;
  repo_id: string;
  supported_languages: string[];
  default_voices: string[];
  supports_prompt: boolean;
  supports_clone: boolean;
  requires_reference_audio: boolean;
  order: number;
  is_downloaded: boolean;
  implementation_available: boolean;
  is_ready: boolean;
  unavailable_reason: string | null;
  missing_files: string[];
  profile: ModelProfile;
}

export type ModelOptions = Record<string, string | number | boolean>;
export interface ModelControl {
  key: string;
  label: string;
  type: 'number' | 'select' | 'boolean';
  default: string | number | boolean;
  min?: number;
  max?: number;
  step?: number;
  help: string;
  choices?: { value: string | number; label: string }[];
}
export interface ModelProfile {
  exploration_preset?: string;
  version: string;
  purpose: string;
  scenarios: string[];
  listen_for: string;
  source_url: string;
  speed_kind: 'native' | 'discrete' | 'postprocess';
  prompt_kind: 'none' | 'tokens' | 'instruction' | 'description';
  tips: string;
  language_note: string;
  controls: ModelControl[];
  presets: { key: string; label: string; options: ModelOptions; prompt: string }[];
  voices: { value: string; label: string }[];
}
export interface RunSettings {
  preset: string;
  preset_label: string;
  options: ModelOptions;
  effective_options: ModelOptions;
  prompt: string;
  speed: number;
  speed_mode: 'model' | 'output';
  speed_kind: string;
  version: string;
  reference: { source: 'none' | 'default' | 'uploaded'; text?: string; sha256?: string };
}

export interface HardwareInfo {
  os: string;
  chip: string;
  cpu_count: number;
  cpu_logical_count: number;
  total_memory_gb: number;
  available_memory_gb: number;
  used_memory_gb: number;
  memory_percent: number;
  mps: {
    torch_version: string;
    mps_available: boolean;
    mps_built: boolean;
    active_device: string;
  };
}

export interface GenerationMetrics {
  model_key: string;
  elapsed_time_sec: number;
  audio_duration_sec: number;
  rtf: number;
  ttfb_ms: number | null;
  memory_used_mb: number;
  memory_diff_mb: number;
  memory_peak_mb: number;
  memory_scope: string;
  timing_scope: string;
}

export interface GenerationResult {
  success: boolean;
  model_key: string;
  model_name: string;
  param_size: string;
  audio_file: string;
  audio_url: string;
  sample_rate: number;
  text: string;
  voice: string;
  metrics: GenerationMetrics;
  error?: string;
  device?: string;
  settings?: RunSettings;
  created_at?: string;
  record_url?: string;
  history_deleted_at?: string;
  evaluation?: { mode: 'uniform' | 'recommended'; scope: string } | null;
  task_key?: string;
  sample_id?: string;
  sample_label?: string;
  repeat_index?: number;
  listening_review?: ListeningReview;
  listening_review_error?: string;
}

export interface ListeningReview {
  verdict: 'unreviewed' | 'acceptable' | 'needs_work' | 'unusable';
  naturalness: 'unreviewed' | 'natural' | 'ordinary' | 'mechanical';
  expression: 'unreviewed' | 'appropriate' | 'flat' | 'exaggerated';
  issues: ('omission' | 'repetition' | 'cutoff' | 'pronunciation' | 'noise')[];
  notes: string;
  source?: 'human';
  updated_at?: string;
}

export interface EvaluationSample { id: string; label: string; text: string; listen_for: string }

export interface ComparisonJob {
  job_id: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
  created_at: string;
  text: string;
  benchmark_mode: 'uniform' | 'recommended';
  speed: number;
  reference_source: 'default' | 'uploaded';
  total: number;
  completed: number;
  successful: number;
  failed: number;
  current_model: string | null;
  repeats?: number;
  samples?: EvaluationSample[];
  model_keys?: string[];
  ref_text?: string;
  retry_of?: string | null;
  stop_requested?: boolean;
  error: string | null;
  models: { key: string; name: string; model_key?: string; sample_id?: string; sample_label?: string; repeat_index?: number; status: 'pending' | 'running' | 'succeeded' | 'failed' | 'skipped'; error?: string }[];
  results: GenerationResult[];
  deleted_at?: string;
}

export interface BatchPagination { total: number; page: number; page_size: number; pages: number }
