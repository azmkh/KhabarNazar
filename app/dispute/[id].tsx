import { useLocalSearchParams, useRouter } from 'expo-router';
import { useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  TextInput,
} from 'react-native';

import { Text, View } from '@/components/Themed';
import Colors from '@/constants/Colors';
import { useColorScheme } from '@/components/useColorScheme';
import { useSubmissions } from '@/lib/SubmissionsContext';
import { useAuth } from '@/lib/AuthContext';

export default function DisputeDetailScreen() {
  const { id: idParam } = useLocalSearchParams<{ id?: string | string[] }>();
  const id = Array.isArray(idParam) ? idParam[0] : idParam;
  const { getById, updateSubmission } = useSubmissions();
  const { user } = useAuth();
  const router = useRouter();
  const colorScheme = useColorScheme() ?? 'light';
  const theme = Colors[colorScheme];
  const row = id ? getById(id) : undefined;

  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);

  if (!row) {
    return (
      <View style={[styles.center, { backgroundColor: theme.background }]}>
        <Text style={{ color: theme.muted }}>Submission not found.</Text>
      </View>
    );
  }

  const submission = row;

  async function submitDispute() {
    const trimmed = message.trim();
    if (trimmed.length < 12) {
      Alert.alert('Dispute', 'Please explain in at least 12 characters why you disagree.');
      return;
    }
    setBusy(true);
    await new Promise((r) => setTimeout(r, 400));
    updateSubmission(submission.id, {
      dispute: { message: trimmed, createdAt: Date.now() },
      submitterEmail: user?.email,
    });
    setBusy(false);
    Alert.alert('Dispute recorded', 'Thank you. In production this enters the admin review queue.', [
      { text: 'OK', onPress: () => router.back() },
    ]);
  }

  return (
    <KeyboardAvoidingView
      style={{ flex: 1, backgroundColor: theme.background }}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
        <View style={[styles.card, { backgroundColor: theme.card, borderColor: theme.border }]}>
          <Text style={[styles.section, { color: theme.muted }]}>You are disputing</Text>
          <Text style={{ color: theme.text, marginTop: 8, fontSize: 15, lineHeight: 22 }}>
            {submission.textPreview || (submission.imageUri ? 'An image-based analysis' : 'This submission')}
          </Text>
          <Text style={{ color: theme.muted, marginTop: 10, fontSize: 13 }}>
            Current verdict: <Text style={{ fontWeight: '700', color: theme.text }}>{submission.verdict}</Text>
            {' · '}
            Confidence {((submission.confidence ?? 0.5) * 100).toFixed(1)}%
          </Text>
        </View>

        {submission.dispute ? (
          <View style={[styles.card, { backgroundColor: theme.card, borderColor: theme.border }]}>
            <Text style={[styles.section, { color: theme.muted }]}>Dispute on file</Text>
            <Text style={{ color: theme.text, marginTop: 8 }}>{submission.dispute.message}</Text>
            <Text style={{ color: theme.muted, marginTop: 8, fontSize: 12 }}>
              {new Date(submission.dispute.createdAt).toLocaleString()}
            </Text>
          </View>
        ) : (
          <>
            <Text style={[styles.label, { color: theme.text }]}>Why do you disagree?</Text>
            <Text style={[styles.hint, { color: theme.muted }]}>
              Reference sources, context, or errors (e.g. OCR). Admins may require a mandatory comment
              before overriding the model.
            </Text>
            <TextInput
              value={message}
              onChangeText={setMessage}
              multiline
              textAlignVertical="top"
              placeholder="Describe the issue…"
              placeholderTextColor={theme.muted}
              style={[
                styles.input,
                { color: theme.text, borderColor: theme.border, backgroundColor: theme.background },
              ]}
            />
            <Pressable
              onPress={() => void submitDispute()}
              disabled={busy}
              style={({ pressed }) => [
                styles.submit,
                { backgroundColor: theme.tint, opacity: busy ? 0.65 : pressed ? 0.92 : 1 },
              ]}>
              {busy ? (
                <ActivityIndicator color="#fff" />
              ) : (
                <Text style={styles.submitText}>Submit dispute</Text>
              )}
            </Pressable>
          </>
        )}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
  },
  container: {
    padding: 20,
    paddingBottom: 40,
    gap: 14,
  },
  card: {
    borderRadius: 14,
    borderWidth: 1,
    padding: 14,
  },
  section: {
    fontSize: 12,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  label: {
    fontSize: 16,
    fontWeight: '700',
  },
  hint: {
    fontSize: 13,
    lineHeight: 19,
    marginTop: 6,
  },
  input: {
    marginTop: 12,
    minHeight: 140,
    borderWidth: 1,
    borderRadius: 12,
    padding: 12,
    fontSize: 16,
    lineHeight: 22,
  },
  submit: {
    marginTop: 16,
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: 'center',
  },
  submitText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '700',
  },
});
