import { useFocusEffect, useRouter } from 'expo-router';
import { useCallback, useMemo, useState } from 'react';
import { FlatList, Pressable, RefreshControl, ScrollView, StyleSheet, View } from 'react-native';

import { LoadMoreFooter } from '@/components/LoadMoreFooter';
import { SubmissionRow } from '@/components/SubmissionRow';
import { AppText, EmptyState, Masthead, useAppTheme } from '@/components/ui';
import { radius, space } from '@/constants/theme';
import { useSubmissions } from '@/lib/SubmissionsContext';
import type { Submission } from '@/types/submission';

type Filter = 'all' | Submission['verdict'] | 'disputed';

const FILTERS: { value: Filter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'misleading', label: 'Misleading' },
  { value: 'uncertain', label: 'Uncertain' },
  { value: 'credible', label: 'Credible' },
  { value: 'disputed', label: 'Disputed' },
];

export default function HistoryScreen() {
  const { colors } = useAppTheme();
  const { submissions, total, loadMore, loadingMore, refreshSubmissions, loading, loadError } = useSubmissions();
  const router = useRouter();
  const [filter, setFilter] = useState<Filter>('all');

  useFocusEffect(useCallback(() => {
    void refreshSubmissions().catch(() => undefined);
  }, [refreshSubmissions]));

  const visible = useMemo(() => submissions.filter((item) => {
    if (filter === 'all') return true;
    if (filter === 'disputed') return Boolean(item.dispute);
    return item.verdict === filter;
  }), [submissions, filter]);

  return (
    <FlatList
      style={{ backgroundColor: colors.background }}
      data={visible}
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
        <>
          <Masthead
            kicker="Your activity"
            title="History"
            subtitle={`${total} ${total === 1 ? 'check' : 'checks'} saved to your account.`}
          />
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.filters}>
            {FILTERS.map((option) => {
              const selected = option.value === filter;
              return (
                <Pressable
                  key={option.value}
                  onPress={() => setFilter(option.value)}
                  accessibilityRole="button"
                  accessibilityState={{ selected }}
                  style={[
                    styles.chip,
                    {
                      backgroundColor: selected ? colors.text : colors.surface,
                      borderColor: selected ? colors.text : colors.border,
                    },
                  ]}>
                  <AppText variant="caption" color={selected ? colors.background : 'textMuted'} style={styles.chipText}>
                    {option.label}
                  </AppText>
                </Pressable>
              );
            })}
          </ScrollView>
        </>
      }
      ItemSeparatorComponent={() => <View style={styles.separator} />}
      onEndReached={() => void loadMore()}
      onEndReachedThreshold={0.4}
      ListFooterComponent={
        <LoadMoreFooter loaded={submissions.length} total={total} loading={loadingMore} onLoadMore={() => void loadMore()} />
      }
      ListEmptyComponent={
        loadError ? (
          <EmptyState icon="circle-alert" title="Could not load history" message={loadError}
            actionLabel="Try again" onAction={() => void refreshSubmissions().catch(() => undefined)} />
        ) : loading ? (
          <EmptyState icon="history" title="Loading your checks…" loading />
        ) : submissions.length === 0 ? (
          <EmptyState icon="scan-search" title="No checks yet"
            message="Run your first analysis from the Check tab." actionLabel="Start a check" onAction={() => router.push('/')} />
        ) : (
          <EmptyState icon="list" title="Nothing here"
            message={submissions.length < total ? 'No loaded checks match this filter yet. Load more below to search older ones.' : 'No checks match this filter.'} />
        )
      }
      renderItem={({ item }) => (
        <View style={styles.item}>
          <SubmissionRow item={item} onPress={() => router.push(`/result/${item.id}`)} />
        </View>
      )}
    />
  );
}

const styles = StyleSheet.create({
  content: { paddingBottom: space.xxxl },
  filters: { gap: space.sm, paddingHorizontal: space.lg, paddingVertical: space.lg },
  chip: { borderWidth: 1, borderRadius: radius.pill, paddingHorizontal: space.lg, paddingVertical: 8 },
  chipText: { fontFamily: 'PlusJakartaSans_700Bold' },
  item: { paddingHorizontal: space.lg },
  separator: { height: space.sm },
});
