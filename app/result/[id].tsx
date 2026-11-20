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
  type IconName,
  Meter,
  Tag,
  useAppTheme,
  verdictMeta,
} from '@/components/ui';
import { type Palette, radius, space } from '@/constants/theme';
import { fullDate, languageLabel, percent } from '@/lib/format';
import { hrefDisputeDetail } from '@/lib/navigation';
import { useSubmissions } from '@/lib/SubmissionsContext';
import type { Submission } from '@/types/submission';

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
  // Text checks keep their signals card; image results show their parts in their own cards.
  const hasExtraSignals = !isImage && (row.languageQuality != null || row.sourceCredibility != null);
  const adminVerdict = row.adminReview?.overrideVerdict ? verdictMeta(row.adminReview.overrideVerdict, colors) : null;
  // An image only gets a news verdict when text read from it was classified (or an admin set one).
  // Without usable text there is no claim, so no answer is given about one.
  const claimClassified = textInImageChecked && row.textClassificationStatus === 'completed';
  const showVerdict = !isImage || claimClassified || row.adminReview?.resolution === 'override';
  const authenticity = imageAuthenticity(row, colors);

  const leadWithVerdict = isImage && showVerdict;
  // Image authenticity: the detector's answer about the picture itself.
  const authenticityCard = isImage ? (
        <View style={[styles.hero, { backgroundColor: authenticity.soft, borderColor: authenticity.color }]}>
          <View style={styles.heroTop}>
            <View style={[styles.heroIcon, { backgroundColor: colors.surface }]}>
              <Icon name={authenticity.icon} size={28} color={authenticity.color} />
            </View>
            <View style={styles.flex}>
              <AppText variant="overline" color={authenticity.color}>
                {leadWithVerdict ? 'Image authenticity (separate from the verdict above)' : 'Image authenticity'}
              </AppText>
              <AppText variant="title" color={authenticity.color}>{authenticity.label}</AppText>
            </View>
          </View>
          {row.imageAnalysisStatus === 'completed' ? (
            <Meter
              label="Chance the picture is AI-generated"
              value={row.aiGeneratedLikelihood == null ? null : row.aiGeneratedLikelihood / 100}
              color={authenticity.color}
            />
          ) : null}
          <AppText variant="caption" color="textMuted">
            {row.imageAnalysisStatus === 'completed'
              ? 'About the picture itself, not whether any news claim is true. The detector was trained on '
                + 'camera photos: screenshots, posters, memes and edited web images are often rated '
                + 'AI-generated, so treat this as a hint, not proof.'
              : row.imageAnalysisStatus === 'skipped'
                ? 'This older check did not analyse the picture because it contained text.'
                : 'The image detector could not analyse this picture.'}
          </AppText>
          {row.imageAnalysisStatus === 'completed' && textInImageChecked ? (
            <AppText variant="caption" color="textMuted">
              This image contains text, like a screenshot or poster: the kind of image the detector most
              often rates as AI-generated.
            </AppText>
          ) : null}
          {!showVerdict ? (
            <AppText variant="caption" color="textMuted">
              {ocrFailed
                ? 'Text could not be read from this image, so no news claim was checked.'
                : 'No readable news text was found in this image, so no news claim was checked.'}
            </AppText>
          ) : null}
        </View>
      ) : null;
  // Grad-CAM: what the detector's ResNet18 model looked at for that answer.
  const heatmapCard = isImage && row.imageAnalysisStatus === 'completed' ? (
        <Card title="Where the detector looked">
          {row.heatmapPath ? (
            <>
              <View style={[styles.imageFrame, { backgroundColor: colors.surfaceMuted }]}>
                <AuthImage uri={row.heatmapPath} style={styles.image} resizeMode="contain" />
              </View>
              <AppText variant="caption" color="textMuted" style={styles.mt4}>
                Grad-CAM from the detector's ResNet18 model (one of its three models), showing what
                supported the image-authenticity answer above. Only the outlined centre area is
                analysed. It does not show edits and is not evidence about the news claim.
              </AppText>
            </>
          ) : (
            <AppText variant="caption" color="uncertain">
              The heatmap could not be produced for this image. Most often this means the detector's
              ResNet18 model leaned strongly the other way, so it has no evidence for this answer to highlight.
            </AppText>
          )}
        </Card>
      ) : null;
  // Verdict on the claim (typed text, or text read from the image).
  const verdictCard = showVerdict ? (
      <View style={[styles.hero, { backgroundColor: meta.soft, borderColor: meta.color }]}>
        <View style={styles.heroTop}>
          <View style={[styles.heroIcon, { backgroundColor: colors.surface }]}>
            <Icon name={meta.icon} size={28} color={meta.color} />
          </View>
          <View style={styles.flex}>
            <AppText variant="overline" color={meta.color}>
              {row.adminReview?.resolution === 'override'
                ? 'AI verdict (overridden)'
                : isImage ? 'Verdict on the text in the image' : 'Verdict'}
            </AppText>
            <AppText variant="title" color={meta.color}>{meta.label}</AppText>
          </View>
        </View>
        <View style={styles.heroStats}>
          <HeroStat label="Score" value={percent(row.confidence)} />
          <HeroStat label="Fake-news risk" value={percent(row.riskScore)} />
        </View>
      </View>
      ) : null;

  return (
    <ScrollView style={{ backgroundColor: colors.background }} contentContainerStyle={styles.container}>
      {/* When text read from an image was classified, the claim verdict leads: it answers the
          news question. Image authenticity and its heatmap follow as separate, labelled results. */}
      {leadWithVerdict ? (
        <>
          {verdictCard}
          {authenticityCard}
          {heatmapCard}
        </>
      ) : (
        <>
          {authenticityCard}
          {heatmapCard}
          {verdictCard}
        </>
      )}

      {/* The user's dispute and the administrator's reply, together */}
      {row.dispute || row.adminReview ? (
        <Card title="Dispute and review">
          {row.dispute ? (
            <View style={styles.rowGap}>
              <Icon name="flag" size={20} color="uncertain" />
              <View style={styles.flex}>
                <AppText variant="overline" color="textSubtle">User's dispute</AppText>
                {row.dispute.message ? (
                  <AppText variant="body" style={styles.mt4}>{row.dispute.message}</AppText>
                ) : null}
                {row.dispute.evidenceLink ? (
                  <AppText variant="caption" color="primary" style={styles.mt4} numberOfLines={2}>
                    Evidence: {row.dispute.evidenceLink}
                  </AppText>
                ) : null}
                <AppText variant="caption" color="textSubtle" style={styles.mt4}>
                  Filed {fullDate(row.dispute.createdAt)}
                </AppText>
              </View>
            </View>
          ) : null}
          <View style={[styles.rowGap, row.dispute ? styles.reply : null, row.dispute ? { borderTopColor: colors.border } : null]}>
            <Icon name={row.adminReview ? 'badge-check' : 'clock'} size={20} color={row.adminReview ? 'credible' : 'textMuted'} />
            <View style={styles.flex}>
              <AppText variant="overline" color="textSubtle">Admin reply</AppText>
              {row.adminReview ? (
                <>
                  <AppText variant="bodyStrong" style={styles.mt4}>
                    {row.adminReview.resolution === 'override' && adminVerdict
                      ? `Verdict changed to ${adminVerdict.label.toLowerCase()}`
                      : 'AI verdict upheld'}
                  </AppText>
                  {row.adminReview.note ? (
                    <AppText variant="body" color="textMuted" style={styles.mt4}>{row.adminReview.note}</AppText>
                  ) : null}
                  <AppText variant="caption" color="textSubtle" style={styles.mt4}>
                    Reviewed {fullDate(row.adminReview.reviewedAt)}
                  </AppText>
                </>
              ) : (
                <AppText variant="body" color="textMuted" style={styles.mt4}>
                  Waiting for an administrator to review this dispute.
                </AppText>
              )}
            </View>
          </View>
        </Card>
      ) : null}

      {/* Submitted content */}
      <Card title={isImage ? 'Submitted image' : 'User claim'}>
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
        {isImage && textInImageChecked && row.textClassificationStatus !== 'completed' ? (
          <AppText variant="caption" color="uncertain" style={styles.mt4}>
            The text in this image could not be classified.
          </AppText>
        ) : null}
        {row.detectedLanguage ? (
          <AppText variant="caption" color="textMuted" style={styles.mt12}>
            Detected language: {languageLabel(row.detectedLanguage)}
          </AppText>
        ) : null}
        {!isImage && row.processingStatus === 'unavailable' ? (
          <AppText variant="caption" color="uncertain" style={styles.mt4}>
            This text could not be classified.
          </AppText>
        ) : null}
        <AppText variant="caption" color="textSubtle" style={styles.mt12}>Checked {fullDate(row.createdAt)}</AppText>
      </Card>

      {/* Explanation */}
      {!isImage || words?.length ? (
      <Card title={isImage ? 'Words that influenced the result' : 'Why this result'}>
        {!isImage ? <AppText variant="body">{row.summary}</AppText> : null}
        {words?.length ? (
          <View style={isImage ? null : styles.mt12}>
            {!isImage ? (
              <AppText variant="caption" color="textMuted" style={styles.mb6}>Words that influenced the result</AppText>
            ) : null}
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
      ) : null}

      {/* Signals */}
      {hasExtraSignals ? (
      <Card title="Signals">
        <View style={styles.signals}>
          <Meter label="Fake-news risk" value={row.riskScore} color={colors.misleading} />
          {row.languageQuality != null ? (
            <Meter label="Language quality" value={row.languageQuality / 100} note={row.languageQualityLabel} />
          ) : null}
          {row.sourceCredibility != null ? (
            <Meter label="Source credibility" value={row.sourceCredibility / 100} color={colors.credible} note={row.sourceCredibilityLabel} />
          ) : null}
        </View>
      </Card>
      ) : null}

      {/* Dispute (shown above once filed) */}
      {/* One dispute at a time; once it is reviewed the user may dispute again */}
      {row.dispute?.status === 'pending' ? null : (
        <Button
          label={row.dispute ? 'Dispute again' : 'Dispute this result'}
          icon="scale"
          variant="secondary"
          onPress={() => router.push(hrefDisputeDetail(row.id))}
          accessibilityHint="Ask an administrator to review this verdict"
        />
      )}
    </ScrollView>
  );
}

/** Label, colour and icon for the image-authenticity hero. */
function imageAuthenticity(row: Submission, colors: Palette) {
  if (row.imageAnalysisStatus !== 'completed' || row.aiGeneratedLikelihood == null) {
    return { label: 'Not analysed', icon: 'image-off' as IconName, color: colors.uncertain, soft: colors.uncertainSoft };
  }
  // The backend's own label (its 0.5 threshold), not a re-rounded percentage.
  // Neutral colours either way: red/green belong to news verdicts, and an AI-made picture does not
  // make a claim false (nor a real photo make it true).
  return row.aiGeneratedLabel === 'Likely AI-generated'
    ? { label: row.aiGeneratedLabel, icon: 'sparkles' as IconName, color: colors.info, soft: colors.infoSoft }
    : { label: row.aiGeneratedLabel, icon: 'camera' as IconName, color: colors.info, soft: colors.infoSoft };
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
  reply: { marginTop: space.md, paddingTop: space.md, borderTopWidth: StyleSheet.hairlineWidth },
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
