import { ScrollView, StyleSheet, View } from 'react-native';

import { AppText, Card, Icon, type IconName, useAppTheme } from '@/components/ui';
import { radius, space } from '@/constants/theme';
import { APP_TAGLINE } from '@/lib/config';

const STEPS: { icon: IconName; title: string; body: string }[] = [
  { icon: 'type', title: 'Submit', body: 'Paste Urdu or Roman Urdu text, or upload a news screenshot.' },
  { icon: 'scan-text', title: 'Analyze', body: 'OCR reads text in images; the text model estimates whether the content is fake.' },
  { icon: 'sparkles', title: 'Explain', body: 'See the words that influenced the model and, for images, any heatmap.' },
  { icon: 'scale', title: 'Dispute', body: 'Disagree? An administrator reviews it and can override the verdict.' },
];

export default function ModalScreen() {
  const { colors } = useAppTheme();
  return (
    <ScrollView style={{ backgroundColor: colors.background }} contentContainerStyle={styles.container}>
      <AppText variant="title">KhabarNazar</AppText>
      <AppText variant="body" color="textMuted">{APP_TAGLINE}</AppText>

      <Card padded={false}>
        {STEPS.map((step, index) => (
          <View
            key={step.title}
            style={[styles.step, index < STEPS.length - 1 && { borderBottomColor: colors.border, borderBottomWidth: StyleSheet.hairlineWidth }]}>
            <View style={[styles.stepIcon, { backgroundColor: colors.primarySoft }]}>
              <Icon name={step.icon} size={18} color="primary" />
            </View>
            <View style={styles.flex}>
              <AppText variant="bodyStrong">{step.title}</AppText>
              <AppText variant="caption" color="textMuted">{step.body}</AppText>
            </View>
          </View>
        ))}
      </Card>

      <Card tone="muted" title="Project">
        <AppText variant="body" color="textMuted">
          A final-year project at FAST-NUCES Lahore on AI-assisted misinformation detection for Urdu and
          Roman Urdu, supporting SDG 16 (credible information) and SDG 9 (innovation for
          under-represented languages).
        </AppText>
      </Card>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  container: { padding: space.xl, gap: space.lg, paddingBottom: space.xxxl },
  step: { flexDirection: 'row', gap: space.md, padding: space.lg },
  stepIcon: { width: 36, height: 36, borderRadius: radius.sm + 2, alignItems: 'center', justifyContent: 'center' },
});
