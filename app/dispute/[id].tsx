import { useLocalSearchParams, useRouter } from 'expo-router';
import { useRef, useState } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, View } from 'react-native';

import {
  AppText,
  AuthImage,
  Button,
  Card,
  ContentText,
  EmptyState,
  Icon,
  Tag,
  TextField,
  VerdictBadge,
  useAppTheme,
  verdictMeta,
} from '@/components/ui';
import { radius, space } from '@/constants/theme';
import { createDispute } from '@/lib/api';
import { useAuth } from '@/lib/AuthContext';
import { fullDate, normalizeEvidenceLink, percent } from '@/lib/format';
import { useSubmissions } from '@/lib/SubmissionsContext';
import { showAlert } from '@/lib/alert';

const MIN_JUSTIFICATION = 10; // matches the backend's validation
const MAX_JUSTIFICATION = 5000;

export default function DisputeDetailScreen() {
  const { id: idParam } = useLocalSearchParams<{ id?: string | string[] }>();
  const id = Array.isArray(idParam) ? idParam[0] : idParam;
  const { getById, updateSubmission } = useSubmissions();
  const { user, accessToken } = useAuth();
  const router = useRouter();
  const { colors } = useAppTheme();
  const row = id ? getById(id) : undefined;

  const [message, setMessage] = useState('');
  const [evidence, setEvidence] = useState('');
  const [busy, setBusy] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [triedSubmit, setTriedSubmit] = useState(false);
  // A quick second tap must not file the same dispute twice.
  const submittingRef = useRef(false);

  if (!row) {
    return (
      <View style={[styles.center, { backgroundColor: colors.background }]}>
        <EmptyState icon="circle-alert" title="Check not found"
          message="Open the check from History, then tap Dispute." actionLabel="Back" onAction={() => router.back()} />
      </View>
    );
  }

  const submission = row;
  const trimmed = message.trim();
  const missing = Math.max(0, MIN_JUSTIFICATION - trimmed.length);
  const link = normalizeEvidenceLink(evidence);
  const linkError = link === null ? 'This does not look like a web link. Example: geo.tv/news/12345' : null;
  const reasonError = triedSubmit && missing > 0
    ? `Please write at least ${MIN_JUSTIFICATION} characters (${missing} more).`
    : null;
  const pending = submission.dispute?.status === 'pending';
  const review = submission.adminReview;
  const reviewVerdict = review?.overrideVerdict ? verdictMeta(review.overrideVerdict, colors) : null;

  async function submitDispute() {
    setTriedSubmit(true);
    setSubmitError(null);
    if (submittingRef.current || missing > 0 || link === null) return;
    if (!accessToken) {
      setSubmitError('Your session has ended. Sign in again, then submit your dispute.');
      return;
    }
    submittingRef.current = true;
    setBusy(true);
    try {
      const created = await createDispute(accessToken, {
        submission_id: Number(submission.id),
        justification: trimmed,
        ...(link ? { evidence_link: link } : {}),
      });
      updateSubmission(submission.id, {
        dispute: {
          id: String(created.id),
          message: created.justification,
          createdAt: Date.parse(created.created_at) || Date.now(),
          status: created.status,
          evidenceLink: created.evidence_link,
        },
        // A new dispute starts a new review; the earlier reply no longer applies to it.
        adminReview: undefined,
        submitterEmail: user?.email,
      });
      // Back to the result, where the dispute now shows as waiting for review.
      router.back();
      showAlert('Dispute sent', 'An administrator will review it. Its status is shown on the result.');
    } catch (error) {
      const text = error instanceof Error ? error.message : 'Could not send your dispute.';
      setSubmitError(/pending dispute already exists/i.test(text)
        ? 'You already have a dispute waiting for review on this check.'
        : text);
    } finally {
      submittingRef.current = false;
      setBusy(false);
    }
  }

  return (
    <KeyboardAvoidingView style={styles.flex} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView
        style={{ backgroundColor: colors.background }}
        contentContainerStyle={styles.container}
        keyboardShouldPersistTaps="handled">
        <Card title="You are disputing">
          <View style={styles.verdictRow}>
            <VerdictBadge verdict={submission.verdict} />
            {submission.confidence != null ? (
              <AppText variant="caption" color="textMuted">Score {percent(submission.confidence)}</AppText>
            ) : null}
          </View>
          {submission.imageUri ? (
            <View style={[styles.imageFrame, { backgroundColor: colors.surfaceMuted }]}>
              <AuthImage uri={submission.imageUri} style={styles.image} resizeMode="contain" />
            </View>
          ) : null}
          {submission.textPreview ? (
            <ContentText numberOfLines={6} style={styles.preview}>{submission.textPreview}</ContentText>
          ) : null}
          <AppText variant="caption" color="textSubtle" style={styles.mt8}>Checked {fullDate(submission.createdAt)}</AppText>
        </Card>

        {submission.dispute ? (
          <Card>
            <View style={styles.statusRow}>
              <Icon name="flag" size={18} color="uncertain" />
              <AppText variant="heading" style={styles.flex}>Your dispute</AppText>
              <Tag label={pending ? 'Waiting for review' : 'Reviewed'} tone={pending ? 'uncertain' : 'credible'} />
            </View>
            {submission.dispute.message ? (
              <AppText variant="body" style={styles.mt8}>{submission.dispute.message}</AppText>
            ) : null}
            {submission.dispute.evidenceLink ? (
              <AppText variant="caption" color="info" style={styles.mt8} selectable>{submission.dispute.evidenceLink}</AppText>
            ) : null}
            <AppText variant="caption" color="textSubtle" style={styles.mt8}>Filed {fullDate(submission.dispute.createdAt)}</AppText>
            {review ? (
              <View style={[styles.reply, { borderTopColor: colors.border }]}>
                <AppText variant="overline" color="textSubtle">Admin reply</AppText>
                <AppText variant="bodyStrong" style={styles.mt4}>
                  {review.resolution === 'override' && reviewVerdict
                    ? `Verdict changed to ${reviewVerdict.label.toLowerCase()}`
                    : 'AI verdict upheld'}
                </AppText>
                {review.note ? <AppText variant="body" color="textMuted" style={styles.mt4}>{review.note}</AppText> : null}
              </View>
            ) : null}
          </Card>
        ) : null}

        {pending ? (
          <AppText variant="body" color="textMuted">
            An administrator has not reviewed this dispute yet. You can file another one after they reply.
          </AppText>
        ) : (
          <>
            {submission.dispute ? (
              <AppText variant="bodyStrong">Still disagree? You can dispute it again.</AppText>
            ) : null}
            <TextField
              label="Why do you disagree?"
              hint={`Mention sources, missing context, or mistakes in the text read from an image. ${trimmed.length} / ${MIN_JUSTIFICATION} characters minimum.`}
              error={reasonError}
              value={message}
              onChangeText={(value) => { setMessage(value); setSubmitError(null); }}
              multiline
              maxLength={MAX_JUSTIFICATION}
              placeholder="e.g. The official press release on the ministry website says the opposite…"
            />
            <TextField
              label="Evidence link (optional)"
              icon="link"
              value={evidence}
              onChangeText={(value) => { setEvidence(value); setSubmitError(null); }}
              autoCapitalize="none"
              autoCorrect={false}
              keyboardType="url"
              placeholder="e.g. geo.tv/news/12345"
              error={linkError}
              hint={link ? `Will be sent as ${link}` : 'A news article or official source that supports your view.'}
            />
            {submitError ? (
              <View style={[styles.errorBox, { backgroundColor: colors.misleadingSoft }]}>
                <Icon name="circle-alert" size={18} color="misleading" />
                <AppText variant="body" color="misleading" style={styles.flex}>{submitError}</AppText>
              </View>
            ) : null}
            <Button
              label="Submit dispute"
              icon="send"
              onPress={() => void submitDispute()}
              loading={busy}
              disabled={busy}
            />
          </>
        )}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  center: { flex: 1, justifyContent: 'center' },
  container: { padding: space.lg, paddingBottom: space.xxxl, gap: space.lg },
  verdictRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: space.sm },
  imageFrame: { borderRadius: radius.md, overflow: 'hidden', height: 180, marginTop: space.md },
  image: { width: '100%', height: '100%' },
  preview: { marginTop: space.md },
  statusRow: { flexDirection: 'row', alignItems: 'center', gap: space.sm },
  reply: { marginTop: space.md, paddingTop: space.md, borderTopWidth: StyleSheet.hairlineWidth },
  errorBox: { flexDirection: 'row', gap: space.sm, alignItems: 'flex-start', padding: space.md, borderRadius: radius.md },
  mt4: { marginTop: 4 },
  mt8: { marginTop: space.sm },
});
