import { Lucide } from '@react-native-vector-icons/lucide';
import type { ComponentProps } from 'react';
import type { ColorValue } from 'react-native';

import type { Palette } from '@/constants/theme';
import { useAppTheme } from './theme';

export type IconName = ComponentProps<typeof Lucide>['name'];

type Props = {
  name: IconName;
  size?: number;
  /** A palette key (e.g. "primary") or any colour value. */
  color?: keyof Palette | ColorValue;
};

export function Icon({ name, size = 20, color = 'text' }: Props) {
  const { colors } = useAppTheme();
  const resolved = typeof color === 'string' && color in colors ? colors[color as keyof Palette] : color;
  return <Lucide name={name} size={size} color={resolved} />;
}
