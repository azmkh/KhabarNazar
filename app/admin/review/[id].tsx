import { useLocalSearchParams, useRouter } from 'expo-router';
import { useState } from 'react';
import {
  Alert,
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import { useSubmissions } from '@/lib/SubmissionsContext';
import type { Verdict } from '@/types/submission';

const verdicts: Verdict[] = ['credible', 'uncertain', 'misleading'];

export default function AdminReviewScreen() {
  const { id: idParam } = useLocalSearchParams<{ id?: string | string[] }>();
  const id = Array.isArray(idParam) ? idParam[0] : idParam;
  const { getById, updateSubmission } = useSubmissions();
  const router = useRouter();

  const [note, setNote] = useState('');
  const [overrideVerdict, setOverrideVerdict] = useState<Verdict>('uncertain');

  const row = id ? getById(id) : undefined;

  if (!row || !row.dispute) {
    return (
      <View style={styles.center}>
        <Text style={styles.muted}>Dispute not found or has no user message.</Text>
      </View>
    );
  }

  const s = row;
  const d = s.dispute!;

  function saveReview(resolution: 'uphold_ai' | 'override') {
    const trimmed = note.trim();
    if (trimmed.length < 8) {
      Alert.alert('Admin review', 'A mandatory comment is required (at least 8 characters).');
      return;
    }
    updateSubmission(s.id, {
      adminReview: {
        note: trimmed,
        resolution,
        overrideVerdict: resolution === 'override' ? overrideVerdict : undefined,
        reviewedAt: Date.now(),
      },
    });
    Alert.alert('Saved', 'Review recorded on this device (demo).', [
      { text: 'OK', onPress: () => router.back() },
    ]);
  }

  return (
    <ScrollView contentContainerStyle={styles.container} style={styles.root}>
      <View style={styles.card}>
        <Text style={styles.kicker}>User dispute</Text>
        <Text style={styles.body}>{d.message}</Text>
        {s.submitterEmail ? (
          <Text style={styles.meta}>Reporter: {s.submitterEmail}</Text>
        ) : null}
        <Text style={styles.meta}>{new Date(d.createdAt).toLocaleString()}</Text>
      </View>

      <View style={styles.card}>
        <Text style={styles.kicker}>Model output</Text>
        <Text style={styles.body}>
          Verdict: <Text style={styles.bold}>{s.verdict}</Text> · Confidence{' '}
          {(s.confidence * 100).toFixed(1)}%
        </Text>
        <Text style={styles.bodySmall}>{s.summary}</Text>
      </View>

      {s.textPreview ? (
        <View style={styles.card}>
          <Text style={styles.kicker}>Content</Text>
          <Text style={styles.body}>{s.textPreview}</Text>
        </View>
      ) : null}

      {s.imageUri ? (
        <Image source={{ uri: s.imageUri }} style={styles.image} resizeMode="contain" />
      ) : null}

      {s.adminReview ? (
        <View style={[styles.card, styles.doneCard]}>
          <Text style={styles.kicker}>Already reviewed</Text>
          <Text style={styles.body}>{s.adminReview.note}</Text>
          <Text style={styles.meta}>
            {s.adminReview.resolution === 'uphold_ai' ? 'Uphold AI' : `Override → ${s.adminReview.overrideVerdict}`}
          </Text>
        </View>
      ) : (
        <>
          <Text style={styles.label}>Admin comment (required)</Text>
          <TextInput
            value={note}
            onChangeText={setNote}
            multiline
            placeholder="Explain your decision for the audit trail…"
            placeholderTextColor="#94a3b8"
            style={styles.input}
          />

          <Text style={[styles.label, { marginTop: 14 }]}>If overriding, new verdict</Text>
          <View style={styles.verdictRow}>
            {verdicts.map((v) => (
              <Pressable
                key={v}
                onPress={() => setOverrideVerdict(v)}
                style={[
                  styles.verdictChip,
                  overrideVerdict === v && styles.verdictChipOn,
                ]}>
                <Text style={[styles.verdictChipText, overrideVerdict === v && styles.verdictChipTextOn]}>
                  {v}
                </Text>
              </Pressable>
            ))}
          </View>

          <Pressable style={[styles.btn, styles.uphold]} onPress={() => saveReview('uphold_ai')}>
            <Text style={styles.btnText}>Uphold AI verdict</Text>
          </Pressable>
          <Pressable style={[styles.btn, styles.override]} onPress={() => saveReview('override')}>
            <Text style={styles.btnText}>Override with selected verdict</Text>
          </Pressable>
        </>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: '#ecfdf5',
  },
  container: {
    padding: 20,
    paddingBottom: 40,
    gap: 14,
  },
  center: {
    flex: 1,
    backgroundColor: '#ecfdf5',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
  },
  muted: {
    color: '#64748b',
    fontSize: 15,
  },
  card: {
    backgroundColor: '#fff',
    borderRadius: 14,
    padding: 16,
    borderWidth: 1,
    borderColor: '#a7f3d0',
  },
  doneCard: {
    borderColor: '#86efac',
    backgroundColor: '#f0fdf4',
  },
  kicker: {
    fontSize: 11,
    fontWeight: '800',
    color: '#0f766e',
    textTransform: 'uppercase',
    letterSpacing: 0.8,
    marginBottom: 8,
  },
  body: {
    fontSize: 15,
    lineHeight: 22,
    color: '#0f172a',
  },
  bodySmall: {
    marginTop: 8,
    fontSize: 13,
    lineHeight: 19,
    color: '#475569',
  },
  meta: {
    marginTop: 8,
    fontSize: 12,
    color: '#64748b',
  },
  bold: {
    fontWeight: '800',
  },
  image: {
    width: '100%',
    height: 200,
    borderRadius: 12,
    backgroundColor: '#e2e8f0',
  },
  label: {
    fontSize: 14,
    fontWeight: '700',
    color: '#042f2e',
  },
  input: {
    marginTop: 8,
    borderWidth: 1,
    borderColor: '#cbd5e1',
    borderRadius: 12,
    padding: 12,
    minHeight: 100,
    textAlignVertical: 'top',
    fontSize: 15,
    color: '#0f172a',
    backgroundColor: '#fff',
  },
  verdictRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginTop: 8,
  },
  verdictChip: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 10,
    backgroundColor: '#f1f5f9',
    borderWidth: 1,
    borderColor: '#e2e8f0',
  },
  verdictChipOn: {
    backgroundColor: '#ccfbf1',
    borderColor: '#0d9488',
  },
  verdictChipText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#64748b',
    textTransform: 'capitalize',
  },
  verdictChipTextOn: {
    color: '#0f766e',
  },
  btn: {
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: 'center',
    marginTop: 10,
  },
  uphold: {
    backgroundColor: '#0f766e',
  },
  override: {
    backgroundColor: '#b45309',
  },
  btnText: {
    color: '#fff',
    fontSize: 15,
    fontWeight: '800',
  },
});
