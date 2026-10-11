import { Pressable, StyleSheet, View } from 'react-native';

import { radius, space } from '@/constants/theme';
import { Icon, type IconName } from './Icon';
import { AppText } from './Text';
import { useAppTheme } from './theme';

type Props = {
  icon: IconName;
  label: string;
  description?: string;
  onPress: () => void;
  tone?: 'default' | 'danger';
  /** Set false for the last row in a grouped list. */
  divider?: boolean;
};

/** Settings-style navigation row, designed to sit inside a <Card padded={false}>. */
export function ListRow({ icon, label, description, onPress, tone = 'default', divider = true }: Props) {
  const { colors } = useAppTheme();
  const accent = tone === 'danger' ? colors.misleading : colors.primary;
  const soft = tone === 'danger' ? colors.misleadingSoft : colors.primarySoft;
  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      style={({ pressed }) => [styles.row, pressed && { backgroundColor: colors.surfaceMuted }]}>
      <View style={[styles.iconWrap, { backgroundColor: soft }]}>
        <Icon name={icon} size={18} color={accent} />
      </View>
      <View style={[styles.body, divider && { borderBottomColor: colors.border, borderBottomWidth: StyleSheet.hairlineWidth }]}>
        <View style={styles.text}>
          <AppText variant="bodyStrong" color={tone === 'danger' ? colors.misleading : 'text'}>{label}</AppText>
          {description ? <AppText variant="caption" color="textMuted">{description}</AppText> : null}
        </View>
        <Icon name="chevron-right" size={18} color="textSubtle" />
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', paddingLeft: space.lg, gap: space.md },
  iconWrap: { width: 36, height: 36, borderRadius: radius.sm + 2, alignItems: 'center', justifyContent: 'center' },
  body: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: space.lg,
    paddingRight: space.lg,
    gap: space.sm,
  },
  text: { flex: 1, gap: 2 },
});
