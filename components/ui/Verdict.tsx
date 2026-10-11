import { StyleSheet, View } from 'react-native';

import { radius, space, type Palette } from '@/constants/theme';
import type { Verdict } from '@/types/submission';
import { Icon, type IconName } from './Icon';
import { AppText } from './Text';
import { useAppTheme } from './theme';

type VerdictMeta = { label: string; short: string; icon: IconName; color: string; soft: string };

export function verdictMeta(verdict: Verdict, colors: Palette): VerdictMeta {
  if (verdict === 'credible') {
    return { label: 'Likely credible', short: 'Credible', icon: 'shield-check', color: colors.credible, soft: colors.credibleSoft };
  }
  if (verdict === 'misleading') {
    return { label: 'Likely misleading', short: 'Misleading', icon: 'shield-alert', color: colors.misleading, soft: colors.misleadingSoft };
  }
  return { label: 'Uncertain', short: 'Uncertain', icon: 'shield-question', color: colors.uncertain, soft: colors.uncertainSoft };
}

export function VerdictBadge({ verdict, size = 'md' }: { verdict: Verdict; size?: 'sm' | 'md' }) {
  const { colors } = useAppTheme();
  const meta = verdictMeta(verdict, colors);
  return (
    <View style={[styles.badge, size === 'sm' && styles.sm, { backgroundColor: meta.soft }]}>
      <Icon name={meta.icon} size={size === 'sm' ? 13 : 15} color={meta.color} />
      <AppText variant="caption" color={meta.color} style={styles.text}>
        {size === 'sm' ? meta.short : meta.label}
      </AppText>
    </View>
  );
}

type TagTone = 'neutral' | 'primary' | 'credible' | 'uncertain' | 'misleading' | 'info';

/** Small status pill (e.g. "Dispute pending"). */
export function Tag({ label, tone = 'neutral', icon }: { label: string; tone?: TagTone; icon?: IconName }) {
  const { colors } = useAppTheme();
  const tones: Record<TagTone, [string, string]> = {
    neutral: [colors.textMuted, colors.surfaceMuted],
    primary: [colors.primary, colors.primarySoft],
    credible: [colors.credible, colors.credibleSoft],
    uncertain: [colors.uncertain, colors.uncertainSoft],
    misleading: [colors.misleading, colors.misleadingSoft],
    info: [colors.info, colors.infoSoft],
  };
  const [fg, bg] = tones[tone];
  return (
    <View style={[styles.badge, styles.sm, { backgroundColor: bg }]}>
      {icon ? <Icon name={icon} size={12} color={fg} /> : null}
      <AppText variant="caption" color={fg} style={[styles.text, styles.tagText]}>{label}</AppText>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    gap: 6,
    borderRadius: radius.pill,
    paddingHorizontal: space.md,
    paddingVertical: 6,
  },
  sm: { paddingHorizontal: 10, paddingVertical: 4, gap: 5 },
  text: { fontFamily: 'PlusJakartaSans_700Bold' },
  tagText: { fontSize: 12, lineHeight: 16 },
});
