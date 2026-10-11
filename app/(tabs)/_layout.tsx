import { Tabs } from 'expo-router';
import type { ColorValue } from 'react-native';

import { Icon, type IconName, useAppTheme } from '@/components/ui';
import { fonts } from '@/constants/theme';

function tabIcon(name: IconName) {
  return ({ color }: { color: ColorValue }) => <Icon name={name} size={22} color={color} />;
}

export default function TabLayout() {
  const { colors } = useAppTheme();

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.primary,
        tabBarInactiveTintColor: colors.textSubtle,
        tabBarLabelStyle: { fontFamily: fonts.semibold, fontSize: 11 },
        tabBarStyle: {
          backgroundColor: colors.surface,
          borderTopColor: colors.border,
        },
        sceneStyle: { backgroundColor: colors.background },
      }}>
      <Tabs.Screen name="index" options={{ title: 'Check', tabBarIcon: tabIcon('scan-search') }} />
      <Tabs.Screen name="history" options={{ title: 'History', tabBarIcon: tabIcon('history') }} />
      <Tabs.Screen name="profile" options={{ title: 'Account', tabBarIcon: tabIcon('user') }} />
    </Tabs>
  );
}
