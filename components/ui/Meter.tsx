import { StyleSheet, View } from 'react-native';

import { radius, space } from '@/constants/theme';
import { AppText } from './Text';
import { useAppTheme } from './theme';

type Props = {
  label: string;
  /** 0–1. `null` renders an "unavailable" state instead of a fake bar. */
  value: number | null;
  color?: string;
  note?: string;
};

/** Labelled horizontal meter for model scores. */
export function Meter({ label, value, color, note }: Props) {
  const { colors } = useAppTheme();
  const pct = value == null ? 0 : Math.min(1, Math.max(0, value));
  return (
    <View style={styles.wrap}>
      <View style={styles.row}>
        <AppText variant="bodyStrong">{label}</AppText>
        <AppText variant="bodyStrong" color={value == null ? 'textSubtle' : 'text'}>
          {value == null ? 'Unavailable' : `${(pct * 100).toFixed(1)}%`}
        </AppText>
      </View>
      <View style={[styles.track, { backgroundColor: colors.surfaceMuted }]}>
        {value != null ? (
          <View style={[styles.fill, { width: `${pct * 100}%`, backgroundColor: color ?? colors.primary }]} />
        ) : null}
      </View>
      {note ? <AppText variant="caption" color="textMuted">{note}</AppText> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: space.sm },
  row: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline', gap: space.md },
  track: { height: 8, borderRadius: radius.pill, overflow: 'hidden' },
  fill: { height: '100%', borderRadius: radius.pill },
});
