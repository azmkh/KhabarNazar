import { Link } from 'expo-router';
import { useRef, useState } from 'react';
import { Pressable, StyleSheet, TextInput, View } from 'react-native';

import { AuthShell } from '@/components/AuthShell';
import { AppText, Button, TextField } from '@/components/ui';
import { space } from '@/constants/theme';
import { useAuth } from '@/lib/AuthContext';
import { showAlert } from '@/lib/alert';

export default function LoginScreen() {
  const { signIn } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const passwordRef = useRef<TextInput>(null);

  async function onSubmit() {
    try {
      setBusy(true);
      await signIn(email, password);
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Sign in failed.';
      showAlert('Sign in', msg);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell
      title="Welcome back"
      subtitle="Sign in to run checks and see your history."
      footer={
        <View style={styles.switchRow}>
          <AppText variant="body" color="onInkMuted">New to KhabarNazar?</AppText>
          <Link href="/register" asChild>
            <Pressable hitSlop={8} accessibilityRole="link">
              <AppText variant="bodyStrong" color="onInk"> Create an account</AppText>
            </Pressable>
          </Link>
        </View>
      }>
      <TextField
        label="Email"
        icon="mail"
        value={email}
        onChangeText={setEmail}
        autoCapitalize="none"
        autoComplete="email"
        keyboardType="email-address"
        placeholder="you@example.com"
        returnKeyType="next"
        onSubmitEditing={() => passwordRef.current?.focus()}
      />
      <TextField
        ref={passwordRef}
        label="Password"
        icon="lock"
        value={password}
        onChangeText={setPassword}
        secureToggle
        autoComplete="password"
        placeholder="Your password"
        returnKeyType="go"
        onSubmitEditing={() => void onSubmit()}
      />
      <Link href="/forgot" asChild>
        <Pressable style={styles.forgot} hitSlop={8} accessibilityRole="link">
          <AppText variant="caption" color="primary">Forgot password?</AppText>
        </Pressable>
      </Link>
      <Button label="Sign in" icon="arrow-right" onPress={() => void onSubmit()} loading={busy} />
    </AuthShell>
  );
}

const styles = StyleSheet.create({
  switchRow: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'center' },
  forgot: { alignSelf: 'flex-end', marginTop: -space.xs },
});
