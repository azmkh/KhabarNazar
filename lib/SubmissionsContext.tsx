import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';

import { getSubmission, listAdminSubmissions, listDisputes, listSubmissions, submissionHeatmapUrl, submissionImageUrl, type ApiDispute, type ApiSubmission } from './api';
import { useAuth } from './AuthContext';
import type { Submission, SubmissionDispute, Verdict } from '@/types/submission';

type SubmissionsContextValue = {
  submissions: Submission[];
  loading: boolean;
  loadError: string | null;
  getById: (id: string) => Submission | undefined;
  refreshSubmissions: () => Promise<void>;
  loadSubmissionDetail: (id: string) => Promise<Submission>;
  addServerSubmission: (item: ApiSubmission, imageUri?: string | null) => string;
  updateSubmission: (id: string, patch: Partial<Submission>) => void;
};

const SubmissionsContext = createContext<SubmissionsContextValue | null>(null);

function verdictFromApi(label: string): Verdict {
  if (label.toLowerCase() === 'real') return 'credible';
  if (label.toLowerCase() === 'fake') return 'misleading';
  return 'uncertain';
}

function fromApi(item: ApiSubmission, imageUri?: string | null): Submission {
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
    manipulationLikelihood: imageScore == null ? null : Math.round(imageScore * 100),
    manipulationLabel: item.image_submission?.manipulation_prediction ?? 'Not evaluated by a connected image model.',
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

export function SubmissionsProvider({ children }: { children: React.ReactNode }) {
  const { accessToken, user, ready } = useAuth();
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const submissionsRef = useRef(submissions);

  useEffect(() => { submissionsRef.current = submissions; }, [submissions]);

  const refreshSubmissions = useCallback(async () => {
    if (!accessToken || !user) {
      setSubmissions([]);
      return;
    }
    setLoading(true);
    setLoadError(null);
    try {
      const [records, disputes] = await Promise.all([
        user.role === 'admin' ? listAdminSubmissions(accessToken) : listSubmissions(accessToken),
        listDisputes(accessToken),
      ]);
      setSubmissions(withDisputes(records.map((item) => fromApi(item)), disputes));
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Could not load submissions.';
      setLoadError(message);
      throw error;
    } finally {
      setLoading(false);
    }
  }, [accessToken, user]);

  useEffect(() => {
    if (!ready) return;
    if (!accessToken) {
      setSubmissions([]);
      return;
    }
    void refreshSubmissions().catch(() => undefined);
  }, [ready, accessToken, refreshSubmissions]);

  const getById = useCallback((id: string) => submissions.find((item) => item.id === id), [submissions]);

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
    setSubmissions((rows) => rows.some((row) => row.id === id)
      ? rows.map((row) => row.id === id ? mapped : row)
      : [mapped, ...rows]);
    return mapped;
  }, [accessToken]);

  const addServerSubmission = useCallback((item: ApiSubmission, imageUri?: string | null) => {
    const row = fromApi(item, imageUri);
    setSubmissions((previous) => [row, ...previous.filter((entry) => entry.id !== row.id)]);
    return row.id;
  }, []);

  const updateSubmission = useCallback((id: string, patch: Partial<Submission>) => {
    setSubmissions((rows) => rows.map((row) => row.id === id ? { ...row, ...patch } : row));
  }, []);

  const value = useMemo(() => ({
    submissions, loading, loadError, getById, refreshSubmissions, loadSubmissionDetail,
    addServerSubmission, updateSubmission,
  }), [submissions, loading, loadError, getById, refreshSubmissions, loadSubmissionDetail, addServerSubmission, updateSubmission]);

  return <SubmissionsContext.Provider value={value}>{children}</SubmissionsContext.Provider>;
}

export function useSubmissions() {
  const ctx = useContext(SubmissionsContext);
  if (!ctx) throw new Error('useSubmissions must be used within SubmissionsProvider');
  return ctx;
}
