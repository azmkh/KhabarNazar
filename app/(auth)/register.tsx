import { Link } from 'expo-router';
import { useRef, useState } from 'react';
import { Pressable, StyleSheet, TextInput, View } from 'react-native';

import { AuthShell } from '@/components/AuthShell';
import { AppText, Button, TextField } from '@/components/ui';
import { useAuth } from '@/lib/AuthContext';
import { showAlert } from '@/lib/alert';

export default function RegisterScreen() {
  const { signUp } = useAuth();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [busy, setBusy] = useState(false);
  const emailRef = useRef<TextInput>(null);
  const passwordRef = useRef<TextInput>(null);
  const confirmRef = useRef<TextInput>(null);

  async function onSubmit() {
    if (password !== confirm) {
      showAlert('Register', 'Passwords do not match.');
      return;
    }
    try {
      setBusy(true);
      await signUp(email, password, name);
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Registration failed.';
      showAlert('Register', msg);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell
      title="Create your account"
      subtitle="Save your checks and dispute results you disagree with."
      footer={
        <View style={styles.switchRow}>
          <AppText variant="body" color="onInkMuted">Already have an account?</AppText>
          <Link href="/login" asChild>
            <Pressable hitSlop={8} accessibilityRole="link">
              <AppText variant="bodyStrong" color="onInk"> Sign in</AppText>
            </Pressable>
          </Link>
        </View>
      }>
      <TextField
        label="Name"
        icon="user"
        value={name}
        onChangeText={setName}
        autoComplete="name"
        placeholder="Your name (optional)"
        returnKeyType="next"
        onSubmitEditing={() => emailRef.current?.focus()}
      />
      <TextField
        ref={emailRef}
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
        autoComplete="new-password"
        placeholder="At least 6 characters"
        returnKeyType="next"
        onSubmitEditing={() => confirmRef.current?.focus()}
      />
      <TextField
        ref={confirmRef}
        label="Confirm password"
        icon="lock"
        value={confirm}
        onChangeText={setConfirm}
        secureToggle
        autoComplete="new-password"
        placeholder="Repeat password"
        returnKeyType="go"
        onSubmitEditing={() => void onSubmit()}
      />
      <Button label="Create account" icon="arrow-right" onPress={() => void onSubmit()} loading={busy} />
      <AppText variant="caption" color="textSubtle" align="center">
        New accounts get standard access. Administrator access is assigned by the backend operator.
      </AppText>
    </AuthShell>
  );
}

const styles = StyleSheet.create({
  switchRow: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'center' },
});
