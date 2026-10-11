import { API_BASE_URL } from './config';

export type ApiUser = {
  id: number;
  name: string;
  email: string;
  role: 'user' | 'admin' | string;
  created_at: string;
  updated_at?: string | null;
};

export type AuthResponse = {
  access_token: string;
  token_type: 'bearer' | string;
  user: ApiUser;
};

export type ApiSubmission = {
  id: number;
  user_id?: number;
  submission_type: 'text' | 'image' | 'both';
  detected_language?: string | null;
  combined_risk_score?: number | null;
  final_label: string;
  final_label_source: string;
  created_at: string;
  text_preview?: string | null;
  has_image?: boolean;
  dispute_count?: number;
  text_submission?: {
    id: number;
    input_text: string;
    detected_language?: string | null;
    text_prediction?: string | null;
    text_confidence?: number | null;
  } | null;
  image_submission?: {
    id: number;
    image_path: string;
    ocr_text?: string | null;
    ocr_confidence?: number | null;
    detected_language?: string | null;
    text_prediction?: string | null;
    text_confidence?: number | null;
    image_score?: number | null;
    manipulation_prediction?: string | null;
  } | null;
  explainability?: {
    highlighted_words?: string | null;
    heatmap_path?: string | null;
    explanation_summary?: string | null;
    model_version?: string | null;
  } | null;
};

export type ApiDispute = {
  id: number;
  submission_id: number;
  user_id: number;
  justification: string;
  evidence_link?: string | null;
  status: 'pending' | 'reviewed' | 'closed' | string;
  admin_decision?: 'uphold_ai' | 'override' | null;
  admin_comment?: string | null;
  override_label?: string | null;
  reviewed_at?: string | null;
  created_at: string;
  submission?: ApiSubmission | null;
  user?: ApiUser | null;
};

export class ApiError extends Error {
  constructor(message: string, public readonly status: number) {
    super(message);
    this.name = 'ApiError';
  }
}

function apiUrl(path: string) {
  if (!API_BASE_URL) {
    throw new Error('Backend URL is not configured. Set EXPO_PUBLIC_API_URL and restart Expo.');
  }
  const base = API_BASE_URL.replace(/\/$/, '');
  const versionedBase = base.endsWith('/api/v1') ? base : `${base}/api/v1`;
  return `${versionedBase}${path.startsWith('/') ? path : `/${path}`}`;
}

async function request<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
  const headers = new Headers(options.headers ?? {});
  headers.set('Accept', 'application/json');
  if (token) headers.set('Authorization', `Bearer ${token}`);
  if (options.body && typeof options.body === 'string') headers.set('Content-Type', 'application/json');

  let response: Response;
  try {
    response = await fetch(apiUrl(path), { ...options, headers });
  } catch {
    throw new Error(`Cannot reach the backend at ${API_BASE_URL}. Check the API URL and that FastAPI is running.`);
  }

  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const payload = await response.json();
      const detail = payload?.detail;
      message = typeof detail === 'string'
        ? detail
        : Array.isArray(detail)
          ? detail.map((item) => item?.msg ?? 'Invalid request').join('\n')
          : message;
    } catch {
      // Keep the status message for non-JSON server responses.
    }
    throw new ApiError(message, response.status);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

const json = (value: unknown): RequestInit => ({ method: 'POST', body: JSON.stringify(value) });

export function register(email: string, password: string, name: string) {
  return request<AuthResponse>('/auth/register', json({ email, password, name }));
}

export function login(email: string, password: string) {
  return request<AuthResponse>('/auth/login', json({ email, password }));
}

export function getCurrentUser(token: string) {
  return request<ApiUser>('/users/me', {}, token);
}

export function submitText(token: string, text: string) {
  return request<ApiSubmission>('/submissions/text', json({ text }), token);
}

export function submitImage(
  token: string,
  image: { uri: string; name: string; type: string },
) {
  const form = new FormData();
  form.append('file', image as unknown as Blob);
  return request<ApiSubmission>('/submissions/image', { method: 'POST', body: form }, token);
}

export function listSubmissions(token: string, skip = 0, limit = 50) {
  return request<ApiSubmission[]>(`/submissions?skip=${skip}&limit=${limit}`, {}, token);
}

export function getSubmission(token: string, id: string | number) {
  return request<ApiSubmission>(`/submissions/${id}`, {}, token);
}

export function submissionImageUrl(id: string | number) {
  return apiUrl(`/submissions/${id}/image`);
}

export function submissionHeatmapUrl(id: string | number) {
  return apiUrl(`/submissions/${id}/heatmap`);
}

export function listAdminSubmissions(token: string, skip = 0, limit = 100) {
  return request<ApiSubmission[]>(`/admin/submissions?skip=${skip}&limit=${limit}`, {}, token);
}

export function createDispute(
  token: string,
  payload: { submission_id: number; justification: string; evidence_link?: string },
) {
  return request<ApiDispute>('/disputes', json(payload), token);
}

export function listDisputes(token: string, status?: string, skip = 0, limit = 100) {
  const query = new URLSearchParams({ skip: String(skip), limit: String(limit) });
  if (status) query.set('status', status);
  return request<ApiDispute[]>(`/disputes?${query.toString()}`, {}, token);
}

export function getDispute(token: string, id: string | number) {
  return request<ApiDispute>(`/disputes/${id}`, {}, token);
}

export function reviewDispute(
  token: string,
  id: string | number,
  payload: { admin_decision: 'uphold_ai' | 'override'; admin_comment: string; override_label?: string },
) {
  return request<ApiDispute>(`/disputes/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  }, token);
}
