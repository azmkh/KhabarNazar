import { Text as RNText, type TextProps } from 'react-native';

import { fonts, type Palette, type, type TypeVariant } from '@/constants/theme';
import { useAppTheme } from './theme';

type ColorKey = keyof Palette;

export type AppTextProps = TextProps & {
  variant?: TypeVariant;
  /** A palette key (e.g. "textMuted") or a raw colour value. */
  color?: ColorKey | (string & {});
  align?: 'left' | 'center' | 'right';
};

export function AppText({ variant = 'body', color = 'text', align, style, ...rest }: AppTextProps) {
  const { colors } = useAppTheme();
  const resolved = color in colors ? colors[color as ColorKey] : color;
  return <RNText style={[type[variant], { color: resolved }, align ? { textAlign: align } : null, style]} {...rest} />;
}

const ARABIC_SCRIPT = /[؀-ۿ]/;

/** True when the text is mostly written in Urdu (Arabic) script. */
export function isUrduScript(value: string) {
  const letters = value.replace(/[^\p{L}]/gu, '');
  if (!letters) return false;
  const urdu = [...letters].filter((ch) => ARABIC_SCRIPT.test(ch)).length;
  return urdu / letters.length >= 0.5;
}

/**
 * User-submitted news content. Urdu-script text is shown right-to-left in
 * Noto Nastaliq Urdu (with the extra line height Nastaliq needs); Roman Urdu
 * and English use the UI font.
 */
export function ContentText({ children, style, ...rest }: Omit<AppTextProps, 'variant'> & { children: string }) {
  const urdu = isUrduScript(children);
  return (
    <AppText
      variant="body"
      style={[
        urdu ? { fontFamily: fonts.urdu, fontSize: 17, lineHeight: 36, writingDirection: 'rtl', textAlign: 'right' } : { fontSize: 16, lineHeight: 24 },
        style,
      ]}
      {...rest}>
      {children}
    </AppText>
  );
}
