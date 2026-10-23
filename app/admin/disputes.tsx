import { useFocusEffect, useRouter } from 'expo-router';
import { useCallback, useRef, useState } from 'react';
import { FlatList, RefreshControl, StyleSheet, View } from 'react-native';

import { LoadMoreFooter } from '@/components/LoadMoreFooter';
import { AppText, Card, EmptyState, Icon, Segmented, Tag, VerdictBadge, useAppTheme } from '@/components/ui';
import { space } from '@/constants/theme';
import { listDisputes, type ApiDispute } from '@/lib/api';
import { useAuth } from '@/lib/AuthContext';
import { percent, relativeTime } from '@/lib/format';
import { hrefAdminReview } from '@/lib/navigation';
import type { Verdict } from '@/types/submission';

type Filter = 'pending' | 'reviewed' | 'all';

const PAGE_SIZE = 50;

function preview(dispute: ApiDispute) {
  return dispute.submission?.text_submission?.input_text
    ?? dispute.submission?.image_submission?.ocr_text
    ?? 'Image submission';
}

function verdictOf(label?: string | null): Verdict {
  if (label === 'Real') return 'credible';
  if (label === 'Fake') return 'misleading';
  return 'uncertain';
}

// Filtering happens on the server, so every page matches the selected tab.
const statusFor = (value: Filter) => (value === 'all' ? undefined : value);

export default function AdminDisputesScreen() {
  const router = useRouter();
  const { colors } = useAppTheme();
  const { accessToken } = useAuth();
  const [disputes, setDisputes] = useState<ApiDispute[]>([]);
  const [total, setTotal] = useState(0);
  const [pendingCount, setPendingCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>('pending');
  const disputesRef = useRef(disputes);
  disputesRef.current = disputes;
  // Ignore responses for a tab the admin has already switched away from.
  const generation = useRef(0);

  const refresh = useCallback(async () => {
    if (!accessToken) return;
    const current = ++generation.current;
    setLoading(true);
    setError(null);
    try {
      const [page, pending] = await Promise.all([
        listDisputes(accessToken, { status: statusFor(filter), limit: PAGE_SIZE }),
        listDisputes(accessToken, { status: 'pending', limit: 1 }),
      ]);
      if (current !== generation.current) return;
      setDisputes(page.items);
      setTotal(page.total);
      setPendingCount(pending.total);
    } catch (err) {
      if (current === generation.current) setError(err instanceof Error ? err.message : 'Could not load the dispute queue.');
    } finally {
      if (current === generation.current) setLoading(false);
    }
  }, [accessToken, filter]);

  const loadMore = useCallback(async () => {
    if (!accessToken || loading || loadingMore || disputesRef.current.length >= total) return;
    const current = generation.current;
    setLoadingMore(true);
    try {
      const page = await listDisputes(accessToken, { status: statusFor(filter), skip: disputesRef.current.length, limit: PAGE_SIZE });
      if (current !== generation.current) return;
      setDisputes((rows) => {
        const seen = new Set(rows.map((row) => row.id));
        return [...rows, ...page.items.filter((row) => !seen.has(row.id))];
      });
      setTotal(page.total);
    } catch (err) {
      if (current === generation.current) setError(err instanceof Error ? err.message : 'Could not load more disputes.');
    } finally {
      if (current === generation.current) setLoadingMore(false);
    }
  }, [accessToken, filter, loading, loadingMore, total]);

  useFocusEffect(useCallback(() => { void refresh(); }, [refresh]));

  return (
    <FlatList
      style={{ backgroundColor: colors.background }}
      data={disputes}
      keyExtractor={(item) => String(item.id)}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={loading && disputes.length > 0} onRefresh={() => void refresh()} tintColor={colors.primary} />}
      ListHeaderComponent={
        <View style={styles.header}>
          <Segmented<Filter>
            value={filter}
            onChange={setFilter}
            options={[
              { value: 'pending', label: `Pending${pendingCount ? ` (${pendingCount})` : ''}` },
              { value: 'reviewed', label: 'Reviewed' },
              { value: 'all', label: 'All' },
            ]}
          />
          {error && disputes.length ? <AppText variant="caption" color="misleading">{error}</AppText> : null}
        </View>
      }
      ItemSeparatorComponent={() => <View style={styles.separator} />}
      onEndReached={() => void loadMore()}
      onEndReachedThreshold={0.4}
      ListFooterComponent={<LoadMoreFooter loaded={disputes.length} total={total} loading={loadingMore} onLoadMore={() => void loadMore()} noun="disputes" />}
      ListEmptyComponent={
        loading ? (
          <EmptyState icon="inbox" title="Loading disputes…" loading />
        ) : error ? (
          <EmptyState icon="circle-alert" title="Could not load disputes" message={error} actionLabel="Try again" onAction={() => void refresh()} />
        ) : (
          <EmptyState icon="inbox" title={filter === 'pending' ? 'Queue is clear' : 'No disputes'}
            message={filter === 'pending' ? 'There are no disputes waiting for review.' : undefined} />
        )
      }
      renderItem={({ item }) => {
        const pending = item.status === 'pending';
        const version = item.submission?.explainability?.model_version;
        const confidence = version === 'text-model-unavailable' || version?.startsWith('stub')
          ? null
          : item.submission?.text_submission?.text_confidence ?? item.submission?.image_submission?.text_confidence;
        return (
          <Card onPress={() => router.push(hrefAdminReview(String(item.id)))}>
            <View style={styles.top}>
              <Tag icon={pending ? 'clock' : 'badge-check'} label={pending ? 'Pending' : item.status} tone={pending ? 'uncertain' : 'credible'} />
              <AppText variant="caption" color="textSubtle">{relativeTime(Date.parse(item.created_at))}</AppText>
            </View>
            <AppText variant="bodyStrong" numberOfLines={2} style={styles.preview}>{preview(item)}</AppText>
            <AppText variant="caption" color="textMuted" numberOfLines={2} style={styles.reason}>
              “{item.justification}”
            </AppText>
            <View style={styles.footer}>
              <VerdictBadge verdict={verdictOf(item.submission?.final_label)} size="sm" />
              <AppText variant="caption" color="textMuted" style={styles.flex} numberOfLines={1}>
                {percent(confidence)} · {item.user?.email ?? `User ${item.user_id}`}
              </AppText>
              <Icon name="chevron-right" size={16} color="textSubtle" />
            </View>
          </Card>
        );
      }}
    />
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  content: { padding: space.lg, paddingBottom: space.xxxl },
  header: { gap: space.sm, marginBottom: space.lg },
  separator: { height: space.sm },
  top: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  preview: { marginTop: space.md },
  reason: { marginTop: space.xs },
  footer: { flexDirection: 'row', alignItems: 'center', gap: space.sm, marginTop: space.md },
});
