import { StyleSheet, View } from 'react-native';

type Props = {
  value: number;
  max?: number;
  trackColor: string;
  fillColor: string;
};

/** Horizontal bar for 0–100 (or 0–max) scores. */
export function ScoreBar({ value, max = 100, trackColor, fillColor }: Props) {
  const pct = Math.min(1, Math.max(0, value / max));
  return (
    <View style={[styles.track, { backgroundColor: trackColor }]}>
      <View style={[styles.fill, { width: `${pct * 100}%`, backgroundColor: fillColor }]} />
    </View>
  );
}

const styles = StyleSheet.create({
  track: {
    height: 8,
    borderRadius: 4,
    overflow: 'hidden',
  },
  fill: {
    height: '100%',
    borderRadius: 4,
  },
});
