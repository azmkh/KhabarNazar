import { Link } from 'expo-router';
import { useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAuth } from '@/lib/AuthContext';

export default function RegisterScreen() {
  const { signUp } = useAuth();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [busy, setBusy] = useState(false);

  async function onSubmit() {
    if (password !== confirm) {
      Alert.alert('Register', 'Passwords do not match.');
      return;
    }
    try {
      setBusy(true);
      await signUp(email, password, name);
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Registration failed.';
      Alert.alert('Register', msg);
    } finally {
      setBusy(false);
    }
  }

  return (
    <SafeAreaView style={styles.safe} edges={['top', 'bottom']}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        style={styles.flex}>
        <Link href="/login" asChild>
          <Pressable style={styles.topLogin} hitSlop={8}>
            <Text style={styles.topLoginText}>Already have an account? Sign in</Text>
          </Pressable>
        </Link>

        <View style={styles.hero}>
          <Text style={styles.title}>Create account</Text>
          <Text style={styles.sub}>Save your check history across sessions (local demo session).</Text>
        </View>

        <View style={styles.card}>
          <Text style={styles.label}>Display name (optional)</Text>
          <TextInput
            value={name}
            onChangeText={setName}
            autoComplete="name"
            placeholder="Waniya"
            placeholderTextColor="#94a3b8"
            style={styles.input}
          />

          <Text style={[styles.label, styles.mt]}>Email</Text>
          <TextInput
            value={email}
            onChangeText={setEmail}
            autoCapitalize="none"
            autoComplete="email"
            keyboardType="email-address"
            placeholder="you@example.com"
            placeholderTextColor="#94a3b8"
            style={styles.input}
          />

          <Text style={[styles.label, styles.mt]}>Password</Text>
          <TextInput
            value={password}
            onChangeText={setPassword}
            secureTextEntry
            placeholder="At least 6 characters"
            placeholderTextColor="#94a3b8"
            style={styles.input}
          />

          <Text style={[styles.label, styles.mt]}>Confirm password</Text>
          <TextInput
            value={confirm}
            onChangeText={setConfirm}
            secureTextEntry
            placeholder="Repeat password"
            placeholderTextColor="#94a3b8"
            style={styles.input}
          />

          <Pressable
            onPress={onSubmit}
            disabled={busy}
            style={({ pressed }) => [
              styles.primary,
              { opacity: busy ? 0.65 : pressed ? 0.9 : 1 },
            ]}>
            {busy ? (
              <ActivityIndicator color="#0f766e" />
            ) : (
              <Text style={styles.primaryText}>Create account</Text>
            )}
          </Pressable>

          <View style={styles.footer}>
            <Text style={styles.footerMuted}>Already have an account?</Text>
            <Link href="/login" asChild>
              <Pressable hitSlop={8}>
                <Text style={styles.footerLink}> Sign in</Text>
              </Pressable>
            </Link>
          </View>
        </View>
        <Text style={styles.registerHint}>
          Tip: use <Text style={{ fontWeight: '800' }}>+admin</Text> in your email (e.g. you+admin@gmail.com) to
          unlock the admin console under Settings after sign-in.
        </Text>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: '#0f766e',
  },
  flex: {
    flex: 1,
    paddingHorizontal: 22,
    paddingBottom: 12,
  },
  topLogin: {
    alignSelf: 'flex-end',
    marginBottom: 14,
    paddingVertical: 6,
  },
  topLoginText: {
    color: '#ecfdf5',
    fontSize: 15,
    fontWeight: '700',
    textDecorationLine: 'underline',
  },
  hero: {
    marginBottom: 18,
  },
  title: {
    fontSize: 26,
    fontWeight: '800',
    color: '#fff',
  },
  sub: {
    marginTop: 8,
    fontSize: 14,
    lineHeight: 20,
    color: '#ecfdf5',
  },
  card: {
    backgroundColor: '#fff',
    borderRadius: 18,
    padding: 22,
    shadowColor: '#000',
    shadowOpacity: 0.12,
    shadowRadius: 16,
    shadowOffset: { width: 0, height: 8 },
    elevation: 6,
  },
  label: {
    fontSize: 13,
    fontWeight: '700',
    color: '#0f172a',
  },
  mt: {
    marginTop: 14,
  },
  input: {
    marginTop: 8,
    borderWidth: 1,
    borderColor: '#e2e8f0',
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: Platform.OS === 'ios' ? 14 : 10,
    fontSize: 16,
    color: '#0f172a',
  },
  primary: {
    marginTop: 22,
    backgroundColor: '#ccfbf1',
    borderRadius: 12,
    paddingVertical: 15,
    alignItems: 'center',
  },
  primaryText: {
    fontSize: 17,
    fontWeight: '800',
    color: '#0f766e',
  },
  footer: {
    flexDirection: 'row',
    justifyContent: 'center',
    marginTop: 18,
    flexWrap: 'wrap',
  },
  footerMuted: {
    fontSize: 15,
    color: '#64748b',
  },
  footerLink: {
    fontSize: 15,
    fontWeight: '700',
    color: '#0d9488',
  },
  registerHint: {
    marginTop: 16,
    marginHorizontal: 4,
    fontSize: 12,
    lineHeight: 17,
    color: '#99f6e4',
    textAlign: 'center',
  },
});
