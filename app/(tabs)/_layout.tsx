import { Tabs, useRouter } from 'expo-router';
import type { ColorValue } from 'react-native';

import { Icon, type IconName, useAppTheme } from '@/components/ui';
import { fonts } from '@/constants/theme';
import { hrefAdminRoot } from '@/lib/navigation';
import { useAdminPending } from '@/lib/useAdminPending';

function tabIcon(name: IconName) {
  return ({ color }: { color: ColorValue }) => <Icon name={name} size={22} color={color} />;
}

export default function TabLayout() {
  const { colors } = useAppTheme();
  const router = useRouter();
  const { isAdmin, pending } = useAdminPending();

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
      <Tabs.Screen
        name="moderation"
        options={{
          title: 'Admin',
          tabBarIcon: tabIcon('shield-check'),
          // Only administrators get this tab; for everyone else it does not exist.
          href: isAdmin ? undefined : null,
          tabBarBadge: pending ? (pending > 99 ? '99+' : pending) : undefined,
          tabBarBadgeStyle: { backgroundColor: colors.uncertain, color: '#FFFFFF', fontFamily: fonts.bold, fontSize: 10 },
          tabBarAccessibilityLabel: pending ? `Admin, ${pending} disputes waiting` : 'Admin',
        }}
        listeners={{
          tabPress: (event) => {
            event.preventDefault();
            router.push(hrefAdminRoot());
          },
        }}
      />
      <Tabs.Screen name="profile" options={{ title: 'Account', tabBarIcon: tabIcon('user') }} />
    </Tabs>
  );
}
