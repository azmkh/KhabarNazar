import { useFocusEffect, useRouter } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useCallback, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';

import { AppText, Card, Icon, type IconName, ListRow, Masthead, useAppTheme } from '@/components/ui';
import { radius, space } from '@/constants/theme';
import { getAdminStats, type ApiAdminStats } from '@/lib/api';
import { useAuth } from '@/lib/AuthContext';
import { hrefAdminDisputes, hrefAdminSubmissions } from '@/lib/navigation';

export default function AdminDashboardScreen() {
  const router = useRouter();
  const { colors } = useAppTheme();
  const { user, accessToken } = useAuth();
  const [stats, setStats] = useState<ApiAdminStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Totals are counted by the server across the whole database, not from one page of rows.
  const refresh = useCallback(async () => {
    if (!accessToken) return;
    setLoading(true);
    setError(null);
    try {
      setStats(await getAdminStats(accessToken));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load the dashboard.');
    } finally {
      setLoading(false);
    }
  }, [accessToken]);

  useFocusEffect(useCallback(() => { void refresh(); }, [refresh]));

  const value = (n: number | undefined) => (stats ? n ?? 0 : '–');
  const pending = stats?.disputes.pending ?? 0;

  return (
    <ScrollView style={{ backgroundColor: colors.background }} contentContainerStyle={styles.scroll}>
      <StatusBar style="light" />
      <Masthead
        kicker="Administration"
        title="Moderation desk"
        subtitle={`Signed in as ${user?.email ?? 'admin'}`}
        accessory={
          <Pressable
            onPress={() => router.replace('/(tabs)')}
            hitSlop={12}
            accessibilityRole="button"
            accessibilityLabel="Close admin console"
            style={[styles.close, { backgroundColor: colors.inkSoft }]}>
            <Icon name="x" size={20} color="onInk" />
          </Pressable>
        }
      />

      <View style={styles.body}>
        <View style={styles.grid}>
          <Stat icon="inbox" label="Total checks" value={value(stats?.submissions)} color={colors.primary} soft={colors.primarySoft} />
          <Stat icon="flag" label="Pending disputes" value={value(stats?.disputes.pending)} color={colors.uncertain} soft={colors.uncertainSoft} />
          <Stat icon="badge-check" label="Disputes reviewed" value={value(stats?.disputes.reviewed)} color={colors.credible} soft={colors.credibleSoft} />
          <Stat icon="shield-alert" label="Flagged misleading" value={value(stats?.submissions_by_label.Fake)} color={colors.misleading} soft={colors.misleadingSoft} />
          <Stat icon="users" label="Registered users" value={value(stats?.users)} color={colors.info} soft={colors.infoSoft} />
          <Stat icon="pencil" label="Admin overrides" value={value(stats?.admin_overrides)} color={colors.textMuted} soft={colors.surfaceMuted} />
        </View>

        <Card padded={false} style={styles.group}>
          <ListRow
            icon="scale"
            label="Dispute queue"
            description={pending ? `${pending} waiting for a decision` : 'No disputes waiting'}
            onPress={() => router.push(hrefAdminDisputes())}
          />
          <ListRow
            icon="list"
            label="All submissions"
            description={stats ? `${stats.submissions} checks from ${stats.users} users` : 'Every check with its verdict and dispute status'}
            divider={false}
            onPress={() => router.push(hrefAdminSubmissions())}
          />
        </Card>

        <Card tone="muted">
          <View style={styles.notice}>
            <Icon name={error ? 'circle-alert' : 'refresh-cw'} size={16} color={error ? 'misleading' : 'textMuted'} />
            <AppText variant="caption" color={error ? 'misleading' : 'textMuted'} style={styles.flex}>
              {error ?? (loading ? 'Refreshing totals…' : 'Totals are counted across the whole database.')}
            </AppText>
            {!loading ? (
              <Pressable onPress={() => void refresh()} hitSlop={8} accessibilityRole="button">
                <AppText variant="caption" color="primary">Refresh</AppText>
              </Pressable>
            ) : null}
          </View>
        </Card>
      </View>
    </ScrollView>
  );
}

function Stat({ icon, label, value, color, soft }: { icon: IconName; label: string; value: number | string; color: string; soft: string }) {
  return (
    <Card style={styles.stat}>
      <View style={[styles.statIcon, { backgroundColor: soft }]}>
        <Icon name={icon} size={18} color={color} />
      </View>
      <AppText variant="title">{value}</AppText>
      <AppText variant="caption" color="textMuted">{label}</AppText>
    </Card>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  scroll: { paddingBottom: space.xxxl },
  close: { width: 40, height: 40, borderRadius: radius.md, alignItems: 'center', justifyContent: 'center' },
  body: { padding: space.lg, gap: space.lg },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: space.md },
  stat: { flexBasis: '47%', flexGrow: 1, gap: 4 },
  statIcon: { width: 36, height: 36, borderRadius: radius.sm + 2, alignItems: 'center', justifyContent: 'center', marginBottom: space.xs },
  group: { overflow: 'hidden' },
  notice: { flexDirection: 'row', alignItems: 'center', gap: space.sm },
});
