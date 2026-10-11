import { useLocalSearchParams, useRouter } from 'expo-router';
import { useState } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, View } from 'react-native';

import { AppText, Button, Card, ContentText, EmptyState, Icon, Tag, TextField, VerdictBadge, useAppTheme } from '@/components/ui';
import { space } from '@/constants/theme';
import { createDispute } from '@/lib/api';
import { useAuth } from '@/lib/AuthContext';
import { fullDate, percent } from '@/lib/format';
import { useSubmissions } from '@/lib/SubmissionsContext';
import { showAlert } from '@/lib/alert';

const MIN_JUSTIFICATION = 10; // matches the backend's validation

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

  if (!row) {
    return (
      <View style={[styles.center, { backgroundColor: colors.background }]}>
        <EmptyState icon="circle-alert" title="Submission not found" actionLabel="Back" onAction={() => router.back()} />
      </View>
    );
  }

  const submission = row;
  const trimmed = message.trim();
  const link = evidence.trim();
  const linkValid = !link || /^https?:\/\/\S+\.\S+/i.test(link);

  async function submitDispute() {
    if (!accessToken) {
      showAlert('Dispute', 'Sign in again before submitting a dispute.');
      return;
    }
    try {
      setBusy(true);
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
        submitterEmail: user?.email,
      });
      showAlert('Dispute submitted', 'An administrator will review it. You can follow its status in History.', [
        { text: 'OK', onPress: () => router.back() },
      ]);
    } catch (error) {
      showAlert('Dispute', error instanceof Error ? error.message : 'Could not submit your dispute.');
    } finally {
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
            <AppText variant="caption" color="textMuted">Confidence {percent(submission.confidence)}</AppText>
          </View>
          {submission.textPreview ? (
            <ContentText numberOfLines={6} style={styles.preview}>{submission.textPreview}</ContentText>
          ) : (
            <AppText variant="body" color="textMuted" style={styles.preview}>An image-based analysis</AppText>
          )}
          <AppText variant="caption" color="textSubtle" style={styles.mt8}>Checked {fullDate(submission.createdAt)}</AppText>
        </Card>

        {submission.dispute ? (
          <Card>
            <View style={styles.statusRow}>
              <Icon name="flag" size={18} color="uncertain" />
              <AppText variant="heading" style={styles.flex}>Dispute on file</AppText>
              <Tag
                label={submission.dispute.status}
                tone={submission.dispute.status === 'pending' ? 'uncertain' : 'credible'}
              />
            </View>
            <AppText variant="body" style={styles.mt8}>{submission.dispute.message}</AppText>
            {submission.dispute.evidenceLink ? (
              <AppText variant="caption" color="info" style={styles.mt8} selectable>{submission.dispute.evidenceLink}</AppText>
            ) : null}
            <AppText variant="caption" color="textSubtle" style={styles.mt8}>Filed {fullDate(submission.dispute.createdAt)}</AppText>
          </Card>
        ) : (
          <>
            <TextField
              label="Why do you disagree?"
              hint={`Mention sources, missing context, or OCR mistakes. At least ${MIN_JUSTIFICATION} characters.`}
              value={message}
              onChangeText={setMessage}
              multiline
              maxLength={5000}
              placeholder="e.g. The official press release on the ministry website says the opposite…"
            />
            <TextField
              label="Evidence link (optional)"
              icon="link"
              value={evidence}
              onChangeText={setEvidence}
              autoCapitalize="none"
              autoCorrect={false}
              keyboardType="url"
              placeholder="https://"
              hint={linkValid ? 'A news article or official source that supports your view.' : 'Enter a full link starting with http:// or https://'}
            />
            <Button
              label="Submit dispute"
              icon="send"
              onPress={() => void submitDispute()}
              loading={busy}
              disabled={trimmed.length < MIN_JUSTIFICATION || !linkValid}
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
  preview: { marginTop: space.md },
  statusRow: { flexDirection: 'row', alignItems: 'center', gap: space.sm },
  mt8: { marginTop: space.sm },
});
