import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';

import { getSubmission, listDisputes, listSubmissions, submissionHeatmapUrl, submissionImageUrl, type ApiDispute, type ApiSubmission } from './api';
import { useAuth } from './AuthContext';
import type { Submission, SubmissionDispute, Verdict } from '@/types/submission';

type SubmissionsContextValue = {
  /** The signed-in user's own submissions loaded so far (newest first). */
  submissions: Submission[];
  /** How many submissions the user has in total, across all pages. */
  total: number;
  /** How many disputes the user has filed in total. */
  disputeTotal: number;
  hasMore: boolean;
  loading: boolean;
  loadingMore: boolean;
  loadError: string | null;
  getById: (id: string) => Submission | undefined;
  refreshSubmissions: () => Promise<void>;
  /** Load the next page of the user's history. */
  loadMore: () => Promise<void>;
  loadSubmissionDetail: (id: string) => Promise<Submission>;
  addServerSubmission: (item: ApiSubmission, imageUri?: string | null) => string;
  updateSubmission: (id: string, patch: Partial<Submission>) => void;
};

const SubmissionsContext = createContext<SubmissionsContextValue | null>(null);

/** Rows per request when paging through history. */
const PAGE_SIZE = 50;

export function verdictFromApi(label: string): Verdict {
  if (label.toLowerCase() === 'real') return 'credible';
  if (label.toLowerCase() === 'fake') return 'misleading';
  return 'uncertain';
}

export function fromApi(item: ApiSubmission, imageUri?: string | null): Submission {
  const text = item.text_submission?.input_text ?? item.text_preview ?? item.image_submission?.ocr_text ?? '';
  const textModelUnavailable = item.explainability?.model_version === 'text-model-unavailable'
    || item.explainability?.model_version?.startsWith('stub');
  const confidence = textModelUnavailable
    ? null
    : item.text_submission?.text_confidence ?? item.image_submission?.text_confidence ?? null;
  const imageScore = item.image_submission?.image_score;
  let highlightedWords: Submission['highlightedWords'];
  try {
    const parsed = item.explainability?.highlighted_words;
    if (parsed) highlightedWords = JSON.parse(parsed);
  } catch {
    highlightedWords = undefined;
  }
  return {
    id: String(item.id),
    createdAt: Date.parse(item.created_at) || Date.now(),
    kind: item.submission_type === 'both' ? 'both' : item.submission_type,
    textPreview: text ? text.slice(0, 280) : undefined,
    detectedLanguage: item.detected_language
      ?? item.text_submission?.detected_language
      ?? item.image_submission?.detected_language
      ?? null,
    processingStatus: item.text_submission?.processing_status ?? null,
    imageUri: imageUri ?? (item.image_submission || item.has_image ? submissionImageUrl(item.id) : null),
    verdict: verdictFromApi(item.final_label),
    confidence,
    riskScore: item.combined_risk_score ?? null,
    summary: item.explainability?.explanation_summary ?? 'The backend did not return an explanation for this submission.',
    highlightedWords,
    heatmapPath: item.explainability?.heatmap_path ? submissionHeatmapUrl(item.id) : null,
    languageQuality: null,
    languageQualityLabel: 'Not provided by the current backend.',
    sourceCredibility: null,
    sourceCredibilityLabel: 'Not provided by the current backend.',
    analysisBranch: item.image_submission?.analysis_branch ?? null,
    aiGeneratedLikelihood: imageScore == null ? null : Math.round(imageScore * 100),
    aiGeneratedLabel: item.image_submission?.manipulation_prediction ?? 'Not evaluated by a connected image model.',
  };
}

/** An admin-list row: the submitter and the latest dispute come with the submission. */
export function fromAdminApi(item: ApiSubmission): Submission {
  const row = fromApi(item);
  return {
    ...row,
    submitterEmail: item.user_email ?? undefined,
    dispute: item.latest_dispute_id
      ? { id: String(item.latest_dispute_id), message: '', createdAt: row.createdAt, status: item.latest_dispute_status ?? 'pending' }
      : undefined,
  };
}

function disputeFromApi(dispute: ApiDispute): SubmissionDispute {
  return {
    id: String(dispute.id),
    message: dispute.justification,
    createdAt: Date.parse(dispute.created_at) || Date.now(),
    status: dispute.status,
    evidenceLink: dispute.evidence_link,
  };
}

function withDisputes(rows: Submission[], disputes: ApiDispute[]): Submission[] {
  const bySubmission = new Map<number, ApiDispute>();
  for (const dispute of disputes) {
    if (!bySubmission.has(dispute.submission_id)) bySubmission.set(dispute.submission_id, dispute);
  }
  return rows.map((row) => {
    const dispute = bySubmission.get(Number(row.id));
    if (!dispute) return row;
    const reviewedAt = dispute.reviewed_at ? Date.parse(dispute.reviewed_at) : NaN;
    const adminReview = dispute.admin_decision ? {
      note: dispute.admin_comment ?? '',
      resolution: dispute.admin_decision,
      overrideVerdict: dispute.override_label ? verdictFromApi(dispute.override_label) : undefined,
      reviewedAt: Number.isFinite(reviewedAt) ? reviewedAt : Date.now(),
    } as Submission['adminReview'] : undefined;
    return {
      ...row,
      dispute: disputeFromApi(dispute),
      submitterEmail: dispute.user?.email,
      adminReview,
    };
  });
}

/** Fetch every dispute the signed-in user filed (all pages), newest first. */
async function listAllMyDisputes(token: string) {
  const all: ApiDispute[] = [];
  let total = 0;
  do {
    const page = await listDisputes(token, { mine: true, skip: all.length, limit: 100 });
    all.push(...page.items);
    total = page.total;
    if (page.items.length === 0) break;
  } while (all.length < total);
  return { items: all, total };
}

export function SubmissionsProvider({ children }: { children: React.ReactNode }) {
  const { accessToken, user, ready } = useAuth();
  // The signed-in user's OWN submissions, newest first, loaded page by page (admins included).
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [total, setTotal] = useState(0);
  const [disputeTotal, setDisputeTotal] = useState(0);
  // Submissions opened by id that are not in the list above (e.g. an admin viewing another
  // user's result). Kept apart so they never show up in the user's own history.
  const [detailCache, setDetailCache] = useState<Record<string, Submission>>({});
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const submissionsRef = useRef(submissions);
  const disputesRef = useRef<ApiDispute[]>([]);
  // Bumped on every refresh so a slow, older response can't overwrite a newer one.
  const generation = useRef(0);

  useEffect(() => { submissionsRef.current = submissions; }, [submissions]);

  const reset = useCallback(() => {
    generation.current++;
    disputesRef.current = [];
    setSubmissions([]);
    setTotal(0);
    setDisputeTotal(0);
    setDetailCache({});
  }, []);

  const refreshSubmissions = useCallback(async () => {
    if (!accessToken || !user) {
      reset();
      return;
    }
    const current = ++generation.current;
    setLoading(true);
    setLoadError(null);
    try {
      const [page, disputes] = await Promise.all([
        listSubmissions(accessToken, 0, PAGE_SIZE),
        listAllMyDisputes(accessToken),
      ]);
      if (current !== generation.current) return;
      disputesRef.current = disputes.items;
      setSubmissions(withDisputes(page.items.map((item) => fromApi(item)), disputes.items));
      setTotal(page.total);
      setDisputeTotal(disputes.total);
    } catch (error) {
      if (current !== generation.current) return;
      setLoadError(error instanceof Error ? error.message : 'Could not load submissions.');
      throw error;
    } finally {
      if (current === generation.current) setLoading(false);
    }
  }, [accessToken, user, reset]);

  const hasMore = submissions.length < total;

  const loadMore = useCallback(async () => {
    if (!accessToken || loading || loadingMore || submissionsRef.current.length >= total) return;
    const current = generation.current;
    setLoadingMore(true);
    try {
      const page = await listSubmissions(accessToken, submissionsRef.current.length, PAGE_SIZE);
      if (current !== generation.current) return;
      const next = withDisputes(page.items.map((item) => fromApi(item)), disputesRef.current);
      setSubmissions((rows) => {
        const seen = new Set(rows.map((row) => row.id));
        return [...rows, ...next.filter((row) => !seen.has(row.id))];
      });
      setTotal(page.total);
    } catch (error) {
      if (current === generation.current) setLoadError(error instanceof Error ? error.message : 'Could not load more submissions.');
    } finally {
      if (current === generation.current) setLoadingMore(false);
    }
  }, [accessToken, loading, loadingMore, total]);

  useEffect(() => {
    if (!ready) return;
    if (!accessToken) {
      reset();
      return;
    }
    void refreshSubmissions().catch(() => undefined);
  }, [ready, accessToken, refreshSubmissions, reset]);

  const getById = useCallback(
    (id: string) => submissions.find((item) => item.id === id) ?? detailCache[id],
    [submissions, detailCache],
  );

  const loadSubmissionDetail = useCallback(async (id: string) => {
    if (!accessToken) throw new Error('Sign in to load this submission.');
    const detail = await getSubmission(accessToken, id);
    const current = submissionsRef.current.find((item) => item.id === id);
    const mapped = {
      ...fromApi(detail, current?.imageUri),
      dispute: current?.dispute,
      submitterEmail: current?.submitterEmail,
      adminReview: current?.adminReview,
    };
    if (current) {
      setSubmissions((rows) => rows.map((row) => row.id === id ? mapped : row));
    } else {
      setDetailCache((cache) => ({ ...cache, [id]: mapped }));
    }
    return mapped;
  }, [accessToken]);

  const addServerSubmission = useCallback((item: ApiSubmission, imageUri?: string | null) => {
    const row = fromApi(item, imageUri);
    if (!submissionsRef.current.some((entry) => entry.id === row.id)) setTotal((count) => count + 1);
    setSubmissions((previous) => [row, ...previous.filter((entry) => entry.id !== row.id)]);
    return row.id;
  }, []);

  const updateSubmission = useCallback((id: string, patch: Partial<Submission>) => {
    const existing = submissionsRef.current.find((row) => row.id === id);
    if (patch.dispute && existing && !existing.dispute) setDisputeTotal((count) => count + 1);
    setSubmissions((rows) => rows.map((row) => row.id === id ? { ...row, ...patch } : row));
    setDetailCache((cache) => (cache[id] ? { ...cache, [id]: { ...cache[id], ...patch } } : cache));
  }, []);

  const value = useMemo(() => ({
    submissions, total, disputeTotal, hasMore, loading, loadingMore, loadError, getById, refreshSubmissions,
    loadMore, loadSubmissionDetail, addServerSubmission, updateSubmission,
  }), [submissions, total, disputeTotal, hasMore, loading, loadingMore, loadError, getById, refreshSubmissions,
    loadMore, loadSubmissionDetail, addServerSubmission, updateSubmission]);

  return <SubmissionsContext.Provider value={value}>{children}</SubmissionsContext.Provider>;
}

export function useSubmissions() {
  const ctx = useContext(SubmissionsContext);
  if (!ctx) throw new Error('useSubmissions must be used within SubmissionsProvider');
  return ctx;
}
