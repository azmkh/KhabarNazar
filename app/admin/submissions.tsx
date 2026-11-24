import { useFocusEffect, useRouter } from 'expo-router';
import { useCallback, useRef, useState } from 'react';
import { FlatList, Pressable, RefreshControl, ScrollView, StyleSheet, View } from 'react-native';

import { LoadMoreFooter } from '@/components/LoadMoreFooter';
import { SubmissionRow } from '@/components/SubmissionRow';
import { AppText, EmptyState, useAppTheme } from '@/components/ui';
import { radius, space } from '@/constants/theme';
import { listAdminSubmissions, type AdminSubmissionFilters } from '@/lib/api';
import { useAuth } from '@/lib/AuthContext';
import { hrefAdminReview } from '@/lib/navigation';
import { fromAdminApi } from '@/lib/SubmissionsContext';
import type { Submission } from '@/types/submission';

const PAGE_SIZE = 50;

/** Filters run on the server, so the total and the pages always match the chosen filter. */
const FILTERS: { key: string; label: string; query: AdminSubmissionFilters }[] = [
  { key: 'all', label: 'All', query: {} },
  { key: 'fake', label: 'Misleading', query: { finalLabel: 'Fake' } },
  { key: 'uncertain', label: 'Uncertain', query: { finalLabel: 'Uncertain' } },
  { key: 'real', label: 'Credible', query: { finalLabel: 'Real' } },
  { key: 'disputed', label: 'Disputed', query: { disputed: true } },
  { key: 'text', label: 'Text', query: { submissionType: 'text' } },
  { key: 'image', label: 'Images', query: { submissionType: 'image' } },
];

/** Every user's submissions, paged. Kept separate from the admin's own history. */
export default function AdminSubmissionsScreen() {
  const router = useRouter();
  const { colors } = useAppTheme();
  const { accessToken } = useAuth();
  const [rows, setRows] = useState<Submission[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filterKey, setFilterKey] = useState('all');
  const filter = FILTERS.find((option) => option.key === filterKey) ?? FILTERS[0];
  const rowsRef = useRef(rows);
  rowsRef.current = rows;

  const refresh = useCallback(async () => {
    if (!accessToken) return;
    setLoading(true);
    setError(null);
    try {
      const page = await listAdminSubmissions(accessToken, 0, PAGE_SIZE, filter.query);
      setRows(page.items.map(fromAdminApi));
      setTotal(page.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load submissions.');
    } finally {
      setLoading(false);
    }
  }, [accessToken, filter]);

  const loadMore = useCallback(async () => {
    if (!accessToken || loading || loadingMore || rowsRef.current.length >= total) return;
    setLoadingMore(true);
    try {
      const page = await listAdminSubmissions(accessToken, rowsRef.current.length, PAGE_SIZE, filter.query);
      setRows((current) => {
        const seen = new Set(current.map((row) => row.id));
        return [...current, ...page.items.map(fromAdminApi).filter((row) => !seen.has(row.id))];
      });
      setTotal(page.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load more submissions.');
    } finally {
      setLoadingMore(false);
    }
  }, [accessToken, filter, loading, loadingMore, total]);

  useFocusEffect(useCallback(() => { void refresh(); }, [refresh]));

  return (
    <FlatList
      style={{ backgroundColor: colors.background }}
      data={rows}
      keyExtractor={(item) => item.id}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={loading && rows.length > 0} onRefresh={() => void refresh()} tintColor={colors.primary} />}
      ListHeaderComponent={
        <View style={styles.header}>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.filters}>
            {FILTERS.map((option) => {
              const selected = option.key === filterKey;
              return (
                <Pressable
                  key={option.key}
                  onPress={() => { setRows([]); setFilterKey(option.key); }}
                  accessibilityRole="button"
                  accessibilityState={{ selected }}
                  style={[
                    styles.chip,
                    { backgroundColor: selected ? colors.text : colors.surface, borderColor: selected ? colors.text : colors.border },
                  ]}>
                  <AppText variant="caption" color={selected ? colors.background : 'textMuted'} style={styles.chipText}>
                    {option.label}
                  </AppText>
                </Pressable>
              );
            })}
          </ScrollView>
          {total ? (
            <AppText variant="caption" color="textMuted">
              {total} {filterKey === 'all' ? 'submissions from all users' : 'matching submissions'} · disputed ones open the review screen.
            </AppText>
          ) : null}
        </View>
      }
      ItemSeparatorComponent={() => <View style={styles.separator} />}
      onEndReached={() => void loadMore()}
      onEndReachedThreshold={0.4}
      ListFooterComponent={<LoadMoreFooter loaded={rows.length} total={total} loading={loadingMore} onLoadMore={() => void loadMore()} noun="submissions" />}
      ListEmptyComponent={
        error ? (
          <EmptyState icon="circle-alert" title="Could not load submissions" message={error} actionLabel="Try again" onAction={() => void refresh()} />
        ) : loading ? (
          <EmptyState icon="list" title="Loading submissions…" loading />
        ) : (
          <EmptyState icon="inbox" title={filterKey === 'all' ? 'No submissions have been recorded yet' : 'No submissions match this filter'} />
        )
      }
      renderItem={({ item }) => (
        <View>
          <SubmissionRow
            item={item}
            onPress={() => router.push(item.dispute ? hrefAdminReview(item.dispute.id) : `/result/${item.id}`)}
          />
          {item.submitterEmail ? (
            <AppText variant="caption" color="textSubtle" style={styles.submitter} numberOfLines={1}>
              From {item.submitterEmail}
            </AppText>
          ) : null}
        </View>
      )}
    />
  );
}

const styles = StyleSheet.create({
  content: { padding: space.lg, paddingBottom: space.xxxl },
  header: { marginBottom: space.md, gap: space.sm },
  filters: { gap: space.sm, paddingVertical: space.xs },
  chip: { borderWidth: 1, borderRadius: radius.pill, paddingHorizontal: space.lg, paddingVertical: 8 },
  chipText: { fontFamily: 'PlusJakartaSans_700Bold' },
  separator: { height: space.sm },
  submitter: { marginTop: 4, marginLeft: space.sm },
});
