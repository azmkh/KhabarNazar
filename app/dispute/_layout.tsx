import { Stack } from 'expo-router';

export default function DisputeLayout() {
  return (
    <Stack>
      <Stack.Screen name="index" options={{ title: 'Dispute a result' }} />
      <Stack.Screen name="[id]" options={{ title: 'Dispute' }} />
    </Stack>
  );
}
