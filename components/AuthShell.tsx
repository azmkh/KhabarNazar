import type { ReactNode } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { AppText, Wordmark, useAppTheme } from '@/components/ui';
import { radius, space } from '@/constants/theme';

type Props = {
  title: string;
  subtitle: string;
  children: ReactNode;
  footer?: ReactNode;
};

/** Shared layout for sign-in, registration and password reset. */
export function AuthShell({ title, subtitle, children, footer }: Props) {
  const { colors } = useAppTheme();
  const insets = useSafeAreaInsets();

  return (
    <KeyboardAvoidingView
      style={[styles.flex, { backgroundColor: colors.ink }]}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView
        contentContainerStyle={[styles.scroll, { paddingTop: insets.top + space.xxl, paddingBottom: insets.bottom + space.xl }]}
        keyboardShouldPersistTaps="handled">
        <View style={styles.brand}>
          <Wordmark size="lg" />
          <AppText variant="body" color="onInkMuted" style={styles.tagline}>
            Check Urdu, Roman Urdu and news images before you share them.
          </AppText>
        </View>

        <View style={[styles.sheet, { backgroundColor: colors.background }]}>
          <View style={styles.heading}>
            <AppText variant="title">{title}</AppText>
            <AppText variant="body" color="textMuted">{subtitle}</AppText>
          </View>
          {children}
        </View>

        {footer ? <View style={styles.footer}>{footer}</View> : null}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  scroll: { flexGrow: 1, paddingHorizontal: space.lg, justifyContent: 'center' },
  brand: { paddingHorizontal: space.sm, marginBottom: space.xxl, gap: space.md },
  tagline: { maxWidth: 320 },
  sheet: { borderRadius: radius.xl, padding: space.xl, gap: space.lg },
  heading: { gap: space.xs, marginBottom: space.xs },
  footer: { marginTop: space.xl, alignItems: 'center' },
});
