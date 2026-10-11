import type { ReactNode } from 'react';
import { StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { radius, space } from '@/constants/theme';
import { AppText } from './Text';
import { useAppTheme } from './theme';

type Props = {
  kicker?: string;
  title: string;
  subtitle?: string;
  /** Rendered at the top-right (e.g. an avatar or a close button). */
  accessory?: ReactNode;
  /** Rendered under the subtitle, inside the dark block. */
  children?: ReactNode;
  /** Add the top safe-area inset (for screens without a navigation header). */
  safeTop?: boolean;
};

/** Ink-dark header block that opens the main screens, like a newspaper masthead. */
export function Masthead({ kicker, title, subtitle, accessory, children, safeTop = true }: Props) {
  const { colors } = useAppTheme();
  const insets = useSafeAreaInsets();
  return (
    <View style={[styles.wrap, { backgroundColor: colors.ink, paddingTop: (safeTop ? insets.top : 0) + space.xl }]}>
      <View style={styles.top}>
        <View style={styles.titles}>
          {kicker ? <AppText variant="overline" color="onInkMuted">{kicker}</AppText> : null}
          <AppText variant="title" color="onInk">{title}</AppText>
        </View>
        {accessory}
      </View>
      {subtitle ? <AppText variant="body" color="onInkMuted" style={styles.subtitle}>{subtitle}</AppText> : null}
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    paddingHorizontal: space.xl,
    paddingBottom: space.xxl,
    borderBottomLeftRadius: radius.xl,
    borderBottomRightRadius: radius.xl,
  },
  top: { flexDirection: 'row', alignItems: 'flex-start', gap: space.md },
  titles: { flex: 1, gap: space.xs },
  subtitle: { marginTop: space.sm },
});
