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
  /** Who set `verdict`: the AI, or an administrator who overrode it after a dispute. */
  verdictSource?: 'AI' | 'Admin';
  /** The AI's own verdict on the claim; differs from `verdict` after an admin override. Null when no claim was classified. */
  aiVerdict?: Verdict | null;
  /** Raw, uncalibrated model score 0–1 of the AI's verdict (not the admin's); not a probability that the claim is true. */
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
   * 'image_pair' (text in the image was classified as a news claim) or 'ai_or_real' (no usable text,
   * so no claim was checked). The picture itself is analysed either way. Null for text checks and
   * for images analysed before the branches existed.
   */
  analysisBranch: 'image_pair' | 'ai_or_real' | null;
  /** What OCR did on an image: null for text checks and older image rows. */
  ocrStatus: 'completed' | 'no_text_found' | 'unavailable' | 'dependency_missing' | string | null;
  /** Text model result for text read from an image (null when no text was classified). */
  ocrTextPrediction: string | null;
  ocrTextConfidence: number | null;
  textClassificationStatus: 'completed' | 'unavailable' | 'not_run' | null;
  /** The AI-generated vs real detector ('skipped' only on rows saved by older versions). */
  imageAnalysisStatus: 'completed' | 'unavailable' | 'skipped' | null;
  /** Grad-CAM heatmap: completed, unavailable (detector ran, no heatmap) or not_run. */
  gradcamStatus: 'completed' | 'unavailable' | 'not_run' | null;
  /** Chance the picture is AI-generated (0–100); null when the detector did not run. Not a claim verdict. */
  aiGeneratedLikelihood: Score100 | null;
  aiGeneratedLabel: string;
  dispute?: SubmissionDispute;
  /** Who filed the dispute (demo). */
  submitterEmail?: string;
  /** Human-in-the-loop outcome (admin console). */
  adminReview?: AdminReview;
};
