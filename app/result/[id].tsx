import { useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';

import {
  AppText,
  AuthImage,
  Button,
  Card,
  ContentText,
  EmptyState,
  Icon,
  Meter,
  Tag,
  useAppTheme,
  verdictMeta,
} from '@/components/ui';
import { radius, space } from '@/constants/theme';
import { fullDate, languageLabel, percent } from '@/lib/format';
import { hrefDisputeDetail } from '@/lib/navigation';
import { useSubmissions } from '@/lib/SubmissionsContext';

export default function ResultScreen() {
  const { id: idParam } = useLocalSearchParams<{ id?: string | string[] }>();
  const id = Array.isArray(idParam) ? idParam[0] : idParam;
  const { getById, loadSubmissionDetail } = useSubmissions();
  const router = useRouter();
  const { colors } = useAppTheme();
  const row = id ? getById(id) : undefined;
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    let active = true;
    setDetailLoading(true);
    loadSubmissionDetail(id)
      .catch((error) => { if (active) setDetailError(error instanceof Error ? error.message : 'Could not load result.'); })
      .finally(() => { if (active) setDetailLoading(false); });
    return () => { active = false; };
  }, [id, loadSubmissionDetail]);

  if (!row) {
    return (
      <View style={[styles.center, { backgroundColor: colors.background }]}>
        {detailLoading ? (
          <EmptyState icon="scan-search" title="Loading result…" loading />
        ) : (
          <EmptyState icon="circle-alert" title="Result not found" message={detailError ?? undefined}
            actionLabel="Back" onAction={() => router.back()} />
        )}
      </View>
    );
  }

  const meta = verdictMeta(row.verdict, colors);
  const isImage = row.kind !== 'text';
  // Every image is analysed by the image detector (with Grad-CAM); OCR text is classified as the
  // news claim only when there was enough of it (the image-pair branch).
  const pictureChecked = row.analysisBranch === 'ai_or_real';
  const textInImageChecked = row.analysisBranch === 'image_pair';
  const ocrFailed = row.ocrStatus === 'unavailable' || row.ocrStatus === 'dependency_missing';
  // The backend scores each occurrence of a word; show each word once.
  const words = row.highlightedWords?.filter(
    (item, index, all) => all.findIndex((other) => other.word === item.word) === index,
  );
  // For text-only checks the risk is already shown in the verdict header.
  const hasExtraSignals = isImage || row.languageQuality != null || row.sourceCredibility != null;
  const adminVerdict = row.adminReview?.overrideVerdict ? verdictMeta(row.adminReview.overrideVerdict, colors) : null;

  return (
    <ScrollView style={{ backgroundColor: colors.background }} contentContainerStyle={styles.container}>
      {/* Verdict */}
      <View style={[styles.hero, { backgroundColor: meta.soft, borderColor: meta.color }]}>
        <View style={styles.heroTop}>
          <View style={[styles.heroIcon, { backgroundColor: colors.surface }]}>
            <Icon name={meta.icon} size={28} color={meta.color} />
          </View>
          <View style={styles.flex}>
            <AppText variant="overline" color={meta.color}>
              {row.adminReview?.resolution === 'override' ? 'AI verdict (overridden)' : 'Verdict'}
            </AppText>
            <AppText variant="title" color={meta.color}>{meta.label}</AppText>
          </View>
        </View>
        <View style={styles.heroStats}>
          <HeroStat label="Model score (uncalibrated)" value={percent(row.confidence)} />
          <HeroStat label="Fake-news risk" value={percent(row.riskScore)} />
        </View>
        <AppText variant="caption" color="textMuted">
          {isImage && !textInImageChecked
            ? 'No news claim was checked in this image (no usable text was read), so there is no '
              + 'fake-news verdict. The picture itself was analysed separately (see Image analysis below).'
            : 'The model score is an uncalibrated output, not a measure of truth. Risk is the estimated '
              + 'chance the content is fake. Neither is proof that a claim is true or false.'}
        </AppText>
      </View>

      {/* Human review outcome */}
      {row.adminReview ? (
        <Card>
          <View style={styles.rowGap}>
            <Icon name="badge-check" size={20} color="credible" />
            <View style={styles.flex}>
              <AppText variant="bodyStrong">
                {row.adminReview.resolution === 'override' && adminVerdict
                  ? `Reviewed: changed to ${adminVerdict.label.toLowerCase()}`
                  : 'Reviewed: AI verdict upheld'}
              </AppText>
              {row.adminReview.note ? (
                <AppText variant="body" color="textMuted" style={styles.mt4}>“{row.adminReview.note}”</AppText>
              ) : null}
              <AppText variant="caption" color="textSubtle" style={styles.mt4}>{fullDate(row.adminReview.reviewedAt)}</AppText>
            </View>
          </View>
        </Card>
      ) : null}

      {/* Submitted content */}
      <Card title={isImage ? 'Submitted image' : 'Submitted text'}>
        {row.imageUri ? (
          <View style={[styles.imageFrame, { backgroundColor: colors.surfaceMuted }]}>
            <AuthImage uri={row.imageUri} style={styles.image} resizeMode="contain" />
          </View>
        ) : null}
        {row.textPreview ? (
          <View style={row.imageUri ? styles.ocr : null}>
            {isImage ? (
              <AppText variant="overline" color="textSubtle" style={styles.mb6}>
                {textInImageChecked ? 'Text found in image (OCR), checked as the claim' : 'Text found in image (OCR)'}
              </AppText>
            ) : null}
            <ContentText>{row.textPreview}</ContentText>
          </View>
        ) : isImage && !ocrFailed ? (
          <AppText variant="caption" color="textMuted" style={styles.ocr}>No readable text was found in this image.</AppText>
        ) : null}
        {isImage && ocrFailed ? (
          <AppText variant="caption" color="uncertain" style={styles.ocr}>
            Text reading (OCR) failed on this image, so any text in it could not be checked.
          </AppText>
        ) : null}
        {isImage && pictureChecked && row.textPreview ? (
          <AppText variant="caption" color="textMuted" style={styles.mt4}>
            Too little or unclear text to check as a news claim.
          </AppText>
        ) : null}
        {isImage && textInImageChecked ? (
          <AppText variant="caption" color={row.textClassificationStatus === 'completed' ? 'textMuted' : 'uncertain'} style={styles.mt4}>
            {row.textClassificationStatus === 'completed'
              ? `Text classification: ${row.ocrTextPrediction ?? 'Unavailable'} (model score ${percent(row.ocrTextConfidence)})`
              : 'The text in this image could not be classified by a compatible model.'}
          </AppText>
        ) : null}
        {row.detectedLanguage ? (
          <AppText variant="caption" color="textMuted" style={styles.mt12}>
            Detected language: {languageLabel(row.detectedLanguage)}
          </AppText>
        ) : null}
        {!isImage && row.processingStatus === 'unavailable' ? (
          <AppText variant="caption" color="uncertain" style={styles.mt4}>
            This text was not classified by a compatible model.
          </AppText>
        ) : null}
        <AppText variant="caption" color="textSubtle" style={styles.mt12}>Checked {fullDate(row.createdAt)}</AppText>
      </Card>

      {/* Explanation */}
      <Card title="Why this result">
        <AppText variant="body">{row.summary}</AppText>
        {words?.length ? (
          <View style={styles.mt12}>
            <AppText variant="caption" color="textMuted" style={styles.mb6}>Words that most influenced the model</AppText>
            <View style={styles.words}>
              {words.map((item, index) => {
                const supports = item.direction === 'supports_prediction';
                return (
                  <View
                    key={`${item.word}-${index}`}
                    style={[styles.word, { backgroundColor: supports ? meta.soft : colors.surfaceMuted }]}>
                    <AppText variant="bodyStrong" color={supports ? meta.color : 'textMuted'}>{item.word}</AppText>
                  </View>
                );
              })}
            </View>
            <View style={styles.legend}>
              <Tag label="Supports verdict" tone={row.verdict === 'credible' ? 'credible' : row.verdict === 'misleading' ? 'misleading' : 'uncertain'} />
              <Tag label="Points the other way" />
            </View>
          </View>
        ) : null}
      </Card>

      {/* Image analysis and Grad-CAM: about the picture, never about whether a claim is true */}
      {isImage ? (
        <Card title="Image analysis">
          {row.imageAnalysisStatus === 'completed' ? (
            <Meter
              label="Chance the picture is AI-generated"
              value={row.aiGeneratedLikelihood == null ? null : row.aiGeneratedLikelihood / 100}
              color={colors.uncertain}
              note={`${row.aiGeneratedLabel}. This is about the picture, not whether any news claim is true.`}
            />
          ) : (
            <AppText variant="caption" color="uncertain">
              {row.imageAnalysisStatus === 'skipped'
                ? 'This older check did not analyse the picture because it contained text.'
                : 'The image detector could not analyse this picture, so there is no image result.'}
            </AppText>
          )}
          <View style={styles.mt12}>
            <AppText variant="overline" color="textSubtle" style={styles.mb6}>Grad-CAM heatmap</AppText>
            {row.heatmapPath ? (
              <>
                <View style={[styles.imageFrame, { backgroundColor: colors.surfaceMuted }]}>
                  <AuthImage uri={row.heatmapPath} style={styles.image} resizeMode="contain" />
                </View>
                <AppText variant="caption" color="textMuted" style={styles.mt4}>
                  Where the detector's ResNet18 model looked. Only the outlined centre area is analysed;
                  the rest of the picture is shown as it is. It explains the image model's output; it
                  does not show edits or prove a claim true or false.
                </AppText>
              </>
            ) : (
              <AppText variant="caption" color="uncertain">
                {row.gradcamStatus === 'unavailable'
                  ? 'Grad-CAM heatmap unavailable: the detector ran, but no heatmap could be produced for this image.'
                  : 'No Grad-CAM heatmap: the image detector did not run on this image.'}
              </AppText>
            )}
          </View>
        </Card>
      ) : null}

      {/* Signals */}
      {hasExtraSignals ? (
      <Card title="Signals">
        <View style={styles.signals}>
          <Meter
            label="Fake-news risk"
            value={row.riskScore}
            color={colors.misleading}
            note={isImage ? 'From the text classification only; the image analysis is never mixed in.' : undefined}
          />
          {row.languageQuality != null ? (
            <Meter label="Language quality" value={row.languageQuality / 100} note={row.languageQualityLabel} />
          ) : null}
          {row.sourceCredibility != null ? (
            <Meter label="Source credibility" value={row.sourceCredibility / 100} color={colors.credible} note={row.sourceCredibilityLabel} />
          ) : null}
        </View>
      </Card>
      ) : null}

      {/* Dispute */}
      {row.dispute ? (
        <Card tone="muted">
          <View style={styles.rowGap}>
            <Icon name="flag" size={18} color="uncertain" />
            <View style={styles.flex}>
              <AppText variant="bodyStrong">
                {row.dispute.status === 'pending' ? 'Your dispute is awaiting review' : `Dispute ${row.dispute.status}`}
              </AppText>
              <AppText variant="caption" color="textMuted" style={styles.mt4} numberOfLines={3}>{row.dispute.message}</AppText>
            </View>
          </View>
        </Card>
      ) : (
        <Button
          label="Dispute this result"
          icon="scale"
          variant="secondary"
          onPress={() => router.push(hrefDisputeDetail(row.id))}
          accessibilityHint="Ask an administrator to review this verdict"
        />
      )}
    </ScrollView>
  );
}

function HeroStat({ label, value }: { label: string; value: string }) {
  const { colors } = useAppTheme();
  return (
    <View style={[styles.heroStat, { backgroundColor: colors.surface }]}>
      <AppText variant="caption" color="textMuted">{label}</AppText>
      <AppText variant="heading" color={value === 'Unavailable' ? 'textSubtle' : 'text'}>{value}</AppText>
    </View>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  center: { flex: 1, justifyContent: 'center' },
  container: { padding: space.lg, paddingBottom: space.xxxl, gap: space.md },
  hero: { borderRadius: radius.xl, borderWidth: 1, padding: space.lg, gap: space.lg },
  heroTop: { flexDirection: 'row', alignItems: 'center', gap: space.md },
  heroIcon: { width: 56, height: 56, borderRadius: radius.lg, alignItems: 'center', justifyContent: 'center' },
  heroStats: { flexDirection: 'row', gap: space.sm },
  heroStat: { flex: 1, borderRadius: radius.md, padding: space.md, gap: 2 },
  rowGap: { flexDirection: 'row', gap: space.md },
  mt4: { marginTop: 4 },
  mt12: { marginTop: space.md },
  mb6: { marginBottom: 6 },
  imageFrame: { borderRadius: radius.md, overflow: 'hidden', height: 240 },
  image: { width: '100%', height: '100%' },
  ocr: { marginTop: space.md },
  words: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  word: { borderRadius: radius.sm, paddingHorizontal: 10, paddingVertical: 4 },
  legend: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: space.md },
  signals: { gap: space.lg },
});
