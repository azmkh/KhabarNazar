import { Redirect } from 'expo-router';
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';
import { useAuth } from '@/lib/AuthContext';

/**
 * Chooses the first real screen after native splash + session hydration.
 */
export default function Index() {
  const { user, ready } = useAuth();

  if (!ready) {
    return (
      <View style={styles.boot}>
        <Text style={styles.wordmark}>KhabarNazar</Text>
        <ActivityIndicator size="large" color="#fff" style={styles.spinner} />
        <Text style={styles.caption}>Loading your session…</Text>
      </View>
    );
  }

  if (user) {
    return <Redirect href="/(tabs)" />;
  }

  return <Redirect href="/register" />;
}

const styles = StyleSheet.create({
  boot: {
    flex: 1,
    backgroundColor: '#0f766e',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
  },
  wordmark: {
    fontSize: 32,
    fontWeight: '800',
    color: '#fff',
    letterSpacing: -0.5,
    marginBottom: 28,
  },
  spinner: {
    marginBottom: 16,
  },
  caption: {
    fontSize: 15,
    color: '#ecfdf5',
  },
});
