export interface Page<T> { items: T[]; next_cursor: string | null }
export interface Project {
  id: string; title: string; brief: string; head_revision_id: string | null;
  created_at: string; updated_at: string;
}
export const features = {
  rhythm: '리듬', energy: '에너지', atmosphere: '분위기',
  instrumentation: '악기 구성', harmony: '화성', production_texture: '프로덕션 질감'
} as const;
export type Weights = Record<keyof typeof features, number>;
export interface Reference {
  id: string; project_id: string; asset_id: string; label: string; version: number;
  weights: Weights; validation_state: 'pending' | 'ready' | 'rejected';
  error: { code: string; message: string } | null;
  audio_metadata: { duration_seconds: number; sample_rate: number; channels: number; frame_count: number; format: string } | null;
}
export interface Job {
  id: string; project_id: string; kind: string; state: string; stage: string;
  progress: number | null; is_mock: boolean; base_revision_id: string | null;
  cancel_requested_at: string | null; result_revision_id: string | null;
  needs_review: boolean; created_at: string; updated_at: string;
  error: { code: string; message: string } | null;
}
export interface Revision { id: string; parent_revision_id: string | null; created_at: string; is_mock?: boolean }
export interface GenerateRequest {
  kind: 'mock_song'; base_revision_id: string | null; reference_ids: string[];
  brief: { prompt: string; duration_seconds: number; language: string; genre: string | null };
  seed: number | null;
}
export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) { super(message); }
}
async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  const response = await fetch(`/api/v1${path}`, { ...options, headers });
  const payload = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(response.status, payload?.error?.code ?? 'http_error',
    payload?.error?.message ?? `요청을 처리하지 못했습니다 (${response.status}).`);
  return payload as T;
}
export const active = (job: Job) => !['completed', 'failed', 'cancelled'].includes(job.state);
const projectPath = (id: string) => `/projects/${encodeURIComponent(id)}`;
export const api = {
  projects: (cursor?: string) => request<Page<Project>>(`/projects?limit=50${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`),
  createProject: (title: string, brief: string) => request<Project>('/projects', { method: 'POST', body: JSON.stringify({ title, brief }) }),
  project: (id: string) => request<Project>(projectPath(id)),
  references: (id: string) => request<Page<Reference>>(`${projectPath(id)}/references`),
  upload: (id: string, file: File) => {
    const body = new FormData(); body.append('file', file); body.append('label', Array.from(file.name).slice(0, 160).join(''));
    return request<{ reference: Reference; validation_job: Job }>(`${projectPath(id)}/references`, { method: 'POST', body });
  },
  weights: (id: string, reference: Reference, weights: Weights) => request<Reference>(`${projectPath(id)}/references/${reference.id}`, {
    method: 'PATCH', body: JSON.stringify({ expected_version: reference.version, weights })
  }),
  jobs: (id: string) => request<Page<Job>>(`${projectPath(id)}/jobs?limit=100`),
  activeJobs: async (id: string): Promise<Job[]> => {
    const jobs: Job[] = [];
    let cursor: string | null = null;
    do {
      const page: Page<Job> = await request<Page<Job>>(`${projectPath(id)}/jobs?active_only=true&limit=100${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`);
      jobs.push(...page.items); cursor = page.next_cursor;
    } while (cursor);
    return jobs;
  },
  referenceContent: (reference: Reference) => `/api/v1${projectPath(reference.project_id)}/assets/${encodeURIComponent(reference.asset_id)}/content`,
  job: (id: string, jobId: string) => request<Job>(`${projectPath(id)}/jobs/${jobId}`),
  cancel: (id: string, jobId: string) => request<Job>(`${projectPath(id)}/jobs/${jobId}/cancel`, { method: 'POST' }),
  generate: (id: string, body: GenerateRequest, key: string) => request<Job>(`${projectPath(id)}/generate`, {
    method: 'POST', headers: { 'Idempotency-Key': key }, body: JSON.stringify(body)
  }),
  revisions: (id: string) => request<Page<Revision>>(`${projectPath(id)}/revisions?limit=100`),
  revision: (id: string, revisionId: string) => request<Record<string, unknown>>(`${projectPath(id)}/revisions/${revisionId}`)
};
