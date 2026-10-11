import { useFocusEffect, useRouter } from 'expo-router';
import { useCallback } from 'react';
import { FlatList, StyleSheet, View } from 'react-native';

import { SubmissionRow } from '@/components/SubmissionRow';
import { AppText, EmptyState, useAppTheme } from '@/components/ui';
import { space } from '@/constants/theme';
import { hrefDisputeDetail } from '@/lib/navigation';
import { useSubmissions } from '@/lib/SubmissionsContext';

export default function DisputePickScreen() {
  const { colors } = useAppTheme();
  const { submissions, refreshSubmissions, loading, loadError } = useSubmissions();
  const router = useRouter();

  useFocusEffect(useCallback(() => {
    void refreshSubmissions().catch(() => undefined);
  }, [refreshSubmissions]));

  return (
    <FlatList
      style={{ backgroundColor: colors.background }}
      data={submissions}
      keyExtractor={(item) => item.id}
      contentContainerStyle={styles.content}
      ListHeaderComponent={
        <AppText variant="body" color="textMuted" style={styles.intro}>
          Pick the check you think is wrong. An administrator will review it and can change the verdict.
        </AppText>
      }
      ItemSeparatorComponent={() => <View style={styles.separator} />}
      ListEmptyComponent={
        loadError ? (
          <EmptyState icon="circle-alert" title="Could not load your checks" message={loadError}
            actionLabel="Try again" onAction={() => void refreshSubmissions().catch(() => undefined)} />
        ) : loading ? (
          <EmptyState icon="history" title="Loading your checks…" loading />
        ) : (
          <EmptyState icon="scale" title="Nothing to dispute yet"
            message="Run a check first, then come back here if you disagree with the verdict." />
        )
      }
      renderItem={({ item }) => (
        <SubmissionRow item={item} onPress={() => router.push(hrefDisputeDetail(item.id))} />
      )}
    />
  );
}

const styles = StyleSheet.create({
  content: { padding: space.lg, paddingBottom: space.xxxl },
  intro: { marginBottom: space.lg },
  separator: { height: space.sm },
});
