import { forwardRef, useState } from 'react';
import { Platform, Pressable, StyleSheet, TextInput, View, type TextInputProps } from 'react-native';

import { fonts, radius, space } from '@/constants/theme';
import { Icon, type IconName } from './Icon';
import { AppText, isUrduScript } from './Text';
import { useAppTheme } from './theme';

type Props = TextInputProps & {
  label?: string;
  hint?: string;
  icon?: IconName;
  /** Adds a show/hide toggle for passwords. */
  secureToggle?: boolean;
};

export const TextField = forwardRef<TextInput, Props>(function TextField(
  { label, hint, icon, secureToggle, multiline, style, value, onFocus, onBlur, secureTextEntry, ...rest },
  ref,
) {
  const { colors } = useAppTheme();
  const [focused, setFocused] = useState(false);
  const [hidden, setHidden] = useState(true);
  const urdu = multiline && typeof value === 'string' && isUrduScript(value);

  return (
    <View style={styles.wrap}>
      {label ? <AppText variant="caption" color="textMuted" style={styles.label}>{label}</AppText> : null}
      <View
        style={[
          styles.field,
          multiline && styles.multiline,
          {
            backgroundColor: colors.surface,
            borderColor: focused ? colors.primary : colors.border,
            borderWidth: focused ? 1.5 : 1,
          },
        ]}>
        {icon ? <View style={multiline ? styles.iconTop : null}><Icon name={icon} size={18} color="textSubtle" /></View> : null}
        <TextInput
          ref={ref}
          value={value}
          multiline={multiline}
          placeholderTextColor={colors.textSubtle}
          secureTextEntry={secureToggle ? hidden : secureTextEntry}
          textAlignVertical={multiline ? 'top' : 'center'}
          onFocus={(event) => { setFocused(true); onFocus?.(event); }}
          onBlur={(event) => { setFocused(false); onBlur?.(event); }}
          style={[
            styles.input,
            { color: colors.text },
            multiline && styles.inputMultiline,
            urdu && styles.urdu,
            style,
          ]}
          {...rest}
        />
        {secureToggle ? (
          <Pressable
            onPress={() => setHidden((current) => !current)}
            hitSlop={10}
            accessibilityRole="button"
            accessibilityLabel={hidden ? 'Show password' : 'Hide password'}>
            <Icon name={hidden ? 'eye' : 'eye-off'} size={18} color="textSubtle" />
          </Pressable>
        ) : null}
      </View>
      {hint ? <AppText variant="caption" color="textSubtle" style={styles.hint}>{hint}</AppText> : null}
    </View>
  );
});

const styles = StyleSheet.create({
  wrap: { gap: 6 },
  label: { fontFamily: fonts.semibold },
  field: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.sm,
    borderRadius: radius.md,
    paddingHorizontal: space.md + 2,
    minHeight: 52,
  },
  multiline: { alignItems: 'flex-start', paddingVertical: space.md },
  iconTop: { paddingTop: 2 },
  input: {
    flex: 1,
    fontFamily: fonts.regular,
    fontSize: 16,
    paddingVertical: Platform.OS === 'ios' ? 14 : 10,
  },
  inputMultiline: { minHeight: 130, paddingVertical: 0, lineHeight: 24 },
  urdu: { fontFamily: fonts.urdu, fontSize: 17, lineHeight: 34, writingDirection: 'rtl', textAlign: 'right' },
  hint: { marginTop: 2 },
});
