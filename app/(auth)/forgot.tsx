import { Link } from 'expo-router';
import { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { AuthShell } from '@/components/AuthShell';
import { AppText, Button, Card, Icon, TextField } from '@/components/ui';
import { space } from '@/constants/theme';

export default function ForgotPasswordScreen() {
  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const valid = email.trim().includes('@');

  return (
    <AuthShell
      title="Reset password"
      subtitle="Enter the email you use with KhabarNazar."
      footer={
        <Link href="/login" asChild>
          <Pressable hitSlop={8} accessibilityRole="link" style={styles.back}>
            <Icon name="chevron-left" size={18} color="onInk" />
            <AppText variant="bodyStrong" color="onInk">Back to sign in</AppText>
          </Pressable>
        </Link>
      }>
      {submitted ? (
        <Card tone="muted">
          <View style={styles.notice}>
            <Icon name="info" size={18} color="info" />
            <AppText variant="body" color="textMuted" style={styles.noticeText}>
              Password reset is not available yet: the backend does not send reset emails. Ask the
              project administrator to reset your account.
            </AppText>
          </View>
        </Card>
      ) : (
        <>
          <TextField
            label="Email"
            icon="mail"
            value={email}
            onChangeText={setEmail}
            autoCapitalize="none"
            keyboardType="email-address"
            placeholder="you@example.com"
          />
          <Button label="Continue" onPress={() => setSubmitted(true)} disabled={!valid} />
        </>
      )}
    </AuthShell>
  );
}

const styles = StyleSheet.create({
  back: { flexDirection: 'row', alignItems: 'center', gap: space.xs },
  notice: { flexDirection: 'row', gap: space.md },
  noticeText: { flex: 1 },
});
