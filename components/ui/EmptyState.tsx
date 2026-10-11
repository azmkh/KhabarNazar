import { ActivityIndicator, StyleSheet, View } from 'react-native';

import { radius, space } from '@/constants/theme';
import { Button } from './Button';
import { Icon, type IconName } from './Icon';
import { AppText } from './Text';
import { useAppTheme } from './theme';

type Props = {
  icon: IconName;
  title: string;
  message?: string;
  loading?: boolean;
  actionLabel?: string;
  onAction?: () => void;
};

export function EmptyState({ icon, title, message, loading, actionLabel, onAction }: Props) {
  const { colors } = useAppTheme();
  return (
    <View style={styles.wrap}>
      <View style={[styles.iconWrap, { backgroundColor: colors.surfaceMuted }]}>
        {loading ? <ActivityIndicator color={colors.primary} /> : <Icon name={icon} size={28} color="textMuted" />}
      </View>
      <AppText variant="heading" align="center">{title}</AppText>
      {message ? <AppText variant="body" color="textMuted" align="center">{message}</AppText> : null}
      {actionLabel && onAction ? (
        <Button label={actionLabel} onPress={onAction} variant="secondary" size="sm" style={styles.action} />
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { alignItems: 'center', gap: space.sm, paddingVertical: space.xxxl, paddingHorizontal: space.xl },
  iconWrap: {
    width: 64,
    height: 64,
    borderRadius: radius.xl,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: space.sm,
  },
  action: { marginTop: space.md },
});
