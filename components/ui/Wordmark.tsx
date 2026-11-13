import { StyleSheet, View } from 'react-native';

import { radius, space } from '@/constants/theme';
import { Icon } from './Icon';
import { AppText } from './Text';
import { useAppTheme } from './theme';

/** Brand lock-up: logo tile and the KhabarNazar wordmark. */
export function Wordmark({ size = 'md' }: { size?: 'md' | 'lg' }) {
  const { colors } = useAppTheme();
  const large = size === 'lg';
  return (
    <View style={styles.row}>
      <View style={[styles.tile, large && styles.tileLg, { backgroundColor: colors.primary }]}>
        <Icon name="scan-search" size={large ? 26 : 20} color="#FFFFFF" />
      </View>
      <AppText variant={large ? 'display' : 'heading'} color="onInk">KhabarNazar</AppText>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: space.md },
  tile: { width: 40, height: 40, borderRadius: radius.md, alignItems: 'center', justifyContent: 'center' },
  tileLg: { width: 56, height: 56, borderRadius: radius.lg },
});
