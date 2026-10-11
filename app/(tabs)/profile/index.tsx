import Constants from 'expo-constants';
import { useRouter } from 'expo-router';
import { ScrollView, StyleSheet, View } from 'react-native';

import { AppText, Avatar, Card, Icon, ListRow, Masthead, Tag, useAppTheme } from '@/components/ui';
import { space } from '@/constants/theme';
import { useAuth } from '@/lib/AuthContext';
import { API_BASE_URL } from '@/lib/config';
import { hrefAdminRoot, hrefProfileEdit, hrefProfileLogout, hrefProfileMe } from '@/lib/navigation';

export default function AccountScreen() {
  const { colors } = useAppTheme();
  const { user } = useAuth();
  const router = useRouter();
  const displayName = user?.name || user?.email?.split('@')[0] || 'User';

  return (
    <ScrollView style={{ backgroundColor: colors.background }} contentContainerStyle={styles.scroll}>
      <Masthead kicker="Account" title={displayName} subtitle={user?.email}>
        <View style={styles.identity}>
          <Avatar uri={user?.avatarUri} name={user?.name || user?.email} size={56} onInk />
          <Tag
            icon={user?.role === 'admin' ? 'shield-check' : 'user'}
            label={user?.role === 'admin' ? 'Administrator' : 'Standard user'}
            tone={user?.role === 'admin' ? 'primary' : 'neutral'}
          />
        </View>
      </Masthead>

      <View style={styles.body}>
        <Section title="Profile">
          <ListRow icon="user" label="My profile" onPress={() => router.push(hrefProfileMe())} />
          <ListRow icon="camera" label="Change profile photo" onPress={() => router.push(hrefProfileEdit())} />
          <ListRow icon="log-out" label="Sign out" tone="danger" divider={false} onPress={() => router.push(hrefProfileLogout())} />
        </Section>

        {user?.role === 'admin' ? (
          <Section title="Administration">
            <ListRow
              icon="layout-dashboard"
              label="Moderation desk"
              description="Review disputes and all submissions"
              divider={false}
              onPress={() => router.push(hrefAdminRoot())}
            />
          </Section>
        ) : null}

        <Section title="About">
          <ListRow icon="info" label="About KhabarNazar" divider={false} onPress={() => router.push('/modal')} />
        </Section>

        <Card tone="muted">
          <View style={styles.serverRow}>
            <Icon name="server" size={18} color="textMuted" />
            <View style={styles.flex}>
              <AppText variant="caption" color="textMuted">Backend</AppText>
              <AppText variant="bodyStrong" selectable numberOfLines={1}>
                {API_BASE_URL || 'Not configured'}
              </AppText>
              {!API_BASE_URL ? (
                <AppText variant="caption" color="misleading" style={styles.mt4}>
                  Set EXPO_PUBLIC_API_URL in .env and restart Expo.
                </AppText>
              ) : null}
            </View>
          </View>
        </Card>

        <AppText variant="caption" color="textSubtle" align="center">
          {Constants.expoConfig?.name ?? 'KhabarNazar'} · version {Constants.expoConfig?.version ?? '1.0.0'}
        </AppText>
      </View>
    </ScrollView>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={styles.section}>
      <AppText variant="overline" color="textMuted" style={styles.sectionTitle}>{title}</AppText>
      <Card padded={false} style={styles.group}>{children}</Card>
    </View>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  scroll: { paddingBottom: space.xxxl },
  identity: { flexDirection: 'row', alignItems: 'center', gap: space.md, marginTop: space.lg },
  body: { padding: space.lg, gap: space.lg },
  section: { gap: space.sm },
  sectionTitle: { paddingHorizontal: space.xs },
  group: { overflow: 'hidden' },
  serverRow: { flexDirection: 'row', gap: space.md },
  mt4: { marginTop: 4 },
});
