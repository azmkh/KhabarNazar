/**
 * KhabarNazar design tokens.
 *
 * "Newsroom" direction: warm newsprint surfaces, an ink-dark masthead, a
 * signal-indigo accent, and verdict colours that always come with a matching
 * soft background so badges stay readable in light and dark mode.
 */

const light = {
  // Surfaces
  background: '#F6F5F1',
  surface: '#FFFFFF',
  surfaceMuted: '#EFEDE7',
  border: '#E3E0D8',
  borderStrong: '#CFCBC0',

  // Text
  text: '#14161B',
  textMuted: '#5C606A',
  textSubtle: '#8A8D95',

  // Brand
  primary: '#4338CA',
  primaryPressed: '#3730A3',
  primarySoft: '#E7E5FB',
  onPrimary: '#FFFFFF',

  // Masthead (dark header block used on hero areas)
  ink: '#111827',
  inkSoft: '#1F2937',
  onInk: '#F9FAFB',
  onInkMuted: '#A5ACBA',

  // Verdicts / status
  credible: '#15803D',
  credibleSoft: '#DCFCE7',
  uncertain: '#B45309',
  uncertainSoft: '#FEF3C7',
  misleading: '#B91C1C',
  misleadingSoft: '#FEE2E2',
  info: '#0369A1',
  infoSoft: '#E0F2FE',

  // Legacy keys kept for template components (Themed.tsx)
  tint: '#4338CA',
  muted: '#5C606A',
  card: '#FFFFFF',
  tabIconDefault: '#8A8D95',
  tabIconSelected: '#4338CA',
};

export type Palette = typeof light;

const dark: Palette = {
  background: '#0D0F14',
  surface: '#161A22',
  surfaceMuted: '#1D222C',
  border: '#272D39',
  borderStrong: '#363E4D',

  text: '#F3F4F6',
  textMuted: '#A3A9B6',
  textSubtle: '#737A88',

  primary: '#8B8DFF',
  primaryPressed: '#A5A7FF',
  primarySoft: '#25265A',
  onPrimary: '#0D0F14',

  ink: '#05070B',
  inkSoft: '#121620',
  onInk: '#F9FAFB',
  onInkMuted: '#9AA1AF',

  credible: '#4ADE80',
  credibleSoft: '#12301E',
  uncertain: '#FBBF24',
  uncertainSoft: '#3A2A0A',
  misleading: '#F87171',
  misleadingSoft: '#3B1414',
  info: '#38BDF8',
  infoSoft: '#0B2A3B',

  tint: '#8B8DFF',
  muted: '#A3A9B6',
  card: '#161A22',
  tabIconDefault: '#737A88',
  tabIconSelected: '#8B8DFF',
};

export const palettes = { light, dark };

export const space = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
  xxl: 28,
  xxxl: 40,
} as const;

export const radius = {
  sm: 8,
  md: 12,
  lg: 16,
  xl: 22,
  pill: 999,
} as const;

export const fonts = {
  regular: 'PlusJakartaSans_400Regular',
  medium: 'PlusJakartaSans_500Medium',
  semibold: 'PlusJakartaSans_600SemiBold',
  bold: 'PlusJakartaSans_700Bold',
  extrabold: 'PlusJakartaSans_800ExtraBold',
  urdu: 'NotoNastaliqUrdu_400Regular',
  urduBold: 'NotoNastaliqUrdu_700Bold',
} as const;

export const type = {
  display: { fontFamily: fonts.extrabold, fontSize: 32, lineHeight: 38, letterSpacing: -0.8 },
  title: { fontFamily: fonts.extrabold, fontSize: 24, lineHeight: 30, letterSpacing: -0.5 },
  heading: { fontFamily: fonts.bold, fontSize: 18, lineHeight: 24, letterSpacing: -0.2 },
  body: { fontFamily: fonts.regular, fontSize: 15, lineHeight: 22 },
  bodyStrong: { fontFamily: fonts.semibold, fontSize: 15, lineHeight: 22 },
  caption: { fontFamily: fonts.medium, fontSize: 13, lineHeight: 18 },
  overline: { fontFamily: fonts.bold, fontSize: 11, lineHeight: 14, letterSpacing: 1.1, textTransform: 'uppercase' as const },
  button: { fontFamily: fonts.bold, fontSize: 16, lineHeight: 20 },
} as const;

export type TypeVariant = keyof typeof type;
