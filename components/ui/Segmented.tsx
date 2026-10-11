import { Pressable, StyleSheet, View } from 'react-native';

import { radius, space } from '@/constants/theme';
import { Icon, type IconName } from './Icon';
import { AppText } from './Text';
import { useAppTheme } from './theme';

type Option<T extends string> = { value: T; label: string; icon?: IconName };

type Props<T extends string> = {
  options: Option<T>[];
  value: T;
  onChange: (value: T) => void;
};

export function Segmented<T extends string>({ options, value, onChange }: Props<T>) {
  const { colors } = useAppTheme();
  return (
    <View accessibilityRole="tablist" style={[styles.wrap, { backgroundColor: colors.surfaceMuted }]}>
      {options.map((option) => {
        const selected = option.value === value;
        return (
          <Pressable
            key={option.value}
            accessibilityRole="tab"
            accessibilityState={{ selected }}
            onPress={() => onChange(option.value)}
            style={[styles.item, selected && [styles.selected, { backgroundColor: colors.surface }]]}>
            {option.icon ? <Icon name={option.icon} size={16} color={selected ? 'primary' : 'textMuted'} /> : null}
            <AppText variant="bodyStrong" color={selected ? 'text' : 'textMuted'}>{option.label}</AppText>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flexDirection: 'row', borderRadius: radius.md, padding: 4, gap: 4 },
  item: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: space.sm,
    borderRadius: radius.sm + 2,
    paddingVertical: 10,
  },
  selected: {
    shadowColor: '#000',
    shadowOpacity: 0.08,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2,
  },
});
