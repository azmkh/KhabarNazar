import { Link, useRouter } from 'expo-router';
import { useState } from 'react';
import {
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

export default function ForgotPasswordScreen() {
  const router = useRouter();
  const [email, setEmail] = useState('');

  function onSubmit() {
    const trimmed = email.trim();
    if (!trimmed.includes('@')) {
      Alert.alert('Reset', 'Enter a valid email address.');
      return;
    }
    Alert.alert(
      'Reset link',
      'When your FastAPI backend is connected, this will trigger a real reset email. For now, nothing is sent.',
      [{ text: 'OK', onPress: () => router.replace('/login') }],
    );
  }

  return (
    <SafeAreaView style={styles.safe} edges={['top', 'bottom']}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        style={styles.flex}>
        <Text style={styles.title}>Forgot password</Text>
        <Text style={styles.sub}>
          Enter the email you use with KhabarNazar. You will receive reset instructions once the
          backend is implemented.
        </Text>

        <View style={styles.card}>
          <Text style={styles.label}>Email</Text>
          <TextInput
            value={email}
            onChangeText={setEmail}
            autoCapitalize="none"
            keyboardType="email-address"
            placeholder="you@example.com"
            placeholderTextColor="#94a3b8"
            style={styles.input}
          />

          <Pressable onPress={onSubmit} style={styles.primary}>
            <Text style={styles.primaryText}>Continue</Text>
          </Pressable>

          <Link href="/login" asChild>
            <Pressable style={styles.linkWrap}>
              <Text style={styles.link}>Back to sign in</Text>
            </Pressable>
          </Link>
        </View>
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
  title: {
    fontSize: 26,
    fontWeight: '800',
    color: '#fff',
    marginBottom: 10,
  },
  sub: {
    fontSize: 14,
    lineHeight: 21,
    color: '#ecfdf5',
    marginBottom: 22,
  },
  card: {
    backgroundColor: '#fff',
    borderRadius: 18,
    padding: 22,
  },
  label: {
    fontSize: 13,
    fontWeight: '700',
    color: '#0f172a',
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
  linkWrap: {
    marginTop: 18,
    alignItems: 'center',
  },
  link: {
    fontSize: 15,
    fontWeight: '700',
    color: '#0d9488',
  },
});
