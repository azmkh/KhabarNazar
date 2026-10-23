import {
  PlusJakartaSans_400Regular,
  PlusJakartaSans_500Medium,
  PlusJakartaSans_600SemiBold,
  PlusJakartaSans_700Bold,
  PlusJakartaSans_800ExtraBold,
} from '@expo-google-fonts/plus-jakarta-sans';
import { NotoNastaliqUrdu_400Regular, NotoNastaliqUrdu_700Bold } from '@expo-google-fonts/noto-nastaliq-urdu';
import { useFonts } from 'expo-font';
import { DarkTheme, DefaultTheme, Stack, ThemeProvider } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { View } from 'react-native';
import 'react-native-reanimated';

import { AnimatedSplash, SPLASH_BACKGROUND } from '@/components/AnimatedSplash';
import { useAppTheme } from '@/components/ui';
import { fonts } from '@/constants/theme';
import { AuthProvider, useAuth } from '@/lib/AuthContext';
import { SubmissionsProvider } from '@/lib/SubmissionsContext';

export {
  // Catch any errors thrown by the Layout component.
  ErrorBoundary,
} from 'expo-router';

export const unstable_settings = {
  initialRouteName: 'index',
};

SplashScreen.preventAutoHideAsync();

export default function RootLayout() {
  const [loaded, error] = useFonts({
    PlusJakartaSans_400Regular,
    PlusJakartaSans_500Medium,
    PlusJakartaSans_600SemiBold,
    PlusJakartaSans_700Bold,
    PlusJakartaSans_800ExtraBold,
    NotoNastaliqUrdu_400Regular,
    NotoNastaliqUrdu_700Bold,
    // Preload the icon font so icons do not pop in after the splash screen.
    Lucide: require('@react-native-vector-icons/lucide/fonts/Lucide.ttf'),
  });

  useEffect(() => {
    if (error) throw error;
  }, [error]);

  if (!loaded) {
    return null;
  }

  return (
    <AuthProvider>
      <RootLayoutBody />
    </AuthProvider>
  );
}

function RootLayoutBody() {
  const { ready } = useAuth();
  // The animated splash plays once, over the app, after everything has loaded.
  const [showSplash, setShowSplash] = useState(true);
  const hideSplash = useCallback(() => setShowSplash(false), []);

  useEffect(() => {
    if (ready) {
      // Hand over from the native splash (same background colour) to the animated one.
      SplashScreen.hideAsync();
    }
  }, [ready]);

  if (!ready) {
    return <View style={{ flex: 1, backgroundColor: SPLASH_BACKGROUND }} />;
  }

  return (
    <View style={{ flex: 1 }}>
      <RootLayoutNav />
      {showSplash ? <AnimatedSplash onDone={hideSplash} /> : null}
    </View>
  );
}

function RootLayoutNav() {
  const { colors, scheme } = useAppTheme();

  // Navigation theme uses our palette so screen transitions never flash white/black.
  const navigationTheme = useMemo(() => {
    const base = scheme === 'dark' ? DarkTheme : DefaultTheme;
    return {
      ...base,
      colors: {
        ...base.colors,
        primary: colors.primary,
        background: colors.background,
        card: colors.surface,
        text: colors.text,
        border: colors.border,
        notification: colors.misleading,
      },
    };
  }, [scheme, colors]);

  return (
    <ThemeProvider value={navigationTheme}>
      <StatusBar style={scheme === 'dark' ? 'light' : 'dark'} />
      <SubmissionsProvider>
        <Stack
          screenOptions={{
            headerShadowVisible: false,
            headerStyle: { backgroundColor: colors.background },
            headerTintColor: colors.text,
            headerTitleStyle: { fontFamily: fonts.bold, fontSize: 17 },
            headerBackButtonDisplayMode: 'minimal',
            contentStyle: { backgroundColor: colors.background },
          }}>
          <Stack.Screen name="index" options={{ headerShown: false }} />
          <Stack.Screen name="(auth)" options={{ headerShown: false }} />
          <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
          <Stack.Screen name="modal" options={{ presentation: 'modal', title: 'About KhabarNazar' }} />
          <Stack.Screen name="result/[id]" options={{ title: 'Analysis' }} />
          <Stack.Screen name="dispute" options={{ headerShown: false }} />
          <Stack.Screen name="admin" options={{ headerShown: false }} />
        </Stack>
      </SubmissionsProvider>
    </ThemeProvider>
  );
}
