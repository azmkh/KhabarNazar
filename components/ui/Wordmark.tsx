import { StyleSheet, View } from 'react-native';

import { fonts, radius, space } from '@/constants/theme';
import { Icon } from './Icon';
import { AppText } from './Text';
import { useAppTheme } from './theme';

/** Brand lock-up: logo tile, Latin wordmark and the Urdu name in Nastaliq. */
export function Wordmark({ size = 'md' }: { size?: 'md' | 'lg' }) {
  const { colors } = useAppTheme();
  const large = size === 'lg';
  return (
    <View style={styles.row}>
      <View style={[styles.tile, large && styles.tileLg, { backgroundColor: colors.primary }]}>
        <Icon name="scan-search" size={large ? 26 : 20} color="#FFFFFF" />
      </View>
      <View>
        <AppText variant={large ? 'title' : 'heading'} color="onInk">KhabarNazar</AppText>
        <AppText color="onInkMuted" style={[styles.urdu, large && styles.urduLg]}>خبر نظر</AppText>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: space.md },
  tile: { width: 40, height: 40, borderRadius: radius.md, alignItems: 'center', justifyContent: 'center' },
  tileLg: { width: 52, height: 52, borderRadius: radius.lg },
  // alignSelf keeps the RTL name hugging the left edge under the Latin wordmark.
  urdu: { fontFamily: fonts.urdu, fontSize: 14, lineHeight: 28, marginTop: -4, alignSelf: 'flex-start' },
  urduLg: { fontSize: 16, lineHeight: 32 },
});
