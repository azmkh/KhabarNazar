import { useRouter } from 'expo-router';
import { Pressable, StyleSheet, View } from 'react-native';

import { Text } from '@/components/Themed';
import Colors from '@/constants/Colors';
import { useColorScheme } from '@/components/useColorScheme';
import { useAuth } from '@/lib/AuthContext';

export default function LogoutScreen() {
  const colorScheme = useColorScheme() ?? 'light';
  const theme = Colors[colorScheme];
  const { signOut } = useAuth();
  const router = useRouter();

  return (
    <View style={[styles.wrap, { backgroundColor: theme.background }]}>
      <View style={[styles.card, { backgroundColor: theme.card, borderColor: theme.border }]}>
        <Text style={[styles.title, { color: theme.text }]}>Sign out?</Text>
        <Text style={[styles.body, { color: theme.muted }]}>
          You will need to sign in again to run checks and view history on this device (demo session
          is cleared from local storage).
        </Text>

        <Pressable
          onPress={() => router.back()}
          style={({ pressed }) => [
            styles.secondary,
            { borderColor: theme.border, opacity: pressed ? 0.85 : 1 },
          ]}>
          <Text style={[styles.secondaryText, { color: theme.text }]}>Cancel</Text>
        </Pressable>

        <Pressable
          onPress={() => void signOut()}
          style={({ pressed }) => [
            styles.primary,
            { backgroundColor: theme.misleading, opacity: pressed ? 0.9 : 1 },
          ]}>
          <Text style={styles.primaryText}>Log out</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flex: 1,
    padding: 20,
    justifyContent: 'center',
  },
  card: {
    borderRadius: 16,
    borderWidth: 1,
    padding: 22,
  },
  title: {
    fontSize: 22,
    fontWeight: '800',
    marginBottom: 10,
  },
  body: {
    fontSize: 15,
    lineHeight: 22,
    marginBottom: 22,
  },
  secondary: {
    borderWidth: 1,
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: 'center',
    marginBottom: 12,
  },
  secondaryText: {
    fontSize: 16,
    fontWeight: '700',
  },
  primary: {
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: 'center',
  },
  primaryText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '800',
  },
});
