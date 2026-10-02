export type Verdict = 'credible' | 'uncertain' | 'misleading';

/** 0–100 scale for UI (mock or API). */
export type Score100 = number;

export type SubmissionDispute = {
  message: string;
  createdAt: number;
};

export type AdminReview = {
  note: string;
  resolution: 'uphold_ai' | 'override';
  overrideVerdict?: Verdict;
  reviewedAt: number;
};

export type Submission = {
  id: string;
  createdAt: number;
  kind: 'text' | 'image' | 'both';
  textPreview?: string;
  imageUri?: string | null;
  verdict: Verdict;
  /** Calibrated model confidence 0–1 (display with extra precision). */
  confidence: number;
  summary: string;
  /** OCR / script clarity and normalization quality (0–100). */
  languageQuality: Score100;
  languageQualityLabel: string;
  /** How well the content matches known reputable patterns (0–100). */
  sourceCredibility: Score100;
  sourceCredibilityLabel: string;
  /** Image tampering / synthetic cues; null when no image was analyzed. */
  manipulationLikelihood: Score100 | null;
  manipulationLabel: string;
  dispute?: SubmissionDispute;
  /** Who filed the dispute (demo). */
  submitterEmail?: string;
  /** Human-in-the-loop outcome (admin console). */
  adminReview?: AdminReview;
};
