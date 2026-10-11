import { ScrollView, StyleSheet, View } from 'react-native';

import { AppText, Avatar, Card, Icon, type IconName, useAppTheme } from '@/components/ui';
import { space } from '@/constants/theme';
import { useAuth } from '@/lib/AuthContext';
import { fullDate } from '@/lib/format';

export default function MyProfileScreen() {
  const { colors } = useAppTheme();
  const { user } = useAuth();
  const joined = user?.created_at ? Date.parse(user.created_at) : NaN;

  return (
    <ScrollView style={{ backgroundColor: colors.background }} contentContainerStyle={styles.container}>
      <View style={styles.header}>
        <Avatar uri={user?.avatarUri} name={user?.name || user?.email} size={96} />
        <AppText variant="title" align="center">{user?.name || user?.email?.split('@')[0] || 'User'}</AppText>
        <AppText variant="body" color="textMuted" align="center">{user?.email ?? '—'}</AppText>
      </View>

      <Card padded={false}>
        <Field icon="user" label="Name" value={user?.name || '—'} />
        <Field icon="mail" label="Email" value={user?.email ?? '—'} />
        <Field icon="shield-check" label="Role" value={user?.role === 'admin' ? 'Administrator' : 'Standard user'} />
        <Field icon="calendar" label="Member since" value={Number.isFinite(joined) ? fullDate(joined) : '—'} last />
      </Card>

      <AppText variant="caption" color="textSubtle" align="center">
        Name and email are managed by the server and cannot be changed from the app yet.
      </AppText>
    </ScrollView>
  );
}

function Field({ icon, label, value, last }: { icon: IconName; label: string; value: string; last?: boolean }) {
  const { colors } = useAppTheme();
  return (
    <View style={[styles.field, !last && { borderBottomColor: colors.border, borderBottomWidth: StyleSheet.hairlineWidth }]}>
      <Icon name={icon} size={18} color="textMuted" />
      <View style={styles.fieldText}>
        <AppText variant="caption" color="textMuted">{label}</AppText>
        <AppText variant="bodyStrong" selectable>{value}</AppText>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { padding: space.lg, gap: space.lg, paddingBottom: space.xxxl },
  header: { alignItems: 'center', gap: space.xs, paddingVertical: space.md },
  field: { flexDirection: 'row', alignItems: 'center', gap: space.md, padding: space.lg },
  fieldText: { flex: 1, gap: 2 },
});
