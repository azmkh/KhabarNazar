import { Redirect, Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';

import { useColorScheme } from '@/components/useColorScheme';

import { useAuth } from '@/lib/AuthContext';
import { isAdminEmail } from '@/lib/admin';

const headerTeal = '#0d4f4a';
const headerTint = '#f0fdfa';

export default function AdminLayout() {
  const { user } = useAuth();
  const scheme = useColorScheme();

  if (!isAdminEmail(user?.email)) {
    return <Redirect href="/(tabs)" />;
  }

  return (
    <>
      <StatusBar style="light" />
      <Stack
        screenOptions={{
          headerStyle: { backgroundColor: headerTeal },
          headerTintColor: headerTint,
          headerTitleStyle: { fontWeight: '700', fontSize: 17 },
          headerShadowVisible: false,
          contentStyle: {
            backgroundColor: scheme === 'dark' ? '#0f172a' : '#ecfdf5',
          },
        }}>
        <Stack.Screen name="index" options={{ title: 'Admin · Overview' }} />
        <Stack.Screen name="disputes" options={{ title: 'Dispute queue' }} />
        <Stack.Screen name="submissions" options={{ title: 'All submissions' }} />
        <Stack.Screen name="review/[id]" options={{ title: 'Review dispute' }} />
      </Stack>
    </>
  );
}
