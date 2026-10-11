import { useFocusEffect, useRouter } from 'expo-router';
import { useCallback } from 'react';
import { FlatList, RefreshControl, StyleSheet, View } from 'react-native';

import { SubmissionRow } from '@/components/SubmissionRow';
import { AppText, EmptyState, useAppTheme } from '@/components/ui';
import { space } from '@/constants/theme';
import { hrefAdminReview } from '@/lib/navigation';
import { useSubmissions } from '@/lib/SubmissionsContext';

export default function AdminSubmissionsScreen() {
  const router = useRouter();
  const { colors } = useAppTheme();
  const { submissions, loading, loadError, refreshSubmissions } = useSubmissions();

  useFocusEffect(useCallback(() => { void refreshSubmissions().catch(() => undefined); }, [refreshSubmissions]));

  return (
    <FlatList
      style={{ backgroundColor: colors.background }}
      data={submissions}
      keyExtractor={(item) => item.id}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl
          refreshing={loading && submissions.length > 0}
          onRefresh={() => void refreshSubmissions().catch(() => undefined)}
          tintColor={colors.primary}
        />
      }
      ListHeaderComponent={
        submissions.length ? (
          <AppText variant="caption" color="textMuted" style={styles.header}>
            {submissions.length} submissions · disputed ones open the review screen.
          </AppText>
        ) : null
      }
      ItemSeparatorComponent={() => <View style={styles.separator} />}
      ListEmptyComponent={
        loadError ? (
          <EmptyState icon="circle-alert" title="Could not load submissions" message={loadError}
            actionLabel="Try again" onAction={() => void refreshSubmissions().catch(() => undefined)} />
        ) : loading ? (
          <EmptyState icon="list" title="Loading submissions…" loading />
        ) : (
          <EmptyState icon="inbox" title="No submissions yet" />
        )
      }
      renderItem={({ item }) => (
        <SubmissionRow
          item={item}
          onPress={() => router.push(item.dispute ? hrefAdminReview(item.dispute.id) : `/result/${item.id}`)}
        />
      )}
    />
  );
}

const styles = StyleSheet.create({
  content: { padding: space.lg, paddingBottom: space.xxxl },
  header: { marginBottom: space.md },
  separator: { height: space.sm },
});
