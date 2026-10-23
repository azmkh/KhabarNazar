import { useEffect, useRef } from 'react';
import { AccessibilityInfo, Animated, Easing, Image, StyleSheet, useWindowDimensions, View } from 'react-native';

import { AppText } from '@/components/ui';
import { fonts } from '@/constants/theme';

// Matches the native splash background in app.json, so the hand-over is seamless.
export const SPLASH_BACKGROUND = '#6D28D9';

type Props = { onDone: () => void };

/**
 * Plays once the app has loaded (fonts + saved session): the logo springs in, the
 * name rises up, then the whole screen fades away to reveal the app. With
 * "Reduce Motion" on, it simply fades.
 */
export function AnimatedSplash({ onDone }: Props) {
  const { width, height } = useWindowDimensions();
  const logo = useRef(new Animated.Value(0)).current;
  const text = useRef(new Animated.Value(0)).current;
  const glow = useRef(new Animated.Value(0)).current;
  const screen = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    let cancelled = false;
    AccessibilityInfo.isReduceMotionEnabled().catch(() => false).then((reduceMotion) => {
      if (cancelled) return;
      const fadeOut = Animated.timing(screen, { toValue: 0, duration: reduceMotion ? 200 : 380, easing: Easing.out(Easing.quad), useNativeDriver: true });
      const sequence = reduceMotion
        ? Animated.sequence([
            Animated.parallel([
              Animated.timing(logo, { toValue: 1, duration: 1, useNativeDriver: true }),
              Animated.timing(text, { toValue: 1, duration: 1, useNativeDriver: true }),
              Animated.timing(glow, { toValue: 1, duration: 1, useNativeDriver: true }),
            ]),
            Animated.delay(600),
            fadeOut,
          ])
        : Animated.sequence([
            Animated.parallel([
              Animated.timing(glow, { toValue: 1, duration: 900, easing: Easing.out(Easing.cubic), useNativeDriver: true }),
              Animated.spring(logo, { toValue: 1, friction: 6, tension: 70, useNativeDriver: true }),
              Animated.sequence([
                Animated.delay(260),
                Animated.timing(text, { toValue: 1, duration: 480, easing: Easing.out(Easing.cubic), useNativeDriver: true }),
              ]),
            ]),
            Animated.delay(700),
            fadeOut,
          ]);
      sequence.start(({ finished }) => { if (finished && !cancelled) onDone(); });
    });
    return () => { cancelled = true; };
  }, [glow, logo, onDone, screen, text]);

  const size = Math.min(width, height);
  const blob = (color: string, diameter: number, top: number, left: number, scaleFrom: number) => (
    <Animated.View
      pointerEvents="none"
      style={[
        styles.blob,
        {
          width: diameter, height: diameter, borderRadius: diameter / 2, backgroundColor: color, top, left,
          opacity: glow.interpolate({ inputRange: [0, 1], outputRange: [0, 1] }),
          transform: [{ scale: glow.interpolate({ inputRange: [0, 1], outputRange: [scaleFrom, 1] }) }],
        },
      ]}
    />
  );

  return (
    <Animated.View
      style={[StyleSheet.absoluteFill, styles.root, { opacity: screen }]}
      accessibilityLabel="KhabarNazar is starting"
      accessibilityRole="image">
      {/* Soft glowing colour fields for a vibrant, gradient-like background without extra libraries */}
      {blob('rgba(236, 72, 153, 0.45)', size * 1.1, -size * 0.35, width - size * 0.55, 0.7)}
      {blob('rgba(79, 70, 229, 0.55)', size * 1.2, height - size * 0.75, -size * 0.45, 0.7)}
      {blob('rgba(167, 139, 250, 0.35)', size * 0.7, height * 0.18, -size * 0.25, 0.8)}

      <View style={styles.center}>
        <Animated.View
          style={{
            opacity: logo.interpolate({ inputRange: [0, 0.4, 1], outputRange: [0, 1, 1] }),
            transform: [
              { scale: logo.interpolate({ inputRange: [0, 1], outputRange: [0.55, 1] }) },
              { rotate: logo.interpolate({ inputRange: [0, 1], outputRange: ['-8deg', '0deg'] }) },
            ],
          }}>
          <Image source={require('../assets/images/splash-icon.png')} style={styles.logo} accessibilityIgnoresInvertColors />
        </Animated.View>

        <Animated.View
          style={[
            styles.titles,
            {
              opacity: text,
              transform: [{ translateY: text.interpolate({ inputRange: [0, 1], outputRange: [14, 0] }) }],
            },
          ]}>
          <AppText variant="display" color="#FFFFFF" align="center">KhabarNazar</AppText>
          <AppText color="rgba(255,255,255,0.85)" align="center" style={styles.urdu}>خبر نظر</AppText>
          <AppText variant="caption" color="rgba(255,255,255,0.78)" align="center" style={styles.tagline}>
            Check the news before you share it
          </AppText>
        </Animated.View>
      </View>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  root: { backgroundColor: SPLASH_BACKGROUND, overflow: 'hidden', zIndex: 1000 },
  blob: { position: 'absolute' },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 24 },
  logo: { width: 168, height: 168 },
  titles: { marginTop: 6, alignItems: 'center' },
  urdu: { fontFamily: fonts.urdu, fontSize: 20, lineHeight: 42, marginTop: -2 },
  tagline: { marginTop: 4, letterSpacing: 0.3 },
});
