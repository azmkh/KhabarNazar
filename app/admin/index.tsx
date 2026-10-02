import FontAwesome from '@expo/vector-icons/FontAwesome';
import { useRouter } from 'expo-router';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useAuth } from '@/lib/AuthContext';
import { hrefAdminDisputes, hrefAdminSubmissions } from '@/lib/navigation';
import { useSubmissions } from '@/lib/SubmissionsContext';

const cardRadius = 16;

function StatCard({
  icon,
  label,
  value,
  sub,
  accent,
}: {
  icon: React.ComponentProps<typeof FontAwesome>['name'];
  label: string;
  value: string | number;
  sub?: string;
  accent: string;
}) {
  return (
    <View style={[styles.statCard, { borderLeftColor: accent }]}>
      <FontAwesome name={icon} size={22} color={accent} />
      <Text style={styles.statValue}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
      {sub ? <Text style={styles.statSub}>{sub}</Text> : null}
    </View>
  );
}

export default function AdminDashboardScreen() {
  const router = useRouter();
  const { submissions } = useSubmissions();
  const { user } = useAuth();

  const total = submissions.length;
  const withDispute = submissions.filter((s) => s.dispute).length;
  const pendingReview = submissions.filter((s) => s.dispute && !s.adminReview).length;
  const reviewed = submissions.filter((s) => s.adminReview).length;

  return (
    <ScrollView contentContainerStyle={styles.scroll} style={styles.root}>
      <View style={styles.hero}>
        <Pressable onPress={() => router.replace('/(tabs)')} style={styles.exitFab} hitSlop={12}>
          <FontAwesome name="times" size={20} color="#042f2e" />
        </Pressable>
        <Text style={styles.heroKicker}>KhabarNazar</Text>
        <Text style={styles.heroTitle}>Moderation desk</Text>
        <Text style={styles.heroSub}>
          Figma-inspired overview — disputes, model outputs, and mandatory human review before
          overrides.
        </Text>
      </View>

      <View style={styles.welcomeBar}>
        <FontAwesome name="user-circle" size={18} color="#0f766e" />
        <Text style={styles.welcomeText}>
          Signed in as <Text style={{ fontWeight: '800' }}>{user?.email}</Text>
        </Text>
      </View>

      <View style={styles.grid}>
        <StatCard icon="inbox" label="Total checks" value={total} accent="#0d9488" />
        <StatCard icon="flag" label="Open disputes" value={pendingReview} sub={`${withDispute} with any dispute`} accent="#b45309" />
        <StatCard icon="check-circle" label="Reviewed" value={reviewed} sub="Admin decisions logged" accent="#15803d" />
        <StatCard icon="line-chart" label="Queue health" value={pendingReview === 0 ? 'Clear' : 'Busy'} accent="#6366f1" />
      </View>

      <Text style={styles.sectionTitle}>Quick actions</Text>
      <View style={styles.actions}>
        <Pressable
          onPress={() => router.push(hrefAdminDisputes())}
          style={({ pressed }) => [styles.actionTile, pressed && styles.actionPressed]}>
          <View style={[styles.actionIconWrap, { backgroundColor: '#ccfbf1' }]}>
            <FontAwesome name="gavel" size={24} color="#0f766e" />
          </View>
          <Text style={styles.actionTitle}>Dispute queue</Text>
          <Text style={styles.actionDesc}>Prioritized list with user comments</Text>
        </Pressable>

        <Pressable
          onPress={() => router.push(hrefAdminSubmissions())}
          style={({ pressed }) => [styles.actionTile, pressed && styles.actionPressed]}>
          <View style={[styles.actionIconWrap, { backgroundColor: '#e0e7ff' }]}>
            <FontAwesome name="list-alt" size={24} color="#4338ca" />
          </View>
          <Text style={styles.actionTitle}>All submissions</Text>
          <Text style={styles.actionDesc}>Browse verdicts and confidence at a glance</Text>
        </Pressable>
      </View>

      <View style={styles.notice}>
        <FontAwesome name="info-circle" size={16} color="#0f766e" />
        <Text style={styles.noticeText}>
          Demo data lives on this device only. Connect FastAPI + PostgreSQL for real queues and audit
          trails.
        </Text>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: '#ecfdf5',
  },
  scroll: {
    padding: 20,
    paddingBottom: 40,
  },
  hero: {
    marginBottom: 18,
    position: 'relative',
  },
  exitFab: {
    position: 'absolute',
    right: 0,
    top: 0,
    zIndex: 2,
    padding: 8,
    backgroundColor: '#fff',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#99f6e4',
  },
  heroKicker: {
    fontSize: 12,
    fontWeight: '800',
    color: '#0f766e',
    letterSpacing: 1.2,
    textTransform: 'uppercase',
  },
  heroTitle: {
    fontSize: 28,
    fontWeight: '800',
    color: '#042f2e',
    marginTop: 6,
    letterSpacing: -0.5,
  },
  heroSub: {
    marginTop: 8,
    fontSize: 14,
    lineHeight: 21,
    color: '#134e4a',
  },
  welcomeBar: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    backgroundColor: '#fff',
    borderRadius: cardRadius,
    padding: 14,
    marginBottom: 18,
    borderWidth: 1,
    borderColor: '#99f6e4',
  },
  welcomeText: {
    flex: 1,
    fontSize: 14,
    color: '#134e4a',
  },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
    marginBottom: 22,
  },
  statCard: {
    width: '47%',
    backgroundColor: '#fff',
    borderRadius: cardRadius,
    padding: 14,
    borderLeftWidth: 4,
    borderWidth: 1,
    borderColor: '#d1fae5',
  },
  statValue: {
    fontSize: 26,
    fontWeight: '800',
    color: '#042f2e',
    marginTop: 8,
  },
  statLabel: {
    fontSize: 13,
    fontWeight: '600',
    color: '#0f766e',
    marginTop: 2,
  },
  statSub: {
    fontSize: 11,
    color: '#64748b',
    marginTop: 6,
    lineHeight: 15,
  },
  sectionTitle: {
    fontSize: 13,
    fontWeight: '800',
    color: '#042f2e',
    textTransform: 'uppercase',
    letterSpacing: 0.8,
    marginBottom: 12,
  },
  actions: {
    gap: 12,
  },
  actionTile: {
    backgroundColor: '#fff',
    borderRadius: cardRadius,
    padding: 18,
    borderWidth: 1,
    borderColor: '#a7f3d0',
  },
  actionPressed: {
    opacity: 0.92,
    transform: [{ scale: 0.99 }],
  },
  actionIconWrap: {
    width: 48,
    height: 48,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 12,
  },
  actionTitle: {
    fontSize: 18,
    fontWeight: '800',
    color: '#042f2e',
  },
  actionDesc: {
    fontSize: 13,
    color: '#475569',
    marginTop: 6,
    lineHeight: 19,
  },
  notice: {
    flexDirection: 'row',
    gap: 10,
    marginTop: 22,
    padding: 14,
    backgroundColor: '#f0fdfa',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#5eead4',
  },
  noticeText: {
    flex: 1,
    fontSize: 13,
    lineHeight: 19,
    color: '#115e59',
  },
});
