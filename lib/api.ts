import type { Verdict } from '@/types/submission';

import { API_BASE_URL } from './config';

export type AnalyzeResponse = {
  verdict: Verdict;
  confidence: number;
  summary: string;
  languageQuality: number;
  languageQualityLabel: string;
  sourceCredibility: number;
  sourceCredibilityLabel: string;
  manipulationLikelihood: number | null;
  manipulationLabel: string;
};

function clamp01(n: number) {
  return Math.min(1, Math.max(0, n));
}

function mockScores(payload: { text: string; hasImage: boolean; verdict: Verdict; confidence: number }) {
  const { text, hasImage, verdict, confidence } = payload;
  const len = text.length;
  const baseLang = verdict === 'credible' ? 78 : verdict === 'misleading' ? 52 : 64;
  const langJitter = (len % 17) - 8;
  const languageQuality = Math.round(Math.min(100, Math.max(12, baseLang + langJitter)));

  let languageQualityLabel = 'Moderate — mixed script or informal Roman Urdu may reduce parser confidence.';
  if (languageQuality >= 75) {
    languageQualityLabel = 'Strong — text is clear and normalization is reliable for this sample.';
  } else if (languageQuality < 45) {
    languageQualityLabel = 'Weak — short fragments, heavy code-switching, or OCR noise detected.';
  }

  const srcBase = verdict === 'credible' ? 72 : verdict === 'misleading' ? 38 : 55;
  const sourceCredibility = Math.round(Math.min(100, Math.max(8, srcBase + (len % 11) - 5)));
  let sourceCredibilityLabel = 'Mixed — limited alignment with high-trust outlet phrasing in training data.';
  if (sourceCredibility >= 70) {
    sourceCredibilityLabel = 'Higher — wording and entities resemble patterns seen in verified reporting.';
  } else if (sourceCredibility < 40) {
    sourceCredibilityLabel = 'Lower — sensational framing or weak attribution typical of unverified chains.';
  }

  let manipulationLikelihood: number | null = null;
  let manipulationLabel = 'Not evaluated — no image attached.';
  if (hasImage) {
    const manip = Math.round(Math.min(100, Math.max(5, 35 + (len % 23) + (verdict === 'misleading' ? 22 : verdict === 'credible' ? -12 : 4))));
    manipulationLikelihood = manip;
    if (manip >= 60) {
      manipulationLabel = 'Elevated — compression artifacts or splice-like boundaries warrant expert review.';
    } else if (manip >= 35) {
      manipulationLabel = 'Moderate — some cues overlap with benign screenshots; not conclusive alone.';
    } else {
      manipulationLabel = 'Lower — no strong manipulation signature from the lightweight vision stub.';
    }
  }

  return {
    languageQuality,
    languageQualityLabel,
    sourceCredibility,
    sourceCredibilityLabel,
    manipulationLikelihood,
    manipulationLabel,
    confidence: clamp01(confidence),
  };
}

/**
 * Calls the backend when `API_BASE_URL` is set; otherwise returns a deterministic mock
 * so the UI can be developed before the FastAPI service exists.
 */
export async function analyzeSubmission(payload: {
  text?: string;
  imageUri?: string | null;
}): Promise<AnalyzeResponse> {
  const trimmed = payload.text?.trim() ?? '';
  const hasImage = Boolean(payload.imageUri);
  if (!trimmed && !hasImage) {
    throw new Error('Please enter text or attach an image.');
  }

  if (API_BASE_URL) {
    const body = new FormData();
    if (trimmed) body.append('text', trimmed);
    if (payload.imageUri) {
      const name = payload.imageUri.split('/').pop() ?? 'upload.jpg';
      body.append('file', {
        uri: payload.imageUri,
        name,
        type: 'image/jpeg',
      } as unknown as Blob);
    }
    const res = await fetch(`${API_BASE_URL.replace(/\/$/, '')}/analyze`, {
      method: 'POST',
      body,
    });
    if (!res.ok) {
      const err = await res.text().catch(() => res.statusText);
      throw new Error(err || `Request failed (${res.status})`);
    }
    const raw = (await res.json()) as Partial<AnalyzeResponse> & { verdict: Verdict };
    const baseConf = typeof raw.confidence === 'number' ? raw.confidence : 0.62;
    const extras = mockScores({
      text: trimmed,
      hasImage,
      verdict: raw.verdict,
      confidence: baseConf,
    });
    return {
      verdict: raw.verdict,
      confidence: baseConf,
      summary: raw.summary ?? 'Analysis complete.',
      languageQuality: raw.languageQuality ?? extras.languageQuality,
      languageQualityLabel: raw.languageQualityLabel ?? extras.languageQualityLabel,
      sourceCredibility: raw.sourceCredibility ?? extras.sourceCredibility,
      sourceCredibilityLabel: raw.sourceCredibilityLabel ?? extras.sourceCredibilityLabel,
      manipulationLikelihood:
        raw.manipulationLikelihood !== undefined ? raw.manipulationLikelihood : extras.manipulationLikelihood,
      manipulationLabel: raw.manipulationLabel ?? extras.manipulationLabel,
    };
  }

  await new Promise((r) => setTimeout(r, 700));
  const hash = (trimmed.length + (hasImage ? 17 : 0)) % 3;
  const verdicts: Verdict[] = ['uncertain', 'credible', 'misleading'];
  const verdict = verdicts[hash];
  const confidence = 0.548 + hash * 0.117 + (trimmed.length % 7) * 0.012;
  const extras = mockScores({ text: trimmed, hasImage, verdict, confidence });
  const summary =
    verdict === 'credible'
      ? 'Mock: signals align with patterns often seen in verified reporting. Replace with model output when the API is live.'
      : verdict === 'misleading'
        ? 'Mock: several cues match known misinformation templates. This is placeholder text for development.'
        : 'Mock: mixed signals — Roman Urdu or partial OCR can lower confidence until your backend responds.';

  return {
    verdict,
    summary,
    ...extras,
  };
}
