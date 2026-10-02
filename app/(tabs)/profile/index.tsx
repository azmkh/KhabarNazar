import { useRouter } from 'expo-router';
import Constants from 'expo-constants';
import { Image, Pressable, ScrollView, StyleSheet } from 'react-native';
import FontAwesome from '@expo/vector-icons/FontAwesome';

import { Text, View } from '@/components/Themed';
import Colors from '@/constants/Colors';
import { useColorScheme } from '@/components/useColorScheme';
import { API_BASE_URL, APP_TAGLINE } from '@/lib/config';
import { isAdminEmail } from '@/lib/admin';
import { useAuth } from '@/lib/AuthContext';
import { hrefAdminRoot, hrefProfileEdit, hrefProfileLogout, hrefProfileMe } from '@/lib/navigation';

function Row({
  icon,
  label,
  onPress,
  theme,
}: {
  icon: React.ComponentProps<typeof FontAwesome>['name'];
  label: string;
  onPress: () => void;
  theme: (typeof Colors)['light'];
}) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.row,
        { backgroundColor: theme.card, borderColor: theme.border, opacity: pressed ? 0.85 : 1 },
      ]}>
      <FontAwesome name={icon} size={20} color={theme.tint} />
      <Text style={[styles.rowLabel, { color: theme.text }]}>{label}</Text>
      <FontAwesome name="chevron-right" size={14} color={theme.muted} style={{ marginLeft: 'auto' }} />
    </Pressable>
  );
}

export default function SettingsHubScreen() {
  const colorScheme = useColorScheme() ?? 'light';
  const theme = Colors[colorScheme];
  const { user } = useAuth();
  const router = useRouter();

  const apiLine = API_BASE_URL ? API_BASE_URL : '(not set — mock analysis on device)';

  return (
    <ScrollView style={{ backgroundColor: theme.background }} contentContainerStyle={styles.container}>
      <View style={[styles.card, { backgroundColor: theme.card, borderColor: theme.border }]}>
        <View style={styles.accountRow}>
          {user?.avatarUri ? (
            <Image source={{ uri: user.avatarUri }} style={styles.accountAvatar} />
          ) : (
            <View style={[styles.accountAvatarPh, { borderColor: theme.border }]}>
              <Text style={[styles.accountInitial, { color: theme.muted }]}>
                {(user?.displayName || user?.email || '?').trim().slice(0, 1).toUpperCase()}
              </Text>
            </View>
          )}
          <View style={{ flex: 1 }}>
            <Text style={[styles.h, { color: theme.text }]}>Account</Text>
            <Text style={[styles.p, { color: theme.muted }]}>
              {user?.displayName || user?.email?.split('@')[0] || 'User'}
            </Text>
            <Text style={[styles.email, { color: theme.muted }]}>{user?.email}</Text>
          </View>
        </View>
      </View>

      <Text style={[styles.section, { color: theme.muted }]}>Profile</Text>
      <Row icon="user" label="My profile" onPress={() => router.push(hrefProfileMe())} theme={theme} />
      <Row icon="pencil" label="Edit profile" onPress={() => router.push(hrefProfileEdit())} theme={theme} />
      <Row icon="sign-out" label="Log out" onPress={() => router.push(hrefProfileLogout())} theme={theme} />

      {isAdminEmail(user?.email) ? (
        <>
          <Text style={[styles.section, { color: theme.muted, marginTop: 8 }]}>Administration</Text>
          <Row
            icon="shield"
            label="Admin console"
            onPress={() => router.push(hrefAdminRoot())}
            theme={theme}
          />
          <Text style={[styles.adminHint, { color: theme.muted }]}>
            Demo access: email local part must include <Text style={{ fontWeight: '800' }}>+admin</Text>{' '}
            (e.g. you+admin@gmail.com).
          </Text>
        </>
      ) : null}

      <Text style={[styles.section, { color: theme.muted, marginTop: 8 }]}>App</Text>
      <View style={[styles.card, { backgroundColor: theme.card, borderColor: theme.border }]}>
        <Text style={[styles.h, { color: theme.text }]}>Backend URL</Text>
        <Text style={[styles.mono, { color: theme.muted }]}>{apiLine}</Text>
        <Text style={[styles.p, { color: theme.muted, marginTop: 10 }]}>
          Set <Text style={{ fontWeight: '700', color: theme.text }}>EXPO_PUBLIC_API_URL</Text> in `.env`,
          then restart Expo.
        </Text>
      </View>

      <View style={[styles.card, { backgroundColor: theme.card, borderColor: theme.border }]}>
        <Text style={[styles.h, { color: theme.text }]}>About</Text>
        <Text style={[styles.p, { color: theme.muted }]}>
          {Constants.expoConfig?.name ?? 'KhabarNazar'} · {Constants.expoConfig?.version ?? '1.0.0'}
        </Text>
        <Text style={[styles.p, { color: theme.muted, marginTop: 8 }]}>{APP_TAGLINE}</Text>
      </View>

      <View style={[styles.card, { backgroundColor: theme.card, borderColor: theme.border }]}>
        <Text style={[styles.h, { color: theme.text }]}>SDG alignment</Text>
        <Text style={[styles.p, { color: theme.muted }]}>
          SDG 16 — credible information. SDG 9 — innovation for underrepresented languages.
        </Text>
      </View>

      <Pressable onPress={() => router.push('/modal')} style={styles.aboutLink}>
        <Text style={{ color: theme.tint, fontWeight: '600' }}>Full about (modal)</Text>
      </Pressable>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    padding: 20,
    gap: 10,
    paddingBottom: 40,
  },
  card: {
    borderRadius: 14,
    borderWidth: 1,
    padding: 16,
  },
  h: {
    fontSize: 17,
    fontWeight: '700',
    marginBottom: 6,
  },
  accountRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
  },
  accountAvatar: {
    width: 52,
    height: 52,
    borderRadius: 26,
  },
  accountAvatarPh: {
    width: 52,
    height: 52,
    borderRadius: 26,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#00000006',
  },
  accountInitial: {
    fontSize: 22,
    fontWeight: '800',
  },
  p: {
    fontSize: 14,
    lineHeight: 21,
  },
  email: {
    fontSize: 13,
    marginTop: 4,
  },
  mono: {
    fontSize: 12,
    lineHeight: 18,
  },
  section: {
    fontSize: 12,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.6,
    marginTop: 8,
    marginBottom: 4,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    borderRadius: 14,
    borderWidth: 1,
    paddingVertical: 14,
    paddingHorizontal: 14,
  },
  rowLabel: {
    fontSize: 16,
    fontWeight: '600',
  },
  aboutLink: {
    marginTop: 8,
    alignSelf: 'center',
    padding: 8,
  },
  adminHint: {
    fontSize: 12,
    lineHeight: 17,
    marginTop: 6,
    paddingHorizontal: 4,
  },
});
