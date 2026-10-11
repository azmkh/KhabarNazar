import { useFocusEffect, useRouter } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useCallback } from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';

import { AppText, Card, Icon, type IconName, ListRow, Masthead, useAppTheme } from '@/components/ui';
import { radius, space } from '@/constants/theme';
import { useAuth } from '@/lib/AuthContext';
import { hrefAdminDisputes, hrefAdminSubmissions } from '@/lib/navigation';
import { useSubmissions } from '@/lib/SubmissionsContext';

export default function AdminDashboardScreen() {
  const router = useRouter();
  const { colors } = useAppTheme();
  const { submissions, loading, loadError, refreshSubmissions } = useSubmissions();
  const { user } = useAuth();

  useFocusEffect(useCallback(() => { void refreshSubmissions().catch(() => undefined); }, [refreshSubmissions]));

  const total = submissions.length;
  const pending = submissions.filter((s) => s.dispute?.status === 'pending').length;
  const reviewed = submissions.filter((s) => s.adminReview).length;
  const misleading = submissions.filter((s) => s.verdict === 'misleading').length;

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
          <Stat icon="inbox" label="Total checks" value={total} color={colors.primary} soft={colors.primarySoft} />
          <Stat icon="flag" label="Pending disputes" value={pending} color={colors.uncertain} soft={colors.uncertainSoft} />
          <Stat icon="badge-check" label="Reviewed" value={reviewed} color={colors.credible} soft={colors.credibleSoft} />
          <Stat icon="shield-alert" label="Flagged misleading" value={misleading} color={colors.misleading} soft={colors.misleadingSoft} />
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
            description="Every check with its verdict and confidence"
            divider={false}
            onPress={() => router.push(hrefAdminSubmissions())}
          />
        </Card>

        <Card tone="muted">
          <View style={styles.notice}>
            <Icon name={loadError ? 'circle-alert' : 'refresh-cw'} size={16} color={loadError ? 'misleading' : 'textMuted'} />
            <AppText variant="caption" color={loadError ? 'misleading' : 'textMuted'} style={styles.flex}>
              {loadError ?? (loading ? 'Refreshing moderation data…' : 'Live data from the FastAPI backend.')}
            </AppText>
            {!loading ? (
              <Pressable onPress={() => void refreshSubmissions().catch(() => undefined)} hitSlop={8} accessibilityRole="button">
                <AppText variant="caption" color="primary">Refresh</AppText>
              </Pressable>
            ) : null}
          </View>
        </Card>
      </View>
    </ScrollView>
  );
}

function Stat({ icon, label, value, color, soft }: { icon: IconName; label: string; value: number; color: string; soft: string }) {
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
