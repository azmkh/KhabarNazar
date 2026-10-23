import { useFocusEffect, useRouter } from 'expo-router';
import { useCallback, useRef, useState } from 'react';
import { FlatList, RefreshControl, StyleSheet, View } from 'react-native';

import { LoadMoreFooter } from '@/components/LoadMoreFooter';
import { SubmissionRow } from '@/components/SubmissionRow';
import { AppText, EmptyState, useAppTheme } from '@/components/ui';
import { space } from '@/constants/theme';
import { listAdminSubmissions } from '@/lib/api';
import { useAuth } from '@/lib/AuthContext';
import { hrefAdminReview } from '@/lib/navigation';
import { fromAdminApi } from '@/lib/SubmissionsContext';
import type { Submission } from '@/types/submission';

const PAGE_SIZE = 50;

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
  const rowsRef = useRef(rows);
  rowsRef.current = rows;

  const refresh = useCallback(async () => {
    if (!accessToken) return;
    setLoading(true);
    setError(null);
    try {
      const page = await listAdminSubmissions(accessToken, 0, PAGE_SIZE);
      setRows(page.items.map(fromAdminApi));
      setTotal(page.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load submissions.');
    } finally {
      setLoading(false);
    }
  }, [accessToken]);

  const loadMore = useCallback(async () => {
    if (!accessToken || loading || loadingMore || rowsRef.current.length >= total) return;
    setLoadingMore(true);
    try {
      const page = await listAdminSubmissions(accessToken, rowsRef.current.length, PAGE_SIZE);
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
  }, [accessToken, loading, loadingMore, total]);

  useFocusEffect(useCallback(() => { void refresh(); }, [refresh]));

  return (
    <FlatList
      style={{ backgroundColor: colors.background }}
      data={rows}
      keyExtractor={(item) => item.id}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={loading && rows.length > 0} onRefresh={() => void refresh()} tintColor={colors.primary} />}
      ListHeaderComponent={
        total ? (
          <AppText variant="caption" color="textMuted" style={styles.header}>
            {total} submissions from all users · disputed ones open the review screen.
          </AppText>
        ) : null
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
          <EmptyState icon="inbox" title="No submissions yet" />
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
  header: { marginBottom: space.md },
  separator: { height: space.sm },
  submitter: { marginTop: 4, marginLeft: space.sm },
});
