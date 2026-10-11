import { Pressable, StyleSheet, View, type StyleProp, type ViewProps, type ViewStyle } from 'react-native';

import { radius, space } from '@/constants/theme';
import { AppText } from './Text';
import { useAppTheme } from './theme';

type Props = ViewProps & {
  /** Optional small uppercase label shown at the top of the card. */
  title?: string;
  tone?: 'default' | 'muted';
  padded?: boolean;
  onPress?: () => void;
  style?: StyleProp<ViewStyle>;
};

export function Card({ title, tone = 'default', padded = true, onPress, style, children, ...rest }: Props) {
  const { colors, scheme } = useAppTheme();
  const surface = [
    styles.card,
    padded && styles.padded,
    {
      backgroundColor: tone === 'muted' ? colors.surfaceMuted : colors.surface,
      borderColor: colors.border,
      shadowOpacity: scheme === 'dark' || tone === 'muted' ? 0 : 0.05,
    },
    style,
  ];
  const body = (
    <>
      {title ? <AppText variant="overline" color="textMuted" style={styles.title}>{title}</AppText> : null}
      {children}
    </>
  );

  if (onPress) {
    return (
      <Pressable
        accessibilityRole="button"
        onPress={onPress}
        style={({ pressed }) => [surface, pressed && { backgroundColor: colors.surfaceMuted }]}>
        {body}
      </Pressable>
    );
  }
  return <View style={surface} {...rest}>{body}</View>;
}

const styles = StyleSheet.create({
  card: {
    borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth * 2,
    shadowColor: '#000',
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 4 },
  },
  padded: { padding: space.lg },
  title: { marginBottom: space.sm },
});
