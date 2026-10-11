import { Stack, useRouter } from 'expo-router';
import { StyleSheet, View } from 'react-native';

import { EmptyState, useAppTheme } from '@/components/ui';

export default function NotFoundScreen() {
  const { colors } = useAppTheme();
  const router = useRouter();
  return (
    <>
      <Stack.Screen options={{ title: 'Not found' }} />
      <View style={[styles.container, { backgroundColor: colors.background }]}>
        <EmptyState
          icon="circle-help"
          title="This screen doesn't exist"
          actionLabel="Go to home"
          onAction={() => router.replace('/')}
        />
      </View>
    </>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: 'center' },
});
