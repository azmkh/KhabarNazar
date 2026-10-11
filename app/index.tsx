import { Redirect } from 'expo-router';
import { ActivityIndicator, StyleSheet, View } from 'react-native';

import { AppText, Wordmark, useAppTheme } from '@/components/ui';
import { space } from '@/constants/theme';
import { useAuth } from '@/lib/AuthContext';

/**
 * Chooses the first real screen after native splash + session hydration.
 */
export default function Index() {
  const { user, ready } = useAuth();
  const { colors } = useAppTheme();

  if (!ready) {
    return (
      <View style={[styles.boot, { backgroundColor: colors.ink }]}>
        <Wordmark size="lg" />
        <ActivityIndicator color={colors.onInk} style={styles.spinner} />
        <AppText variant="caption" color="onInkMuted">Loading your session…</AppText>
      </View>
    );
  }

  if (user) {
    return <Redirect href="/(tabs)" />;
  }

  return <Redirect href="/login" />;
}

const styles = StyleSheet.create({
  boot: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: space.xl,
    gap: space.lg,
  },
  spinner: { marginTop: space.xl },
});
