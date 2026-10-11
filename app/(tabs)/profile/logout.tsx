import { useRouter } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { AppText, Button, Icon, useAppTheme } from '@/components/ui';
import { radius, space } from '@/constants/theme';
import { useAuth } from '@/lib/AuthContext';

export default function LogoutScreen() {
  const { colors } = useAppTheme();
  const { signOut } = useAuth();
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  return (
    <View style={[styles.wrap, { backgroundColor: colors.background }]}>
      <View style={[styles.icon, { backgroundColor: colors.misleadingSoft }]}>
        <Icon name="log-out" size={28} color="misleading" />
      </View>
      <AppText variant="title" align="center">Sign out?</AppText>
      <AppText variant="body" color="textMuted" align="center" style={styles.body}>
        Your checks stay saved on the server. You will need to sign in again to see them on this
        device.
      </AppText>
      <View style={styles.actions}>
        <Button label="Sign out" variant="danger" loading={busy} onPress={() => { setBusy(true); void signOut(); }} />
        <Button label="Cancel" variant="secondary" onPress={() => router.back()} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, padding: space.xl, justifyContent: 'center', alignItems: 'center', gap: space.md },
  icon: { width: 64, height: 64, borderRadius: radius.xl, alignItems: 'center', justifyContent: 'center', marginBottom: space.sm },
  body: { maxWidth: 340 },
  actions: { alignSelf: 'stretch', gap: space.sm, marginTop: space.xl },
});
