import { File } from 'expo-file-system';
import { Platform } from 'react-native';

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
  /** Admin list only. */
  user_email?: string | null;
  latest_dispute_id?: number | null;
  latest_dispute_status?: string | null;
  text_submission?: {
    id: number;
    input_text: string;
    detected_language?: string | null;
    text_prediction?: string | null;
    text_confidence?: number | null;
    processing_status?: 'completed' | 'unavailable';
  } | null;
  image_submission?: {
    id: number;
    image_path: string;
    ocr_text?: string | null;
    ocr_confidence?: number | null;
    detected_language?: string | null;
    text_prediction?: string | null;
    text_confidence?: number | null;
    /** Probability the picture is AI-generated (only on the ai_or_real branch). */
    image_score?: number | null;
    manipulation_prediction?: string | null;
    /** image_pair: text in the image was classified; ai_or_real: the picture itself was checked. */
    analysis_branch?: 'image_pair' | 'ai_or_real' | null;
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

export type ApiAdminStats = {
  users: number;
  submissions: number;
  submissions_by_label: Record<string, number>;
  submissions_by_type: Record<string, number>;
  admin_overrides: number;
  disputes: { total: number; pending: number; reviewed: number };
};

export class ApiError extends Error {
  constructor(message: string, public readonly status: number) {
    super(message);
    this.name = 'ApiError';
  }
}

type UnauthorizedHandler = (failedToken: string) => void;
let onUnauthorized: UnauthorizedHandler | null = null;

/** Called (by AuthContext) when a request made with a token gets 401, i.e. the session expired. */
export function setUnauthorizedHandler(handler: UnauthorizedHandler | null) {
  onUnauthorized = handler;
}

function apiUrl(path: string) {
  if (!API_BASE_URL) {
    throw new Error('Backend URL is not configured. Set EXPO_PUBLIC_API_URL and restart Expo.');
  }
  const base = API_BASE_URL.replace(/\/$/, '');
  const versionedBase = base.endsWith('/api/v1') ? base : `${base}/api/v1`;
  return `${versionedBase}${path.startsWith('/') ? path : `/${path}`}`;
}

async function send(path: string, options: RequestInit = {}, token?: string): Promise<Response> {
  const headers = new Headers(options.headers ?? {});
  headers.set('Accept', 'application/json');
  if (token) headers.set('Authorization', `Bearer ${token}`);
  if (options.body && typeof options.body === 'string') headers.set('Content-Type', 'application/json');

  let response: Response;
  try {
    response = await fetch(apiUrl(path), { ...options, headers });
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error);
    // Only blame the connection for real network failures; otherwise show what went wrong
    // (e.g. a request the app could not build), so the cause is not hidden.
    if (/network|failed to fetch|timed? ?out|connection|could not connect|offline/i.test(reason)) {
      throw new Error(`Cannot reach the backend at ${API_BASE_URL}. Check the API URL and that FastAPI is running.`);
    }
    throw new Error(`Could not send the request: ${reason}`);
  }

  if (!response.ok) {
    // Login itself sends no token, so a wrong password never triggers a sign-out here.
    if (response.status === 401 && token) onUnauthorized?.(token);
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
  return response;
}

async function request<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
  const response = await send(path, options, token);
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

/** One page of a list endpoint, plus the total across all pages (X-Total-Count header). */
export type Page<T> = { items: T[]; total: number };

async function requestPage<T>(path: string, token: string): Promise<Page<T>> {
  const response = await send(path, {}, token);
  const items = (await response.json()) as T[];
  const total = Number(response.headers.get('X-Total-Count'));
  return { items, total: response.headers.has('X-Total-Count') && Number.isFinite(total) ? total : items.length };
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

export async function submitImage(
  token: string,
  image: { uri: string; name: string; type: string },
) {
  const form = new FormData();
  if (Platform.OS === 'web') {
    // Browsers need real file bytes; the picker gives a blob:/data: URI.
    const blob = await (await globalThis.fetch(image.uri)).blob();
    form.append('file', blob, image.name);
  } else {
    // Expo SDK 57 replaces fetch with expo/fetch, which rejects React Native's old
    // `{ uri, name, type }` upload objects ("Unsupported FormDataPart implementation").
    // An expo-file-system File implements Blob, so expo/fetch can read it.
    form.append('file', new File(image.uri) as unknown as Blob);
  }
  return request<ApiSubmission>('/submissions/image', { method: 'POST', body: form }, token);
}

/** The signed-in user's own submissions, newest first. */
export function listSubmissions(token: string, skip = 0, limit = 50) {
  return requestPage<ApiSubmission>(`/submissions?skip=${skip}&limit=${limit}`, token);
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

/** Admin only: every user's submissions with submitter and latest dispute, newest first. */
export function listAdminSubmissions(token: string, skip = 0, limit = 50) {
  return requestPage<ApiSubmission>(`/admin/submissions?skip=${skip}&limit=${limit}`, token);
}

export function getAdminStats(token: string) {
  return request<ApiAdminStats>('/admin/stats', {}, token);
}

export function createDispute(
  token: string,
  payload: { submission_id: number; justification: string; evidence_link?: string },
) {
  return request<ApiDispute>('/disputes', json(payload), token);
}

/**
 * Disputes, newest first. Users always get their own; admins get everyone's
 * unless `mine` is set.
 */
export function listDisputes(
  token: string,
  { status, skip = 0, limit = 100, mine = false }: { status?: string; skip?: number; limit?: number; mine?: boolean } = {},
) {
  const query = new URLSearchParams({ skip: String(skip), limit: String(limit) });
  if (status) query.set('status', status);
  if (mine) query.set('mine', 'true');
  return requestPage<ApiDispute>(`/disputes?${query.toString()}`, token);
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
