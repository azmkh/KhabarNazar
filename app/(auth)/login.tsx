import FontAwesome from '@expo/vector-icons/FontAwesome';
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

export default function LoginScreen() {
  const { signIn } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);

  async function onSubmit() {
    try {
      setBusy(true);
      await signIn(email, password);
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Sign in failed.';
      Alert.alert('Sign in', msg);
    } finally {
      setBusy(false);
    }
  }

  return (
    <SafeAreaView style={styles.safe} edges={['top', 'bottom']}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        style={styles.flex}>
        <Link href="/register" asChild>
          <Pressable style={styles.topRegister} hitSlop={8}>
            <Text style={styles.topRegisterText}>New here? Create an account</Text>
          </Pressable>
        </Link>

        <View style={styles.hero}>
          <FontAwesome name="newspaper-o" size={40} color="#fff" />
          <Text style={styles.title}>KhabarNazar</Text>
          <Text style={styles.sub}>Sign in to check news and manage your history.</Text>
        </View>

        <View style={styles.card}>
          <Text style={styles.label}>Email</Text>
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
            autoComplete="password"
            placeholder="••••••••"
            placeholderTextColor="#94a3b8"
            style={styles.input}
          />

          <Link href="/forgot" asChild>
            <Pressable style={styles.forgotWrap}>
              <Text style={styles.forgot}>Forgot password?</Text>
            </Pressable>
          </Link>

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
              <Text style={styles.primaryText}>Sign in</Text>
            )}
          </Pressable>

          <View style={styles.footer}>
            <Text style={styles.footerMuted}>No account?</Text>
            <Link href="/register" asChild>
              <Pressable hitSlop={8}>
                <Text style={styles.footerLink}> Create one</Text>
              </Pressable>
            </Link>
          </View>
        </View>

        <Text style={styles.hint}>
          Demo mode: any valid-looking email and a password of 6+ characters will sign you in. Wire
          this screen to your FastAPI auth when ready.
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
    justifyContent: 'center',
  },
  topRegister: {
    alignSelf: 'center',
    marginBottom: 16,
    paddingVertical: 6,
  },
  topRegisterText: {
    color: '#ecfdf5',
    fontSize: 15,
    fontWeight: '700',
    textDecorationLine: 'underline',
  },
  hero: {
    alignItems: 'center',
    marginBottom: 28,
  },
  title: {
    marginTop: 14,
    fontSize: 30,
    fontWeight: '800',
    color: '#fff',
    letterSpacing: -0.5,
  },
  sub: {
    marginTop: 8,
    fontSize: 15,
    lineHeight: 22,
    color: '#ecfdf5',
    textAlign: 'center',
    paddingHorizontal: 12,
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
    marginTop: 16,
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
  forgotWrap: {
    alignSelf: 'flex-end',
    marginTop: 12,
  },
  forgot: {
    fontSize: 14,
    fontWeight: '600',
    color: '#0d9488',
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
    marginTop: 20,
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
  hint: {
    marginTop: 20,
    fontSize: 12,
    lineHeight: 17,
    color: '#99f6e4',
    textAlign: 'center',
  },
});
