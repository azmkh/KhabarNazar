import { useFocusEffect, useLocalSearchParams, useRouter } from 'expo-router';
import { useCallback, useState } from 'react';
import { KeyboardAvoidingView, Linking, Platform, Pressable, ScrollView, StyleSheet, View } from 'react-native';

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
import { getDispute, reviewDispute, submissionImageUrl, type ApiDispute } from '@/lib/api';
import { useAuth } from '@/lib/AuthContext';
import { fullDate, percent } from '@/lib/format';
import { showAlert } from '@/lib/alert';
import type { Verdict } from '@/types/submission';

const labels: { value: Verdict; api: string }[] = [
  { value: 'credible', api: 'Real' },
  { value: 'uncertain', api: 'Uncertain' },
  { value: 'misleading', api: 'Fake' },
];

function verdictOf(label?: string | null): Verdict {
  return labels.find((item) => item.api === label)?.value ?? 'uncertain';
}

export default function AdminReviewScreen() {
  const { id: idParam } = useLocalSearchParams<{ id?: string | string[] }>();
  const id = Array.isArray(idParam) ? idParam[0] : idParam;
  const { accessToken } = useAuth();
  const router = useRouter();
  const { colors } = useAppTheme();
  const [dispute, setDispute] = useState<ApiDispute | null>(null);
  const [note, setNote] = useState('');
  const [overrideVerdict, setOverrideVerdict] = useState<Verdict>('uncertain');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<'uphold_ai' | 'override' | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!accessToken || !id) return;
    setLoading(true);
    setError(null);
    try {
      const result = await getDispute(accessToken, id);
      setDispute(result);
      setNote(result.admin_comment ?? '');
      const current = labels.find((item) => item.api === result.override_label);
      if (current) setOverrideVerdict(current.value);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load dispute.');
    } finally {
      setLoading(false);
    }
  }, [accessToken, id]);

  useFocusEffect(useCallback(() => { void load(); }, [load]));

  async function saveReview(resolution: 'uphold_ai' | 'override') {
    const trimmed = note.trim();
    if (trimmed.length < 3) {
      showAlert('Admin review', 'A comment is required (at least 3 characters).');
      return;
    }
    if (!accessToken || !id) return;
    try {
      setBusy(resolution);
      const result = await reviewDispute(accessToken, id, {
        admin_decision: resolution,
        admin_comment: trimmed,
        ...(resolution === 'override' ? { override_label: labels.find((item) => item.value === overrideVerdict)?.api } : {}),
      });
      setDispute(result);
      showAlert('Review saved', 'The decision was recorded.', [{ text: 'OK', onPress: () => router.back() }]);
    } catch (err) {
      showAlert('Admin review', err instanceof Error ? err.message : 'Could not save the review.');
    } finally {
      setBusy(null);
    }
  }

  if (!dispute) {
    return (
      <View style={[styles.center, { backgroundColor: colors.background }]}>
        {loading ? <EmptyState icon="scale" title="Loading dispute…" loading /> : (
          <EmptyState icon="circle-alert" title="Dispute not found" message={error ?? undefined} actionLabel="Back" onAction={() => router.back()} />
        )}
      </View>
    );
  }

  const submission = dispute.submission;
  const image = submission?.image_submission;
  const content = submission?.text_submission?.input_text ?? image?.ocr_text;
  const version = submission?.explainability?.model_version;
  const confidence = version === 'text-model-unavailable' || version?.startsWith('stub')
    ? null
    : submission?.text_submission?.text_confidence ?? image?.text_confidence;
  const canReview = dispute.status === 'pending';

  return (
    <KeyboardAvoidingView style={styles.flex} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView style={{ backgroundColor: colors.background }} contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
        {error ? <AppText variant="caption" color="misleading">{error}</AppText> : null}

        <Card>
          <View style={styles.between}>
            <AppText variant="overline" color="textMuted">User's dispute</AppText>
            <Tag label={dispute.status} tone={canReview ? 'uncertain' : 'credible'} />
          </View>
          <AppText variant="body" style={styles.mt8}>{dispute.justification}</AppText>
          {dispute.evidence_link ? (
            <Pressable onPress={() => void Linking.openURL(dispute.evidence_link!)} style={styles.link} accessibilityRole="link">
              <Icon name="external-link" size={14} color="info" />
              <AppText variant="caption" color="info" numberOfLines={1} style={styles.flex}>{dispute.evidence_link}</AppText>
            </Pressable>
          ) : null}
          <AppText variant="caption" color="textSubtle" style={styles.mt8}>
            {dispute.user?.email ?? `User ${dispute.user_id}`} · {fullDate(Date.parse(dispute.created_at))}
          </AppText>
        </Card>

        <Card title="Model output">
          <View style={styles.between}>
            <VerdictBadge verdict={verdictOf(submission?.final_label)} />
            <AppText variant="caption" color="textMuted">Confidence {percent(confidence)}</AppText>
          </View>
          {submission?.explainability?.explanation_summary ? (
            <AppText variant="caption" color="textMuted" style={styles.mt8}>{submission.explainability.explanation_summary}</AppText>
          ) : null}
        </Card>

        {image || content ? (
          <Card title={image ? 'Submitted image' : 'Submitted text'}>
            {image ? (
              <View style={[styles.imageFrame, { backgroundColor: colors.surfaceMuted }]}>
                <AuthImage uri={submissionImageUrl(submission!.id)} style={styles.image} resizeMode="contain" />
              </View>
            ) : null}
            {content ? <ContentText style={image ? styles.mt8 : undefined}>{content}</ContentText> : null}
          </Card>
        ) : null}

        {!canReview ? (
          <Card tone="muted">
            <View style={styles.row}>
              <Icon name="badge-check" size={18} color="credible" />
              <View style={styles.flex}>
                <AppText variant="bodyStrong">
                  {dispute.admin_decision === 'uphold_ai'
                    ? 'AI verdict upheld'
                    : `Changed to ${verdictMeta(verdictOf(dispute.override_label), colors).label.toLowerCase()}`}
                </AppText>
                {dispute.admin_comment ? <AppText variant="body" color="textMuted" style={styles.mt4}>“{dispute.admin_comment}”</AppText> : null}
                {dispute.reviewed_at ? (
                  <AppText variant="caption" color="textSubtle" style={styles.mt4}>{fullDate(Date.parse(dispute.reviewed_at))}</AppText>
                ) : null}
              </View>
            </View>
          </Card>
        ) : (
          <Card title="Your decision" style={styles.decision}>
            <TextField
              label="Comment (required, shown to the user)"
              value={note}
              onChangeText={setNote}
              multiline
              placeholder="Explain your decision for the audit trail…"
            />
            <Button
              label="Uphold AI verdict"
              icon="check"
              variant="secondary"
              loading={busy === 'uphold_ai'}
              disabled={busy !== null}
              onPress={() => void saveReview('uphold_ai')}
            />
            <View style={[styles.divider, { backgroundColor: colors.border }]} />
            <AppText variant="caption" color="textMuted">Or override with a new verdict</AppText>
            <View style={styles.choices}>
              {labels.map(({ value }) => {
                const meta = verdictMeta(value, colors);
                const selected = overrideVerdict === value;
                return (
                  <Pressable
                    key={value}
                    onPress={() => setOverrideVerdict(value)}
                    accessibilityRole="radio"
                    accessibilityState={{ selected }}
                    style={[
                      styles.choice,
                      {
                        borderColor: selected ? meta.color : colors.border,
                        backgroundColor: selected ? meta.soft : colors.surface,
                      },
                    ]}>
                    <Icon name={meta.icon} size={18} color={selected ? meta.color : 'textMuted'} />
                    <AppText variant="caption" color={selected ? meta.color : 'textMuted'}>{meta.short}</AppText>
                  </Pressable>
                );
              })}
            </View>
            <Button
              label="Override verdict"
              icon="pencil"
              loading={busy === 'override'}
              disabled={busy !== null}
              onPress={() => void saveReview('override')}
            />
          </Card>
        )}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  center: { flex: 1, justifyContent: 'center' },
  container: { padding: space.lg, paddingBottom: space.xxxl, gap: space.md },
  between: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: space.sm },
  row: { flexDirection: 'row', gap: space.md },
  mt4: { marginTop: 4 },
  mt8: { marginTop: space.sm },
  link: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: space.sm },
  imageFrame: { borderRadius: radius.md, overflow: 'hidden', height: 230 },
  image: { width: '100%', height: '100%' },
  decision: { gap: space.md },
  divider: { height: StyleSheet.hairlineWidth, marginVertical: space.xs },
  choices: { flexDirection: 'row', gap: space.sm },
  choice: {
    flex: 1,
    alignItems: 'center',
    gap: 4,
    borderWidth: 1.5,
    borderRadius: radius.md,
    paddingVertical: space.md,
  },
});
