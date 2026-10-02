import { useLocalSearchParams, useRouter } from 'expo-router';
import { Image, Pressable, ScrollView, StyleSheet } from 'react-native';

import { ScoreBar } from '@/components/ScoreBar';
import { Text, View } from '@/components/Themed';
import Colors from '@/constants/Colors';
import { useColorScheme } from '@/components/useColorScheme';
import { hrefDisputeDetail } from '@/lib/navigation';
import { useSubmissions } from '@/lib/SubmissionsContext';

function verdictTitle(verdict: string) {
  if (verdict === 'credible') return 'Likely credible';
  if (verdict === 'misleading') return 'Likely misleading';
  return 'Uncertain';
}

export default function ResultScreen() {
  const { id: idParam } = useLocalSearchParams<{ id?: string | string[] }>();
  const id = Array.isArray(idParam) ? idParam[0] : idParam;
  const { getById } = useSubmissions();
  const router = useRouter();
  const colorScheme = useColorScheme() ?? 'light';
  const theme = Colors[colorScheme];
  const row = id ? getById(id) : undefined;

  if (!row) {
    return (
      <View style={[styles.center, { backgroundColor: theme.background }]}>
        <Text style={{ color: theme.muted }}>This result is no longer in memory.</Text>
      </View>
    );
  }

  const verdictColor = theme[row.verdict];
  const conf = row.confidence ?? 0.5;
  const lq = row.languageQuality ?? 55;
  const lqLabel = row.languageQualityLabel ?? '—';
  const sc = row.sourceCredibility ?? 50;
  const scLabel = row.sourceCredibilityLabel ?? '—';
  const manip = row.manipulationLikelihood;
  const manipLabel = row.manipulationLabel ?? '—';

  const track = colorScheme === 'dark' ? '#334155' : '#e2e8f0';

  return (
    <ScrollView contentContainerStyle={styles.container} style={{ backgroundColor: theme.background }}>
      <View
        style={[
          styles.banner,
          { backgroundColor: `${verdictColor}22`, borderColor: verdictColor },
        ]}>
        <Text style={[styles.verdict, { color: verdictColor }]}>{verdictTitle(row.verdict)}</Text>
        <Text style={[styles.confLabel, { color: theme.muted }]}>Calibrated confidence</Text>
        <Text style={[styles.confValue, { color: theme.text }]}>{(conf * 100).toFixed(1)}%</Text>
        <Text style={[styles.confHint, { color: theme.muted }]}>
          Combined text + image cues (when present). Not a probability of “truth.”
        </Text>
      </View>

      <View style={[styles.card, { backgroundColor: theme.card, borderColor: theme.border }]}>
        <Text style={[styles.section, { color: theme.muted }]}>Language quality</Text>
        <Text style={[styles.scoreNum, { color: theme.text }]}>{lq}/100</Text>
        <ScoreBar value={lq} trackColor={track} fillColor={theme.tint} />
        <Text style={[styles.metricNote, { color: theme.muted }]}>{lqLabel}</Text>
      </View>

      <View style={[styles.card, { backgroundColor: theme.card, borderColor: theme.border }]}>
        <Text style={[styles.section, { color: theme.muted }]}>Source credibility</Text>
        <Text style={[styles.scoreNum, { color: theme.text }]}>{sc}/100</Text>
        <ScoreBar value={sc} trackColor={track} fillColor={theme.credible} />
        <Text style={[styles.metricNote, { color: theme.muted }]}>{scLabel}</Text>
      </View>

      <View style={[styles.card, { backgroundColor: theme.card, borderColor: theme.border }]}>
        <Text style={[styles.section, { color: theme.muted }]}>Manipulation likelihood</Text>
        {manip === null ? (
          <Text style={{ color: theme.muted, marginTop: 6, fontSize: 15 }}>{manipLabel}</Text>
        ) : (
          <>
            <Text style={[styles.scoreNum, { color: theme.text }]}>{manip}/100</Text>
            <ScoreBar value={manip} trackColor={track} fillColor={theme.uncertain} />
            <Text style={[styles.metricNote, { color: theme.muted }]}>{manipLabel}</Text>
          </>
        )}
      </View>

      {row.imageUri ? (
        <Image source={{ uri: row.imageUri }} style={styles.image} resizeMode="contain" />
      ) : null}

      {row.textPreview ? (
        <View style={[styles.card, { backgroundColor: theme.card, borderColor: theme.border }]}>
          <Text style={[styles.section, { color: theme.muted }]}>Submitted text</Text>
          <Text style={{ color: theme.text, marginTop: 6, fontSize: 16, lineHeight: 24 }}>{row.textPreview}</Text>
        </View>
      ) : null}

      <View style={[styles.card, { backgroundColor: theme.card, borderColor: theme.border }]}>
        <Text style={[styles.section, { color: theme.muted }]}>Summary</Text>
        <Text style={{ color: theme.text, marginTop: 6, fontSize: 16, lineHeight: 24 }}>{row.summary}</Text>
      </View>

      <View style={[styles.card, { backgroundColor: theme.card, borderColor: theme.border }]}>
        <Text style={[styles.section, { color: theme.muted }]}>Explainability (next)</Text>
        <Text style={{ color: theme.muted, marginTop: 6, fontSize: 14, lineHeight: 21 }}>
          SHAP token highlights and Grad-CAM heatmaps will render here once your FastAPI returns
          those payloads.
        </Text>
      </View>

      <Pressable
        onPress={() => router.push(hrefDisputeDetail(row.id))}
        style={({ pressed }) => [
          styles.disputeBtn,
          { borderColor: theme.tint, opacity: pressed ? 0.88 : 1 },
        ]}>
        <Text style={[styles.disputeBtnText, { color: theme.tint }]}>
          {row.dispute ? 'View or update dispute' : 'Dispute this result'}
        </Text>
      </Pressable>
    </ScrollView>
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
  banner: {
    borderRadius: 14,
    borderWidth: 1,
    padding: 16,
  },
  verdict: {
    fontSize: 22,
    fontWeight: '800',
  },
  confLabel: {
    marginTop: 10,
    fontSize: 12,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.6,
  },
  confValue: {
    fontSize: 28,
    fontWeight: '800',
    marginTop: 4,
  },
  confHint: {
    marginTop: 8,
    fontSize: 13,
    lineHeight: 18,
  },
  image: {
    width: '100%',
    height: 220,
    borderRadius: 12,
    backgroundColor: '#00000012',
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
    letterSpacing: 0.6,
  },
  scoreNum: {
    fontSize: 20,
    fontWeight: '800',
    marginTop: 6,
    marginBottom: 8,
  },
  metricNote: {
    marginTop: 10,
    fontSize: 14,
    lineHeight: 20,
  },
  disputeBtn: {
    borderWidth: 2,
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: 'center',
  },
  disputeBtnText: {
    fontSize: 16,
    fontWeight: '800',
  },
});
