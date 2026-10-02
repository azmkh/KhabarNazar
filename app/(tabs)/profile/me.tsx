import { Image, ScrollView, StyleSheet, View } from 'react-native';

import { Text } from '@/components/Themed';
import Colors from '@/constants/Colors';
import { useColorScheme } from '@/components/useColorScheme';
import { useAuth } from '@/lib/AuthContext';

export default function MyProfileScreen() {
  const colorScheme = useColorScheme() ?? 'light';
  const theme = Colors[colorScheme];
  const { user } = useAuth();

  return (
    <ScrollView style={{ backgroundColor: theme.background }} contentContainerStyle={styles.container}>
      <View style={[styles.avatarCard, { backgroundColor: theme.card, borderColor: theme.border }]}>
        {user?.avatarUri ? (
          <Image source={{ uri: user.avatarUri }} style={styles.avatarLarge} />
        ) : (
          <View style={[styles.avatarFallback, { borderColor: theme.border }]}>
            <Text style={[styles.initials, { color: theme.muted }]}>
              {(user?.displayName || user?.email || '?')
                .trim()
                .slice(0, 2)
                .toUpperCase()}
            </Text>
          </View>
        )}
        <Text style={[styles.name, { color: theme.text }]}>
          {user?.displayName || user?.email?.split('@')[0] || 'User'}
        </Text>
        <Text style={[styles.emailLine, { color: theme.muted }]}>{user?.email ?? '—'}</Text>
      </View>

      <View style={[styles.card, { backgroundColor: theme.card, borderColor: theme.border }]}>
        <Text style={[styles.label, { color: theme.muted }]}>Display name</Text>
        <Text style={[styles.value, { color: theme.text }]}>{user?.displayName || '—'}</Text>
      </View>
      <View style={[styles.card, { backgroundColor: theme.card, borderColor: theme.border }]}>
        <Text style={[styles.label, { color: theme.muted }]}>Email</Text>
        <Text style={[styles.value, { color: theme.text }]}>{user?.email ?? '—'}</Text>
      </View>
      <Text style={[styles.note, { color: theme.muted }]}>
        Password and verification are managed on the server in production.
      </Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    padding: 20,
    gap: 14,
    paddingBottom: 40,
  },
  avatarCard: {
    borderRadius: 16,
    borderWidth: 1,
    padding: 20,
    alignItems: 'center',
  },
  avatarLarge: {
    width: 96,
    height: 96,
    borderRadius: 48,
  },
  avatarFallback: {
    width: 96,
    height: 96,
    borderRadius: 48,
    borderWidth: 2,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#00000008',
  },
  initials: {
    fontSize: 28,
    fontWeight: '800',
  },
  name: {
    marginTop: 14,
    fontSize: 20,
    fontWeight: '800',
  },
  emailLine: {
    marginTop: 4,
    fontSize: 14,
  },
  card: {
    borderRadius: 14,
    borderWidth: 1,
    padding: 16,
  },
  label: {
    fontSize: 12,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  value: {
    marginTop: 8,
    fontSize: 17,
    fontWeight: '600',
  },
  note: {
    fontSize: 13,
    lineHeight: 19,
  },
});
