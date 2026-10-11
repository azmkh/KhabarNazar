import { useColorScheme } from '@/components/useColorScheme';
import { palettes, type Palette } from '@/constants/theme';

export type AppTheme = { colors: Palette; scheme: 'light' | 'dark' };

export function useAppTheme(): AppTheme {
  const scheme = useColorScheme() === 'dark' ? 'dark' : 'light';
  return { colors: palettes[scheme], scheme };
}
