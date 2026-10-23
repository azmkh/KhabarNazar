export type Verdict = 'credible' | 'uncertain' | 'misleading';

/** 0–100 scale for values supplied by an API. */
export type Score100 = number;

export type SubmissionDispute = {
  id: string;
  message: string;
  createdAt: number;
  status: 'pending' | 'reviewed' | 'closed' | string;
  evidenceLink?: string | null;
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
  /** Raw, uncalibrated model score 0–1; this is not a probability that the claim is true. */
  confidence: number | null;
  detectedLanguage: string | null;
  processingStatus: 'completed' | 'unavailable' | null;
  /** Probability the claim is fake (0–1), from the text classifier only; null when no claim was classified. */
  riskScore: number | null;
  summary: string;
  highlightedWords?: Array<{ word: string; contribution: number; direction: string }>;
  heatmapPath?: string | null;
  /** OCR / script clarity and normalization quality (0–100). */
  languageQuality: Score100 | null;
  languageQualityLabel: string;
  /** How well the content matches known reputable patterns (0–100). */
  sourceCredibility: Score100 | null;
  sourceCredibilityLabel: string;
  /**
   * Which image branch ran: 'image_pair' (text in the image was classified as a news claim) or
   * 'ai_or_real' (no usable text, so the picture was checked for AI generation). Null for text
   * checks and for images analysed before the two branches existed.
   */
  analysisBranch: 'image_pair' | 'ai_or_real' | null;
  /** Chance the picture is AI-generated (0–100); null when the detector did not run. Not a claim verdict. */
  aiGeneratedLikelihood: Score100 | null;
  aiGeneratedLabel: string;
  dispute?: SubmissionDispute;
  /** Who filed the dispute (demo). */
  submitterEmail?: string;
  /** Human-in-the-loop outcome (admin console). */
  adminReview?: AdminReview;
};
