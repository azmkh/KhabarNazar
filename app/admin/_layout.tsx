import { Redirect, Stack } from 'expo-router';

import { useAppTheme } from '@/components/ui';
import { fonts } from '@/constants/theme';
import { useAuth } from '@/lib/AuthContext';

export default function AdminLayout() {
  const { user } = useAuth();
  const { colors } = useAppTheme();

  if (user?.role !== 'admin') {
    return <Redirect href="/(tabs)" />;
  }

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
      <Stack.Screen name="index" options={{ headerShown: false, title: 'Moderation desk' }} />
      <Stack.Screen name="disputes" options={{ title: 'Dispute queue' }} />
      <Stack.Screen name="submissions" options={{ title: 'All submissions' }} />
      <Stack.Screen name="review/[id]" options={{ title: 'Review dispute' }} />
    </Stack>
  );
}
