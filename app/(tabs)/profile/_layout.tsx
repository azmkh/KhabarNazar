import { Stack } from 'expo-router';

import { useAppTheme } from '@/components/ui';
import { fonts } from '@/constants/theme';

export default function ProfileStackLayout() {
  const { colors } = useAppTheme();
  return (
    <Stack
      screenOptions={{
        headerShadowVisible: false,
        headerStyle: { backgroundColor: colors.background },
        headerTintColor: colors.text,
        headerTitleStyle: { fontFamily: fonts.bold, fontSize: 17 },
        headerBackButtonDisplayMode: 'minimal',
        contentStyle: { backgroundColor: colors.background },
      }}>
      <Stack.Screen name="index" options={{ headerShown: false, title: 'Account' }} />
      <Stack.Screen name="me" options={{ title: 'My profile' }} />
      <Stack.Screen name="edit" options={{ title: 'Edit profile' }} />
      <Stack.Screen name="logout" options={{ title: 'Sign out', presentation: 'modal' }} />
    </Stack>
  );
}
