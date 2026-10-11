import { Stack } from 'expo-router';

import { useAppTheme } from '@/components/ui';
import { fonts } from '@/constants/theme';

export default function DisputeLayout() {
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
      <Stack.Screen name="index" options={{ title: 'Dispute a result' }} />
      <Stack.Screen name="[id]" options={{ title: 'Dispute' }} />
    </Stack>
  );
}
