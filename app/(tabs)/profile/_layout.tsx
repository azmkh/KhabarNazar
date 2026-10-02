import { Stack } from 'expo-router';

export default function ProfileStackLayout() {
  return (
    <Stack>
      <Stack.Screen name="index" options={{ title: 'Settings' }} />
      <Stack.Screen name="me" options={{ title: 'My profile' }} />
      <Stack.Screen name="edit" options={{ title: 'Edit profile' }} />
      <Stack.Screen name="logout" options={{ title: 'Sign out' }} />
    </Stack>
  );
}
