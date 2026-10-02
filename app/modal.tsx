import { Platform, StyleSheet } from 'react-native';

import { Text, View } from '@/components/Themed';

export default function ModalScreen() {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>About KhabarNazar</Text>
      <Text style={styles.body}>
        KhabarNazar is a final-year project at FAST-NUCES Lahore: AI-assisted misinformation detection
        for Urdu and Roman Urdu, with optional image analysis (OCR + manipulation cues) and planned
        SHAP / Grad-CAM explanations plus an admin dispute flow.
      </Text>
      <Text style={styles.body}>
        This mobile shell is ready to connect to your FastAPI backend. Until{' '}
        <Text style={{ fontWeight: '700' }}>EXPO_PUBLIC_API_URL</Text> is set, the app uses on-device
        mock responses so you can demo navigation and UX.
      </Text>
      {Platform.OS === 'web' ? null : (
        <Text style={[styles.body, styles.muted]}>
          Use the Check tab to submit text or a gallery image, then open History to revisit analyses.
        </Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 22,
    justifyContent: 'center',
  },
  title: {
    fontSize: 22,
    fontWeight: '800',
    marginBottom: 14,
  },
  body: {
    fontSize: 16,
    lineHeight: 24,
    marginBottom: 12,
  },
  muted: {
    opacity: 0.85,
  },
});
