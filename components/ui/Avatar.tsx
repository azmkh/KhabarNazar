import { Image, StyleSheet, View } from 'react-native';

import { fonts } from '@/constants/theme';
import { AppText } from './Text';
import { useAppTheme } from './theme';

type Props = { uri?: string | null; name?: string | null; size?: number; onInk?: boolean };

export function Avatar({ uri, name, size = 44, onInk = false }: Props) {
  const { colors } = useAppTheme();
  const initials = (name || '?')
    .trim()
    .split(/[\s@._-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]!.toUpperCase())
    .join('') || '?';
  const box = { width: size, height: size, borderRadius: size / 2 };

  if (uri) return <Image source={{ uri }} style={box} accessibilityLabel="Profile photo" />;
  return (
    <View style={[styles.fallback, box, { backgroundColor: onInk ? colors.inkSoft : colors.primarySoft }]}>
      <AppText style={{ fontFamily: fonts.bold, fontSize: size * 0.38, lineHeight: size * 0.46 }} color={onInk ? 'onInk' : 'primary'}>
        {initials}
      </AppText>
    </View>
  );
}

const styles = StyleSheet.create({
  fallback: { alignItems: 'center', justifyContent: 'center' },
});
